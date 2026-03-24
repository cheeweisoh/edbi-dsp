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
TABLE_REF_PATTERN = r"(?:`[^`]+`|[a-zA-Z0-9_.]+)"
SQL_TABLE_CLAUSE_PATTERN = r"(?i)\b(from|join)\s+(.+?)(?=\s+(?:join|on|where|group|order|limit|offset|having|union)\b|,|\)|$)"


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
        alias_to_table = self._build_alias_to_table_map(datasets)
        sql = self._qualify_sql_tables(sql, alias_to_table)
        if not self._is_safe_sql(sql):
            raise ForbiddenError("Unsafe SQL generated. Query blocked.")
        if not current_user.is_superuser and not self._is_allowed_sql(sql, [dataset["table_ref"] for dataset in datasets]):
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
                    f"Table: {dataset['table_ref']}",
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
        tables_in_sql = re.findall(rf"(?:from|join)\s+({TABLE_REF_PATTERN})", sql, flags=re.IGNORECASE)
        normalized_allowed = {t.replace("`", "").lower() for t in allowed_tables}
        return all(table.replace("`", "").lower() in normalized_allowed for table in tables_in_sql)

    @staticmethod
    def _normalize_identifier(value: str) -> str:
        return value.replace("`", "").replace('"', "").strip().lower()

    @staticmethod
    def _qualify_with_env(table_name: str) -> str:
        catalog = settings.DATABRICKS_UC_CATALOG
        schema = settings.DATABRICKS_UC_SCHEMA
        if catalog and schema:
            return f"{catalog}.{schema}.{table_name}"
        if schema:
            return f"{schema}.{table_name}"
        return table_name

    @classmethod
    def _resolve_table_reference(
        cls,
        metadata_json: dict[str, Any] | None,
        schema_name: str | None,
        table_name: str | None,
        file_path: str | None,
        dataset_name: str | None,
    ) -> str | None:
        if file_path and file_path.strip():
            return file_path
        if isinstance(metadata_json, dict):
            metadata_path = metadata_json.get("file_path")
            if isinstance(metadata_path, str) and metadata_path.strip():
                return metadata_path
            uc_info = metadata_json.get("unity_catalog")
            if isinstance(uc_info, dict):
                full_name = uc_info.get("full_name")
                if isinstance(full_name, str) and full_name.strip():
                    return full_name
        if table_name and table_name.strip():
            return cls._qualify_with_env(table_name)
        if dataset_name and dataset_name.strip():
            return cls._qualify_with_env(dataset_name)
        if schema_name and table_name:
            return f"{schema_name}.{table_name}"
        if table_name:
            return table_name
        if dataset_name:
            return dataset_name
        return None

    @classmethod
    def _build_table_aliases(
        cls,
        table_ref: str,
        dataset_name: str | None,
        display_name: str | None,
        schema_name: str | None,
        table_name: str | None,
    ) -> set[str]:
        aliases: set[str] = set()

        def add_alias(raw: str | None) -> None:
            if not isinstance(raw, str):
                return
            normalized = cls._normalize_identifier(raw)
            if not normalized:
                return
            aliases.add(normalized)
            parts = [part for part in normalized.split(".") if part]
            if parts:
                aliases.add(parts[-1])
            if len(parts) >= 2:
                aliases.add(".".join(parts[-2:]))

        add_alias(table_ref)
        add_alias(dataset_name)
        add_alias(table_name)
        if schema_name and table_name:
            add_alias(f"{schema_name}.{table_name}")
        if display_name:
            add_alias(display_name)
            add_alias(display_name.replace(" ", "_"))
        return aliases

    @classmethod
    def _build_alias_to_table_map(cls, datasets: list[dict[str, Any]]) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for dataset in datasets:
            table_ref = dataset["table_ref"]
            aliases = cls._build_table_aliases(
                table_ref=table_ref,
                dataset_name=dataset.get("dataset_name"),
                display_name=dataset.get("display_name"),
                schema_name=dataset.get("schema_name"),
                table_name=dataset.get("table_name"),
            )
            for alias in aliases:
                alias_map[alias] = table_ref
        return alias_map

    @classmethod
    def _qualify_sql_tables(cls, sql: str, alias_to_table: dict[str, str]) -> str:
        def qualify_candidate(raw_candidate: str) -> str:
            stripped = raw_candidate.strip()
            normalized = cls._normalize_identifier(stripped)
            if normalized in alias_to_table:
                return alias_to_table[normalized]

            tokens = stripped.split()
            for i in range(len(tokens), 0, -1):
                candidate = " ".join(tokens[:i])
                mapped = alias_to_table.get(cls._normalize_identifier(candidate))
                if not mapped:
                    continue
                suffix = " ".join(tokens[i:])
                return f"{mapped} {suffix}".strip()
            return stripped.replace("`", "")

        def repl(match: re.Match[str]) -> str:
            keyword = match.group(1)
            raw_candidate = match.group(2)
            return f"{keyword} {qualify_candidate(raw_candidate)}"

        return re.sub(SQL_TABLE_CLAUSE_PATTERN, repl, sql)

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
            table_ref = self._resolve_table_reference(
                metadata_json=dm.metadata_json,
                schema_name=dm.schema_name,
                table_name=dm.table_name,
                file_path=dm.file_path,
                dataset_name=getattr(dataset, "dataset_name", None),
            )
            if table_ref is None:
                continue
            usable_datasets.append(
                {
                    "table_ref": table_ref,
                    "dataset_name": getattr(dataset, "dataset_name", None),
                    "display_name": getattr(dataset, "display_name", None),
                    "schema_name": dm.schema_name,
                    "table_name": dm.table_name,
                    "metadata_json": dm.metadata_json,
                }
            )

        if not usable_datasets:
            raise NotFoundError("No dataset metadata available for query generation")
        return usable_datasets
