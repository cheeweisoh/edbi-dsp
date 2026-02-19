from services.base import APIClient


class DatasetService:
    def __init__(self, client: APIClient):
        self.client = APIClient(base_url="http://localhost:8000", api_prefix="/api/v1")

    def list(self):
        return self.client.get("/datasets")

    def create(self, name: str, description: str | None = None):
        json = {"name": name, "description": description}

        return self.client.post("/datasets", json=json)

    def get(self, dataset_id: str):
        return self.client.get(f"/datasets/{dataset_id}")

    def update(self, dataset_id: str, payload: dict):
        return self.client.put(f"/datasets/{dataset_id}", json=payload)

    def delete(self, dataset_id: str):
        return self.client.delete(f"/datasets/{dataset_id}")

    def get_metadata(self, dataset_id: str):
        return self.client.get(f"/datasets/{dataset_id}/metadata")

    def update_metadata(self, dataset_id: str, payload: dict):
        return self.client.put(f"/datasets/{dataset_id}/metadata", json=payload)

    def query(self, dataset_id: str, limit: int | None = 10, offset: int | None = 0):
        params = {"limit": limit, "offset": offset}

        return self.client.get(f"/datasets/{dataset_id}/data", params=params)
