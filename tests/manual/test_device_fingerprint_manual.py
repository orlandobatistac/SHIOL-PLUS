"""
Manual test for device fingerprint consistency.
Extracted from src/device_fingerprint.py to keep production code clean.

Run with: python tests/manual/test_device_fingerprint_manual.py
"""


def test_fingerprint_consistency():
    """
    Test fingerprint generation consistency.
    """
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    client = TestClient(app)

    # Mock request data
    test_frontend_data = {
        'screen_resolution': '1920x1080',
        'timezone_offset': -300,
        'color_depth': 24,
        'platform': 'MacIntel',
        'language': 'en-US',
        'cookie_enabled': True,
        'canvas_fingerprint': 'test_canvas_hash_123',
        'webgl_fingerprint': 'test_webgl_hash_456',
        'touch_support': False,
        'hardware_concurrency': 8,
        'device_memory': 8.0
    }

    # Test consistency
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'accept-language': 'en-US,en;q=0.9',
        'accept-encoding': 'gzip, deflate, br'
    }

    with client:
        _ = client.get("/", headers=headers)  # response1
        _ = client.get("/", headers=headers)  # response2

        # Create mock request objects (this is simplified for testing)
        # In practice, you would use actual Request objects
        print("Fingerprint consistency test would require actual Request objects")
        return True


if __name__ == "__main__":
    """Run tests when executed directly."""
    print("Testing fingerprint validation...")
    test_fingerprint_consistency()
    print("Test completed!")
