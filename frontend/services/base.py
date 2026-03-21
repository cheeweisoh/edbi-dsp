import requests
import streamlit as st


class APIClient:
    def __init__(self, base_url: str, api_prefix: str):
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix.rstrip("/")

    def _headers(self, content_type="application/json"):
        headers = {}
        token = st.session_state.get("access_token")

        if token:
            headers["Authorization"] = f"Bearer {token}"

        if content_type:
            headers["Content-Type"] = content_type

        return headers

    def _build_url(self, path: str) -> str:
        return f"{self.base_url}{self.api_prefix}{path}"

    def get(self, path: str, params: dict | None = None):
        return requests.get(self._build_url(path), headers=self._headers(), params=params)

    def post(self, path: str, json: dict | None = None, data: dict | None = None):
        return requests.post(self._build_url(path), headers=self._headers(), json=json, data=data)

    def post_form(self, path: str, data: dict):
        return requests.post(self._build_url(path), headers=self._headers(content_type="application/x-www-form-urlencoded"), data=data)

    def put(self, path: str, json: dict | None = None):
        return requests.put(self._build_url(path), headers=self._headers(), json=json)

    def delete(self, path: str):
        return requests.delete(self._build_url(path), headers=self._headers())
