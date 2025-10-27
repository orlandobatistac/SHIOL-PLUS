# Device Fingerprinting for Guest User Identification
"""
Secure device fingerprinting system for tracking guest users without persistent storage.
Uses browser characteristics and HTTP headers to create unique identifiers.
"""

import hashlib
import json
from typing import Dict, Optional, Any
from fastapi import Request
from loguru import logger


def generate_device_fingerprint(request: Request, frontend_data: Optional[Dict] = None) -> str:
    """
    Generate a stable device fingerprint from browser and HTTP characteristics.
    
    Args:
        request: FastAPI Request object with headers and client info
        frontend_data: Optional frontend fingerprint data from JavaScript
        
    Returns:
        SHA-256 hex string as device fingerprint
        
    Note:
        - Uses only non-PII browser characteristics  
        - Stable across sessions but changes on major browser updates
        - Not designed to track users permanently, just for weekly limits
    """
    fingerprint_components = {}

    # HTTP Headers (stable browser characteristics)
    headers = request.headers
    fingerprint_components.update({
        'user_agent': headers.get('user-agent', ''),
        'accept_language': headers.get('accept-language', ''),
        'accept_encoding': headers.get('accept-encoding', ''),
        'accept': headers.get('accept', ''),
        'sec_ch_ua': headers.get('sec-ch-ua', ''),
        'sec_ch_ua_platform': headers.get('sec-ch-ua-platform', ''),
        'sec_ch_ua_mobile': headers.get('sec-ch-ua-mobile', ''),
    })

    # Client IP (for additional uniqueness, not for tracking)
    client_ip = get_client_ip(request)
    if client_ip:
        # Use only first 3 octets for privacy (avoid full IP tracking)
        ip_parts = client_ip.split('.')
        if len(ip_parts) == 4:
            fingerprint_components['ip_subnet'] = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0"

    # Frontend JavaScript fingerprint data (if available)
    if frontend_data:
        # Safe characteristics that don't identify users personally
        safe_frontend_data = {
            'screen_resolution': frontend_data.get('screen_resolution'),
            'timezone_offset': frontend_data.get('timezone_offset'),
            'color_depth': frontend_data.get('color_depth'),
            'platform': frontend_data.get('platform'),
            'language': frontend_data.get('language'),
            'cookie_enabled': frontend_data.get('cookie_enabled'),
            'canvas_fingerprint': frontend_data.get('canvas_fingerprint'),
            'webgl_fingerprint': frontend_data.get('webgl_fingerprint'),
            'touch_support': frontend_data.get('touch_support'),
            'hardware_concurrency': frontend_data.get('hardware_concurrency'),
            'device_memory': frontend_data.get('device_memory'),
        }

        # Only include non-null values
        fingerprint_components['frontend'] = {
            k: v for k, v in safe_frontend_data.items() if v is not None
        }

    # Create deterministic hash
    fingerprint_string = json.dumps(fingerprint_components, sort_keys=True)
    fingerprint_hash = hashlib.sha256(fingerprint_string.encode('utf-8')).hexdigest()

    logger.debug(f"Generated device fingerprint: {fingerprint_hash[:16]}... from {len(fingerprint_components)} components")

    return fingerprint_hash


def get_client_ip(request: Request, trust_forwarded: bool = False) -> Optional[str]:
    """
    Extract client IP from request headers, with secure IP handling.
    
    Args:
        request: FastAPI Request object
        trust_forwarded: If True, trust X-Forwarded-For headers (only use behind trusted proxy)
        
    Returns:
        Client IP address string or None
    """
    # Only trust forwarded headers if explicitly enabled (trusted proxy environment)
    if trust_forwarded:
        forwarded_headers = [
            'x-forwarded-for',
            'x-real-ip',
            'cf-connecting-ip',  # Cloudflare
            'x-cluster-client-ip',
            'forwarded'
        ]

        for header in forwarded_headers:
            value = request.headers.get(header)
            if value:
                # X-Forwarded-For can contain multiple IPs (client, proxy1, proxy2...)
                # Take the first one (original client)
                ip = value.split(',')[0].strip()
                if is_valid_ip(ip):
                    return ip

    # Fallback to direct client IP (default secure behavior)
    if request.client and hasattr(request.client, 'host') and request.client.host:
        return request.client.host

    return None


