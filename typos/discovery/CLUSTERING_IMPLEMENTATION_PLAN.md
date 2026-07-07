# План реализации: ноутбук кластеризации типов искажений

**Goal:** один запускаемый ноутбук `typos/discovery/typos_clustering.ipynb`, который
обнаруживает типы дефектов в запросах и выдаёт таблицу «запрос → тип».

**Формат:** ВСЯ логика — в ячейках ноутбука. Никаких модулей `.py`, никаких тестов
(это ML-разведка, не продакшн-разработка). Проверка каждой секции — запустить ячейки
и глазами посмотреть вывод.

**Стек:** pandas, numpy, re, rapidfuzz, scikit-learn (`StandardScaler`, `HDBSCAN`),
pymorphy3, matplotlib, seaborn. Опционально umap-learn.

**Доп. зависимости:** `rapidfuzz` (быстрый Левенштейн), `umap-learn` (2D-проекция).
Ставим в venv.

Спек: `typos/discovery/CLUSTERING_PLAN.md`. Ноутбук строим секция за секцией; после
каждой рабочей секции — коммит.

---

## Задача 0: окружение и данные

- [ ] Активировать venv, установить rapidfuzz:
  `source ../../.venv/bin/activate && pip install rapidfuzz`
- [ ] Создать ноутбук `typos/discovery/typos_clustering.ipynb`, kernel «Python (LSH)».
- [ ] **Cell 0 (markdown):** заголовок + краткое описание задачи (discovery типов
  искажений, вход — уникальные запросы, выход — `query_types.csv`).
- [ ] **Cell 1 (imports):**

```python
import re
from collections import Counter
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from rapidfuzz import process, distance
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import HDBSCAN
import pymorphy3

morph = pymorphy3.MorphAnalyzer()
DATA_PATH = "../../data.csv"   # относительно typos/discovery/
```

- [ ] **Cell 2 (load):**

```python
df = pd.read_csv(DATA_PATH)
queries = pd.Series(df["query"].dropna().unique(), name="query")
print(len(queries), "уникальных запросов")
queries.head(10)
```

Проверка: печатает 9496.
- [ ] Коммит: `chore: init typo-clustering notebook`.

---

## Задача 1: словарь-эталон из каталога (Шаг 0 спека)

- [ ] **Cell 3 (markdown):** пояснение — каталог даёт словарь «правильных» товарных слов.
- [ ] **Cell 4 (build vocab):**

```python
TOKEN_RE = re.compile(r"[а-яёa-z]+", re.IGNORECASE)

def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(str(text).lower())

catalog_cols = ["item_name", "category4_name", "category3_name",
                "category2_name", "category1_name"]
catalog_vocab: Counter = Counter()
for col in catalog_cols:
    for name in df[col].dropna():
        catalog_vocab.update(tokenize(name))

print("уникальных слов в каталоге:", len(catalog_vocab))
catalog_vocab.most_common(15)
```

- [ ] **Cell 5 (known-word helper):**

```python
CATALOG_WORDS = set(catalog_vocab)

def is_known(token: str) -> bool:
    """Слово настоящее, если есть в каталоге или известно pymorphy (рус.)."""
    if token in CATALOG_WORDS:
        return True
    if re.fullmatch(r"[а-яё]+", token) and morph.word_is_known(token):
        return True
    return False
```

Проверка: `is_known("молоко")` → True, `is_known("кросчовки")` → False.
- [ ] Коммит: `feat: catalog lexicon in notebook`.

---

## Задача 2: ближайшее слово каталога (для расстояния и подсказки)

- [ ] **Cell 6 (markdown):** для неизвестного слова ищем ближайшее слово каталога —
  малое расстояние → опечатка, большое → мусор/иностранное.
- [ ] **Cell 7 (nearest word, с кэшем):**

```python
# кандидаты — только достаточно частые слова каталога (шум режем частотой)
CANDIDATES = [w for w, c in catalog_vocab.items()
              if c >= 3 and re.fullmatch(r"[а-яё]+", w)]

_nearest_cache: dict[str, tuple[str, float]] = {}

def nearest_catalog(token: str) -> tuple[str, float]:
    """Возвращает (ближайшее_слово, нормированная_дистанция 0..1)."""
    if token in _nearest_cache:
        return _nearest_cache[token]
    match = process.extractOne(
        token, CANDIDATES,
        scorer=distance.Levenshtein.normalized_distance,
    )
    word, dist = match[0], match[1]
    _nearest_cache[token] = (word, dist)
    return word, dist
```

Проверка: `nearest_catalog("кросчовки")` → близко к «кроссовки», dist маленькая (< 0.3).
- [ ] Коммит: `feat: nearest-catalog-word lookup`.

---

## Задача 3: структурные признаки на каждый запрос (Шаг 1 спека)

