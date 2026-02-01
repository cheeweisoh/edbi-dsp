from metadata.datasets import DATASETS
from typing import Optional, Any
from services.auth_service import can_user_access_dataset, get_current_user


def get_visible_datasets():
    user = get_current_user()
    return [d for d in DATASETS if can_user_access_dataset(user, d)]


def get_dataset_by_id(id: int) -> dict[str, Any]:
    return next(d for d in DATASETS if d["id"] == id)


def search_datasets(query: str, category: Optional[str] = None, datasets=None) -> list:
    results = datasets if datasets is not None else DATASETS

    if category:
        results = [d for d in results if category in d["category"]]

    if query:
        q = query.lower()
        results = [
            d
            for d in results
            if q in f"{d['title']} {d['description']} {d['agency']}".lower()
        ]

    return results
