# Сетка релевантных товаров через ESCI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в веб-приложение сетку релевантных товаров: по самой уверенной категории берём случайные товары каталога, размечаем их классификатором ESCI и показываем только `E` (≤16).

**Architecture:** `ProductCatalog` держит каталог из `DATA.csv` в памяти (индекс category1 → товары, без `final_answer`). `RelevanceClassifier` — адаптер над модулем `esci_classifier_module`. Новый эндпоинт `/api/products` пересчитывает исправление+категорию и добирает `E`-товары партиями до лимитов. Фронт вызывает его вторым запросом с лоадером.

**Tech Stack:** Python 3.12, FastAPI, pandas, `esci_classifier_module` (e5 + sklearn), vanilla HTML/CSS/JS.

## Global Constraints

- Python **3.12**, venv: `/Users/maxos/PythonProjects/LSH/.venv`. Пакеты — только в этот venv, НИКОГДА не глобально.
- Всё в `samokat/app/`. Ветка `app/typo-correction-web`.
- **`final_answer` из `DATA.csv` НЕ используем** — только каталог (`item_name`, `category1_name`, `category4_name`). Релевантность предсказываем `predict_esci`.
- Модуль ESCI: `samokat/esci/esci_classifier_module/`, интерфейс `predict_esci(query: str, item_name: str) -> str` ∈ {`E`,`S`,`C`,`I`}. Модуль **не меняем**, в git не коммитим.
- Лимиты: `GRID_SIZE = 16`, `CAP = 60`, `BATCH = 20`.
- Каталог `DATA.csv` — корень `samokat/`; колонки `query,item_name,item_id,final_answer,category4_name,category3_name,category2_name,category1_name`; `category4_name` без пропусков.
- Строгая типизация, pydantic вместо dict. Бэкенд не зависит от фронтенда.
- Удаление файлов — только `trash`. Git-команды — из корня `samokat/`. Тесты запускать из `app/` через `sh -c 'cd .../app && ...python -m pytest'`.

---

## File Structure

```
samokat/app/
├── backend/
│   ├── main.py                 # + /api/products; catalog + relevance в lifespan (relevance graceful)
│   ├── models.py               # + Product, ProductsResponse
│   └── pipeline/
│       ├── catalog.py          # НОВОЕ: ProductCatalog
│       └── relevance.py        # НОВОЕ: RelevanceClassifier (адаптер над predict_esci)
├── frontend/
│   ├── index.html              # + блок «Товары»
│   ├── style.css               # + стили сетки/карточек/лоадера
│   └── app.js                  # после /api/analyze — запрос /api/products, рендер сетки
└── tests/
    ├── test_catalog.py         # НОВОЕ
    └── test_api.py             # + тест /api/products
```

---

## Task 1: Модели Product и ProductsResponse

**Files:**
- Modify: `app/backend/models.py`
- Test: `app/tests/test_models.py` (дополнить)

**Interfaces:**
- Consumes: —
- Produces:
  - `Product(BaseModel)` — `item_name: str`, `category4: str | None = None`.
  - `ProductsResponse(BaseModel)` — `category: str`, `products: list[Product]`, `scanned: int`, `reached_cap: bool`.

- [ ] **Step 1: Дописать тесты в конец `app/tests/test_models.py`**

```python
def test_product_defaults_category4_none():
    from backend.models import Product

    p = Product(item_name="Молоко 3.2%")
    assert p.item_name == "Молоко 3.2%"
    assert p.category4 is None


def test_products_response_fields():
    from backend.models import Product, ProductsResponse

    resp = ProductsResponse(
        category="молочная продукция",
        products=[Product(item_name="Молоко", category4="молоко питьевое")],
        scanned=23,
        reached_cap=False,
    )
    assert resp.category == "молочная продукция"
    assert resp.products[0].category4 == "молоко питьевое"
    assert resp.scanned == 23
    assert resp.reached_cap is False
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_models.py -q'
```
Expected: FAIL — `ImportError: cannot import name 'Product'`.

