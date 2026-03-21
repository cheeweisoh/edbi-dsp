from services.base import APIClient


class QueryService:
    def __init__(self, client: APIClient):
        self.client = client

    def query(self, dataset_id: str, limit: int | None = 10, offset: int | None = 0):
        params = {"limit": limit, "offset": offset}

        return self.client.get(f"/datasets/{dataset_id}/data", params=params)

    def query_nl(self, nl_query: str, max_tokens: int = 500):
        payload = {"nl_query": nl_query, "max_new_tokens": max_tokens}
        return self.client.post("/datasets/gensql", json=payload)

    def query_sql(self, sql: str, limit: int | None = 500, offset: int = 0):
        payload = {"sql": sql, "limit": limit, "offset": offset}
        return self.client.post("/datasets/query", json=payload)
