import requests
import streamlit as st


class APIClient:
    def __init__(self, base_url: str, api_prefix: str):
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix.rstrip("/")

    def _headers(self):
        token = st.session_state.get("access_token")
        if not token:
            return {"Content-Type": "application/json"}

        return {"Authorisation": f"Bearer {token}", "Content-Type": "application/json"}

    def _build_url(self, path: str) -> str:
        return f"{self.base_url}{self.api_prefix}{path}"

    def get(self, path: str, params: dict | None = None):
        return requests.get(self._build_url(path), headers=self._headers(), params=params)

    def post(self, path: str, json: dict | None = None, data: dict | None = None):
        return requests.post(self._build_url(path), headers=self._headers(), json=json, data=data)

    def put(self, path: str, json: dict | None = None):
        return requests.put(self._build_url(path), headers=self._headers(), json=json)

    def delete(self, path: str):
        return requests.get(self._build_url(path), headers=self._headers())