def is_valid_ip(ip: str) -> bool:
    """
    Basic IP address validation.
    
    Args:
        ip: IP address string to validate
        
    Returns:
        True if valid IPv4 address
    """
    try:
        parts = ip.split('.')
        if len(parts) != 4:
            return False

        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return False

        return True
    except (ValueError, AttributeError):
        return False


def validate_fingerprint_data(frontend_data: Dict) -> Dict[str, Any]:
    """
    Validate and sanitize frontend fingerprint data.
    
    Args:
        frontend_data: Raw frontend fingerprint data
        
    Returns:
        Validated and sanitized fingerprint data
        
    Raises:
        ValueError: If required data is missing or invalid
    """
    if not isinstance(frontend_data, dict):
        raise ValueError("Frontend data must be a dictionary")

    validated = {}

    # Screen resolution (format: "1920x1080")
    if 'screen_resolution' in frontend_data:
        resolution = frontend_data['screen_resolution']
        if isinstance(resolution, str) and 'x' in resolution:
            try:
                width, height = resolution.split('x')
                if 100 <= int(width) <= 8000 and 100 <= int(height) <= 8000:
                    validated['screen_resolution'] = resolution
            except (ValueError, AttributeError):
                pass

    # Timezone offset (minutes from UTC)
    if 'timezone_offset' in frontend_data:
        offset = frontend_data['timezone_offset']
        if isinstance(offset, (int, float)) and -720 <= offset <= 720:  # ±12 hours
            validated['timezone_offset'] = int(offset)

    # Color depth (bits per pixel)
    if 'color_depth' in frontend_data:
        depth = frontend_data['color_depth']
        if isinstance(depth, int) and depth in [1, 4, 8, 15, 16, 24, 32]:
            validated['color_depth'] = depth

    # Platform string
    if 'platform' in frontend_data:
        platform = frontend_data['platform']
        if isinstance(platform, str) and 1 <= len(platform) <= 100:
            validated['platform'] = platform[:100]  # Truncate if too long

    # Language
    if 'language' in frontend_data:
        language = frontend_data['language']
        if isinstance(language, str) and 1 <= len(language) <= 20:
            validated['language'] = language[:20]

    # Boolean flags
    for bool_field in ['cookie_enabled', 'touch_support']:
        if bool_field in frontend_data:
            value = frontend_data[bool_field]
            if isinstance(value, bool):
                validated[bool_field] = value

    # Fingerprint hashes (for canvas, webgl)
    for hash_field in ['canvas_fingerprint', 'webgl_fingerprint']:
        if hash_field in frontend_data:
            value = frontend_data[hash_field]
            if isinstance(value, str) and 10 <= len(value) <= 200:
                validated[hash_field] = value[:200]

    # Hardware specs (integers with reasonable bounds)
    if 'hardware_concurrency' in frontend_data:
        cores = frontend_data['hardware_concurrency']
        if isinstance(cores, int) and 1 <= cores <= 256:
            validated['hardware_concurrency'] = cores

    if 'device_memory' in frontend_data:
        memory = frontend_data['device_memory']
        if isinstance(memory, (int, float)) and 0.25 <= memory <= 512:
            validated['device_memory'] = float(memory)

    if not validated:
        raise ValueError("No valid fingerprint components found")

    return validated


def log_fingerprint_generation(fingerprint: str, request: Request, components_count: int):
    """
    Log fingerprint generation for debugging and monitoring.
    
    Args:
        fingerprint: Generated fingerprint hash
        request: Original request
        components_count: Number of components used
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get('user-agent', 'Unknown')

    logger.info(
        f"Device fingerprint generated: {fingerprint[:16]}... "
        f"(components: {components_count}, IP: {client_ip or 'Unknown'}, "
        f"UA: {user_agent[:50]}{'...' if len(user_agent) > 50 else ''})"
    )


def create_fallback_fingerprint(request: Request) -> str:
    """
    Create a basic fingerprint when frontend data is unavailable.
    Uses only HTTP headers and IP subnet.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Fallback fingerprint hash
    """
    logger.warning("Creating fallback fingerprint - frontend data not available")

    return generate_device_fingerprint(request, frontend_data=None)