- [ ] **Cell 8 (markdown):** список признаков и зачем каждый.
- [ ] **Cell 9 (feature fn):**

```python
CYR = re.compile(r"[а-яё]")
LAT = re.compile(r"[a-z]")

def has_mixed_alphabet(tok: str) -> bool:
    return bool(CYR.search(tok)) and bool(LAT.search(tok))

def has_repeat_run(text: str, n: int = 3) -> bool:
    return re.search(r"(.)\1{" + str(n - 1) + r",}", text) is not None

def extract_features(query: str) -> dict:
    q = str(query).lower()
    toks = tokenize(q)
    n_chars = len(q)
    n_tok = len(toks)
    tok_lens = [len(t) for t in toks] or [0]
    letters = [ch for ch in q if ch.isalpha()]
    n_letters = len(letters) or 1
    unknown = [t for t in toks if not is_known(t)]
    # мин. дистанция до каталога по неизвестным рус. токенам
    dists = [nearest_catalog(t)[1] for t in unknown
             if re.fullmatch(r"[а-яё]+", t)]
    last_unknown_short = bool(toks) and (not is_known(toks[-1])) and len(toks[-1]) <= 2
    return {
        "query": query,
        "n_chars": n_chars,
        "n_tokens": n_tok,
        "mean_tok_len": float(np.mean(tok_lens)),
        "max_tok_len": max(tok_lens),
        "frac_lat": sum(bool(LAT.match(c)) for c in letters) / n_letters,
        "frac_cyr": sum(bool(CYR.match(c)) for c in letters) / n_letters,
        "frac_digit": sum(ch.isdigit() for ch in q) / n_chars,
        "frac_known": (n_tok - len(unknown)) / n_tok if n_tok else 1.0,
        "min_dist_catalog": min(dists) if dists else 0.0,
        "flag_mixed_alpha": int(any(has_mixed_alphabet(t) for t in toks)),
        "flag_repeat": int(has_repeat_run(q)),
        "flag_abrupt_tail": int(last_unknown_short),
        "flag_all_latin": int(bool(toks) and all(LAT.match(t) for t in toks)),
    }
```

- [ ] **Cell 10 (build feature frame):**

```python
feat = pd.DataFrame(extract_features(q) for q in queries)
print(feat.shape)
feat.describe()
```

Проверка: 9496 строк, ~13 числовых колонок, NaN нет.
- [ ] Коммит: `feat: structural features for queries`.

---

## Задача 4: отсев «ок» (Шаг 2 спека)

- [ ] **Cell 11 (markdown):** чистый запрос = все токены известны; откладываем в `ок`.
- [ ] **Cell 12 (split):**

```python
is_ok = (feat["frac_known"] == 1.0) & (feat["flag_mixed_alpha"] == 0)
ok_df = feat[is_ok].copy()
sus_df = feat[~is_ok].copy()
print(f"ок: {len(ok_df)}   подозрительных: {len(sus_df)}")
sus_df.sample(15)[["query", "frac_known", "min_dist_catalog",
                   "frac_lat", "max_tok_len"]]
```

Проверка: разумное деление (ок — заметная доля), глазами — в sus_df реально дефекты.
- [ ] Коммит: `feat: split ok vs suspicious queries`.

---

## Задача 5: кластеризация остатка (Шаг 3 спека)

- [ ] **Cell 13 (markdown):** почему HDBSCAN (число типов неизвестно, бакет «шум»).
- [ ] **Cell 14 (cluster):**

```python
FEATURE_COLS = ["n_chars", "n_tokens", "mean_tok_len", "max_tok_len",
                "frac_lat", "frac_cyr", "frac_digit", "frac_known",
                "min_dist_catalog", "flag_mixed_alpha", "flag_repeat",
                "flag_abrupt_tail", "flag_all_latin"]

X = StandardScaler().fit_transform(sus_df[FEATURE_COLS])
labels = HDBSCAN(min_cluster_size=40, min_samples=5).fit_predict(X)
sus_df["cluster"] = labels
print("кластеров:", len(set(labels)) - (1 if -1 in labels else 0),
      "| шум:", (labels == -1).sum())
sus_df["cluster"].value_counts()
```

Проверка: несколько кластеров + бакет шума (-1). Если всё в шум — снизить
`min_cluster_size`; если один гигантский кластер — поднять. Подобрать вручную.
- [ ] Коммит: `feat: HDBSCAN clustering of suspicious queries`.

---

## Задача 6: интерпретация и имена кластеров (Шаг 4 спека)

- [ ] **Cell 15 (profiles):**

```python
profile = sus_df.groupby("cluster")[FEATURE_COLS].mean().round(2)
profile["size"] = sus_df["cluster"].value_counts()
profile
```

- [ ] **Cell 16 (examples per cluster):**

