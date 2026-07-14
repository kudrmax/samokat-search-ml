# Классификатор категории в веб-приложении — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в существующее веб-приложение классификатор: `query → исправление опечаток → топ-3 категории верхнего уровня`.

**Architecture:** Офлайн-скрипт обучает KNN на эмбеддингах названий товаров и сохраняет артефакты в `app/models/` (в git не коммитятся). FastAPI при старте грузит эмбеддер и KNN в `app.state`; новый эндпоинт `/api/analyze` прогоняет исправленный запрос через классификатор. Фронтенд показывает топ-3 категории.

**Tech Stack:** Python 3.12, FastAPI, sentence-transformers (`d0rj/e5-small-en-ru`), scikit-learn KNN, joblib, regex, pandas; vanilla HTML/CSS/JS.

## Global Constraints

- Python **3.12**, venv: `/Users/maxos/PythonProjects/LSH/.venv`. Пакеты — только в этот venv, НИКОГДА не глобально.
- Всё в папке `samokat/app/`. Продолжаем ветку `app/typo-correction-web`.
- Модель и предобработку из `samokat/categories/classificator.ipynb` — переносим и вызываем **КАК ЕСТЬ**, без тюнинга гиперпараметров.
- KNN: `KNeighborsClassifier(n_neighbors=3, weights='distance', metric='euclidean')`.
- Эмбеддер: `d0rj/e5-small-en-ru`, вход префиксится `"query: "`.
- Обучающий датасет: `DATA.csv` (корень `samokat/`), колонки `query,item_name,item_id,final_answer,category4_name,category3_name,category2_name,category1_name`.
- Артефакты в `app/models/` (KNN + копия эмбеддера); каталог — в `.gitignore`.
- Классифицируется **исправленный** запрос (выход опечаточника).
- Строгая типизация, pydantic вместо dict. Бэкенд-логика не зависит от фронтенда.
- Удаление файлов — только `trash`, никогда `rm`. Git-команды — из корня `samokat/`.

---

## File Structure

```
samokat/app/
├── .gitignore                  # НОВОЕ: models/, __pycache__/, .pytest_cache/
├── train_classifier.py         # НОВОЕ: офлайн-обучение KNN + сохранение артефактов
├── models/                     # НОВОЕ (в .gitignore): category1_knn.joblib, e5-small-en-ru/
├── requirements.txt            # + sentence-transformers, scikit-learn, joblib, regex, pandas
├── backend/
│   ├── main.py                 # + /api/analyze, classifier в lifespan (graceful)
│   ├── models.py               # + CategoryScore, AnalyzeResponse
│   └── pipeline/
│       └── classifier.py       # НОВОЕ: preprocess_query + CategoryClassifier
├── frontend/
│   ├── index.html              # + блок «Категории»
│   ├── style.css               # + стили блока категорий
│   └── app.js                  # /api/analyze, рендер топ-3
└── tests/
    ├── test_classifier.py      # НОВОЕ: preprocess_query + smoke (skipif без артефакта)
    └── test_api.py             # + тест /api/analyze (skipif без артефакта)
```

---

## Task 1: .gitignore, каталог моделей, зависимости

**Files:**
- Create: `app/.gitignore`
- Modify: `app/requirements.txt`
- Create: `app/models/.gitkeep` (чтобы каталог существовал; сам он игнорируется, файл добавим форсом)

**Interfaces:**
- Consumes: —
- Produces: игнор `models/`; в venv доступны `sentence_transformers`, `sklearn`, `joblib`, `regex`, `pandas` (уже стоят — фиксируем в requirements).

- [ ] **Step 1: Создать `app/.gitignore`**

```
models/
__pycache__/
.pytest_cache/
*.pyc
```

- [ ] **Step 2: Обновить `app/requirements.txt`** — заменить содержимое на:

```
fastapi
uvicorn[standard]
pydantic>=2
symspellpy
marisa-trie
httpx
pytest
sentence-transformers
scikit-learn
joblib
regex
pandas
```

- [ ] **Step 3: Создать каталог `app/models/` с `.gitkeep`**

Создать файл `app/models/.gitkeep` (пустой).

- [ ] **Step 4: Проверить импорты**