- [ ] **Step 3: Дописать модели в конец `app/backend/models.py`**

```python
class Product(BaseModel):
    item_name: str
    category4: str | None = None


class ProductsResponse(BaseModel):
    category: str
    products: list[Product]
    scanned: int
    reached_cap: bool
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_models.py -q'
```
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/models.py app/tests/test_models.py
git commit -m "feat: pydantic-модели Product и ProductsResponse"
```

---

## Task 2: Каталог товаров — `pipeline/catalog.py`

**Files:**
- Create: `app/backend/pipeline/catalog.py`
- Test: `app/tests/test_catalog.py`

**Interfaces:**
- Consumes: `Product` из `backend.models`; `DATA.csv`.
- Produces:
  - `ProductCatalog(data_path: Path)` — индекс `category1_name → list[Product]` (без `final_answer`).
  - `has_category(self, category: str) -> bool`.
  - `sample(self, category: str, count: int, exclude: set[str]) -> list[Product]` — до `count` случайных товаров категории, `item_name` которых не в `exclude`.

- [ ] **Step 1: Написать тест `app/tests/test_catalog.py`**

```python
from pathlib import Path

from backend.catalog_testdata import write_sample_csv  # создаётся в Step 3
from backend.models import Product
from backend.pipeline.catalog import ProductCatalog


def _make_catalog(tmp_path: Path) -> ProductCatalog:
    csv_path = tmp_path / "mini.csv"
    write_sample_csv(csv_path)
    return ProductCatalog(csv_path)


def test_sample_returns_products_of_category(tmp_path):
    cat = _make_catalog(tmp_path)
    items = cat.sample("напитки", count=10, exclude=set())
    names = {p.item_name for p in items}
    assert names == {"кола", "сок", "вода"}
    assert all(isinstance(p, Product) for p in items)


def test_sample_respects_exclude(tmp_path):
    cat = _make_catalog(tmp_path)
    items = cat.sample("напитки", count=10, exclude={"кола", "сок"})
    assert {p.item_name for p in items} == {"вода"}


def test_sample_count_limits_size(tmp_path):
    cat = _make_catalog(tmp_path)
    items = cat.sample("напитки", count=2, exclude=set())
    assert len(items) == 2


def test_has_category(tmp_path):
    cat = _make_catalog(tmp_path)
    assert cat.has_category("напитки") is True
    assert cat.has_category("мебель") is False


def test_final_answer_not_used_for_membership(tmp_path):
    # В мини-CSV товар "вода" помечен final_answer='i', но он ДОЛЖЕН попадать
    # в выборку категории — разметка не влияет на каталог.
    cat = _make_catalog(tmp_path)
    names = {p.item_name for p in cat.sample("напитки", count=10, exclude=set())}
    assert "вода" in names


def test_category4_carried(tmp_path):
    cat = _make_catalog(tmp_path)
    by_name = {p.item_name: p for p in cat.sample("напитки", count=10, exclude=set())}
    assert by_name["кола"].category4 == "газировка"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_catalog.py -q'
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.catalog_testdata'`.

- [ ] **Step 3: Создать хелпер тестовых данных `app/backend/catalog_testdata.py`**

```python
from pathlib import Path

_SAMPLE_ROWS = """query,item_name,item_id,final_answer,category4_name,category3_name,category2_name,category1_name
кола,кола,1,e,газировка,,,напитки
кола,кола,1,e,газировка,,,напитки
сок,сок,2,s,соки,,,напитки
вода,вода,3,i,вода питьевая,,,напитки
стул,стул,4,e,стулья,,,мебель
"""


def write_sample_csv(path: Path) -> None:
    path.write_text(_SAMPLE_ROWS, encoding="utf-8")
```

- [ ] **Step 4: Реализовать `app/backend/pipeline/catalog.py`**

```python
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
```

