from unittest.mock import AsyncMock

from httpx import AsyncClient

from app.exceptions import ForbiddenError, NotFoundError
from app.services.querynl_service import QueryNLService

BASE = "/api/v1/datasets"


async def _create_dataset(client: AsyncClient, name: str = "Sales Data") -> dict:
    resp = await client.post(BASE + "/", json={"name": name, "description": "desc"})
    assert resp.status_code == 201
    return resp.json()


class TestQueryNLEndpoint:
    async def test_returns_generated_sql(self, client: AsyncClient, monkeypatch) -> None:
        ds = await _create_dataset(client, "electricity_sales")
        await client.put(
            f"{BASE}/{ds['id']}/metadata",
            json={
                "metadata_json": {
                    "description": "Monthly electricity sales",
                    "schema": [{"column": "year", "type": "INT"}],
                }
            },
        )

        mocked_generate_sql = AsyncMock(return_value="SELECT year FROM electricity_sales")
        monkeypatch.setattr(QueryNLService, "generate_sql", mocked_generate_sql)

        resp = await client.post(
            f"{BASE}/{ds['id']}/querynl",
            json={"nl_query": "show years", "max_new_tokens": 128},
        )

        assert resp.status_code == 200
        assert resp.json() == {"sql": "SELECT year FROM electricity_sales"}
        mocked_generate_sql.assert_awaited_once()

    async def test_returns_404_when_service_raises_not_found(
        self, client: AsyncClient, monkeypatch
    ) -> None:
        ds = await _create_dataset(client)
        monkeypatch.setattr(
            QueryNLService,
            "generate_sql",
            AsyncMock(side_effect=NotFoundError("Dataset missing")),
        )

        resp = await client.post(f"{BASE}/{ds['id']}/querynl", json={"nl_query": "show years"})

        assert resp.status_code == 404
        assert resp.json() == {"detail": "Dataset missing"}

    async def test_returns_403_when_service_raises_forbidden(
        self, client: AsyncClient, monkeypatch
    ) -> None:
        ds = await _create_dataset(client)
        monkeypatch.setattr(
            QueryNLService,
            "generate_sql",
            AsyncMock(side_effect=ForbiddenError("Blocked")),
        )

        resp = await client.post(f"{BASE}/{ds['id']}/querynl", json={"nl_query": "drop table"})

        assert resp.status_code == 403
        assert resp.json() == {"detail": "Blocked"}
