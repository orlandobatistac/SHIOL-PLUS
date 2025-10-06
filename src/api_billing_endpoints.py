# Billing API Endpoints for Stripe Integration
"""
FastAPI endpoints for handling Stripe billing operations.
Includes checkout session creation, webhook processing, and status checking.
"""

import json
import stripe
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Response, Header, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from loguru import logger

from src.stripe_config import get_stripe_config, get_feature_flag_billing_enabled
from src.premium_pass_service import (
    create_premium_pass, 
    revoke_premium_pass_by_subscription,
    get_premium_pass_by_email
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "success_url": "https://shiol.app/payment-success",
                "cancel_url": "https://shiol.app/"
            }
        }

class BillingStatusResponse(BaseModel):
    enabled: bool
    is_premium: Optional[bool] = None
    source: Optional[str] = None
    message: Optional[str] = None

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
                datetime.utcnow()
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
        raise HTTPException(
            status_code=503,
            detail="Billing functionality is currently disabled"
        )
    
    endpoint = "create-checkout-session"
    request_payload = json.dumps(checkout_request.dict())
    
    # Check idempotency
    existing_result = check_idempotency_key(idempotency_key, endpoint, request_payload)
    if existing_result:
        return existing_result["response"]
    
    try:
        # Get current user if authenticated
        current_user = get_user_from_request(request)
        customer_email = current_user.get("email") if current_user else None
        
        # Create Stripe Checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': stripe_config["price_id_annual"],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=checkout_request.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=checkout_request.cancel_url,
            customer_email=customer_email,
            metadata={
                'user_id': str(current_user["id"]) if current_user else None,
                'source': 'shiol_plus_upgrade'
            },
            subscription_data={
                'metadata': {
                    'user_id': str(current_user["id"]) if current_user else None,
                    'source': 'shiol_plus_upgrade'
                }
            }
        )
        
        response_data = {
            "checkout_url": session.url,
            "session_id": session.id
        }
        
        # Store idempotency result
        store_idempotency_result(idempotency_key, endpoint, request_payload, response_data, 200)
        
        logger.info(f"Checkout session created: {session.id} for user {current_user.get('id') if current_user else 'guest'}")
        
        return response_data
        
    except Exception as e:  # Stripe errors are just exceptions
        logger.error(f"Stripe error creating checkout session: {e}")
        error_response = {"error": f"Payment processing error: {str(e)}"}
        store_idempotency_result(idempotency_key, endpoint, request_payload, error_response, 400)
        raise HTTPException(status_code=400, detail=error_response["error"])
        
    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {e}")
        error_response = {"error": "Internal server error"}
        store_idempotency_result(idempotency_key, endpoint, request_payload, error_response, 500)
        raise HTTPException(status_code=500, detail="Internal server error")

