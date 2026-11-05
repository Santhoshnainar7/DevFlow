"""
Tests for system endpoints (/health and /).
"""


def test_health_check_endpoint(client, test_settings):
    """Verify /health returns 200 OK and matches the HealthResponse schema."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == test_settings.PROJECT_NAME
    assert data["version"] == test_settings.VERSION
    assert data["environment"] == test_settings.ENVIRONMENT
    assert "timestamp" in data


def test_root_endpoint(client, test_settings):
    """Verify root endpoint returns operational metadata."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == test_settings.PROJECT_NAME
    assert data["status"] == "operational"
    assert data["docs_url"] == "/docs"

