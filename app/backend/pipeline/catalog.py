import random
from pathlib import Path

import pandas as pd

from backend.models import Product


class ProductCatalog:
    """Каталог товаров из DATA.csv: индекс category1 -> товары.

    Использует только item_name и категории; final_answer НЕ читается.
    """

    def __init__(self, data_path: Path) -> None:
        df = pd.read_csv(
            data_path,
            usecols=["item_name", "category1_name", "category4_name"],
            encoding="utf-8",
        )
        df = df.dropna(subset=["item_name", "category1_name"])
        df = df.drop_duplicates(subset=["item_name"])

        self._by_cat: dict[str, list[Product]] = {}
        for row in df.itertuples(index=False):
            cat4 = row.category4_name
            product = Product(
                item_name=row.item_name,
                category4=None if pd.isna(cat4) else str(cat4),
            )
            self._by_cat.setdefault(row.category1_name, []).append(product)

    def has_category(self, category: str) -> bool:
        return category in self._by_cat

    def sample(self, category: str, count: int, exclude: set[str]) -> list[Product]:
        pool = [p for p in self._by_cat.get(category, []) if p.item_name not in exclude]
        if not pool:
            return []
        return random.sample(pool, min(count, len(pool)))
