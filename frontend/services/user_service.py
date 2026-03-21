from services.base import APIClient


class UserService:
    def __init__(self, client: APIClient):
        self.client = client

    def list(self):
        return self.client.get("/users")