- [ ] **Step 5: Запустить — убедиться, что проходит**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_catalog.py -q'
```
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/pipeline/catalog.py app/backend/catalog_testdata.py app/tests/test_catalog.py
git commit -m "feat: ProductCatalog (каталог из DATA.csv без final_answer)"
```

---

## Task 3: Классификатор релевантности — `pipeline/relevance.py`

**Files:**
- Create: `app/backend/pipeline/relevance.py`
- Test: `app/tests/test_relevance.py`

**Interfaces:**
- Consumes: модуль `samokat/esci/esci_classifier_module` (`predict_esci`).
- Produces:
  - `RelevanceClassifier(module_parent: Path)` — добавляет `module_parent` в `sys.path`, импортирует `predict_esci` (тяжёлая загрузка один раз); при отсутствии модуля — `RuntimeError`.
  - `predict(self, query: str, item_name: str) -> str`.
  - `is_exact(self, query: str, item_name: str) -> bool` — `predict(...) == "E"`.

- [ ] **Step 1: Написать тест `app/tests/test_relevance.py`**

```python
from pathlib import Path

import pytest

from backend.pipeline.relevance import RelevanceClassifier

ESCI_PARENT = Path(__file__).resolve().parents[2] / "esci"
HAS_MODULE = (ESCI_PARENT / "esci_classifier_module" / "predict_esci.py").exists()


def test_missing_module_raises(tmp_path):
    with pytest.raises(RuntimeError, match="esci_classifier_module"):
        RelevanceClassifier(tmp_path)


@pytest.mark.skipif(not HAS_MODULE, reason="нет модуля ESCI")
def test_exact_and_irrelevant():
    clf = RelevanceClassifier(ESCI_PARENT)
    assert clf.is_exact("малако", "Молоко Домик в деревне 3.2%, 900 мл") is True
    assert clf.is_exact("малако", "Кроссовки Nike беговые") is False
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_relevance.py -q'
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.pipeline.relevance'`.

- [ ] **Step 3: Реализовать `app/backend/pipeline/relevance.py`**

```python
import sys
from pathlib import Path


class RelevanceClassifier:
    """Адаптер над модулем esci_classifier_module (модуль не меняем)."""

    def __init__(self, module_parent: Path) -> None:
        module_dir = module_parent / "esci_classifier_module"
        if not (module_dir / "predict_esci.py").exists():
            raise RuntimeError(
                f"Модуль esci_classifier_module не найден в {module_parent}."
            )
        parent = str(module_parent.resolve())
        if parent not in sys.path:
            sys.path.insert(0, parent)
        from esci_classifier_module.predict_esci import predict_esci

        self._predict_esci = predict_esci

    def predict(self, query: str, item_name: str) -> str:
        return self._predict_esci(query, item_name)

    def is_exact(self, query: str, item_name: str) -> bool:
        return self.predict(query, item_name) == "E"
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && TOKENIZERS_PARALLELISM=false /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_relevance.py -q'
```
Expected: PASS (2 passed — загрузка модуля ~8 с).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/pipeline/relevance.py app/tests/test_relevance.py
git commit -m "feat: RelevanceClassifier (адаптер над predict_esci)"
```

---

## Task 4: Эндпоинт `/api/products`

**Files:**
- Modify: `app/backend/main.py`
- Test: `app/tests/test_api.py` (дополнить)

**Interfaces:**
- Consumes: `SymSpellCorrector`, `CategoryClassifier`, `ProductCatalog`, `RelevanceClassifier`; `CorrectRequest`, `Product`, `ProductsResponse`.
- Produces:
  - `POST /api/products` (тело `CorrectRequest`) → `ProductsResponse`.
  - `catalog` и `relevance` в lifespan; `relevance` — graceful (нет модуля → `app.state.relevance = None`, эндпоинт 503).
  - Константы `GRID_SIZE = 16`, `CAP = 60`, `BATCH = 20`.

- [ ] **Step 1: Дописать тесты в конец `app/tests/test_api.py`**

```python
ESCI_PARENT = Path(__file__).resolve().parents[2] / "esci"
HAS_ESCI = (ESCI_PARENT / "esci_classifier_module" / "predict_esci.py").exists()


