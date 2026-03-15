"""Agent management API tests."""

from app.agent.service import _agents


async def test_register_agent(client):
    """Test agent registration."""
    _agents.clear()
    resp = await client.post(
        "/api/v1/agent/register",
        json={"host": "192.168.1.100", "port": 8600, "name": "test-server"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["host"] == "192.168.1.100"
    assert data["port"] == 8600
    assert data["name"] == "test-server"
    assert "id" in data


async def test_list_agents(client):
    """Test listing agents."""
    _agents.clear()
    # Register an agent first
    await client.post(
        "/api/v1/agent/register",
        json={"host": "192.168.1.100", "port": 8600},
    )

    resp = await client.get("/api/v1/agent/list")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1


async def test_unregister_agent(client):
    """Test agent unregistration."""
    _agents.clear()
    reg_resp = await client.post(
        "/api/v1/agent/register",
        json={"host": "192.168.1.100", "port": 8600},
    )
    agent_id = reg_resp.json()["id"]

    resp = await client.delete(f"/api/v1/agent/{agent_id}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/agent/{agent_id}")
    assert resp.status_code == 404


async def test_unregister_agent_not_found(client):
    """Test unregistering a non-existent agent."""
    _agents.clear()
    resp = await client.delete("/api/v1/agent/non-existent-id")
    assert resp.status_code == 404
