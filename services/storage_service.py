import pandas as pd
import duckdb
from pathlib import Path

con = duckdb.connect(database=":memory:")

data_folder = Path("data/samples")
csv_files = list(data_folder.glob("*.csv"))

for file in csv_files:
    table_name = file.stem
    con.execute(f"""
        CREATE TABLE {table_name} AS
        SELECT * FROM read_csv_auto("{file}")
    """)


def load_dataset(dataset):
    table_name = dataset["id"]

    return con.execute(f"SELECT * FROM {table_name}").fetchdf()


def run_sql(sql: str) -> pd.DataFrame:
    return con.execute(sql).fetchdf()