@pytest.mark.skipif(not (HAS_ARTIFACT and HAS_ESCI), reason="нет артефакта категории или модуля ESCI")
def test_products_endpoint_returns_grid():
    with TestClient(app) as client:
        resp = client.post("/api/products", json={"query": "малако"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"]
    assert isinstance(body["products"], list)
    assert len(body["products"]) <= 16
    assert body["scanned"] <= 60
    assert isinstance(body["reached_cap"], bool)
    for p in body["products"]:
        assert "item_name" in p
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && TOKENIZERS_PARALLELISM=false /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_api.py::test_products_endpoint_returns_grid -q'
```
Expected: FAIL — `404 Not Found` (эндпоинта ещё нет).

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
    Product,
    ProductsResponse,
    WordCorrection,
)
from backend.pipeline.catalog import ProductCatalog
from backend.pipeline.classifier import CategoryClassifier
from backend.pipeline.corrector import SymSpellCorrector
from backend.pipeline.relevance import RelevanceClassifier

BASE_DIR = Path(__file__).resolve().parent          # .../app/backend
PROJECT_ROOT = BASE_DIR.parents[1]                  # .../samokat
FRONTEND_DIR = BASE_DIR.parent / "frontend"         # .../app/frontend
MODELS_DIR = BASE_DIR.parent / "models"             # .../app/models
DICT_PATH = PROJECT_ROOT / "data" / "domain_dictionary.txt"
DATA_PATH = PROJECT_ROOT / "DATA.csv"
ESCI_PARENT = PROJECT_ROOT / "esci"

GRID_SIZE = 16
CAP = 60
BATCH = 20


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.corrector = SymSpellCorrector(DICT_PATH)
    try:
        app.state.classifier = CategoryClassifier(MODELS_DIR)
        app.state.classifier_error = None
    except Exception as exc:  # noqa: BLE001
        app.state.classifier = None
        app.state.classifier_error = str(exc)
    app.state.catalog = ProductCatalog(DATA_PATH)
    try:
        app.state.relevance = RelevanceClassifier(ESCI_PARENT)
        app.state.relevance_error = None
    except Exception as exc:  # noqa: BLE001
        app.state.relevance = None
        app.state.relevance_error = str(exc)
    yield


app = FastAPI(title="Поиск: опечатки, категория, товары", lifespan=lifespan)


def _correct_query(corrector: SymSpellCorrector, query: str) -> tuple[str, list[WordCorrection]]:
    words = corrector.correct(query)
    return " ".join(w.corrected for w in words), words


@app.post("/api/correct", response_model=CorrectResponse)
async def correct(req: CorrectRequest, request: Request) -> CorrectResponse:
    corrector: SymSpellCorrector = request.app.state.corrector
    try:
        corrected, words = _correct_query(corrector, req.query)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
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
        corrected, words = _correct_query(corrector, req.query)
        categories: list[CategoryScore] = classifier.predict_top(corrected, k=3)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return AnalyzeResponse(
        original=req.query, corrected=corrected, words=words, categories=categories
    )


@app.post("/api/products", response_model=ProductsResponse)
async def products(req: CorrectRequest, request: Request):
    corrector: SymSpellCorrector = request.app.state.corrector
    classifier: CategoryClassifier | None = request.app.state.classifier
    catalog: ProductCatalog = request.app.state.catalog
    relevance: RelevanceClassifier | None = request.app.state.relevance
    if classifier is None:
        return JSONResponse(
            status_code=503,
            content={"error": request.app.state.classifier_error or "классификатор недоступен"},
        )
    if relevance is None:
        return JSONResponse(
            status_code=503,
            content={"error": request.app.state.relevance_error or "модуль ESCI недоступен"},
        )
    try:
        corrected, _ = _correct_query(corrector, req.query)
        category = classifier.predict_top(corrected, k=3)[0].name

        selected: list[Product] = []
        seen: set[str] = set()
        scanned = 0
        while len(selected) < GRID_SIZE and scanned < CAP:
            batch = catalog.sample(category, BATCH, exclude=seen)
            if not batch:
                break
            for product in batch:
                seen.add(product.item_name)
                scanned += 1
                if relevance.is_exact(corrected, product.item_name):
                    selected.append(product)
                    if len(selected) >= GRID_SIZE:
                        break
                if scanned >= CAP:
                    break
        reached_cap = scanned >= CAP and len(selected) < GRID_SIZE
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return ProductsResponse(
        category=category, products=selected, scanned=scanned, reached_cap=reached_cap
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
```

- [ ] **Step 4: Запустить весь набор тестов**

Run:
```bash
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && TOKENIZERS_PARALLELISM=false /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest -q'
```
Expected: PASS — все тесты (модели, корректор, классификатор, каталог, релевантность, api, включая `/api/products`).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/main.py app/tests/test_api.py
git commit -m "feat: эндпоинт /api/products — сетка E-товаров через ESCI"
```

---

## Task 5: Фронтенд — сетка товаров

**Files:**
- Modify: `app/frontend/index.html`
- Modify: `app/frontend/style.css`
- Modify: `app/frontend/app.js`

**Interfaces:**
- Consumes: `POST /api/products` → `{category, products: [{item_name, category4}], scanned, reached_cap}`.
- Produces: блок «Товары» с лоадером и сеткой (≤16 карточек).

- [ ] **Step 1: Добавить блок в `app/frontend/index.html`** — вставить сразу после закрывающего `</section>` блока `categories` (перед `<p id="error" ...>`):

```html
    <section id="products" class="products" hidden>
      <span class="label">Товары</span>
      <p id="products-status" class="products-status"></p>
      <div id="product-grid" class="product-grid"></div>
    </section>
```

- [ ] **Step 2: Добавить стили в конец `app/frontend/style.css`**

```css
.products { margin-top: 20px; }

.products-status { margin: 8px 0 12px; color: var(--muted); font-size: 14px; }

.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}

.product-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  background: #fff;
}

