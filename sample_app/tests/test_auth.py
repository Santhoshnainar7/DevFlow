"""
Automated Pytest test suite for the DevFlow sample login application.

Covers:
  - Successful login (200)
  - Wrong password (401)
  - Unknown username (404)
  - Empty username (422)
  - Empty password (422)
  - Missing request body (422)
  - Response schema conformance (200 — both fields present)
"""

LOGIN_URL = "/api/v1/login"


# ---------------------------------------------------------------------------
# 1. Successful login
# ---------------------------------------------------------------------------
def test_login_success(client, valid_credentials):
    response = client.post(LOGIN_URL, json=valid_credentials)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["access_token"] != ""


# ---------------------------------------------------------------------------
# 2. Wrong password → 401 Unauthorized
# ---------------------------------------------------------------------------
def test_login_wrong_password(client):
    response = client.post(
        LOGIN_URL,
        json={"username": "alice", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "detail" in response.json()


# ---------------------------------------------------------------------------
# 3. Unknown username → 404 Not Found
# ---------------------------------------------------------------------------
def test_login_unknown_user(client):
    response = client.post(
        LOGIN_URL,
        json={"username": "ghost", "password": "doesntmatter"},
    )
    assert response.status_code == 404
    assert "detail" in response.json()


# ---------------------------------------------------------------------------
# 4. Empty username → 422 Unprocessable Entity
# ---------------------------------------------------------------------------
def test_login_empty_username(client):
    response = client.post(
        LOGIN_URL,
        json={"username": "", "password": "password123"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 5. Empty password → 422 Unprocessable Entity
# ---------------------------------------------------------------------------
def test_login_empty_password(client):
    response = client.post(
        LOGIN_URL,
        json={"username": "alice", "password": ""},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 6. Missing request body → 422 Unprocessable Entity
# ---------------------------------------------------------------------------
def test_login_missing_body(client):
    response = client.post(LOGIN_URL)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 7. Response schema — both token fields must be present
# ---------------------------------------------------------------------------
def test_login_response_schema(client, valid_credentials):
    response = client.post(LOGIN_URL, json=valid_credentials)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data, "access_token missing from response"
    assert "token_type" in data, "token_type missing from response"
    assert data["token_type"] == "bearer"