Run:
```bash
/Users/maxos/PythonProjects/LSH/.venv/bin/python -c "import sentence_transformers, sklearn, joblib, regex, pandas; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Commit** (`.gitkeep` добавляем форсом, т.к. `models/` игнорируется)

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/.gitignore app/requirements.txt
git add -f app/models/.gitkeep
git commit -m "chore: gitignore артефактов и зависимости классификатора"
```

---

## Task 2: pydantic-модели классификатора

**Files:**
- Modify: `app/backend/models.py`
- Test: `app/tests/test_models.py` (дополнить)

**Interfaces:**
- Consumes: существующий `WordCorrection`.
- Produces:
  - `CategoryScore(BaseModel)` — `name: str`, `score: float`.
  - `AnalyzeResponse(BaseModel)` — `original: str`, `corrected: str`, `words: list[WordCorrection]`, `categories: list[CategoryScore]`.

- [ ] **Step 1: Дописать тесты в конец `app/tests/test_models.py`**

```python
def test_category_score_fields():
    from backend.models import CategoryScore

    cs = CategoryScore(name="безалкогольные напитки", score=1.0)
    assert cs.name == "безалкогольные напитки"
    assert cs.score == 1.0


def test_analyze_response_holds_categories():
    from backend.models import AnalyzeResponse, CategoryScore, WordCorrection

    resp = AnalyzeResponse(
        original="кола",
        corrected="кола",
        words=[WordCorrection(original="кола", corrected="кола")],
        categories=[CategoryScore(name="безалкогольные напитки", score=1.0)],
    )
    assert resp.categories[0].name == "безалкогольные напитки"
    assert resp.words[0].changed is False
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_models.py -v'
```
Expected: FAIL — `ImportError: cannot import name 'CategoryScore'`.

- [ ] **Step 3: Дописать модели в конец `app/backend/models.py`**

```python
class CategoryScore(BaseModel):
    name: str
    score: float


class AnalyzeResponse(BaseModel):
    original: str
    corrected: str
    words: list[WordCorrection]
    categories: list[CategoryScore]
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_models.py -v'
```
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/models.py app/tests/test_models.py
git commit -m "feat: pydantic-модели CategoryScore и AnalyzeResponse"
```

---

## Task 3: Обучающий скрипт и генерация артефактов

**Files:**
- Create: `app/train_classifier.py`

**Interfaces:**
- Consumes: `DATA.csv`; эмбеддер `d0rj/e5-small-en-ru`.
- Produces: `app/models/category1_knn.joblib` (обученный `KNeighborsClassifier`), `app/models/e5-small-en-ru/` (копия эмбеддера через `SentenceTransformer.save`).

> Логика построения `item_names` и гиперпараметры KNN — из ноутбука. KNN обучается на
> ПОЛНОМ `item_names` (для рабочей модели используем все данные; метрики меряет ноутбук,
> здесь замер не нужен). Это тот же алгоритм на том же источнике данных, без тюнинга.

- [ ] **Step 1: Создать `app/train_classifier.py`**

```python
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
```

- [ ] **Step 2: Запустить обучение (создать артефакты)**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python train_classifier.py'
```
Expected: печатает число примеров, прогресс-бар эмбеддинга (займёт 1–3 минуты), затем `сохранено: .../category1_knn.joblib` и `сохранено: .../e5-small-en-ru`. Таймаут команды — 600000 мс.

- [ ] **Step 3: Проверить артефакты**

Run:
```bash
ls -la /Users/maxos/PythonProjects/LSH/_project/samokat/app/models/
ls /Users/maxos/PythonProjects/LSH/_project/samokat/app/models/e5-small-en-ru/ | head
```
Expected: есть `category1_knn.joblib` (десятки МБ) и каталог `e5-small-en-ru/` с файлами модели.

- [ ] **Step 4: Commit** (артефакты игнорируются — коммитим только скрипт)

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/train_classifier.py
git commit -m "feat: офлайн-скрипт обучения KNN-классификатора категории"
```

---

## Task 4: Классификатор — `pipeline/classifier.py`

**Files:**
- Create: `app/backend/pipeline/classifier.py`
- Test: `app/tests/test_classifier.py`

**Interfaces:**
- Consumes: `CategoryScore` из `backend.models`; артефакты из `app/models/`.
- Produces:
  - `preprocess_query(text: str) -> str` — `lower` + удаление всего кроме букв/пробела/дефиса (`\p{L}` через `regex`).
  - `CategoryClassifier(model_dir: Path)`; метод `predict_top(query: str, k: int = 3) -> list[CategoryScore]` (сортировка по убыванию score).
  - Если артефактов нет — конструктор кидает `RuntimeError` с подсказкой про `train_classifier.py`.

- [ ] **Step 1: Написать тест `app/tests/test_classifier.py`**

```python
from pathlib import Path

