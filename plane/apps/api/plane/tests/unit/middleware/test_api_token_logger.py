from plane.middleware.logger import api_token_fingerprint, redacted_headers


def test_api_token_fingerprint_is_stable_without_exposing_secret():
    token = "plane_api_super_secret"

    fingerprint = api_token_fingerprint(token)

    assert fingerprint == api_token_fingerprint(token)
    assert fingerprint.startswith("sha256:")
    assert token not in fingerprint


def test_redacted_headers_removes_authentication_material():
    headers = {
        "X-Api-Key": "plane_api_super_secret",
        "Authorization": "Bearer secret",
        "Cookie": "session-id=secret",
        "Content-Type": "application/json",
    }

    result = redacted_headers(headers)

    assert "plane_api_super_secret" not in result
    assert "Bearer secret" not in result
    assert "session-id=secret" not in result
    assert result.count("[REDACTED]") == 3
    assert "application/json" in result
