import re
from pathlib import Path
from typing import Any

from app.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.dataset_repo import DatasetRepository
from app.services.permission_service import PermissionService
from sqlalchemy.ext.asyncio import AsyncSession

FORBIDDEN_SQL_KEYWORDS = ["insert", "update", "delete", "drop", "alter", "truncate"]


class QueryNLService:
    _pipe: Any = None
    _model_path = str(Path(__file__).resolve().parents[3] / "models" / "prem3Dai-1b-sql")

    def __init__(self, db: AsyncSession) -> None:
        self.dataset_repo = DatasetRepository(db)
        self.perm_svc = PermissionService(db)

    async def generate_sql(
        self,
        nl_query: str,
        current_user: User,
        max_new_tokens: int = 200,
    ) -> str:
        datasets = await self._list_queryable_datasets(current_user)
        schema_context = self._build_schema_context(datasets)
        prompt = self._build_prompt(nl_query, schema_context)

        raw_output = self._get_pipe()(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=0.0,
            do_sample=False,
            return_full_text=False,
        )[
            0
        ]["generated_text"]

        sql = self._extract_sql(raw_output)
        if not self._is_safe_sql(sql):
            raise ForbiddenError("Unsafe SQL generated. Query blocked.")
        if not self._is_allowed_sql(sql, [dataset["name"] for dataset in datasets]):
            raise ForbiddenError("You are not allowed to access some tables in the query. Query blocked.")
        return sql

    @classmethod
    def _get_pipe(cls) -> Any:
        if cls._pipe is not None:
            return cls._pipe

        model_path = Path(cls._model_path)
        if not model_path.exists():
            raise NotFoundError(f"Text-to-SQL model not found at: {cls._model_path}")

        try:
            from transformers import (AutoModelForCausalLM, AutoTokenizer,
                                      pipeline)
        except ImportError as exc:
            raise AppError("transformers dependency is not installed", 500) from exc

        tokenizer = AutoTokenizer.from_pretrained(cls._model_path, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            cls._model_path,
            device_map="auto",
            torch_dtype="auto",
            local_files_only=True,
        )
        cls._pipe = pipeline("text-generation", model=model, tokenizer=tokenizer)
        return cls._pipe

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
        cleaned = cleaned.replace("Ġ", " ")
        keywords = [
            "SELECT",
            "FROM",
            "WHERE",
            "JOIN",
            "LEFT JOIN",
            "RIGHT JOIN",
            "INNER JOIN",
            "OUTER JOIN",
            "GROUP BY",
            "ORDER BY",
            "HAVING",
            "LIMIT",
            "OFFSET",
        ]
        for keyword in sorted(keywords, key=len, reverse=True):
            pattern = keyword.replace(" ", r"\s+")
            cleaned = re.sub(rf"(?i)(?<!\s)({pattern})", r" \1", cleaned)
            cleaned = re.sub(rf"(?i)({pattern})(?!\s|$|[(),;])", r"\1 ", cleaned)
        for keyword in ["AND", "OR", "ON"]:
            cleaned = re.sub(rf"(?<!\s)({keyword})(?=[A-Za-z_])", r" \1", cleaned)
            cleaned = re.sub(rf"({keyword})(?=[A-Za-z_])(?!\s)", r"\1 ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
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
