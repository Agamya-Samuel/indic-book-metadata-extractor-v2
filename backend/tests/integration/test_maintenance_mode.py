"""Maintenance mode enforcement and the admin toggle."""

from __future__ import annotations

import pytest

from app.services import maintenance_service as ms


@pytest.fixture(autouse=True)
def _reset_state():
    ms.set_state_for_test({"enabled": False})
    yield
    ms.set_state_for_test({"enabled": False})


class TestPublicStatus:
    async def test_reports_disabled_by_default(self, anon_client) -> None:
        response = await anon_client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["maintenance"]["enabled"] is False
        assert response.headers.get("cache-control") == "no-store"

    async def test_reports_enabled_state(self, anon_client) -> None:
        ms.set_state_for_test({"enabled": True, "message": "Upgrading the database"})

        response = await anon_client.get("/api/status")

        assert response.status_code == 200
        maintenance = response.json()["maintenance"]
        assert maintenance["enabled"] is True
        assert maintenance["message"] == "Upgrading the database"


class TestEnforcement:
    async def test_blocks_regular_users(self, client) -> None:
        ms.set_state_for_test({"enabled": True, "message": "Back shortly"})

        response = await client.get("/api/dashboard/summary")

        assert response.status_code == 503
        data = response.json()
        assert data["type"] == "maintenance"
        assert data["detail"] == "Back shortly"

    async def test_admins_bypass_the_block(self, admin_client) -> None:
        ms.set_state_for_test({"enabled": True, "message": "Back shortly"})

        response = await admin_client.get("/api/dashboard/summary")

        assert response.status_code == 200

    async def test_health_and_status_stay_reachable(self, anon_client) -> None:
        ms.set_state_for_test({"enabled": True})

        assert (await anon_client.get("/api/health")).status_code == 200
        assert (await anon_client.get("/api/status")).status_code == 200

    async def test_disabled_state_passes_through(self, client) -> None:
        response = await client.get("/api/dashboard/summary")
        assert response.status_code == 200


class TestAdminToggle:
    async def test_admin_can_enable_and_disable(self, client, admin_client, db_session) -> None:
        enabled = await admin_client.put(
            "/api/admin/maintenance",
            json={"enabled": True, "message": "Upgrading the database"},
        )
        assert enabled.status_code == 200
        body = enabled.json()
        assert body["enabled"] is True
        assert body["message"] == "Upgrading the database"
        assert body["updated_by"] == "Admin User"

        assert (await client.get("/api/dashboard/summary")).status_code == 503

        disabled = await admin_client.put("/api/admin/maintenance", json={"enabled": False})
        assert disabled.status_code == 200
        assert (await client.get("/api/dashboard/summary")).status_code == 200

    async def test_regular_users_cannot_toggle(self, client) -> None:
        response = await client.put("/api/admin/maintenance", json={"enabled": True})
        assert response.status_code == 403

    async def test_admin_status_endpoint(self, admin_client) -> None:
        await admin_client.put("/api/admin/maintenance", json={"enabled": True, "message": "Patch"})

        response = await admin_client.get("/api/admin/maintenance")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["message"] == "Patch"
        assert data["updated_by"] == "Admin User"