import pytest

from backend.models import CategoryScore
from backend.pipeline.classifier import CategoryClassifier, preprocess_query

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
HAS_ARTIFACT = (MODELS_DIR / "category1_knn.joblib").exists() and (
    MODELS_DIR / "e5-small-en-ru"
).exists()


def test_preprocess_lowercases_and_strips_punct():
    assert preprocess_query("Кока-Кола 2л!!!") == "кока-кола л"


def test_preprocess_keeps_spaces_and_hyphen():
    assert preprocess_query("сок  апельсин-манго") == "сок  апельсин-манго"


@pytest.mark.skipif(not HAS_ARTIFACT, reason="нет артефакта модели (запусти train_classifier.py)")
def test_predict_top_returns_three_sorted():
    clf = CategoryClassifier(MODELS_DIR)
    result = clf.predict_top("кока кола", k=3)
    assert len(result) == 3
    assert all(isinstance(c, CategoryScore) for c in result)
    assert result[0].score >= result[1].score >= result[2].score


def test_missing_artifacts_raise(tmp_path):
    with pytest.raises(RuntimeError, match="train_classifier"):
        CategoryClassifier(tmp_path)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_classifier.py -v'
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.pipeline.classifier'`.

- [ ] **Step 3: Реализовать `app/backend/pipeline/classifier.py`**

```python
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
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_classifier.py -v'
```
Expected: PASS (4 passed — артефакт создан в Task 3, smoke реально прогоняется).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/pipeline/classifier.py app/tests/test_classifier.py
git commit -m "feat: классификатор категории (эмбеддер + KNN) с предобработкой"
```

---

## Task 5: Эндпоинт `/api/analyze`

**Files:**
- Modify: `app/backend/main.py`
- Test: `app/tests/test_api.py` (дополнить)

**Interfaces:**
- Consumes: `SymSpellCorrector`, `CategoryClassifier`; `CorrectRequest`, `AnalyzeResponse`, `CategoryScore`, `WordCorrection`.
- Produces:
  - `POST /api/analyze` (тело `CorrectRequest`) → `AnalyzeResponse` (исправление + топ-3 категории по исправленному запросу).
  - Классификатор грузится в lifespan **graceful**: при ошибке загрузки сервер стартует, `app.state.classifier = None`, а `/api/analyze` отвечает 503 `{"error": ...}`.

- [ ] **Step 1: Дописать тесты в конец `app/tests/test_api.py`**

```python
from pathlib import Path

import pytest

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
HAS_ARTIFACT = (MODELS_DIR / "category1_knn.joblib").exists() and (
    MODELS_DIR / "e5-small-en-ru"
).exists()