.product-name { font-size: 14px; font-weight: 600; line-height: 1.3; }

.product-cat { margin-top: 6px; color: var(--muted); font-size: 12px; }
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
const productsBlock = document.getElementById("products");
const productsStatus = document.getElementById("products-status");
const productGrid = document.getElementById("product-grid");
const errorEl = document.getElementById("error");

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
  resultBlock.hidden = true;
  categoriesBlock.hidden = true;
  productsBlock.hidden = true;
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

function renderProducts(data) {
  productGrid.replaceChildren();
  if (data.products.length === 0) {
    productsStatus.textContent = "Релевантных товаров не найдено";
    return;
  }
  productsStatus.textContent = data.reached_cap
    ? "Показаны все найденные релевантные"
    : `Найдено релевантных: ${data.products.length}`;
  data.products.forEach((p) => {
    const card = document.createElement("div");
    card.className = "product-card";
    const name = document.createElement("div");
    name.className = "product-name";
    name.textContent = p.item_name;
    card.append(name);
    if (p.category4) {
      const cat = document.createElement("div");
      cat.className = "product-cat";
      cat.textContent = p.category4;
      card.append(cat);
    }
    productGrid.append(card);
  });
}

async function fetchProducts(query) {
  productsBlock.hidden = false;
  productsStatus.textContent = "Подбираем товары…";
  productGrid.replaceChildren();
  try {
    const response = await fetch("/api/products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await response.json();
    if (!response.ok) {
      productsStatus.textContent = data.error || "Не удалось подобрать товары";
      return;
    }
    renderProducts(data);
  } catch (err) {
    productsStatus.textContent = "Сеть недоступна: " + err.message;
  }
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
    fetchProducts(query);
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
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && TOKENIZERS_PARALLELISM=false /Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest -q'
```
Expected: PASS (все тесты).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/frontend/index.html app/frontend/style.css app/frontend/app.js
git commit -m "feat: фронтенд — сетка релевантных товаров с лоадером"
```

---

## Task 6: Ручная проверка и README

**Files:**
- Modify: `app/README.md`

**Interfaces:**
- Consumes: всё приложение.
- Produces: обновлённая инструкция; подтверждение живого полного пайплайна.

- [ ] **Step 1: Обновить блок «Структура» и заголовок в `app/README.md`** — заменить строку заголовка `# ...` на:

```markdown
# Веб-приложение «Опечатки → категория → товары»
```

и заменить список в разделе `## Структура` на:

```markdown
- `train_classifier.py` — офлайн-обучение KNN, сохранение артефактов.
- `backend/pipeline/corrector.py` — исправление опечаток (SymSpell).
- `backend/pipeline/classifier.py` — эмбеддер + KNN, топ-3 категории.
- `backend/pipeline/catalog.py` — каталог товаров из DATA.csv (без final_answer).
- `backend/pipeline/relevance.py` — разметка релевантности через esci_classifier_module.
- `backend/main.py` — FastAPI: `/api/correct`, `/api/analyze`, `/api/products`, раздача фронтенда.
- `frontend/` — статическая страница (исправление, категории, сетка товаров).

Данные: `samokat/DATA.csv`, словарь `samokat/data/domain_dictionary.txt`,
модуль релевантности: `samokat/esci/esci_classifier_module/` (не в git).
```

- [ ] **Step 2: Поднять сервер и проверить полный пайплайн**

Run:
```bash
pkill -f "uvicorn backend.main:app" 2>/dev/null; sleep 1
sh -c 'cd /Users/maxos/PythonProjects/LSH/_project/samokat/app && TOKENIZERS_PARALLELISM=false /Users/maxos/PythonProjects/LSH/.venv/bin/uvicorn backend.main:app --port 8000 --log-level warning' >/tmp/uvicorn_app.log 2>&1 &
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ 2>/dev/null)
  [ "$code" = "200" ] && break
  sleep 1
done
echo "=== /api/products (малако) ==="
curl -s -X POST http://127.0.0.1:8000/api/products -H "Content-Type: application/json" -d '{"query":"малако"}'
```
Expected: JSON с `category` (напр. «молочная продукция»), `products` (≤16, каждый с `item_name` и `category4`), `scanned` (≤60), `reached_cap`. Сервер НЕ останавливать (оставить для просмотра). Таймаут — 180000 мс.

- [ ] **Step 3: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/README.md
git commit -m "docs: README — полный пайплайн опечатки/категория/товары"
```

---

## Self-Review (выполнено при написании плана)

- **Покрытие спеки:** модели `Product`/`ProductsResponse` (Task 1), `ProductCatalog` без `final_answer` (Task 2), `RelevanceClassifier` над `predict_esci` (Task 3), `/api/products` с добором до 16/потолком 60 + graceful (Task 4), сетка+лоадер, второй запрос (Task 5), ручная проверка+README (Task 6).
- **Заглушек нет:** весь код приведён целиком, включая тестовый CSV-хелпер.
- **Согласованность типов:** `Product(item_name, category4)`, `ProductsResponse(category, products, scanned, reached_cap)`, `ProductCatalog.sample(category, count, exclude)`/`has_category`, `RelevanceClassifier.is_exact(query, item_name)`, лимиты `GRID_SIZE=16/CAP=60/BATCH=20`, эндпоинт `/api/products` — имена совпадают в задачах, тестах и на фронте (`data.products`, `p.item_name`, `p.category4`, `data.reached_cap`).
- **final_answer:** явно исключён в `usecols` каталога и проверяется тестом `test_final_answer_not_used_for_membership`.
