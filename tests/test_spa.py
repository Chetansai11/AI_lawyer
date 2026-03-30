from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.main import app


def test_root_serves_spa() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Intake Auditor" in response.text


def test_ui_bundle_reachable() -> None:
    """Vite build uses /assets/*.js; default stack serves /static/App.jsx."""
    client = TestClient(app)
    root = client.get("/")
    assert root.status_code == 200
    match = re.search(r'src="(/assets/[^"]+\.js)"', root.text)
    if match:
        assert client.get(match.group(1)).status_code == 200
    else:
        jsx = client.get("/static/App.jsx")
        assert jsx.status_code == 200
        assert "AI Intake Auditor" in jsx.text or "App" in jsx.text
