import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.dataset_repo import DatasetRepository
from app.services.permission_service import PermissionService

FORBIDDEN_SQL_KEYWORDS = ["insert", "update", "delete", "drop", "alter", "truncate"]


class QueryNLService:
    _pipe: Any = None
    _model_path = str(Path(__file__).resolve().parents[3] / "models" / "prem3Dai-1b-sql")

    def __init__(self, db: AsyncSession) -> None:
        self.dataset_repo = DatasetRepository(db)
        self.perm_svc = PermissionService(db)

    async def generate_sql(
        self,
        dataset_id: uuid.UUID,
        nl_query: str,
        current_user: User,
        max_new_tokens: int = 200,
    ) -> str:
        await self.perm_svc.verify_access(current_user, dataset_id, min_permission="query")

        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if dataset is None or not dataset.is_active:
            raise NotFoundError(f"Dataset {dataset_id} not found")

        dm = await self.dataset_repo.get_metadata(dataset_id)
        if dm is None or dm.metadata_json is None:
            raise NotFoundError(f"No metadata found for dataset {dataset_id}")

        schema_context = self._build_schema_context(dataset.name, dm.metadata_json)
        prompt = self._build_prompt(nl_query, schema_context)

        raw_output = self._get_pipe()(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=0.0,
            do_sample=False,
            return_full_text=False,
        )[0]["generated_text"]

        sql = self._extract_sql(raw_output)
        if not self._is_safe_sql(sql):
            raise ForbiddenError("Unsafe SQL generated. Query blocked.")
        if not self._is_allowed_sql(sql, [dataset.name]):
            raise ForbiddenError(
                "You are not allowed to access some tables in the query. Query blocked."
            )
        return sql

    @classmethod
    def _get_pipe(cls) -> Any:
        if cls._pipe is not None:
            return cls._pipe

        model_path = Path(cls._model_path)
        if not model_path.exists():
            raise NotFoundError(f"Text-to-SQL model not found at: {cls._model_path}")

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
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
    def _build_schema_context(dataset_name: str, metadata_json: dict[str, Any]) -> str:
        schema = metadata_json.get("schema")
        if not isinstance(schema, list) or not schema:
            raise NotFoundError(f"No schema columns found in metadata for dataset '{dataset_name}'")

        lines = [
            f"Table: {dataset_name}",
            f"Description: {metadata_json.get('description', '')}",
            "Columns:",
        ]
        for col in schema:
            if isinstance(col, dict):
                lines.append(
                    f"- {col.get('column', '')} ({col.get('type', '')}): {col.get('description', '')}"
                )
        return "\n".join(lines)

    @staticmethod
    def _build_prompt(nl_query: str, schema_context: str) -> str:
        prompt = f"""
        You are a senior data analyst. Convert the user request into a valid SQL query.

        Rules:
        - Use ONLY the table and columns provided.
        - Do NOT invent columns.
        - Do NOT use UPDATE, DELETE, INSERT, DROP, or ALTER.
        - Do NOT join additional tables beyond what is required.
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
