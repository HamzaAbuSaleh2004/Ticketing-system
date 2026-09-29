"""POST /internal/sweeps: Cloud Scheduler's HTTP trigger for the sweeps that
otherwise only run inside the worker's loop. The OIDC verifier itself
(google.oauth2.id_token.verify_oauth2_token) is mocked — it's Google's code,
not ours — but the audience/email checks around it are ours and are tested
for real: a validly-signed token for the wrong audience or the wrong caller
must not pass."""

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _sweep_settings(monkeypatch):
    monkeypatch.setattr(get_settings(), "SWEEP_AUDIENCE", "https://helpdesk.example.com")
    monkeypatch.setattr(get_settings(), "SWEEP_INVOKER_EMAIL", "scheduler@x.iam.gserviceaccount.com")


def _mock_verify(monkeypatch, claims=None, error=None):
    def fake_verify(token, request, audience=None):
        assert audience == get_settings().SWEEP_AUDIENCE
        if error is not None:
            raise error
        return claims

    monkeypatch.setattr("google.oauth2.id_token.verify_oauth2_token", fake_verify)


async def test_missing_token_is_401(client):
    resp = await client.post("/internal/sweeps")
    assert resp.status_code == 401


async def test_malformed_header_is_401(client):
    resp = await client.post("/internal/sweeps", headers={"Authorization": "not-a-bearer-token"})
    assert resp.status_code == 401


async def test_a_token_google_rejects_is_401(client, monkeypatch):
    _mock_verify(monkeypatch, error=ValueError("Token expired"))
    resp = await client.post("/internal/sweeps", headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 401


async def test_a_transport_failure_verifying_the_token_is_503_not_401(client, monkeypatch):
    from google.auth import exceptions as google_exceptions

    _mock_verify(monkeypatch, error=google_exceptions.TransportError("network blip"))
    resp = await client.post("/internal/sweeps", headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 503


async def test_wrong_caller_email_is_403(client, monkeypatch):
    _mock_verify(monkeypatch, claims={"email": "someone-else@x.iam.gserviceaccount.com", "email_verified": True})
    resp = await client.post("/internal/sweeps", headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 403


async def test_valid_token_from_the_right_caller_runs_the_sweeps(client, monkeypatch):
    _mock_verify(monkeypatch, claims={"email": "scheduler@x.iam.gserviceaccount.com", "email_verified": True})
    resp = await client.post("/internal/sweeps", headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"sla-risk", "auto-close", "prune-login-attempts"}
    assert all(isinstance(v, list) for v in body.values())
