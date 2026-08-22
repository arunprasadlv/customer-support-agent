"""Scaffold smoke test for the /health endpoint only.

Placeholder to satisfy aamad.config.yml testing.require_integration_tests
at setup time. Real integration tests (full InquiryFlow per hotel
scenario, sad.md §9) are @qa.eng's responsibility (*test-integration).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
