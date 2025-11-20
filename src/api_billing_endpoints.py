# Billing API Endpoints for Stripe Integration
"""
FastAPI endpoints for handling Stripe billing operations.
Includes checkout session creation, webhook processing, and status checking.
"""

import json
import stripe
from datetime import datetime, UTC
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Response, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from src.stripe_config import get_stripe_config, get_feature_flag_billing_enabled
from src.premium_pass_service import (
    create_premium_pass,
    revoke_premium_pass_by_subscription
)
from src.auth_middleware import get_user_from_request
from src.database import get_db_connection

# Initialize Stripe with configuration
stripe_config = get_stripe_config()
stripe.api_key = stripe_config["secret_key"]

# Router setup
billing_router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Pydantic models
class CreateCheckoutSessionRequest(BaseModel):
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment cancelled")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success_url": "https://shiol.app/payment-success",
                "cancel_url": "https://shiol.app/",
            }
        }
    )

class BillingStatusResponse(BaseModel):
    enabled: bool
    is_premium: Optional[bool] = None
    source: Optional[str] = None
    message: Optional[str] = None

def _append_session_placeholder(success_url: str) -> str:
    """Append Stripe placeholder session_id to a URL safely.

    If the URL already contains query parameters, use '&'; otherwise use '?'.
    """
    try:
        delimiter = '&' if '?' in success_url else '?'
        return f"{success_url}{delimiter}session_id={{CHECKOUT_SESSION_ID}}"
    except Exception:
        # Fallback to original behavior (avoid raising during checkout)
        return success_url + "?session_id={CHECKOUT_SESSION_ID}"


def _epoch_to_dt(value) -> Optional[datetime]:
    """Convert epoch seconds to aware UTC datetime if possible."""
    try:
        if value is None:
            return None
        # Stripe may provide int seconds or string
        seconds = int(value)
        return datetime.fromtimestamp(seconds, UTC)
    except Exception:
        return None


def _upsert_stripe_customer(stripe_customer_id: Optional[str], email: Optional[str], user_id: Optional[int]) -> None:
    """Ensure a stripe_customer record exists and is up-to-date."""
    if not stripe_customer_id:
        return
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO stripe_customers (stripe_customer_id, email, user_id, created_at, updated_at)
                VALUES (?, COALESCE(?, ''), ?, ?, ?)
                ON CONFLICT(stripe_customer_id) DO UPDATE SET
                    email=excluded.email,
                    user_id=COALESCE(excluded.user_id, stripe_customers.user_id),
                    updated_at=excluded.updated_at
                """,
                (stripe_customer_id, email, user_id, datetime.now(UTC), datetime.now(UTC)),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to upsert stripe_customer {stripe_customer_id}: {e}")


def _upsert_stripe_subscription(
    stripe_subscription_id: Optional[str],
    stripe_customer_id: Optional[str],
    *,
    status: Optional[str] = None,
    current_period_start: Optional[datetime] = None,
    current_period_end: Optional[datetime] = None,
    canceled_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    trial_start: Optional[datetime] = None,
    trial_end: Optional[datetime] = None,
) -> None:
    """Ensure a stripe_subscription record exists referencing the customer."""
    if not stripe_subscription_id or not stripe_customer_id:
        return
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO stripe_subscriptions (
                    stripe_subscription_id, stripe_customer_id, status,
                    current_period_start, current_period_end, canceled_at, ended_at,
                    trial_start, trial_end, created_at, updated_at
                ) VALUES (?, ?, COALESCE(?, 'active'), ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stripe_subscription_id) DO UPDATE SET
                    status=excluded.status,
                    current_period_start=excluded.current_period_start,
                    current_period_end=excluded.current_period_end,
                    canceled_at=excluded.canceled_at,
                    ended_at=excluded.ended_at,
                    trial_start=excluded.trial_start,
                    trial_end=excluded.trial_end,
                    updated_at=excluded.updated_at
                """,
                (
                    stripe_subscription_id,
                    stripe_customer_id,
                    status,
                    current_period_start,
                    current_period_end,
                    canceled_at,
                    ended_at,
                    trial_start,
                    trial_end,
                    datetime.now(UTC),
                    datetime.now(UTC),
                ),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to upsert stripe_subscription {stripe_subscription_id}: {e}")


def _validate_user_id(user_id: Optional[int]) -> Optional[int]:
    """Return user_id if it exists in DB; otherwise return None and log."""
    if not user_id:
        return None
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE id = ? LIMIT 1", (user_id,))
            exists = cursor.fetchone()
            if exists:
                return user_id
    except Exception as e:
        logger.warning(f"User validation failed for user_id={user_id}: {e}")
    logger.warning(f"User id {user_id} not found; proceeding without linking to user")
    return None

