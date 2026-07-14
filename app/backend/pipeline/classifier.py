from pathlib import Path

import joblib
import regex as re
from sentence_transformers import SentenceTransformer

from backend.models import CategoryScore

_NON_LETTER = re.compile(r"[^\p{L}\s-]")


def preprocess_query(text: str) -> str:
    """Чистка запроса как в ноутбуке: нижний регистр + только буквы/пробел/дефис."""
    return _NON_LETTER.sub("", text.lower())


class CategoryClassifier:
    """Эмбеддер + KNN: предсказывает топ-k категорий верхнего уровня."""

    def __init__(self, model_dir: Path) -> None:
        knn_path = model_dir / "category1_knn.joblib"
        embedder_dir = model_dir / "e5-small-en-ru"
        if not knn_path.exists() or not embedder_dir.exists():
            raise RuntimeError(
                f"Артефакты классификатора не найдены в {model_dir}. "
                "Сначала запусти: python train_classifier.py"
            )
        self._embedder = SentenceTransformer(str(embedder_dir))
        self._knn = joblib.load(knn_path)

    def predict_top(self, query: str, k: int = 3) -> list[CategoryScore]:
        text = preprocess_query(query)
        emb = self._embedder.encode([f"query: {text}"], convert_to_numpy=True)
        proba = self._knn.predict_proba(emb)[0]
        classes = self._knn.classes_
        top_idx = proba.argsort()[::-1][:k]
        return [
            CategoryScore(name=str(classes[i]), score=float(proba[i]))
            for i in top_idx
        ]
