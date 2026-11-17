from fastapi.testclient import TestClient

from kontho.config import get_settings
from kontho.main import create_app


def test_api_keys_enforced(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "auth_enabled", True)
    monkeypatch.setattr(s, "admin_key", "admin-secret")
    c = TestClient(create_app())
    assert c.get("/v1/voices").status_code == 401
    assert c.get("/v1/voices", headers={"xi-api-key": "wrong"}).status_code == 401
    created = c.post("/v1/api-keys", json={"name": "ci"}, headers={"xi-api-key": "admin-secret"}).json()
    key = created["api_key"]
    assert c.get("/v1/voices", headers={"xi-api-key": key}).status_code == 200
    assert c.get("/v1/voices", headers={"Authorization": f"Bearer {key}"}).status_code == 200
    assert c.delete(f"/v1/api-keys/{created['id']}", headers={"xi-api-key": key}).status_code == 200
    assert c.get("/v1/voices", headers={"xi-api-key": key}).status_code == 401
    assert c.get("/health").status_code == 200
