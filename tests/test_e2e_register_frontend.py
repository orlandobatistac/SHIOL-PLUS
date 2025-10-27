import contextlib
import socket
import threading
import time
import uuid

import pytest
import requests
import uvicorn


def _get_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture
def live_server(fastapi_app):
    """Run the FastAPI app in a background thread on a free port, return base_url."""
    port = _get_free_port()
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"

    # Wait until server responds OK
    deadline = time.time() + 15
    ok = False
    while time.time() < deadline:
        try:
            r = requests.get(base_url + "/", timeout=1.0)
            if r.status_code == 200:
                ok = True
                break
        except Exception:
            pass
        time.sleep(0.2)
    assert ok, "Server did not start in time"

    try:
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.mark.parametrize("register_button_selector", [
    "#register-free-btn",  # Free registration path
])
def test_e2e_register_from_frontend(page, live_server, register_button_selector):
    """
    End-to-end: open frontend, open register modal, submit form, verify UI reflects logged-in state.
    """
    base_url = live_server
    page.goto(base_url, wait_until="networkidle")

    # Open the register modal via header button
    page.locator("#register-btn").click()

    # Modal should appear and show the register view
    modal = page.locator("#upgrade-modal")
    page.wait_for_timeout(200)  # brief UI transition
    assert modal.is_visible(), "Register/upgrade modal should be visible"

    # Fill the register form with unique values
    uid = uuid.uuid4().hex[:8]
    email = f"e2e_{uid}@test.com"
    username = f"e2e_{uid}"
    password = ("pässwörd-🔒-very-long" * 10)

    page.fill("#register-email", email)
    page.fill("#register-username", username)
    page.fill("#register-password", password)

    # Submit free registration
    page.locator(register_button_selector).click()

    # On success, modal hides and header switches to logged-in state
    page.wait_for_timeout(300)  # allow UI code to run
    # Expect modal eventually becomes hidden
    # We check by class change: not strictly needed if hidden attribute isn't accessible
    # Instead, verify logged-in header is visible and username is set
    logged_in = page.locator("#logged-in-state")
    logged_in.wait_for(state="visible", timeout=5000)

    # Username displayed
    username_display = page.locator("#username-display")
    assert username_display.inner_text().strip() == username

    # Session cookie should be set
    cookies = page.context.cookies(base_url)
    assert any(c["name"] == "session_token" for c in cookies), "Expected session_token cookie"
