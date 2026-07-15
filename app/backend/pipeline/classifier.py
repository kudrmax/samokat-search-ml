from pathlib import Path

import joblib
import numpy as np
import regex as re
from sentence_transformers import SentenceTransformer

from backend.models import CategoryScore

CASCADE_FILENAME = "category_cascade.joblib"
EMBEDDER_DIRNAME = "e5-small-en-ru"

_NON_LETTER = re.compile(r"[^\p{L}\s-]")


def preprocess_query(text: str) -> str:
    """Чистка запроса как в ноутбуке: нижний регистр + только буквы/пробел/дефис."""
    return _NON_LETTER.sub("", text.lower())


class CategoryClassifier:
    """Эмбеддер + каскад KNN: топ-k category1 и условная category2 для каждой."""

    def __init__(self, model_dir: Path) -> None:
        cascade_path = model_dir / CASCADE_FILENAME
        embedder_dir = model_dir / EMBEDDER_DIRNAME
        if not cascade_path.exists() or not embedder_dir.exists():
            raise RuntimeError(
                f"Артефакты классификатора не найдены в {model_dir}. "
                "Сначала запусти: python train_classifier.py"
            )
        self._embedder = SentenceTransformer(str(embedder_dir))
        bundle = joblib.load(cascade_path)
        self._l1 = bundle["l1"]
        self._cat2_models: dict[str, object] = bundle["cat2_models"]
        self._cat2_single_answer: dict[str, str] = bundle["cat2_single_answer"]

    def _predict_category2(self, emb: np.ndarray, category1: str) -> str | None:
        """Вторая ступень каскада: подкатегория внутри предсказанной category1."""
        single = self._cat2_single_answer.get(category1)
        if single is not None:
            return single
        model = self._cat2_models.get(category1)
        if model is not None:
            return str(model.predict([emb])[0])
        return None

    def predict_top(self, query: str, k: int = 3) -> list[CategoryScore]:
        text = preprocess_query(query)
        emb = self._embedder.encode([f"query: {text}"], convert_to_numpy=True)[0]
        proba = self._l1.predict_proba([emb])[0]
        classes = self._l1.classes_
        top_idx = proba.argsort()[::-1][:k]
        return [
            CategoryScore(
                name=str(classes[i]),
                score=float(proba[i]),
                subcategory=self._predict_category2(emb, str(classes[i])),
            )
            for i in top_idx
        ]
