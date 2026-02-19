from services.base import APIClient


class QueryService:
    def __init__(self, client: APIClient):
        self.client = client

    def query(self, dataset_id: str, limit: int | None = 10, offset: int | None = 0):
        params = {"limit": limit, "offset": offset}

        return self.client.get(f"/datasets/{dataset_id}/data", params=params)