def check_idempotency_key(idempotency_key: str, endpoint: str, request_payload: str) -> Optional[Dict[str, Any]]:
    """
    Check if request was already processed using idempotency key.
    
    Returns:
        Previous response if found, None if new request
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT response_data, status_code, processed_at
                FROM idempotency_keys 
                WHERE idempotency_key = ? AND endpoint = ?
            """, (idempotency_key, endpoint))

            result = cursor.fetchone()

            if result:
                response_data, status_code, processed_at = result
                logger.info(f"Idempotent request found: {idempotency_key} (processed at {processed_at})")

                if response_data:
                    return {
                        "response": json.loads(response_data),
                        "status_code": status_code
                    }

            return None

    except Exception as e:
        logger.error(f"Error checking idempotency key: {e}")
        return None

def store_idempotency_result(idempotency_key: str, endpoint: str, request_payload: str,
                           response_data: Dict[str, Any], status_code: int) -> None:
    """Store idempotency result in database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO idempotency_keys 
                (idempotency_key, endpoint, request_payload, response_data, status_code, processed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                idempotency_key,
                endpoint,
                request_payload,
                json.dumps(response_data),
                status_code,
                datetime.now(UTC)
            ))

            conn.commit()

    except Exception as e:
        logger.error(f"Error storing idempotency result: {e}")

@billing_router.post("/create-checkout-session")
async def create_checkout_session(
    request: Request,
    checkout_request: CreateCheckoutSessionRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):
    """
    Create Stripe Checkout session for annual premium subscription.
    Requires Idempotency-Key header for safe retries.
    """
    if not get_feature_flag_billing_enabled():
        logger.warning("Checkout session creation attempted but billing is disabled")
        raise HTTPException(
            status_code=503,
            detail="Billing functionality is currently disabled"
        )

    endpoint = "create-checkout-session"
    request_payload = json.dumps(checkout_request.model_dump())

    logger.info(f"Checkout session creation requested with idempotency key: {idempotency_key}")

    # Check idempotency
    existing_result = check_idempotency_key(idempotency_key, endpoint, request_payload)
    if existing_result:
        logger.info(f"Returning cached checkout session for idempotency key: {idempotency_key}")
        return existing_result["response"]

    try:
        # Get current user if authenticated
        current_user = get_user_from_request(request)
        customer_email = current_user.get("email") if current_user else None
        user_id = current_user.get("id") if current_user else None

        if user_id:
            logger.info(f"Creating checkout session for authenticated user: user_id={user_id}, email={customer_email}")
        else:
            logger.info("Creating checkout session for guest user")

        # Create Stripe Checkout session
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': stripe_config["price_id_annual"],
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=_append_session_placeholder(checkout_request.success_url),
                cancel_url=checkout_request.cancel_url,
                customer_email=customer_email,
                metadata={
                    'user_id': str(user_id) if user_id else None,
                    'source': 'shiol_plus_upgrade'
                },
                subscription_data={
                    'metadata': {
                        'user_id': str(user_id) if user_id else None,
                        'source': 'shiol_plus_upgrade'
                    }
                }
            )
            logger.info(f"Stripe checkout session created successfully: session_id={session.id}, user_id={user_id}")
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid Stripe request parameters: {e}")
            error_response = {"error": f"Invalid payment configuration: {str(e)}"}
            store_idempotency_result(idempotency_key, endpoint, request_payload, error_response, 400)
            raise HTTPException(status_code=400, detail=error_response["error"])
        except stripe.error.AuthenticationError as e:
            logger.error(f"Stripe authentication error: {e}")
            error_response = {"error": "Payment system authentication error"}
            store_idempotency_result(idempotency_key, endpoint, request_payload, error_response, 500)
            raise HTTPException(status_code=500, detail=error_response["error"])
        except stripe.error.APIConnectionError as e:
            logger.error(f"Stripe API connection error: {e}")
            error_response = {"error": "Unable to connect to payment system"}
            store_idempotency_result(idempotency_key, endpoint, request_payload, error_response, 503)
            raise HTTPException(status_code=503, detail=error_response["error"])
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            error_response = {"error": f"Payment processing error: {str(e)}"}
            store_idempotency_result(idempotency_key, endpoint, request_payload, error_response, 400)
            raise HTTPException(status_code=400, detail=error_response["error"])

        response_data = {
            "checkout_url": session.url,
            "session_id": session.id
        }

        # Store idempotency result
        store_idempotency_result(idempotency_key, endpoint, request_payload, response_data, 200)

        logger.info(f"Checkout session creation completed: session_id={session.id}, url={session.url}")

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {type(e).__name__}: {e}")
        error_response = {"error": "Internal server error"}
        store_idempotency_result(idempotency_key, endpoint, request_payload, error_response, 500)
        raise HTTPException(status_code=500, detail="Internal server error")

@billing_router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events with idempotent processing.
    Validates webhook signature and processes events safely.
    
    NOTE: Response object cannot set cookies reliably in webhook context.
    Premium Pass cookies are set via session verification in /activate-premium endpoint.
    """
    if not get_feature_flag_billing_enabled():
        logger.warning("Webhook received but billing is disabled")
        raise HTTPException(status_code=503, detail="Billing functionality disabled")

    try:
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')

        if not sig_header:
            logger.error("Webhook: Missing stripe-signature header")
            raise HTTPException(status_code=400, detail="Missing signature header")

        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, stripe_config["webhook_secret"]
            )
            logger.info(f"Webhook: Signature verified for event {event.get('id', 'unknown')}")
        except ValueError as e:
            logger.error(f"Webhook: Invalid payload - {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook: Signature verification failed - {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception as e:
            logger.error(f"Webhook: Unexpected signature verification error - {type(e).__name__}: {e}")
            raise HTTPException(status_code=400, detail="Signature verification error")

        # Check if event already processed (idempotency)
        event_id = event['id']
        event_type = event['type']
        
        logger.info(f"Webhook: Received event {event_id} of type {event_type}")

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check if already processed
            cursor.execute("""
                SELECT processed, processing_error FROM webhook_events 
                WHERE stripe_event_id = ?
            """, (event_id,))

            existing_event = cursor.fetchone()

            if existing_event:
                processed, processing_error = existing_event
                if processed:
                    logger.info(f"Webhook: Event {event_id} already processed successfully, returning success")
                    return {"status": "already_processed"}
                elif processing_error:
                    logger.warning(f"Webhook: Retrying previously failed event {event_id}, previous error: {processing_error}")

            # Store/update webhook event
            cursor.execute("""
                INSERT OR REPLACE INTO webhook_events 
                (stripe_event_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
            """, (event_id, event_type, json.dumps(event), datetime.now(UTC)))

            conn.commit()
            logger.info(f"Webhook: Event {event_id} stored in database")

        # Process webhook event
        try:
            await process_webhook_event(event)

            # Mark as processed
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE webhook_events 
                    SET processed = TRUE, processed_at = ?, processing_error = NULL, retry_count = retry_count + 1
                    WHERE stripe_event_id = ?
                """, (datetime.now(UTC), event_id))
                conn.commit()

            logger.info(f"Webhook: Event {event_id} ({event_type}) processed SUCCESSFULLY")

        except Exception as e:
            # Mark processing error
            error_message = f"{type(e).__name__}: {str(e)}"
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE webhook_events 
                    SET processing_error = ?, retry_count = retry_count + 1
                    WHERE stripe_event_id = ?
                """, (error_message, event_id))
                conn.commit()

            logger.error(f"Webhook: FAILED to process event {event_id} ({event_type}): {error_message}")
            raise HTTPException(status_code=500, detail="Webhook processing failed")

        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook: Unexpected error - {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

async def process_webhook_event(event: Dict[str, Any]) -> None:
    """Process individual webhook events based on type."""
    event_type = event['type']
    data = event['data']['object']

    if event_type == 'checkout.session.completed':
        await handle_checkout_completed(data)
    elif event_type == 'invoice.paid':
        await handle_invoice_paid(data)
    elif event_type == 'customer.subscription.updated':
        await handle_subscription_updated(data)
    elif event_type == 'customer.subscription.deleted':
        await handle_subscription_deleted(data)
    elif event_type in ['charge.dispute.created', 'charge.refunded']:
        await handle_payment_dispute_or_refund(data)
    else:
        logger.info(f"Unhandled webhook event type: {event_type}")

async def handle_checkout_completed(session: Dict[str, Any]) -> None:
    """Handle successful checkout completion - activate Premium Pass."""
    session_id = session.get('id', 'unknown')
    logger.info(f"Webhook: Processing checkout.session.completed for session {session_id}")
    
    try:
        customer_email = session.get('customer_email') or session.get('customer_details', {}).get('email')
        subscription_id = session.get('subscription')
        stripe_customer_id = session.get('customer')

        if not customer_email or not subscription_id:
            logger.error(f"Webhook: Missing required data in checkout session {session_id}: email={customer_email}, subscription={subscription_id}")
            return

        logger.info(f"Webhook: Checkout completed - email={customer_email}, subscription={subscription_id}")

        # Ensure Stripe customer/subscription are persisted for FK integrity
        sub_obj = None
        try:
            if subscription_id:
                sub_obj = stripe.Subscription.retrieve(subscription_id)
                if not stripe_customer_id:
                    stripe_customer_id = sub_obj.get('customer') if isinstance(sub_obj, dict) else getattr(sub_obj, 'customer', None)
        except Exception as e:
            logger.warning(f"Webhook: Failed to retrieve subscription {subscription_id} details: {e}")

        try:
            _upsert_stripe_customer(stripe_customer_id, customer_email, user_id)
        except Exception:
            pass
        try:
            _upsert_stripe_subscription(
                subscription_id,
                stripe_customer_id,
                status=(sub_obj.get('status') if isinstance(sub_obj, dict) else getattr(sub_obj, 'status', None)) if sub_obj else 'active',
                current_period_start=_epoch_to_dt((sub_obj.get('current_period_start') if isinstance(sub_obj, dict) else getattr(sub_obj, 'current_period_start', None)) if sub_obj else None),
                current_period_end=_epoch_to_dt((sub_obj.get('current_period_end') if isinstance(sub_obj, dict) else getattr(sub_obj, 'current_period_end', None)) if sub_obj else None),
                canceled_at=_epoch_to_dt((sub_obj.get('canceled_at') if isinstance(sub_obj, dict) else getattr(sub_obj, 'canceled_at', None)) if sub_obj else None),
                ended_at=_epoch_to_dt((sub_obj.get('ended_at') if isinstance(sub_obj, dict) else getattr(sub_obj, 'ended_at', None)) if sub_obj else None),
                trial_start=_epoch_to_dt((sub_obj.get('trial_start') if isinstance(sub_obj, dict) else getattr(sub_obj, 'trial_start', None)) if sub_obj else None),
                trial_end=_epoch_to_dt((sub_obj.get('trial_end') if isinstance(sub_obj, dict) else getattr(sub_obj, 'trial_end', None)) if sub_obj else None),
            )
        except Exception:
            pass

        # Check if user is registered
        user_id = None
        if 'metadata' in session and session['metadata'].get('user_id'):
            user_id = _validate_user_id(int(session['metadata']['user_id']))
            logger.info(f"Webhook: Registered user detected: user_id={user_id}")

        # Create Premium Pass (idempotent - will return existing if already created)
        from src.premium_pass_service import get_premium_pass_by_email
        existing_pass = get_premium_pass_by_email(customer_email)
        
        if existing_pass:
            logger.info(f"Webhook: Premium Pass already exists for {customer_email}, pass_id={existing_pass['pass_id']} (likely created by backend validation)")
            pass_data = existing_pass
        else:
            logger.info(f"Webhook: Creating new Premium Pass for {customer_email}")
            pass_data = create_premium_pass(customer_email, subscription_id, user_id, stripe_customer_id)
            logger.info(f"Webhook: Premium Pass CREATED - pass_id={pass_data['pass_id']}, email={customer_email}, subscription={subscription_id}")

        # Update user premium status if registered
        if user_id:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE users 
                        SET is_premium = TRUE, premium_expires_at = ?
                        WHERE id = ?
                    """, (pass_data["expires_at"], user_id))
                    updated_rows = cursor.rowcount
                    conn.commit()
                
                if updated_rows > 0:
                    logger.info(f"Webhook: Updated registered user premium status: user_id={user_id}")
                else:
                    logger.warning(f"Webhook: User {user_id} not found in database")
            except Exception as db_error:
                logger.error(f"Webhook: Failed to update user premium status: {db_error}")
                # Continue - Premium Pass is created

        logger.info(f"Webhook: Premium activation COMPLETED for {customer_email}: subscription={subscription_id}, pass_id={pass_data['pass_id']}")

    except Exception as e:
        logger.error(f"Webhook: Error handling checkout completion for session {session_id}: {type(e).__name__}: {e}")
        raise

async def handle_subscription_deleted(subscription: Dict[str, Any]) -> None:
    """Handle subscription cancellation - revoke Premium Pass."""
    subscription_id = subscription.get('id', 'unknown')
    logger.info(f"Webhook: Processing customer.subscription.deleted for subscription {subscription_id}")
    
    try:
        # Revoke Premium Pass
        revoked_count = revoke_premium_pass_by_subscription(
            subscription_id,
            "subscription_canceled"
        )

        if revoked_count > 0:
            logger.info(f"Webhook: Revoked {revoked_count} Premium Pass(es) for canceled subscription {subscription_id}")
        else:
            logger.warning(f"Webhook: No Premium Passes found to revoke for subscription {subscription_id}")

        # Update user premium status if applicable
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users 
                    SET is_premium = FALSE, premium_expires_at = NULL
                    WHERE id IN (
                        SELECT user_id FROM premium_passes 
                        WHERE stripe_subscription_id = ? AND user_id IS NOT NULL
                    )
                """, (subscription_id,))
                updated_rows = cursor.rowcount
                conn.commit()
            
            if updated_rows > 0:
                logger.info(f"Webhook: Updated {updated_rows} user(s) premium status to inactive")
        except Exception as db_error:
            logger.error(f"Webhook: Failed to update user premium status: {db_error}")

        logger.info(f"Webhook: Subscription cancellation COMPLETED for {subscription_id}")

    except Exception as e:
        logger.error(f"Webhook: Error handling subscription deletion for {subscription_id}: {type(e).__name__}: {e}")
        raise

