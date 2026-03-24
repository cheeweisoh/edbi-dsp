import uuid

import pytest
from httpx import AsyncClient


BASE = "/api/v1/datasets"


async def _create_dataset(client: AsyncClient, name: str = "Sales Data") -> dict:
    resp = await client.post(BASE + "/", json={"name": name, "description": "desc"})
    assert resp.status_code == 201
    return resp.json()


class TestCreateDataset:
    async def test_creates_and_returns_201(self, client: AsyncClient) -> None:
        resp = await client.post(BASE + "/", json={"name": "My Dataset", "description": "d"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "My Dataset"
        assert "id" in body
        assert body["is_active"] is True

    async def test_duplicate_name_returns_409(self, client: AsyncClient) -> None:
        await _create_dataset(client, name="Unique")
        resp = await client.post(BASE + "/", json={"name": "Unique"})
        assert resp.status_code == 409

    async def test_missing_name_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post(BASE + "/", json={"description": "no name"})
        assert resp.status_code == 422


class TestListDatasets:
    async def test_returns_empty_list_initially(self, client: AsyncClient) -> None:
        resp = await client.get(BASE + "/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_created_datasets(self, client: AsyncClient) -> None:
        await _create_dataset(client, "DS1")
        await _create_dataset(client, "DS2")
        resp = await client.get(BASE + "/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        first = resp.json()[0]
        assert "table_name" in first
        assert "display_name" in first
        assert first["name"] == first["display_name"]

    async def test_deleted_dataset_excluded(self, client: AsyncClient) -> None:
        ds = await _create_dataset(client, "ToDelete")
        await client.delete(f"{BASE}/{ds['id']}")
        resp = await client.get(BASE + "/")
        assert all(d["id"] != ds["id"] for d in resp.json())


class TestGetDataset:
    async def test_returns_existing_dataset(self, client: AsyncClient) -> None:
        ds = await _create_dataset(client)
        resp = await client.get(f"{BASE}/{ds['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == ds["id"]

    async def test_unknown_id_returns_404(self, client: AsyncClient) -> None:
        resp = await client.get(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestUpdateDataset:
    async def test_owner_can_update_name(self, client: AsyncClient) -> None:
        ds = await _create_dataset(client)
        resp = await client.put(f"{BASE}/{ds['id']}", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    async def test_rename_to_taken_name_returns_409(self, client: AsyncClient) -> None:
        await _create_dataset(client, "First")
        ds2 = await _create_dataset(client, "Second")
        resp = await client.put(f"{BASE}/{ds2['id']}", json={"name": "First"})
        assert resp.status_code == 409

    async def test_unknown_id_returns_404(self, client: AsyncClient) -> None:
        resp = await client.put(f"{BASE}/{uuid.uuid4()}", json={"name": "X"})
        assert resp.status_code == 404


class TestDeleteDataset:
    async def test_owner_can_soft_delete(self, client: AsyncClient) -> None:
        ds = await _create_dataset(client)
        resp = await client.delete(f"{BASE}/{ds['id']}")
        assert resp.status_code == 204

    async def test_deleted_dataset_not_found(self, client: AsyncClient) -> None:
        ds = await _create_dataset(client)
        await client.delete(f"{BASE}/{ds['id']}")
        resp = await client.get(f"{BASE}/{ds['id']}")
        assert resp.status_code == 404

    async def test_unknown_id_returns_404(self, client: AsyncClient) -> None:
        resp = await client.delete(f"{BASE}/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestMetadata:
    async def test_get_metadata_no_metadata_returns_404(self, client: AsyncClient) -> None:
        ds = await _create_dataset(client)
        resp = await client.get(f"{BASE}/{ds['id']}/metadata")
        assert resp.status_code == 404

    async def test_upsert_creates_metadata(self, client: AsyncClient) -> None:
        ds = await _create_dataset(client)
        payload = {"schema_name": "public", "table_name": "sales", "row_count": 1000}
        resp = await client.put(f"{BASE}/{ds['id']}/metadata", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["schema_name"] == "public"
        assert body["row_count"] == 1000
        assert body["dataset_id"] == ds["id"]

    async def test_upsert_updates_existing_metadata(self, client: AsyncClient) -> None:
        ds = await _create_dataset(client)
        await client.put(f"{BASE}/{ds['id']}/metadata", json={"schema_name": "old"})
        resp = await client.put(f"{BASE}/{ds['id']}/metadata", json={"schema_name": "new"})
        assert resp.status_code == 200
        assert resp.json()["schema_name"] == "new"

    async def test_get_metadata_after_upsert(self, client: AsyncClient) -> None:
        ds = await _create_dataset(client)
        await client.put(f"{BASE}/{ds['id']}/metadata", json={"table_name": "tbl"})
        resp = await client.get(f"{BASE}/{ds['id']}/metadata")
        assert resp.status_code == 200
        assert resp.json()["table_name"] == "tbl"

    async def test_metadata_for_unknown_dataset_returns_404(self, client: AsyncClient) -> None:
        resp = await client.get(f"{BASE}/{uuid.uuid4()}/metadata")
        assert resp.status_code == 404
