from services.base import APIClient


class GroupService:
    def __init__(self, client: APIClient):
        self.client = client

    def list(self):
        return self.client.get("/groups")

    def create(self, payload: dict):
        return self.client.post("/groups", json=payload)

    def get(self, group_id: str):
        return self.client.get(f"/groups/{group_id}")

    def list_members(self, group_id: str):
        return self.client.get(f"/groups/{group_id}/members")

    def add_member(self, group_id: str, user_id: str):
        return self.client.put(f"/groups/{group_id}/members/{user_id}")

    def remove_member(self, group_id: str, user_id: str):
        return self.client.delete(f"/groups/{group_id}/members/{user_id}")
