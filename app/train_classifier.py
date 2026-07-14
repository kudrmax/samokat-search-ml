"""Офлайн-обучение классификатора категории (category1) и сохранение артефактов.

Запуск (разово, руками):
    source /Users/maxos/PythonProjects/LSH/.venv/bin/activate
    cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
    python train_classifier.py
"""
from pathlib import Path

import joblib
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import KNeighborsClassifier

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
DATA_PATH = PROJECT_ROOT / "DATA.csv"
MODELS_DIR = APP_DIR / "models"
EMBEDDER_NAME = "d0rj/e5-small-en-ru"

KNN_PATH = MODELS_DIR / "category1_knn.joblib"
EMBEDDER_DIR = MODELS_DIR / "e5-small-en-ru"


def build_item_names(df: pd.DataFrame) -> pd.DataFrame:
    """Датасет 'название товара -> category1', предобработка как в ноутбуке."""
    p = df.copy()
    p["item_name"] = (
        p["item_name"]
        .str.split(",").str[0]
        .str.replace(r"[^а-яА-Яa-zA-Z\s-]", "", regex=True)
        .str.replace(r"\b(шт|г|кг|мл|л)\b", "", regex=True)
    )
    d = p.dropna(subset=["category1_name"])
    d = d.drop_duplicates(subset=["item_name"])[["item_name", "category1_name"]]
    return d.rename(columns={"item_name": "query"})


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH, encoding="utf-8")
    item_names = build_item_names(df)
    print(f"обучающих примеров: {len(item_names)}")

    X = [f"query: {q}" for q in item_names["query"]]
    y = item_names["category1_name"]

    embedder = SentenceTransformer(EMBEDDER_NAME)
    X_emb = embedder.encode(X, convert_to_numpy=True, show_progress_bar=True)

    knn = KNeighborsClassifier(n_neighbors=3, weights="distance", metric="euclidean")
    knn.fit(X_emb, y)

    joblib.dump(knn, KNN_PATH)
    embedder.save(str(EMBEDDER_DIR))
    print(f"сохранено: {KNN_PATH}")
    print(f"сохранено: {EMBEDDER_DIR}")


if __name__ == "__main__":
    main()
