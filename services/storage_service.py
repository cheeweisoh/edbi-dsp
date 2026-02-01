import pandas as pd


def load_dataset(dataset):
    if dataset["source"] == "local":
        return pd.read_csv(dataset["path"])