@billing_router.post("/webhook")
async def stripe_webhook(request: Request, response: Response):
    """
    Handle Stripe webhook events with idempotent processing.
    Validates webhook signature and processes events safely.
    """
    if not get_feature_flag_billing_enabled():
        raise HTTPException(status_code=503, detail="Billing functionality disabled")
    
    try:
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        
        if not sig_header:
            logger.error("Missing stripe-signature header")
            raise HTTPException(status_code=400, detail="Missing signature header")
        
        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, stripe_config["webhook_secret"]
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except Exception as e:  # Signature verification errors
            logger.error(f"Invalid signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Check if event already processed (idempotency)
        event_id = event['id']
        event_type = event['type']
        
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
                    logger.info(f"Webhook event already processed: {event_id}")
                    return {"status": "already_processed"}
                elif processing_error:
                    logger.warning(f"Retrying failed webhook event: {event_id}")
            
            # Store/update webhook event
            cursor.execute("""
                INSERT OR REPLACE INTO webhook_events 
                (stripe_event_id, event_type, payload, created_at)
                VALUES (?, ?, ?, ?)
            """, (event_id, event_type, json.dumps(event), datetime.utcnow()))
            
            conn.commit()
        
        # Process webhook event
        try:
            await process_webhook_event(event, response)
            
            # Mark as processed
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE webhook_events 
                    SET processed = TRUE, processed_at = ?, processing_error = NULL, retry_count = retry_count + 1
                    WHERE stripe_event_id = ?
                """, (datetime.utcnow(), event_id))
                conn.commit()
            
            logger.info(f"Webhook event processed successfully: {event_id} ({event_type})")
            
        except Exception as e:
            # Mark processing error
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE webhook_events 
                    SET processing_error = ?, retry_count = retry_count + 1
                    WHERE stripe_event_id = ?
                """, (str(e), event_id))
                conn.commit()
            
            logger.error(f"Error processing webhook event {event_id}: {e}")
            raise HTTPException(status_code=500, detail="Webhook processing failed")
        
        return {"status": "success"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

async def process_webhook_event(event: Dict[str, Any], response: Response) -> None:
    """Process individual webhook events based on type."""
    event_type = event['type']
    data = event['data']['object']
    
    if event_type == 'checkout.session.completed':
        await handle_checkout_completed(data, response)
    elif event_type == 'invoice.paid':
        await handle_invoice_paid(data)
    elif event_type == 'customer.subscription.updated':
        await handle_subscription_updated(data)
    elif event_type == 'customer.subscription.deleted':
        await handle_subscription_deleted(data, response)
    elif event_type in ['charge.dispute.created', 'charge.refunded']:
        await handle_payment_dispute_or_refund(data, response)
    else:
        logger.info(f"Unhandled webhook event type: {event_type}")

async def handle_checkout_completed(session: Dict[str, Any], response: Response) -> None:
    """Handle successful checkout completion - activate Premium Pass."""
    try:
        customer_email = session.get('customer_email') or session.get('customer_details', {}).get('email')
        subscription_id = session.get('subscription')
        customer_id = session.get('customer')
        
        if not customer_email or not subscription_id:
            logger.error(f"Missing required data in checkout session: {session['id']}")
            return
        
        # Check if user is registered
        user_id = None
        if 'metadata' in session and session['metadata'].get('user_id'):
            user_id = int(session['metadata']['user_id'])
        
        # Create Premium Pass
        pass_data = create_premium_pass(customer_email, subscription_id, user_id)
        
        # Set Premium Pass cookie (HttpOnly, Secure, SameSite=Lax)
        response.set_cookie(
            key="premium_pass",
            value=pass_data["token"],
            httponly=True,
            secure=True,  # HTTPS only in production
            samesite="lax",
            max_age=365 * 24 * 60 * 60  # 1 year in seconds
        )
        
        # Update user premium status if registered
        if user_id:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users 
                    SET is_premium = TRUE, premium_expires_at = ?
                    WHERE id = ?
                """, (pass_data["expires_at"], user_id))
                conn.commit()
        
        logger.info(f"Premium activated for {customer_email}: subscription={subscription_id}, pass_id={pass_data['pass_id']}")
        
    except Exception as e:
        logger.error(f"Error handling checkout completion: {e}")
        raise

async def handle_subscription_deleted(subscription: Dict[str, Any], response: Response) -> None:
    """Handle subscription cancellation - revoke Premium Pass."""
    try:
        subscription_id = subscription['id']
        
        # Revoke Premium Pass
        revoked_count = revoke_premium_pass_by_subscription(
            subscription_id, 
            "subscription_canceled"
        )
        
        # Clear Premium Pass cookie
        response.delete_cookie(key="premium_pass", httponly=True, secure=True, samesite="lax")
        
        # Update user premium status if applicable
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
            conn.commit()
        
        logger.info(f"Premium revoked for subscription {subscription_id}: {revoked_count} passes revoked")
        
    except Exception as e:
        logger.error(f"Error handling subscription deletion: {e}")
        raise

async def handle_payment_dispute_or_refund(charge: Dict[str, Any], response: Response) -> None:
    """Handle payment disputes and refunds - revoke Premium Pass."""
    try:
        # Get subscription from charge
        invoice_id = charge.get('invoice')
        if not invoice_id:
            return
        
        # Retrieve invoice to get subscription
        invoice = stripe.Invoice.retrieve(invoice_id)
        subscription_id = invoice.get('subscription')
        
        if subscription_id:
            # Revoke Premium Pass
            revoked_count = revoke_premium_pass_by_subscription(
                subscription_id, 
                "payment_dispute_or_refund"
            )
            
            # Clear Premium Pass cookie
            response.delete_cookie(key="premium_pass", httponly=True, secure=True, samesite="lax")
            
            logger.info(f"Premium revoked due to dispute/refund for subscription {subscription_id}: {revoked_count} passes revoked")
        
    except Exception as e:
        logger.error(f"Error handling payment dispute/refund: {e}")
        raise

async def handle_invoice_paid(invoice: Dict[str, Any]) -> None:
    """Handle successful invoice payment - sync subscription status."""
    # This could be used for renewal notifications or status sync
    subscription_id = invoice.get('subscription')
    if subscription_id:
        logger.info(f"Invoice paid for subscription {subscription_id}")

async def handle_subscription_updated(subscription: Dict[str, Any]) -> None:
    """Handle subscription updates - sync status changes."""
    subscription_id = subscription['id']
    status = subscription['status']
    logger.info(f"Subscription {subscription_id} updated to status: {status}")

@billing_router.get("/status", response_model=BillingStatusResponse)
async def get_billing_status(request: Request):
    """
    Get billing system status and user premium status.
    Returns billing enabled state and premium status if authenticated.
    """
    billing_enabled = get_feature_flag_billing_enabled()
    
    response_data = BillingStatusResponse(enabled=billing_enabled)
    
    if not billing_enabled:
        response_data.message = "Billing functionality is currently disabled"
        return response_data
    
    # Check user authentication and premium status
    current_user = get_user_from_request(request)
    
    if current_user and current_user.get("is_premium"):
        response_data.is_premium = True
        response_data.source = "stripe_subscription"
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
            except Exception as e:
                logger.warning(f"Invalid Premium Pass token: {e}")
    
    return response_data