@pytest.mark.skipif(not HAS_ARTIFACT, reason="нет артефакта модели (запусти train_classifier.py)")
def test_analyze_endpoint_returns_correction_and_categories():
    with TestClient(app) as client:
        resp = client.post("/api/analyze", json={"query": "кока кола"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["original"] == "кока кола"
    assert "corrected" in body
    assert len(body["words"]) == 2
    assert len(body["categories"]) == 3
    assert body["categories"][0]["score"] >= body["categories"][1]["score"]


@pytest.mark.skipif(not HAS_ARTIFACT, reason="нет артефакта модели (запусти train_classifier.py)")
def test_analyze_rejects_empty_query():
    with TestClient(app) as client:
        resp = client.post("/api/analyze", json={"query": ""})
    assert resp.status_code == 422
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_api.py -v'
```
Expected: FAIL — `404 Not Found` для `/api/analyze` (эндпоинта ещё нет).

- [ ] **Step 3: Обновить `app/backend/main.py`** — заменить содержимое на:

```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.models import (
    AnalyzeResponse,
    CategoryScore,
    CorrectRequest,
    CorrectResponse,
    WordCorrection,
)
from backend.pipeline.classifier import CategoryClassifier
from backend.pipeline.corrector import SymSpellCorrector

BASE_DIR = Path(__file__).resolve().parent          # .../app/backend
PROJECT_ROOT = BASE_DIR.parents[1]                  # .../samokat
FRONTEND_DIR = BASE_DIR.parent / "frontend"         # .../app/frontend
MODELS_DIR = BASE_DIR.parent / "models"             # .../app/models
DICT_PATH = PROJECT_ROOT / "data" / "domain_dictionary.txt"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.corrector = SymSpellCorrector(DICT_PATH)
    try:
        app.state.classifier = CategoryClassifier(MODELS_DIR)
        app.state.classifier_error = None
    except Exception as exc:  # noqa: BLE001 — сервис поднимаем без классификатора
        app.state.classifier = None
        app.state.classifier_error = str(exc)
    yield


app = FastAPI(title="Исправление опечаток и категория", lifespan=lifespan)


@app.post("/api/correct", response_model=CorrectResponse)
async def correct(req: CorrectRequest, request: Request) -> CorrectResponse:
    corrector: SymSpellCorrector = request.app.state.corrector
    try:
        words: list[WordCorrection] = corrector.correct(req.query)
    except Exception as exc:  # noqa: BLE001 — отдаём понятную ошибку фронту
        return JSONResponse(status_code=500, content={"error": str(exc)})
    corrected = " ".join(w.corrected for w in words)
    return CorrectResponse(original=req.query, corrected=corrected, words=words)


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(req: CorrectRequest, request: Request):
    corrector: SymSpellCorrector = request.app.state.corrector
    classifier: CategoryClassifier | None = request.app.state.classifier
    if classifier is None:
        return JSONResponse(
            status_code=503,
            content={"error": request.app.state.classifier_error or "классификатор недоступен"},
        )
    try:
        words: list[WordCorrection] = corrector.correct(req.query)
        corrected = " ".join(w.corrected for w in words)
        categories: list[CategoryScore] = classifier.predict_top(corrected, k=3)
    except Exception as exc:  # noqa: BLE001 — отдаём понятную ошибку фронту
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return AnalyzeResponse(
        original=req.query, corrected=corrected, words=words, categories=categories
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
```

- [ ] **Step 4: Запустить весь набор тестов**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest -q'
```
Expected: PASS — все тесты (модели, корректор, классификатор, api, включая `/api/analyze`).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/main.py app/tests/test_api.py
git commit -m "feat: эндпоинт /api/analyze с классификацией топ-3 категорий"
```

---

## Task 6: Фронтенд — блок «Категории»

**Files:**
- Modify: `app/frontend/index.html`
- Modify: `app/frontend/style.css`
- Modify: `app/frontend/app.js`

**Interfaces:**
- Consumes: `POST /api/analyze` → `{original, corrected, words, categories: [{name, score}]}`.
- Produces: страница показывает исправление и топ-3 категории.

- [ ] **Step 1: Добавить блок в `app/frontend/index.html`** — вставить сразу после закрывающего `</section>` блока `result` (перед `<p id="error" ...>`):

```html
    <section id="categories" class="categories" hidden>
      <span class="label">Категории</span>
      <ol id="category-list" class="category-list"></ol>
    </section>
```

- [ ] **Step 2: Добавить стили в конец `app/frontend/style.css`**

```css
.categories { margin-top: 20px; }

.category-list {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.category {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 16px;
}

.category-main {
  border-color: var(--accent);
  background: #fff5f6;
  font-weight: 600;
}

.category-score { color: var(--muted); font-size: 14px; }
```

- [ ] **Step 3: Обновить `app/frontend/app.js`** — заменить содержимое на:

```javascript
const form = document.getElementById("form");
const queryInput = document.getElementById("query");
const submitButton = document.getElementById("submit");
const resultBlock = document.getElementById("result");
const originalEl = document.getElementById("original");
const correctedEl = document.getElementById("corrected");
const categoriesBlock = document.getElementById("categories");
const categoryList = document.getElementById("category-list");
const errorEl = document.getElementById("error");

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
  resultBlock.hidden = true;
  categoriesBlock.hidden = true;
}

function renderCorrection(data) {
  originalEl.textContent = data.original;
  correctedEl.replaceChildren();
  data.words.forEach((word, index) => {
    if (index > 0) correctedEl.append(" ");
    const span = document.createElement("span");
    span.textContent = word.corrected;
    if (word.changed) span.className = "word-changed";
    correctedEl.append(span);
  });
  resultBlock.hidden = false;
}

function renderCategories(categories) {
  categoryList.replaceChildren();
  categories.forEach((cat, index) => {
    const li = document.createElement("li");
    li.className = index === 0 ? "category category-main" : "category";
    const name = document.createElement("span");
    name.className = "category-name";
    name.textContent = cat.name;
    const score = document.createElement("span");
    score.className = "category-score";
    score.textContent = Math.round(cat.score * 100) + "%";
    li.append(name, score);
    categoryList.append(li);
  });
  categoriesBlock.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;

  submitButton.disabled = true;
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "Не удалось обработать запрос");
      return;
    }
    errorEl.hidden = true;
    renderCorrection(data);
    renderCategories(data.categories);
  } catch (err) {
    showError("Сеть недоступна: " + err.message);
  } finally {
    submitButton.disabled = false;
  }
});
```

- [ ] **Step 4: Прогнать все тесты — ничего не сломалось**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest -q'
```
Expected: PASS (все тесты).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/frontend/index.html app/frontend/style.css app/frontend/app.js
git commit -m "feat: фронтенд — блок топ-3 категорий"
```

---

## Task 7: Ручная проверка и README

**Files:**
- Modify: `app/README.md`

**Interfaces:**
- Consumes: всё приложение.
- Produces: обновлённая инструкция; подтверждение живого пайплайна.

- [ ] **Step 1: Обновить `app/README.md`** — заменить содержимое на:

````markdown
# Веб-приложение «Исправление опечаток + категория»

Демо пайплайна: запрос → исправление опечаток → топ-3 категории верхнего уровня.

## Подготовка модели (разово)

Обучить классификатор и сохранить артефакты в `app/models/` (в git не коммитятся):

```bash
source /Users/maxos/PythonProjects/LSH/.venv/bin/activate
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
python train_classifier.py
```

## Запуск

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
uvicorn backend.main:app --reload
```

