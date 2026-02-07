import subprocess
import re
import os
import tempfile
from typing import Dict, List
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import streamlit as st
from dotenv import load_dotenv

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


def extract_sql(sql: str) -> str:
    sql = sql.strip()
    sql = re.sub(r"^```sql", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    return sql


def text_to_sql(nl_query: str, data_contract: Dict, pipe) -> str:
    prompt = build_prompt(nl_query, data_contract)

    result = pipe(
        prompt,
        max_new_tokens=200,
        temperature=0.0,
        do_sample=False,
        return_full_text=False,
    )[0]["generated_text"]

    sql = extract_sql(result)

    if not is_safe_sql(sql):
        raise ValueError("Unsafe SQL generated. Query blocked.")

    return sql
