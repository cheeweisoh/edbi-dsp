from services.base import APIClient


class PermissionService:
    def __init__(self, client: APIClient):
        self.client = client

    def list(self, dataset_id: str):
        return self.client.get(f"/datasets/{dataset_id}/permissions")

    def grant(self, dataset_id: str, payload: dict):
        return self.client.post(f"/datasets/{dataset_id}/permissions", json=payload)

    def revoke(self, dataset_id: str, permission_id: str):
        return self.client.delete(f"/datasets/{dataset_id}/permissions/{permission_id}")
