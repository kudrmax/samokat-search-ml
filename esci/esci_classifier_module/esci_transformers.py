"""
Общие классы препроцессинга для ESCI-пайплайна.
ВАЖНО: этот файл должен лежать рядом и с ноутбуком обучения, и с
инференс-скриптом — joblib при unpickle ищет классы именно по пути
их модуля (esci_transformers.ClassName), а не хранит код внутри .joblib.
"""

import re
import numpy as np
import pandas as pd
import torch
from difflib import SequenceMatcher
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import pymorphy3
from transformers import AutoTokenizer, AutoModel

morph = pymorphy3.MorphAnalyzer()


def lemmatize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\d+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    words = [w for w in text.split() if len(w) > 2]
    return ' '.join(morph.parse(w)[0].normal_form for w in words)


def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return (token_embeddings * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


# кеш моделей на уровне модуля -- чтобы e5 грузился с диска один раз,
# даже если его использует и stage1, и stage2 пайплайн в одном процессе
_MODEL_CACHE = {}


def load_e5(model_dir: str):
    if model_dir not in _MODEL_CACHE:
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        model = AutoModel.from_pretrained(model_dir)
        model.eval()
        _MODEL_CACHE[model_dir] = (tokenizer, model)
    return _MODEL_CACHE[model_dir]


def embed_texts(texts, tokenizer, model, batch_size=32, prefix="query: "):
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = [f"{prefix}{t}" for t in texts[i:i + batch_size]]
        enc = tokenizer(batch, padding=True, truncation=True, return_tensors='pt')
        with torch.no_grad():
            out = model(**enc)
        emb = mean_pooling(out, enc['attention_mask'])
        emb = torch.nn.functional.normalize(emb, p=2, dim=1)
        embeddings.append(emb.numpy())
    return np.vstack(embeddings)


class WordOverlapTransformer(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        q_lemma = X['query'].apply(lemmatize_text)
        i_lemma = X['item_name'].apply(lemmatize_text)

        def ratio(q, i):
            q_words, i_words = set(q.split()), set(i.split())
            return len(q_words & i_words) / len(q_words) if q_words else 0.0

        result = [ratio(q, i) for q, i in zip(q_lemma, i_lemma)]
        return np.array(result).reshape(-1, 1)


class SubstringRatioTransformer(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        q_lemma = X['query'].apply(lemmatize_text)
        i_lemma = X['item_name'].apply(lemmatize_text)
        result = [SequenceMatcher(None, q, i).ratio() for q, i in zip(q_lemma, i_lemma)]
        return np.array(result).reshape(-1, 1)


class TfidfSimTransformer(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        q_lemma = X['query'].apply(lemmatize_text)
        i_lemma = X['item_name'].apply(lemmatize_text)
        self.tfidf = TfidfVectorizer()
        self.tfidf.fit(pd.concat([q_lemma, i_lemma]))
        return self

    def transform(self, X):
        q_lemma = X['query'].apply(lemmatize_text)
        i_lemma = X['item_name'].apply(lemmatize_text)
        q_vecs = self.tfidf.transform(q_lemma)
        i_vecs = self.tfidf.transform(i_lemma)
        sims = [cosine_similarity(q_vecs[i], i_vecs[i])[0][0] for i in range(X.shape[0])]
        return np.array(sims).reshape(-1, 1)


class EmbSimTransformer(BaseEstimator, TransformerMixin):
    """
    Хранит только путь к папке с моделью (model_dir), а не сами
    torch-объекты -- модель подгружается лениво через load_e5()
    (с кешем на модуль), поэтому .joblib файл лёгкий и не тащит
    веса e5 внутри себя.
    """

    def __init__(self, model_dir: str):
        self.model_dir = model_dir

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        tokenizer, model = load_e5(self.model_dir)
        q_emb = embed_texts(X['query'].tolist(), tokenizer, model, prefix="query: ")
        i_emb = embed_texts(X['item_name'].tolist(), tokenizer, model, prefix="passage: ")
        return (q_emb * i_emb).sum(axis=1).reshape(-1, 1)


class BinarizeFeaturesTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, cols_idx):
        self.cols_idx = cols_idx

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        extra = (X[:, self.cols_idx] > 0).astype(int)
        return np.hstack([X, extra])