async def handle_payment_dispute_or_refund(charge: Dict[str, Any]) -> None:
    """Handle payment disputes and refunds - revoke Premium Pass."""
    charge_id = charge.get('id', 'unknown')
    logger.info(f"Webhook: Processing payment dispute/refund for charge {charge_id}")
    
    try:
        # Get subscription from charge
        invoice_id = charge.get('invoice')
        if not invoice_id:
            logger.warning(f"Webhook: No invoice associated with charge {charge_id}, cannot revoke Premium Pass")
            return

        # Retrieve invoice to get subscription
        try:
            invoice = stripe.Invoice.retrieve(invoice_id)
            subscription_id = invoice.get('subscription')
        except stripe.error.StripeError as e:
            logger.error(f"Webhook: Failed to retrieve invoice {invoice_id}: {e}")
            return

        if subscription_id:
            # Revoke Premium Pass
            revoked_count = revoke_premium_pass_by_subscription(
                subscription_id,
                "payment_dispute_or_refund"
            )

            logger.info(f"Webhook: Premium revoked due to dispute/refund - subscription={subscription_id}, charge={charge_id}, passes_revoked={revoked_count}")
        else:
            logger.warning(f"Webhook: No subscription found in invoice {invoice_id} for charge {charge_id}")

    except Exception as e:
        logger.error(f"Webhook: Error handling payment dispute/refund for charge {charge_id}: {type(e).__name__}: {e}")
        raise

