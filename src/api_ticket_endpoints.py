"""
API endpoints for ticket verification functionality.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger
from typing import Dict, Any, List, Optional
import io
import json

from src.ticket_processor import create_ticket_processor
from src.ticket_verifier import create_ticket_verifier
from src.ticket_limits_integration import check_verification_access, record_verification_usage, get_limits_info


# Create router for ticket verification endpoints
ticket_router = APIRouter(prefix="/api/v1/ticket", tags=["ticket"])

# Initialize processors
ticket_processor = create_ticket_processor()
ticket_verifier = create_ticket_verifier()


# Pydantic models for limits endpoint
class DeviceFingerprintData(BaseModel):
    screen_resolution: Optional[str] = None
    timezone_offset: Optional[int] = None
    color_depth: Optional[int] = None
    platform: Optional[str] = None
    language: Optional[str] = None
    cookie_enabled: Optional[bool] = None
    canvas_fingerprint: Optional[str] = None
    webgl_fingerprint: Optional[str] = None
    touch_support: Optional[bool] = None
    hardware_concurrency: Optional[int] = None
    device_memory: Optional[float] = None

class LimitsCheckRequest(BaseModel):
    device_info: Optional[DeviceFingerprintData] = None

@ticket_router.post("/limits-check")
async def check_verification_limits(request: Request, body: LimitsCheckRequest = LimitsCheckRequest()):
    """
    Check verification limits for current user/device.
    
    Args:
        request: FastAPI request object
        body: Optional device fingerprint data for guest users
        
    Returns:
        Limits information including remaining verifications and reset time
    """
    try:
        device_info = None
        if body.device_info:
            device_info = body.device_info.dict(exclude_none=True)
        
        limits_info = get_limits_info(request, device_info)
        
        logger.info(f"Limits check: {limits_info.get('user_type', 'unknown')} user, "
                   f"remaining: {limits_info.get('remaining', 'N/A')}")
        
        return {
            "success": True,
            "limits": limits_info
        }
        
    except Exception as e:
        logger.error(f"Error checking verification limits: {e}")
        return {
            "success": False,
            "error": "Failed to check limits",
            "limits": {
                "allowed": False,
                "error": "System error"
            }
        }

@ticket_router.post("/verify")
async def verify_ticket_image(request: Request, file: UploadFile = File(...), manual_date: Optional[str] = None):
    """
    Verify a Powerball ticket by processing an uploaded image.
    
    Args:
        request: FastAPI request object
        file: Uploaded image file (JPG, PNG, etc.)
        manual_date: Optional manual date override
        
    Returns:
        JSON response with verification results
    """
    try:
        # CRITICAL SECURITY CHECK: Verify access limits before processing
        # Extract device info from header for limit checking
        device_info = None
        fingerprint_header = request.headers.get('x-device-fingerprint')
        if fingerprint_header:
            try:
                import json
                device_info = json.loads(fingerprint_header)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Invalid device fingerprint header: {e}")
        
        # CHECK VERIFICATION LIMITS FIRST (Critical security check)
        try:
            access_result = check_verification_access(request, device_info)
            if not access_result.get("allowed", False):
                logger.warning(f"Verification blocked due to limits: {access_result}")
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "verification_limit_reached",
                        "message": "You have reached your verification limit for this week.",
                        "limits_info": access_result
                    }
                )
        except Exception as e:
            logger.error(f"Error checking verification limits: {e}")
            # For security, fail closed - deny if we can't check limits
            raise HTTPException(
                status_code=500,
                detail="Unable to verify access limits. Please try again later."
            )
        
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image (JPG, PNG, etc.)"
            )
        
        # Read image data
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )
        
        if len(image_data) > 25 * 1024 * 1024:  # 25MB limit (increased for mobile support)
            raise HTTPException(
                status_code=400,
                detail="File size too large. Maximum size is 25MB"
            )
        
        logger.info(f"Processing ticket image: {file.filename}, size: {len(image_data)} bytes")
        
        # Process the image to extract ticket data
        ticket_data = ticket_processor.process_ticket_image(image_data)
        
        # Override date if manual date is provided
        if manual_date:
            try:
                # Validate manual date format
                from datetime import datetime
                datetime.strptime(manual_date, '%Y-%m-%d')
                ticket_data['draw_date'] = manual_date
                ticket_data['manual_date_override'] = True
                logger.info(f"Using manual date override: {manual_date}")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Please use YYYY-MM-DD format."
                )
        
        if not ticket_data.get('success', False):
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error": "Could not process ticket image",
                    "details": ticket_data.get('error', 'Unknown processing error'),
                    "raw_text_lines": ticket_data.get('raw_text_lines', [])
                }
            )
        
        # Final validation check: Ensure we have valid plays
        plays = ticket_data.get('plays', [])
        if not plays:
            # Check if we had validation errors
            validation_summary = ticket_data.get('validation_summary', {})
            validation_errors = validation_summary.get('validation_errors', [])
            
            if validation_errors:
                return JSONResponse(
                    status_code=422,
                    content={
                        "success": False,
                        "error": "No valid lottery numbers found on ticket",
                        "details": f"All detected numbers were invalid: {'; '.join(validation_errors[:3])}",
                        "validation_summary": validation_summary,
                        "raw_text_lines": ticket_data.get('raw_text_lines', [])
                    }
                )
            else:
                return JSONResponse(
                    status_code=422,
                    content={
                        "success": False,
                        "error": "No lottery numbers detected on ticket",
                        "details": "Could not find any valid Powerball plays in the image",
                        "raw_text_lines": ticket_data.get('raw_text_lines', [])
                    }
                )
        
        # Log validation results
        validation_summary = ticket_data.get('validation_summary', {})
        if validation_summary.get('invalid_plays', 0) > 0:
            logger.warning(f"Rejected {validation_summary['invalid_plays']} invalid plays out of {validation_summary['total_detected']} detected")
            logger.info(f"Proceeding with {len(plays)} valid plays")
        
        # Verify the extracted ticket data against official results
        verification_result = ticket_verifier.verify_ticket(ticket_data)
        
        if not verification_result.get('success', False):
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error": "Could not verify ticket",
                    "details": verification_result.get('error', 'Unknown verification error'),
                    "ticket_data": ticket_data
                }
            )
        
        # Format the response
        response = {
            "success": True,
            "message": "Ticket processed and verified successfully",
            "ticket_verification": {
                "is_winner": verification_result.get('is_winning_ticket', False),
                "total_prize_amount": verification_result.get('total_prize_amount', 0),
                "total_plays": verification_result.get('total_plays', 0),
                "winning_plays": verification_result.get('total_winning_plays', 0),
                "draw_date": verification_result.get('draw_date'),
                "official_numbers": verification_result.get('official_numbers', []),
                "official_powerball": verification_result.get('official_powerball', 0),
                "play_results": []
            },
            "processing_info": {
                "filename": file.filename,
                "extracted_plays": ticket_data.get('total_plays', 0),
                "processed_at": verification_result.get('processed_at')
            }
        }
        
        # Add detailed results for each play
        for result in verification_result.get('verification_results', []):
            play_result = {
                "line": result.get('line', '?'),
                "numbers": result.get('play_numbers', []),
                "powerball": result.get('powerball', 0),
                "main_matches": result.get('main_matches', 0),
                "powerball_match": result.get('powerball_match', False),
                "prize_amount": result.get('prize_amount', 0),
                "prize_tier": result.get('prize_tier', 'No Prize'),
                "is_winner": result.get('is_winner', False)
            }
            response["ticket_verification"]["play_results"].append(play_result)
        
        # Add summary message
        summary = ticket_verifier.format_verification_summary(verification_result)
        response["summary"] = summary
        
        logger.info(f"Ticket verification completed: {verification_result.get('is_winning_ticket', False)}")
        
        # CRITICAL SECURITY: ATOMIC USAGE RECORDING BEFORE RETURNING RESULTS
        # This prevents race conditions where concurrent requests get free verifications
        device_info = None
        if 'x-device-fingerprint' in request.headers:
            try:
                device_info = json.loads(request.headers['x-device-fingerprint'])
            except (json.JSONDecodeError, ValueError):
                logger.warning("Invalid device fingerprint header format during usage recording")
        
        # Record usage atomically - if it fails, deny the verification even though processing succeeded
        usage_recorded = record_verification_usage(request, device_info)
        if not usage_recorded:
            logger.warning("SECURITY: Atomic usage recording failed - denying verification to prevent limit bypass")
            # CRITICAL: Even though verification succeeded, we deny it due to limit enforcement
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "verification_limit_reached",
                    "message": "You have reached your verification limit for this week.",
                    "security_note": "Verification was successful but cannot be delivered due to usage limits."
                }
            )
        
        logger.info("Verification usage recorded successfully - proceeding with result delivery")
            
        # Add usage info to response for frontend tracking
        try:
            access_result = check_verification_access(request, device_info)
            reset_time = access_result.get("reset_time")
            response["verification_limits"] = {
                "remaining": access_result.get("remaining", -1),
                "next_reset": reset_time.isoformat() if reset_time else None,
                "user_type": access_result.get("user_type", "unknown")
            }
        except Exception as e:
            logger.warning(f"Could not add verification limits to response: {e}")
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in ticket verification endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during ticket verification: {str(e)}"
        )


@ticket_router.post("/preview")
async def preview_ticket_numbers(request: Request, file: UploadFile = File(...)):
    """
    Preview numbers detected from ticket image (no limits applied).
    Shows what OCR detected without consuming verification quotas.
    
    Args:
        request: FastAPI request object
        file: Uploaded ticket image file
        
    Returns:
        Detected numbers and metadata
    """
    try:
        # NOTE: Preview endpoint does NOT enforce verification limits
        # Only actual verification (/verify) consumes quotas
        
        # Validate file
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload an image file."
            )
        
        # Read and process the image
        logger.info(f"Processing ticket preview (no limits): {file.filename}, size: {file.size} bytes")
        
        try:
            ticket_processor = create_ticket_processor()
        except Exception as processor_error:
            logger.error(f"Failed to initialize ticket processor: {processor_error}")
            raise HTTPException(
                status_code=503,
                detail=f"Gemini AI service not initialized: {str(processor_error)}"
            )
        
        image_data = await file.read()
        
        # Extract ticket data (numbers only, no verification)
        ticket_data = ticket_processor.process_ticket_image(image_data)
        
        if not ticket_data or not ticket_data.get('success', False):
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error": "Could not process ticket image",
                    "details": ticket_data.get('error', 'Unknown processing error'),
                    "raw_text_lines": ticket_data.get('raw_text_lines', [])
                }
            )
        
        plays = ticket_data.get('plays', [])
        
        # Format the detected plays for preview
        detected_plays = []
        for i, play in enumerate(plays):
            detected_plays.append({
                "play_id": i + 1,
                "play_letter": play.get('play_letter', chr(ord('A') + i)),
                "main_numbers": sorted(play.get('main_numbers', [])),
                "powerball": play.get('powerball', 0),
                "is_valid": len(play.get('main_numbers', [])) == 5 and 
                           1 <= play.get('powerball', 0) <= 26
            })
        
        response = {
            "success": True,
            "message": "Ticket numbers detected successfully",
            "detected_plays": detected_plays,
            "total_plays_found": len(plays),
            "draw_date_detected": ticket_data.get('draw_date'),
            "extraction_method": ticket_data.get('extraction_method', 'unknown'),
            "confidence": ticket_data.get('confidence', 0),
            "processing_info": {
                "filename": file.filename,
                "total_lines_extracted": len(ticket_data.get('raw_text_lines', [])),
                "validation_summary": ticket_data.get('validation_summary', {})
            }
        }
        
        logger.info(f"Ticket preview completed: {len(plays)} plays detected")
        
        # NOTE: Preview endpoint NO LONGER counts as verification usage
        # Only the /verify endpoint should count usage when verification is successful
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ticket preview endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during ticket preview: {str(e)}"
        )


@ticket_router.get("/health")
async def ticket_service_health():
    """
    Health check endpoint for ticket verification service.
    
    Returns:
        Service health status
    """
    try:
        return {
            "status": "healthy",
            "service": "ticket_verification",
            "version": "1.0.0",
            "features": [
                "image_processing",
                "ocr_extraction",
                "number_verification",
                "prize_calculation"
            ]
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Service health check failed"
        )


@ticket_router.post("/debug/extract")
async def debug_extract_ticket_data(file: UploadFile = File(...)):
    """
    Debug endpoint to see raw extraction results without verification.
    
    Args:
        file: Uploaded image file
        
    Returns:
        Raw extraction results for debugging
    """
    try:
        # Validate file
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image"
            )
        
        # Read and process image
        image_data = await file.read()
        ticket_data = ticket_processor.process_ticket_image(image_data)
        
        return {
            "success": True,
            "filename": file.filename,
            "extraction_result": ticket_data,
            "note": "This is a debug endpoint showing raw extraction results"
        }
        
    except Exception as e:
        logger.error(f"Error in debug extraction endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Debug extraction failed: {str(e)}"
        )


class ManualPlay(BaseModel):
    line: int
    main_numbers: List[int]
    powerball: int

class ManualVerificationRequest(BaseModel):
    plays: List[ManualPlay]
    draw_date: str


@ticket_router.post("/verify-manual")
async def verify_manual_plays(fastapi_request: Request, request: ManualVerificationRequest):
    """
    Verify manually entered lottery numbers against official results.
    
    Args:
        fastapi_request: FastAPI request object
        request: Manual verification request with plays and draw date
        
    Returns:
        JSON response with verification results
    """
    try:
        # NOTE: Limits checking moved to preview endpoint - no limits check needed here
        
        if not request.plays:
            raise HTTPException(
                status_code=400,
                detail="At least one play is required"
            )

        if len(request.plays) > 5:
            raise HTTPException(
                status_code=400,
                detail="Maximum 5 plays allowed"
            )

        # Validate draw date format
        try:
            from datetime import datetime
            datetime.strptime(request.draw_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Please use YYYY-MM-DD format."
            )

        logger.info(f"Processing manual verification: {len(request.plays)} plays for date {request.draw_date}")
        
        # Convert Pydantic models to dict format expected by ticket processor
        plays_data = []
        for play in request.plays:
            # Validate play numbers using ticket processor validation
            play_dict = {
                'line': play.line,
                'main_numbers': play.main_numbers,
                'powerball': play.powerball
            }
            plays_data.append(play_dict)

        # Create ticket processor and validate all plays
        processor = create_ticket_processor()
        validation_result = processor.validate_all_plays(plays_data)
        
        if not validation_result['valid_plays']:
            # All plays were invalid
            error_details = "; ".join(validation_result['validation_errors'][:3])
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error": "Invalid lottery numbers entered",
                    "details": f"All plays were rejected: {error_details}",
                    "validation_summary": {
                        'total_detected': validation_result['total_plays'],
                        'valid_plays': len(validation_result['valid_plays']),
                        'invalid_plays': len(validation_result['invalid_plays']),
                        'validation_errors': validation_result['validation_errors'],
                        'validation_warnings': validation_result['validation_warnings']
                    }
                }
            )

        # Log validation results
        if validation_result['invalid_plays']:
            logger.warning(f"Manual entry validation rejected {len(validation_result['invalid_plays'])} plays out of {validation_result['total_plays']}")
            for invalid_play in validation_result['invalid_plays']:
                logger.warning(f"Invalid manual play {invalid_play['line']}: {invalid_play['errors']}")

        # Create ticket data structure for verification
        ticket_data = {
            'success': True,
            'plays': validation_result['valid_plays'],
            'draw_date': request.draw_date,
            'total_plays': len(validation_result['valid_plays']),
            'extraction_method': 'manual_entry',
            'validation_summary': {
                'total_detected': validation_result['total_plays'],
                'valid_plays': len(validation_result['valid_plays']),
                'invalid_plays': len(validation_result['invalid_plays']),
                'validation_errors': validation_result['validation_errors'],
                'validation_warnings': validation_result['validation_warnings']
            }
        }

        # Create ticket verifier and verify the manual ticket data against official results
        ticket_verifier = create_ticket_verifier()
        verification_result = ticket_verifier.verify_ticket(ticket_data)

        if not verification_result.get('success', False):
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "error": "Could not verify manual ticket",
                    "details": verification_result.get('error', 'Unknown verification error'),
                    "ticket_data": ticket_data
                }
            )

        # Format the response
        response = {
            "success": True,
            "message": "Manual numbers verified successfully",
            "ticket_verification": {
                "is_winner": verification_result.get('is_winning_ticket', False),
                "total_prize_amount": verification_result.get('total_prize_amount', 0),
                "total_plays": verification_result.get('total_plays', 0),
                "winning_plays": verification_result.get('total_winning_plays', 0),
                "draw_date": verification_result.get('draw_date'),
                "official_numbers": verification_result.get('official_numbers', []),
                "official_powerball": verification_result.get('official_powerball', 0),
                "play_results": []
            },
            "processing_info": {
                "source": "manual_entry",
                "extracted_plays": ticket_data.get('total_plays', 0),
                "processed_at": verification_result.get('processed_at')
            }
        }

        # Add detailed results for each play
        for result in verification_result.get('verification_results', []):
            play_result = {
                "line": result.get('line', '?'),
                "numbers": result.get('play_numbers', []),
                "powerball": result.get('powerball', 0),
                "main_matches": result.get('main_matches', 0),
                "powerball_match": result.get('powerball_match', False),
                "prize_amount": result.get('prize_amount', 0),
                "prize_tier": result.get('prize_tier', 'No Prize'),
                "is_winner": result.get('is_winner', False)
            }
            response["ticket_verification"]["play_results"].append(play_result)

        # Add validation summary if there were issues
        if validation_result['invalid_plays'] or validation_result['validation_warnings']:
            response["validation_info"] = {
                "total_entered": validation_result['total_plays'],
                "valid_plays": len(validation_result['valid_plays']),
                "rejected_plays": len(validation_result['invalid_plays']),
                "warnings": validation_result['validation_warnings']
            }

        # Add summary message
        summary = ticket_verifier.format_verification_summary(verification_result)
        response["summary"] = summary

        logger.info(f"Manual verification completed: {verification_result.get('is_winning_ticket', False)} for {len(validation_result['valid_plays'])} plays")

        # NOTE: Usage recording moved to preview endpoint - no recording needed here

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in manual verification endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during manual verification: {str(e)}"
        )