Открыть http://127.0.0.1:8000

Без артефактов сервер стартует, но `/api/analyze` вернёт 503 — сначала выполни шаг подготовки.

## Тесты

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
python -m pytest -v
```

## Структура

- `train_classifier.py` — офлайн-обучение KNN, сохранение артефактов.
- `backend/pipeline/corrector.py` — исправление опечаток (SymSpell).
- `backend/pipeline/classifier.py` — эмбеддер + KNN, топ-3 категории.
- `backend/main.py` — FastAPI: `/api/correct`, `/api/analyze`, раздача фронтенда.
- `frontend/` — статическая страница.

Данные: `samokat/DATA.csv`, словарь `samokat/data/domain_dictionary.txt`.
````

- [ ] **Step 2: Поднять сервер и проверить пайплайн**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/uvicorn backend.main:app --port 8000 --log-level warning' &
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ 2>/dev/null)
  [ "$code" = "200" ] && break
  sleep 1
done
echo "=== /api/analyze ==="
curl -s -X POST http://127.0.0.1:8000/api/analyze -H "Content-Type: application/json" -d '{"query":"кока кола"}'
echo
pkill -f "uvicorn backend.main:app"
```
Expected: JSON с полями `original`, `corrected`, `words`, `categories` (3 элемента, у первого наибольший `score`). Таймаут — 120000 мс.

- [ ] **Step 3: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/README.md
git commit -m "docs: README обновлён под классификатор категории"
```

---

## Self-Review (выполнено при написании плана)

- **Покрытие спеки:** артефакты/gitignore (Task 1), модели `CategoryScore`/`AnalyzeResponse` (Task 2), офлайн-обучение (Task 3), `preprocess_query` + `CategoryClassifier.predict_top` топ-3 (Task 4), `/api/analyze` + graceful classifier (Task 5), блок топ-3 на фронте (Task 6), ручная проверка + README (Task 7).
- **Заглушек нет:** весь код приведён целиком.
- **Согласованность типов:** `CategoryScore(name, score)`, `predict_top(query, k=3) -> list[CategoryScore]`, `AnalyzeResponse(original, corrected, words, categories)`, эндпоинт `/api/analyze` — имена совпадают в задачах, тестах и на фронте (`data.categories`, `cat.name`, `cat.score`).
- **Отклонение от спеки:** классификатор грузится graceful (сервер не падает без артефакта, `/api/analyze` → 503) — надёжнее для тестов и запуска шага опечаток; функциональность классификации не меняется.
