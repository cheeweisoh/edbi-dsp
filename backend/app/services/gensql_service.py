import re
from typing import Any

import requests
from app.core.config import settings
from app.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.dataset_repo import DatasetRepository
from app.services.permission_service import PermissionService
from sqlalchemy.ext.asyncio import AsyncSession

FORBIDDEN_SQL_KEYWORDS = ["insert", "update", "delete", "drop", "alter", "truncate"]


class GenSQLService:
    def __init__(self, db: AsyncSession) -> None:
        self.dataset_repo = DatasetRepository(db)
        self.perm_svc = PermissionService(db)

    async def generate_sql(self, nl_query: str, current_user: User, max_new_tokens: int = 200) -> str:
        datasets = await self._list_queryable_datasets(current_user)
        schema_context = self._build_schema_context(datasets)
        prompt = self._build_prompt(nl_query, schema_context)

        raw_output = self._generate_with_ollama(prompt, max_new_tokens)

        sql = self._extract_sql(raw_output)
        if not self._is_safe_sql(sql):
            raise ForbiddenError("Unsafe SQL generated. Query blocked.")
        if not self._is_allowed_sql(sql, [dataset["name"] for dataset in datasets]):
            raise ForbiddenError("You are not allowed to access some tables in the query. Query blocked.")
        return sql

    @staticmethod
    def _generate_with_ollama(prompt: str, max_new_tokens: int) -> str:
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        endpoint = f"{base_url}/api/generate"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": max_new_tokens,
            },
        }
        try:
            response = requests.post(
                endpoint,
                json=payload,
                timeout=settings.OLLAMA_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise AppError(f"Failed to reach Ollama at {base_url}", 500) from exc

        if response.status_code != 200:
            detail = response.text
            try:
                body = response.json()
                detail = body.get("error", detail)
            except ValueError:
                pass
            raise AppError(f"Ollama generation failed: {detail}", 500)

        try:
            body = response.json()
        except ValueError as exc:
            raise AppError("Invalid JSON response from Ollama", 500) from exc

        generated = body.get("response")
        if not isinstance(generated, str) or not generated.strip():
            raise AppError("Ollama returned empty generation output", 500)
        return generated

    @staticmethod
    def _build_schema_context(datasets: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for dataset in datasets:
            metadata_json = dataset["metadata_json"]
            schema = metadata_json.get("schema", [])
            lines.extend(
                [
                    f"Table: {dataset['name']}",
                    f"Description: {metadata_json.get('description', '')}",
                    "Columns:",
                ]
            )
            for col in schema:
                if isinstance(col, dict):
                    lines.append(f"- {col.get('column', '')} ({col.get('type', '')}): {col.get('description', '')}")
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _build_prompt(nl_query: str, schema_context: str) -> str:
        prompt = f"""
        You are a senior data analyst. Convert the user's request into a valid SQL query.

        Rules:
        - Use ONLY the tables and columns provided.
        - Do NOT join additional tables beyond what is required for the user's query, even though more may be provided.
        - Use the minimal number of joins required (could be none).
        - Do NOT invent columns.
        - Do NOT use UPDATE, DELETE, INSERT, DROP, or ALTER.
        - Return ONLY SQL. No explanations.

        If there are no available tables for the user to query, return the statement: "null" instead

        Schema:
        {schema_context}

        User request:
        {nl_query}

        SQL:
        """
        return prompt.strip()

    @staticmethod
    def _extract_sql(sql: str) -> str:
        cleaned = sql.strip()
        cleaned = re.sub(r"^```sql", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

        return cleaned

    @staticmethod
    def _is_safe_sql(sql: str) -> bool:
        sql_lower = sql.lower()
        return not any(keyword in sql_lower for keyword in FORBIDDEN_SQL_KEYWORDS)

    @staticmethod
    def _is_allowed_sql(sql: str, allowed_tables: list[str]) -> bool:
        tables_in_sql = re.findall(r"(?:from|join)\s+([a-zA-Z0-9_]+)", sql, flags=re.IGNORECASE)
        normalized_allowed = {t.lower() for t in allowed_tables}
        return all(table.lower() in normalized_allowed for table in tables_in_sql)

    async def _list_queryable_datasets(self, current_user: User) -> list[dict[str, Any]]:
        if current_user.is_superuser:
            datasets = await self.dataset_repo.list_active()
        else:
            accessible_ids = await self.perm_svc.get_accessible_dataset_ids(current_user)
            datasets = await self.dataset_repo.list_accessible(current_user.id, accessible_ids)

        usable_datasets: list[dict[str, Any]] = []
        for dataset in datasets:
            dm = await self.dataset_repo.get_metadata(dataset.id)
            if dm is None or not isinstance(dm.metadata_json, dict):
                continue
            schema = dm.metadata_json.get("schema")
            if not isinstance(schema, list) or not schema:
                continue
            usable_datasets.append({"name": dataset.name, "metadata_json": dm.metadata_json})

        if not usable_datasets:
            raise NotFoundError("No dataset metadata available for query generation")
        return usable_datasets
