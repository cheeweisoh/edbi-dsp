import re
from typing import Dict, List
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import streamlit as st
from services.dataset_service import DATASETS
from services.auth_service import get_accessible_tables

MODEL_PATH = "./models/prem3Dai-1b-sql"
FORBIDDEN_SQL_KEYWORDS = ["insert", "update", "delete", "drop", "alter", "truncate"]


@st.cache_resource
def load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        device_map="auto",
        torch_dtype="auto",
        local_files_only=True,
    )
    return pipeline("text-generation", model=model, tokenizer=tokenizer)


def build_schema_context(datasets: List[Dict]) -> str:
    tables = []

    for metadata in datasets:
        lines = []
        lines.append(f"Table: {metadata['id']}")
        lines.append(f"Description: {metadata.get('description', '')}")
        lines.append("Columns:")

        for col in metadata["schema"]:
            lines.append(
                f"- {col['column']} ({col['type']}): {col.get('description', '')}"
            )

        tables.append("\n".join(lines))

    return "\n".join(tables)


def build_prompt(nl_query: str, data_contract: Dict) -> str:
    schema_context = build_schema_context(data_contract)

    prompt = f"""
        You are a senior data analyst. Convert the user request into a valid SQL query.

        Rules:
        - Use ONLY the table and columns provided.
        - Do NOT invent columns.
        - Do NOT use UPDATE, DELETE, INSERT, DROP, or ALTER.
        - Do NOT join additionl tables beyond what is required.
        - Return ONLY SQL. No explanations.

        Schema:
        {schema_context}

        User request:
        {nl_query}

        SQL:
    """

    return prompt.strip()


def is_safe_sql(sql: str) -> bool:
    sql_lower = sql.lower()
    return not any(keyword in sql_lower for keyword in FORBIDDEN_SQL_KEYWORDS)


def is_allowed_sql(sql: str, accessible_tables: list[str]) -> bool:
    tables_in_sql = re.findall(
        r"(?:from|join)\s+([a-zA-Z0-9_]+)", sql, flags=re.IGNORECASE
    )
    return all(
        table.lower() in [t.lower() for t in accessible_tables]
        for table in tables_in_sql
    )


def extract_sql(sql: str) -> str:
    sql = sql.strip()
    sql = re.sub(r"^```sql", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    return sql


def text_to_sql(nl_query: str, data_contract: Dict, pipe, user) -> str:
    prompt = build_prompt(nl_query, data_contract)

    result = pipe(
        prompt,
        max_new_tokens=200,
        temperature=0.0,
        do_sample=False,
        return_full_text=False,
    )[0]["generated_text"]

    sql = extract_sql(result)
    accessible_tables = get_accessible_tables(user, DATASETS)

    if not is_safe_sql(sql):
        raise ValueError("Unsafe SQL generated. Query blocked.")
    if not is_allowed_sql(sql, accessible_tables):
        raise PermissionError(
            "You are not allowed to access some tables in the query. Query blocked."
        )

    return sql