async def handle_invoice_paid(invoice: Dict[str, Any]) -> None:
    """Handle successful invoice payment - sync subscription status."""
    subscription_id = invoice.get('subscription', 'unknown')
    invoice_id = invoice.get('id', 'unknown')
    logger.info(f"Webhook: Invoice paid - subscription={subscription_id}, invoice={invoice_id}")

async def handle_subscription_updated(subscription: Dict[str, Any]) -> None:
    """Handle subscription updates - sync status changes."""
    subscription_id = subscription.get('id', 'unknown')
    status = subscription.get('status', 'unknown')
    logger.info(f"Webhook: Subscription updated - subscription={subscription_id}, new_status={status}")

@billing_router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status(request: Request, session_id: str = None):
    """
    Get billing system status and user premium status.
    Returns billing enabled state and premium status if authenticated.
    
    Args:
        session_id: Optional Stripe checkout session ID to check status
    """
    billing_enabled = get_feature_flag_billing_enabled()

    response_data = BillingStatusResponse(enabled=billing_enabled)

    if not billing_enabled:
        response_data.message = "Billing functionality is currently disabled"
        logger.info("Billing status check: billing disabled")
        return response_data

    # Check user authentication and premium status
    current_user = get_user_from_request(request)

    if current_user and current_user.get("is_premium"):
        response_data.is_premium = True
        response_data.source = "stripe_subscription"
        logger.info(f"User {current_user.get('id')} has premium via registered account")
    else:
        # Check Premium Pass cookie
        premium_pass_token = request.cookies.get("premium_pass")
        if premium_pass_token:
            try:
                from src.premium_pass_service import validate_premium_pass_token
                pass_info = validate_premium_pass_token(premium_pass_token)
                if pass_info["valid"]:
                    response_data.is_premium = True
                    response_data.source = "premium_pass"
                    logger.info(f"Premium Pass validated from cookie: {pass_info['email']}")
            except Exception as e:
                logger.warning(f"Invalid Premium Pass token in cookie: {e}")

    # CRITICAL FIX: Check Stripe session directly if provided (for immediate validation)
    # This ensures payment verification happens on the backend, not just browser redirect
    if session_id and not response_data.is_premium:
        logger.info(f"Validating payment via Stripe session: {session_id}")
        try:
            # Retrieve session from Stripe API with error handling
            try:
                session = stripe.checkout.Session.retrieve(session_id)
                logger.info(f"Stripe session retrieved: {session_id}, payment_status={session.payment_status}, status={session.status}")
            except stripe.error.InvalidRequestError as e:
                logger.error(f"Invalid Stripe session ID {session_id}: {e}")
                response_data.message = "Invalid payment session"
                return response_data
            except stripe.error.AuthenticationError as e:
                logger.error(f"Stripe authentication error: {e}")
                response_data.message = "Payment system authentication error"
                return response_data
            except stripe.error.APIConnectionError as e:
                logger.error(f"Stripe API connection error: {e}")
                response_data.message = "Unable to verify payment, please try again"
                return response_data
            except stripe.error.StripeError as e:
                logger.error(f"Stripe API error retrieving session {session_id}: {e}")
                response_data.message = "Payment verification error"
                return response_data
            
            # Validate payment completion
            if session.payment_status == 'paid' and session.status == 'complete':
                subscription_id = session.subscription
                customer_email = session.customer_details.email if session.customer_details else session.customer_email
                
                logger.info(f"Payment VERIFIED for session {session_id}: email={customer_email}, subscription={subscription_id}")
                
                if not customer_email or not subscription_id:
                    logger.error(f"Missing critical data in paid session {session_id}: email={customer_email}, subscription={subscription_id}")
                    response_data.message = "Payment completed but missing customer information"
                    return response_data
                
                # Check if Premium Pass already exists
                from src.premium_pass_service import get_premium_pass_by_email
                existing_pass = get_premium_pass_by_email(customer_email)
                
                if existing_pass:
                    response_data.is_premium = True
                    response_data.source = "premium_pass_verified"
                    logger.info(f"Existing Premium Pass found for {customer_email}: pass_id={existing_pass['pass_id']}")
                else:
                    # Create Premium Pass immediately (ensures activation even if webhook hasn't fired)
                    logger.warning("Payment verified but no Premium Pass exists - creating now (webhook may be delayed or failed)")
                    
                    user_id = None
                    if current_user:
                        user_id = current_user.get("id")
                        logger.info(f"Authenticated user detected: user_id={user_id}")
                    elif session.metadata and session.metadata.get('user_id'):
                        user_id = int(session.metadata['user_id'])
                        logger.info(f"User ID from session metadata: user_id={user_id}")
                    
                    try:
                        pass_data = create_premium_pass(customer_email, subscription_id, user_id)
                        
                        response_data.is_premium = True
                        response_data.source = "premium_pass_created"
                        response_data.message = "Premium activated successfully"
                        
                        logger.info(f"Premium Pass CREATED from backend validation: pass_id={pass_data['pass_id']}, email={customer_email}, subscription={subscription_id}")
                        
                        # Update registered user status if applicable
                        if user_id:
                            try:
                                with get_db_connection() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE users 
                                        SET is_premium = TRUE, premium_expires_at = ?
                                        WHERE id = ?
                                    """, (pass_data["expires_at"], user_id))
                                    conn.commit()
                                logger.info(f"Updated registered user premium status: user_id={user_id}")
                            except Exception as db_error:
                                logger.error(f"Failed to update user premium status: {db_error}")
                                # Continue anyway - Premium Pass is created
                    except Exception as create_error:
                        logger.error(f"CRITICAL: Failed to create Premium Pass for paid session {session_id}: {create_error}")
                        response_data.message = "Payment verified but activation failed - please contact support"
                        return response_data
            else:
                logger.warning(f"Session {session_id} not yet paid: payment_status={session.payment_status}, status={session.status}")
                response_data.message = f"Payment status: {session.payment_status}"
                    
        except Exception as e:
            logger.error(f"Unexpected error validating Stripe session {session_id}: {type(e).__name__}: {e}")
            response_data.message = "Payment verification error"
            # Don't fail the entire request - return current status

    return response_data

@billing_router.post("/activate-premium")
async def activate_premium(request: Request, response: Response, session_id: str = None):
    """
    Activate premium pass and set cookie after successful payment.
    This endpoint verifies payment with Stripe before activating Premium access.
    
    Args:
        session_id: Stripe checkout session ID (required)
        
    Returns:
        Success response with premium pass details
        
    Raises:
        HTTPException: If payment not verified or activation fails
    """
    if not get_feature_flag_billing_enabled():
        logger.warning("Premium activation attempted but billing is disabled")
        raise HTTPException(
            status_code=503,
            detail="Billing functionality is currently disabled"
        )
    
    # Accept session_id from either query parameter or JSON body for robustness
    if not session_id:
        try:
            body = await request.json()
            if isinstance(body, dict):
                session_id = body.get("session_id")
        except Exception:
            # Ignore JSON parsing errors and fall through to validation
            pass

    if not session_id:
        logger.error("Premium activation attempted without session_id")
        raise HTTPException(status_code=400, detail="session_id is required")
    
    logger.info(f"Premium activation requested for session: {session_id}")
    
    try:
        # CRITICAL: Retrieve and verify the Stripe session (backend validation)
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            logger.info(f"Stripe session retrieved for activation: {session_id}, payment_status={session.payment_status}, status={session.status}")
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid Stripe session ID for activation {session_id}: {e}")
            raise HTTPException(status_code=400, detail="Invalid payment session ID")
        except stripe.error.AuthenticationError as e:
            logger.error(f"Stripe authentication error during activation: {e}")
            raise HTTPException(status_code=500, detail="Payment system authentication error")
        except stripe.error.APIConnectionError as e:
            logger.error(f"Stripe API connection error during activation: {e}")
            raise HTTPException(status_code=503, detail="Unable to verify payment - please try again later")
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error during activation for session {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Payment verification failed: {str(e)}")
        
        # Validate payment is actually completed
        if session.payment_status != 'paid' or session.status != 'complete':
            logger.warning(f"Activation attempted for unpaid session {session_id}: payment_status={session.payment_status}, status={session.status}")
            raise HTTPException(
                status_code=400, 
                detail=f"Payment not completed. Payment status: {session.payment_status}, session status: {session.status}"
            )
        
        subscription_id = session.subscription
        customer_email = session.customer_details.email if session.customer_details else session.customer_email
        stripe_customer_id = getattr(session, 'customer', None)
        
        if not customer_email or not subscription_id:
            logger.error(f"Missing required data in paid session {session_id}: email={customer_email}, subscription={subscription_id}")
            raise HTTPException(
                status_code=400,
                detail="Payment completed but missing customer email or subscription ID"
            )
        
        logger.info(f"Payment CONFIRMED for activation: session={session_id}, email={customer_email}, subscription={subscription_id}")
        
        # Sync Stripe customer/subscription rows to satisfy FK constraints
        # Try to enrich with subscription details when possible
        sub_obj = None
        try:
            if subscription_id:
                sub_obj = stripe.Subscription.retrieve(subscription_id)
                if not stripe_customer_id:
                    stripe_customer_id = getattr(sub_obj, 'customer', None)
        except Exception as e:
            logger.warning(f"Failed to retrieve subscription {subscription_id} details: {e}")

        try:
            _upsert_stripe_customer(stripe_customer_id, customer_email, None)
        except Exception:
            pass

        try:
            _upsert_stripe_subscription(
                subscription_id,
                stripe_customer_id,
                status=(getattr(sub_obj, 'status', None) if sub_obj else 'active'),
                current_period_start=_epoch_to_dt(getattr(sub_obj, 'current_period_start', None) if sub_obj else None),
                current_period_end=_epoch_to_dt(getattr(sub_obj, 'current_period_end', None) if sub_obj else None),
                canceled_at=_epoch_to_dt(getattr(sub_obj, 'canceled_at', None) if sub_obj else None),
                ended_at=_epoch_to_dt(getattr(sub_obj, 'ended_at', None) if sub_obj else None),
                trial_start=_epoch_to_dt(getattr(sub_obj, 'trial_start', None) if sub_obj else None),
                trial_end=_epoch_to_dt(getattr(sub_obj, 'trial_end', None) if sub_obj else None),
            )
        except Exception:
            pass

        # Get or create Premium Pass with comprehensive error handling
        from src.premium_pass_service import get_premium_pass_by_email, PremiumPassError
        
        pass_data = get_premium_pass_by_email(customer_email)
        
        if not pass_data:
            # Create Premium Pass - payment is verified by Stripe
            logger.info(f"Creating new Premium Pass for {customer_email}")
            
            current_user = get_user_from_request(request)
            user_id = None
            
            if current_user:
                user_id = _validate_user_id(current_user.get("id"))
                logger.info(f"Premium activation for authenticated user: user_id={user_id}")
            elif session.metadata and session.metadata.get('user_id'):
                user_id = _validate_user_id(int(session.metadata['user_id']))
                logger.info(f"Premium activation for user from session metadata: user_id={user_id}")
            else:
                logger.info(f"Premium activation for guest user: {customer_email}")
            
            try:
                pass_data = create_premium_pass(customer_email, subscription_id, user_id, stripe_customer_id)
                logger.info(f"Premium Pass CREATED for activation: pass_id={pass_data['pass_id']}, email={customer_email}, subscription={subscription_id}")
                
                # Update registered user status if applicable
                if user_id:
                    try:
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE users 
                                SET is_premium = TRUE, premium_expires_at = ?
                                WHERE id = ?
                            """, (pass_data["expires_at"], user_id))
                            conn.commit()
                        logger.info(f"Updated registered user premium status: user_id={user_id}")
                    except Exception as db_error:
                        logger.error(f"Failed to update user premium status: {db_error}")
                        # Continue - Premium Pass is created
                        
            except PremiumPassError as e:
                logger.error(f"CRITICAL: Premium Pass creation failed for verified payment {session_id}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Payment verified but Premium activation failed: {str(e)}"
                )
            except Exception as e:
                logger.error(f"CRITICAL: Unexpected error creating Premium Pass for session {session_id}: {type(e).__name__}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Premium activation failed - please contact support with your payment confirmation"
                )
        else:
            logger.info(f"Existing Premium Pass found for activation: pass_id={pass_data['pass_id']}, email={customer_email}")
        
        # Set Premium Pass cookie (HttpOnly, SameSite=Lax) with environment-aware security and global path
        try:
            import os
            is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        except Exception:
            is_production = False

        response.set_cookie(
            key="premium_pass",
            value=pass_data["token"],
            httponly=True,
            secure=is_production,  # Only secure in production/HTTPS
            samesite="lax",
            path="/",              # Make cookie available to entire site
            max_age=365 * 24 * 60 * 60  # 1 year
        )
        
        logger.info(f"Premium Pass cookie SET successfully for {customer_email}, pass_id={pass_data['pass_id']}")
        
        return {
            "success": True,
            "message": "Premium activated successfully",
            "premium_pass_id": pass_data["pass_id"],
            "email": customer_email,
            "subscription_id": subscription_id,
            "expires_at": pass_data["expires_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CRITICAL: Unexpected error in premium activation for session {session_id}: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate premium: {str(e)}"
        )


@billing_router.get("/activate-via-redirect")
async def activate_premium_via_redirect(request: Request, session_id: str = None, next: str = "/payment-success.html?activated=1"):
    """
    Robust activation endpoint for use as Stripe success_url.
    Verifies the payment session, creates Premium Pass if needed, sets cookie, and redirects to a success page.

    Query params:
        session_id: Stripe Checkout session ID appended by Stripe to success_url
        next: Optional relative URL to redirect after setting the cookie (default: /payment-success.html?activated=1)
    """
    if not get_feature_flag_billing_enabled():
        logger.warning("Premium activation (redirect) attempted but billing is disabled")
        raise HTTPException(status_code=503, detail="Billing functionality is currently disabled")

    if not session_id:
        logger.error("Redirect activation attempted without session_id")
        raise HTTPException(status_code=400, detail="session_id is required")

    logger.info(f"Premium activation via redirect requested for session: {session_id}")

    # We'll reuse the core of the POST activation logic here
    try:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            logger.info(f"Stripe session retrieved for redirect activation: {session_id}, payment_status={session.payment_status}, status={session.status}")
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid Stripe session ID for redirect activation {session_id}: {e}")
            raise HTTPException(status_code=400, detail="Invalid payment session ID")
        except stripe.error.AuthenticationError as e:
            logger.error(f"Stripe authentication error during redirect activation: {e}")
            raise HTTPException(status_code=500, detail="Payment system authentication error")
        except stripe.error.APIConnectionError as e:
            logger.error(f"Stripe API connection error during redirect activation: {e}")
            raise HTTPException(status_code=503, detail="Unable to verify payment - please try again later")
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error during redirect activation for session {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Payment verification failed: {str(e)}")

        if session.payment_status != 'paid' or session.status != 'complete':
            logger.warning(f"Redirect activation attempted for unpaid session {session_id}: payment_status={session.payment_status}, status={session.status}")
            raise HTTPException(status_code=400, detail=f"Payment not completed. Payment status: {session.payment_status}, session status: {session.status}")

        subscription_id = session.subscription
        customer_email = session.customer_details.email if session.customer_details else session.customer_email
        stripe_customer_id = getattr(session, 'customer', None)

        if not customer_email or not subscription_id:
            logger.error(f"Missing required data in paid session {session_id}: email={customer_email}, subscription={subscription_id}")
            raise HTTPException(status_code=400, detail="Payment completed but missing customer email or subscription ID")

        logger.info(f"Payment CONFIRMED for redirect activation: session={session_id}, email={customer_email}, subscription={subscription_id}")

        # Ensure Stripe customer/subscription exist in DB for FK integrity
        sub_obj = None
        try:
            if subscription_id:
                sub_obj = stripe.Subscription.retrieve(subscription_id)
                if not stripe_customer_id:
                    stripe_customer_id = getattr(sub_obj, 'customer', None)
        except Exception as e:
            logger.warning(f"Failed to retrieve subscription {subscription_id} details (redirect): {e}")

        try:
            _upsert_stripe_customer(stripe_customer_id, customer_email, None)
        except Exception:
            pass
        try:
            _upsert_stripe_subscription(
                subscription_id,
                stripe_customer_id,
                status=(getattr(sub_obj, 'status', None) if sub_obj else 'active'),
                current_period_start=_epoch_to_dt(getattr(sub_obj, 'current_period_start', None) if sub_obj else None),
                current_period_end=_epoch_to_dt(getattr(sub_obj, 'current_period_end', None) if sub_obj else None),
                canceled_at=_epoch_to_dt(getattr(sub_obj, 'canceled_at', None) if sub_obj else None),
                ended_at=_epoch_to_dt(getattr(sub_obj, 'ended_at', None) if sub_obj else None),
                trial_start=_epoch_to_dt(getattr(sub_obj, 'trial_start', None) if sub_obj else None),
                trial_end=_epoch_to_dt(getattr(sub_obj, 'trial_end', None) if sub_obj else None),
            )
        except Exception:
            pass

        # Get or create Premium Pass
        from src.premium_pass_service import get_premium_pass_by_email, PremiumPassError

        pass_data = get_premium_pass_by_email(customer_email)
        if not pass_data:
            current_user = get_user_from_request(request)
            user_id = None
            if current_user:
                user_id = _validate_user_id(current_user.get("id"))
                logger.info(f"Redirect activation for authenticated user: user_id={user_id}")
            elif session.metadata and session.metadata.get('user_id'):
                user_id = _validate_user_id(int(session.metadata['user_id']))
                logger.info(f"Redirect activation for user from session metadata: user_id={user_id}")

            try:
                pass_data = create_premium_pass(customer_email, subscription_id, user_id, stripe_customer_id)
                logger.info(f"Premium Pass CREATED (redirect): pass_id={pass_data['pass_id']}, email={customer_email}, subscription={subscription_id}")

                if user_id:
                    try:
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                UPDATE users 
                                SET is_premium = TRUE, premium_expires_at = ?
                                WHERE id = ?
                                """,
                                (pass_data["expires_at"], user_id)
                            )
                            conn.commit()
                        logger.info(f"Updated registered user premium status (redirect): user_id={user_id}")
                    except Exception as db_error:
                        logger.error(f"Failed to update user premium status (redirect): {db_error}")
            except PremiumPassError as e:
                logger.error(f"Premium Pass creation failed (redirect) for verified payment {session_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Payment verified but Premium activation failed: {str(e)}")

        # Prepare redirect response and set cookie
        try:
            import os
            is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        except Exception:
            is_production = False

        redirect_response = RedirectResponse(url=next, status_code=303)
        redirect_response.set_cookie(
            key="premium_pass",
            value=pass_data["token"],
            httponly=True,
            secure=is_production,
            samesite="lax",
            path="/",
            max_age=365 * 24 * 60 * 60
        )

        logger.info(f"Premium Pass cookie SET (redirect) for {customer_email}, pass_id={pass_data['pass_id']}")
        return redirect_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CRITICAL: Unexpected error in redirect premium activation for session {session_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete premium activation via redirect")

