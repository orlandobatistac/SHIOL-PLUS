import pytest
from fastapi.testclient import TestClient
from src.api import app
from src.database import create_user, get_user_by_id, delete_user_account

client = TestClient(app)


@pytest.fixture
def admin_session(scope="function"):
    """Login as admin and return session cookies"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "login": "admin@shiolplus.com",
            "password": "Admin123!",
            "remember_me": False
        }
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    return response.cookies


@pytest.fixture
def test_user(scope="function"):
    """Create a test user for admin operations"""
    email = "testuser_admin@test.com"
    username = "testuser_admin"
    password = "TestPassword123!"
    
    # Create user
    user_id = create_user(email, username, password)
    assert user_id is not None
    
    yield {"id": user_id, "email": email, "username": username}
    
    # Cleanup - delete test user if it still exists
    try:
        delete_user_account(user_id)
    except:
        pass  # User might have been deleted by test


def test_list_users_admin(admin_session):
    """Test that admin can list all users"""
    response = client.get("/api/v1/admin/users", cookies=admin_session)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0
    
    # Check user structure
    first_user = response.json()[0]
    assert "id" in first_user
    assert "username" in first_user
    assert "email" in first_user
    assert "is_admin" in first_user
    assert "premium_until" in first_user
    assert "created_at" in first_user


def test_list_users_non_admin():
    """Test that non-admin users cannot list users"""
    # Create a new client instance without any cookies
    from fastapi.testclient import TestClient
    from src.api import app
    fresh_client = TestClient(app)
    
    response = fresh_client.get("/api/v1/admin/users")
    assert response.status_code == 401


def test_list_users_regular_user():
    """Test that regular logged-in users cannot access admin endpoints"""
    # Create and login as regular user
    email = "regularuser@test.com"
    username = "regularuser"
    password = "RegularPass123!"
    
    create_user(email, username, password)
    
    login_response = client.post(
        "/api/v1/auth/login",
        json={"login": email, "password": password, "remember_me": False}
    )
    assert login_response.status_code == 200
    
    # Try to access admin endpoint
    response = client.get("/api/v1/admin/users", cookies=login_response.cookies)
    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]
    
    # Cleanup
    user_data = login_response.json()["user"]
    delete_user_account(user_data["id"])


def test_reset_password_success(admin_session, test_user):
    """Test successful password reset"""
    response = client.post(
        f"/api/v1/admin/users/{test_user['id']}/reset-password",
        cookies=admin_session
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "temp_password" in data
    assert len(data["temp_password"]) > 8


def test_reset_password_invalid_user(admin_session):
    """Test password reset for non-existent user"""
    response = client.post(
        "/api/v1/admin/users/999999/reset-password",
        cookies=admin_session
    )
    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


def test_delete_user_success(admin_session, test_user):
    """Test successful user deletion"""
    response = client.delete(
        f"/api/v1/admin/users/{test_user['id']}",
        cookies=admin_session
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Verify user was deleted
    user = get_user_by_id(test_user['id'])
    assert user is None


def test_delete_user_self(admin_session):
    """Test that admin cannot delete their own account"""
    # Admin user ID is 1
    response = client.delete("/api/v1/admin/users/1", cookies=admin_session)
    assert response.status_code == 403
    assert "cannot delete own account" in response.json()["detail"]


def test_delete_user_invalid(admin_session):
    """Test deleting non-existent user"""
    response = client.delete("/api/v1/admin/users/999999", cookies=admin_session)
    assert response.status_code == 404


def test_toggle_premium_activate(admin_session, test_user):
    """Test activating premium for a user"""
    response = client.put(
        f"/api/v1/admin/users/{test_user['id']}/premium",
        cookies=admin_session
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["premium_status"] == "active"
    
    # Verify premium was activated
    user = get_user_by_id(test_user['id'])
    assert user["is_premium"] == 1


def test_toggle_premium_deactivate(admin_session, test_user):
    """Test deactivating premium for a user"""
    # First activate premium
    client.put(f"/api/v1/admin/users/{test_user['id']}/premium", cookies=admin_session)
    
    # Then deactivate
    response = client.put(
        f"/api/v1/admin/users/{test_user['id']}/premium",
        cookies=admin_session
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["premium_status"] == "inactive"
    
    # Verify premium was deactivated
    user = get_user_by_id(test_user['id'])
    assert user["is_premium"] == 0


def test_toggle_premium_invalid_user(admin_session):
    """Test toggling premium for non-existent user"""
    response = client.put("/api/v1/admin/users/999999/premium", cookies=admin_session)
    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


def test_all_endpoints_require_admin(test_user):
    """Test that all admin endpoints require authentication"""
    # Create a new client instance without any cookies
    from fastapi.testclient import TestClient
    from src.api import app
    fresh_client = TestClient(app)
    
    endpoints = [
        ("GET", "/api/v1/admin/users"),
        ("POST", f"/api/v1/admin/users/{test_user['id']}/reset-password"),
        ("DELETE", f"/api/v1/admin/users/{test_user['id']}"),
        ("PUT", f"/api/v1/admin/users/{test_user['id']}/premium"),
    ]
    
    for method, url in endpoints:
        response = fresh_client.request(method, url)
        assert response.status_code == 401, f"{method} {url} should require authentication"