```python
for cid in sorted(sus_df["cluster"].unique()):
    sample = sus_df[sus_df["cluster"] == cid]["query"].head(12).tolist()
    print(f"\n=== cluster {cid} (n={ (sus_df['cluster']==cid).sum() }) ===")
    print("  ", "  |  ".join(map(str, sample)))
```

- [ ] **Cell 17 (markdown + label map):** Макс читает профили и примеры, заполняет
  словарь имён:

```python
CLUSTER_NAMES = {
    -1: "мусор/выброс",
    # 0: "опечатка",
    # 1: "латиница",
    # 2: "слипшиеся",
    # 3: "оборванный",
    # ... заполнить по факту
}
sus_df["type"] = sus_df["cluster"].map(CLUSTER_NAMES).fillna("не размечен")
```

Проверка: имена осмысленны и согласуются с профилем (напр. кластер с высоким
`frac_lat` → «латиница»).
- [ ] Коммит: `feat: interpret and name clusters`.

---

## Задача 7: сборка выхода (Шаг 5 спека)

- [ ] **Cell 18 (final table + csv):**

```python
ok_df["type"] = "ок"
ok_df["cluster"] = -2  # маркер «не кластеризовали»

def correction_hint(row) -> str:
    if row["type"] in ("ок", "мусор/выброс"):
        return ""
    toks = tokenize(row["query"])
    unknown = [t for t in toks if not is_known(t) and re.fullmatch(r"[а-яё]+", t)]
    return " ".join(nearest_catalog(t)[0] if t in set(unknown) else t
                    for t in toks)

result = pd.concat([sus_df, ok_df], ignore_index=True)
result["correction_hint"] = result.apply(correction_hint, axis=1)
out_cols = ["query", "type", "correction_hint", "cluster"] + FEATURE_COLS
result[out_cols].to_csv("query_types.csv", index=False)
print("сохранено:", len(result), "строк")
result["type"].value_counts()
```

- [ ] **Cell 19 (bar chart):**

```python
plt.figure(figsize=(9, 4))
result["type"].value_counts().plot.bar()
plt.title("Распределение типов запросов")
plt.tight_layout(); plt.savefig("type_distribution.png", dpi=120); plt.show()
```

Проверка: `query_types.csv` создан, распределение типов правдоподобно.
- [ ] Коммит: `feat: export query_types.csv and charts`.

---

## Задача 8: 2D-визуализация UMAP (вариант C из спека)

- [ ] Поставить в venv: `pip install umap-learn`.
- [ ] **Cell 21 (markdown):** проецируем 13-мерный вектор признаков в 2D, чтобы
  глазами увидеть, отделяются ли кластеры и «шум». UMAP лучше сохраняет локальную
  структуру, чем PCA; при неудаче установки — фолбэк на `sklearn` t-SNE.
- [ ] **Cell 22 (project + scatter):**

```python
try:
    import umap
    reducer = umap.UMAP(n_neighbors=15, min_dist=0.1,
                        n_components=2, metric="euclidean")
    method = "UMAP"
except ImportError:
    from sklearn.manifold import TSNE
    reducer = TSNE(n_components=2, perplexity=30, init="pca")
    method = "t-SNE"

emb2d = reducer.fit_transform(X)   # X — стандартизованные признаки sus_df
sus_df["dim1"], sus_df["dim2"] = emb2d[:, 0], emb2d[:, 1]

plt.figure(figsize=(9, 7))
palette = sns.color_palette("tab20", sus_df["cluster"].nunique())
sns.scatterplot(data=sus_df, x="dim1", y="dim2", hue="type",
                s=14, linewidth=0, palette=palette, legend="full")
plt.title(f"Запросы в 2D ({method}), цвет — тип дефекта")
plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
plt.tight_layout(); plt.savefig("clusters_2d.png", dpi=120); plt.show()
```

Проверка: точки одного типа тяготеют друг к другу; `clusters_2d.png` создан.
Если типы сильно перемешаны — сигнал вернуться к признакам/параметрам HDBSCAN.
- [ ] **Cell 23 (опционально):** раскраска того же scatter по `hue="cluster"` —
  сравнить, совпадают ли визуальные сгустки с метками HDBSCAN.
- [ ] Коммит: `feat: 2D UMAP visualization of clusters`.

---

## Самопроверка плана

- Покрытие спека: Шаг 0 → З.1; Шаг 1 → З.2–3; Шаг 2 → З.4; Шаг 3 → З.5;
  Шаг 4 → З.6; Шаг 5 → З.7. ✓
- Плейсхолдеров нет (кроме `CLUSTER_NAMES`, который заполняется по факту кластеров —
  это осознанный ручной шаг интерпретации).
- Имена функций согласованы: `tokenize`, `is_known`, `nearest_catalog`,
  `extract_features` используются единообразно во всех ячейках. ✓
