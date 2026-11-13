"""Clean page URLs must work; the legacy .html routes must keep working."""
from __future__ import annotations

from fastapi.testclient import TestClient

from synapse.api.app import app


def test_clean_page_urls_render(monkeypatch, tmp_path):
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKSPACE_ROOT", str(tmp_path))
    with TestClient(app) as client:
        for page in ("providers", "agents", "settings"):
            response = client.get(f"/{page}")
            assert response.status_code == 200, page
            assert "<html" in response.text.lower()
        assert client.get("/dashboard").status_code == 200
        # Bookmark compatibility: old URLs still render.
        assert client.get("/providers.html").status_code == 200
        # Unknown pages are still 404, not a catch-all.
        assert client.get("/nope.html").status_code == 404
