"""Dashboard API tests."""

from app.agent.service import _agents


async def test_dashboard_overview(client):
    """Test dashboard overview."""
    _agents.clear()
    resp = await client.get("/api/v1/dashboard/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert data["agents"]["total"] == 0


async def test_agent_summary(client):
    """Test agent summary."""
    _agents.clear()
    resp = await client.get("/api/v1/dashboard/agents/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["online"] == 0
