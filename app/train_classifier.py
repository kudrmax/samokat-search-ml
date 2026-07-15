"""Офлайн-обучение каскадного классификатора категорий и сохранение артефактов.

Каскад из двух ступеней (как в categories/classificator.ipynb):
  L1  — KNN на category1 (самый общий уровень);
  L2  — для каждой category1 свой KNN на category2, либо единственный вариант.

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

from backend.pipeline.classifier import (
    CASCADE_FILENAME,
    EMBEDDER_DIRNAME,
    preprocess_query,
)

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
DATA_PATH = PROJECT_ROOT / "DATA.csv"
MODELS_DIR = APP_DIR / "models"
EMBEDDER_NAME = "d0rj/e5-small-en-ru"

CASCADE_PATH = MODELS_DIR / CASCADE_FILENAME
EMBEDDER_DIR = MODELS_DIR / EMBEDDER_DIRNAME

CATEGORY_COLS = ("category1_name", "category2_name")
MIN_PAIR_COUNT = 3      # пары (cat1, cat2) реже этого отбрасываем
MIN_CAT1_COUNT = 2      # category1 реже этого отбрасываем
KNN_NEIGHBORS = 3


def build_dataset(
    df: pd.DataFrame,
    key_col: str,
    category_cols: tuple[str, ...] = ("category1_name",),
    unique_category_only: bool = False,
) -> pd.DataFrame:
    """Датасет 'ключ -> категории', ключ переименовывается в 'query'.

    `unique_category_only` оставляет только ключи, у которых по всем category-
    колонкам ровно одно уникальное значение (чистая разметка).
    """
    cols = list(category_cols)
    d = df.dropna(subset=cols)
    if unique_category_only:
        nunique = d.groupby(key_col)[cols].nunique()
        clean_keys = nunique[(nunique == 1).all(axis=1)].index
        d = d[d[key_col].isin(clean_keys)]
    d = d.drop_duplicates(subset=[key_col])[[key_col] + cols]
    return d.rename(columns={key_col: "query"})


def build_category_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Каскадный датасет (category1 + category2) как в ноутбуке."""
    p = df.copy()
    p["query"] = p["query"].map(preprocess_query)

    item_names = build_dataset(p, "item_name", category_cols=CATEGORY_COLS)

    rows = p[p["final_answer"].isin(["e", "s"])]
    category2_dataset = build_dataset(
        rows, "query", category_cols=CATEGORY_COLS, unique_category_only=True
    )

    data = pd.concat([category2_dataset, item_names], ignore_index=True)

    # фильтрация редких пар и редких category1
    pair_counts = data.groupby(list(CATEGORY_COLS)).size()
    valid_pairs = set(pair_counts[pair_counts >= MIN_PAIR_COUNT].index)
    data = data[
        data.apply(
            lambda r: (r["category1_name"], r["category2_name"]) in valid_pairs, axis=1
        )
    ]
    cat1_counts = data["category1_name"].value_counts()
    valid_cat1 = cat1_counts[cat1_counts >= MIN_CAT1_COUNT].index
    data = data[data["category1_name"].isin(valid_cat1)]
    return data.reset_index(drop=True)


def train_l2(
    embeddings, y1: pd.Series, y2: pd.Series
) -> tuple[dict[str, KNeighborsClassifier], dict[str, str]]:
    """Вторая ступень: свой KNN на каждую category1 либо единственный ответ."""
    table = pd.DataFrame({"category1": y1.values, "category2": y2.values})
    table["embedding"] = list(embeddings)

    cat2_models: dict[str, KNeighborsClassifier] = {}
    cat2_single_answer: dict[str, str] = {}

    for category1 in table["category1"].unique():
        subset = table[table["category1"] == category1]
        answers = subset["category2"].unique()
        if len(answers) == 1:
            cat2_single_answer[category1] = answers[0]
            continue
        n_neighbors = min(KNN_NEIGHBORS, int(subset["category2"].value_counts().min()))
        model = KNeighborsClassifier(
            weights="distance", n_neighbors=n_neighbors, metric="euclidean"
        )
        model.fit(list(subset["embedding"]), subset["category2"])
        cat2_models[category1] = model

    return cat2_models, cat2_single_answer


def load_embedder() -> SentenceTransformer:
    """Локальный эмбеддер, если уже скачан (слабый интернет), иначе с HuggingFace."""
    source = str(EMBEDDER_DIR) if EMBEDDER_DIR.exists() else EMBEDDER_NAME
    print(f"эмбеддер: {source}")
    return SentenceTransformer(source)


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH, encoding="utf-8")
    data = build_category_dataset(df)
    print(
        f"обучающих примеров: {len(data)}, "
        f"category1: {data['category1_name'].nunique()}, "
        f"category2: {data['category2_name'].nunique()}"
    )

    embedder = load_embedder()
    X = ["query: " + q for q in data["query"]]
    X_emb = embedder.encode(X, convert_to_numpy=True, show_progress_bar=True)

    y1 = data["category1_name"]
    y2 = data["category2_name"]

    l1 = KNeighborsClassifier(
        weights="distance", n_neighbors=KNN_NEIGHBORS, metric="euclidean"
    )
    l1.fit(X_emb, y1)

    cat2_models, cat2_single_answer = train_l2(X_emb, y1, y2)
    print(
        f"под-классификаторов L2: {len(cat2_models)}, "
        f"категорий с единственным вариантом: {len(cat2_single_answer)}"
    )

    bundle = {
        "l1": l1,
        "cat2_models": cat2_models,
        "cat2_single_answer": cat2_single_answer,
    }
    joblib.dump(bundle, CASCADE_PATH)
    embedder.save(str(EMBEDDER_DIR))
    print(f"сохранено: {CASCADE_PATH}")
    print(f"сохранено: {EMBEDDER_DIR}")


if __name__ == "__main__":
    main()
