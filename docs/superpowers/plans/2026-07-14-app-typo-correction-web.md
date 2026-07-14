# Веб-приложение «Исправление опечаток» — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Веб-приложение: пользователь вводит поисковый запрос → видит исправленный запрос с подсветкой изменённых слов (демо для презентации мастерской).

**Architecture:** FastAPI-бэкенд раздаёт статический фронтенд и эндпоинт `POST /api/correct`. Логика исправления опечаток (присланный SymSpell-код) вынесена в `pipeline/corrector.py` без изменения самого алгоритма и не зависит от HTTP. Фронтенд — одна статическая страница на чистом HTML/CSS/JS.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, pydantic v2, symspellpy, marisa_trie; vanilla HTML/CSS/JS.

## Global Constraints

- Python **3.12**, venv: `/Users/maxos/PythonProjects/LSH/.venv`. Ставить пакеты только в этот venv, НИКОГДА не глобально.
- Всё приложение — в папке `samokat/app/`.
- Функцию-исправлятор (`correct_word_prefix`, `correct_query_prefix`) переносим из `samokat/typos/ispravlator.ipynb` **ДОСЛОВНО**. Алгоритм не улучшаем и не меняем.
- Словарь: `samokat/data/domain_dictionary.txt` (формат `слово частота`, разделитель — пробел).
- Строгая типизация (type hints везде), pydantic-модели вместо dict. Бэкенд-логика не зависит от фронтенда.
- Удаление файлов — только через `trash`, никогда `rm`.
- Команды git запускать из корня репозитория `samokat/`.

---

## File Structure

```
samokat/app/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI: lifespan-инициализация корректора, /api/correct, раздача фронта
│   ├── models.py               # pydantic: CorrectRequest, WordCorrection, CorrectResponse
│   └── pipeline/
│       ├── __init__.py
│       └── corrector.py        # функции исправлятора ДОСЛОВНО + init_corrector + класс SymSpellCorrector
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_corrector.py
│   └── test_api.py
├── requirements.txt
└── README.md
```

---

## Task 1: Зависимости и скелет проекта

**Files:**
- Create: `app/requirements.txt`
- Create: `app/backend/__init__.py` (пустой)
- Create: `app/backend/pipeline/__init__.py` (пустой)
- Create: `app/tests/__init__.py` (пустой)

**Interfaces:**
- Consumes: —
- Produces: установленные в venv пакеты `fastapi`, `uvicorn`, `symspellpy`, `marisa_trie`, `httpx`, `pytest`; структура пакетов `backend`, `backend.pipeline`, `tests`.

- [ ] **Step 1: Создать `app/requirements.txt`**

```
fastapi
uvicorn[standard]
pydantic>=2
symspellpy
marisa-trie
httpx
pytest
```

- [ ] **Step 2: Создать пустые `__init__.py`**

Создать три пустых файла: `app/backend/__init__.py`, `app/backend/pipeline/__init__.py`, `app/tests/__init__.py`.

- [ ] **Step 3: Установить зависимости в venv**

Run:
```bash
source /Users/maxos/PythonProjects/LSH/.venv/bin/activate
pip install -r /Users/maxos/PythonProjects/LSH/_project/samokat/app/requirements.txt
```
Expected: установка без ошибок; в конце `Successfully installed ... fastapi ... marisa-trie ... symspellpy ... uvicorn ...`.

- [ ] **Step 4: Проверить импорты**

Run:
```bash
/Users/maxos/PythonProjects/LSH/.venv/bin/python -c "import fastapi, uvicorn, symspellpy, marisa_trie, httpx, pytest; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/requirements.txt app/backend/__init__.py app/backend/pipeline/__init__.py app/tests/__init__.py
git commit -m "chore: скелет app и зависимости веб-приложения опечаток"
```

---

## Task 2: pydantic-модели

**Files:**
- Create: `app/backend/models.py`
- Test: `app/tests/test_models.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `WordCorrection(BaseModel)` с полями `original: str`, `corrected: str` и computed-полем `changed: bool` (`original != corrected`; `corrected` может содержать пробел при разбиении слипшихся слов).
  - `CorrectRequest(BaseModel)` с полем `query: str` (`min_length=1`).
  - `CorrectResponse(BaseModel)` с полями `original: str`, `corrected: str`, `words: list[WordCorrection]`.

- [ ] **Step 1: Написать падающий тест `app/tests/test_models.py`**

```python
import pytest
from pydantic import ValidationError

from backend.models import CorrectRequest, CorrectResponse, WordCorrection


def test_word_correction_changed_true_when_differs():
    wc = WordCorrection(original="кросчовки", corrected="кроссовки")
    assert wc.changed is True


def test_word_correction_changed_false_when_same():
    wc = WordCorrection(original="молоко", corrected="молоко")
    assert wc.changed is False


def test_word_correction_changed_in_dump():
    wc = WordCorrection(original="кросчовки", corrected="кроссовки")
    assert wc.model_dump()["changed"] is True


def test_correct_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        CorrectRequest(query="")


def test_correct_response_holds_words():
    resp = CorrectResponse(
        original="кросчовки",
        corrected="кроссовки",
        words=[WordCorrection(original="кросчовки", corrected="кроссовки")],
    )
    assert resp.words[0].corrected == "кроссовки"
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run:
```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
/Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.models'`.

- [ ] **Step 3: Реализовать `app/backend/models.py`**

```python
from pydantic import BaseModel, Field, computed_field


class WordCorrection(BaseModel):
    """Соответствие одного исходного слова его исправлению.

    `corrected` может содержать пробел, если корректор разбил слипшееся
    слово (например, "укропбатон" -> "укроп батон").
    """

    original: str
    corrected: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def changed(self) -> bool:
        return self.original != self.corrected


class CorrectRequest(BaseModel):
    query: str = Field(min_length=1)


class CorrectResponse(BaseModel):
    original: str
    corrected: str
    words: list[WordCorrection]
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run:
```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
/Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_models.py -v
```
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/models.py app/tests/test_models.py
git commit -m "feat: pydantic-модели запроса и ответа исправления опечаток"
```

---

## Task 3: Корректор (присланный код + удобный адаптер)

**Files:**
- Create: `app/backend/pipeline/corrector.py`
- Test: `app/tests/test_corrector.py`

**Interfaces:**
- Consumes: `WordCorrection` из `backend.models`; словарь `samokat/data/domain_dictionary.txt`.
- Produces:
  - `Protocol TypoCorrector` с методом `correct(self, query: str) -> list[WordCorrection]`.
  - `init_corrector(dict_path: Path) -> None` — однократная загрузка словаря/trie/SymSpell в глобальное состояние модуля.
  - `correct_word_prefix(word, max_edit_distance=2) -> str` и `correct_query_prefix(query, max_edit_distance=2) -> str` — ДОСЛОВНО из ноутбука.
  - `SymSpellCorrector` — класс, реализующий `TypoCorrector`; конструктор `SymSpellCorrector(dict_path: Path)`.

> ВАЖНО: тела `correct_word_prefix` и `correct_query_prefix` скопированы из
> `samokat/typos/ispravlator.ipynb` без единого изменения логики. Загрузка словаря
> вынесена в `init_corrector`, потому что в ноутбуке она была на уровне модуля —
> это переезд в файл, а не правка алгоритма.

- [ ] **Step 1: Написать падающий тест `app/tests/test_corrector.py`**

```python
from pathlib import Path

import pytest

from backend.models import WordCorrection
from backend.pipeline.corrector import SymSpellCorrector

DICT_PATH = Path(__file__).resolve().parents[2] / "data" / "domain_dictionary.txt"


@pytest.fixture(scope="module")
def corrector() -> SymSpellCorrector:
    return SymSpellCorrector(DICT_PATH)


def test_fixes_simple_typo(corrector: SymSpellCorrector):
    words = corrector.correct("крсовки")
    assert words == [WordCorrection(original="крсовки", corrected="кроссовки")]


def test_splits_glued_words(corrector: SymSpellCorrector):
    words = corrector.correct("укропбатон")
    assert words == [WordCorrection(original="укропбатон", corrected="укроп батон")]


def test_keeps_multiple_words_and_marks_changes(corrector: SymSpellCorrector):
    words = corrector.correct("крсовки молоко")
    assert len(words) == 2
    assert words[0].corrected == "кроссовки"
    assert words[0].changed is True
    assert words[1].original == "молоко"
    assert words[1].changed is False
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run:
```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
/Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_corrector.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.pipeline.corrector'`.

- [ ] **Step 3: Реализовать `app/backend/pipeline/corrector.py`**

```python
from collections import Counter
from pathlib import Path
from typing import Protocol

import marisa_trie
from symspellpy import SymSpell, Verbosity

from backend.models import WordCorrection

# --- глобальное состояние корректора (заполняется init_corrector) ---
word_freq: Counter = Counter()
dictionary: set[str] = set()
trie: marisa_trie.Trie | None = None
sym_spell: SymSpell | None = None

DISTANCE_PENALTY = 10


def init_corrector(dict_path: Path) -> None:
    """Однократная загрузка словаря, trie и SymSpell в глобальное состояние.

    Код перенесён из ispravlator.ipynb (в ноутбуке был на уровне модуля).
    """
    global word_freq, dictionary, trie, sym_spell

    word_freq = Counter()
    with open(dict_path, encoding="utf-8") as f:
        for line in f:
            term, _, count = line.rpartition(" ")
            if term:
                word_freq[term] = int(count)

    dictionary = set(word_freq)
    trie = marisa_trie.Trie(dictionary)

    sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    sym_spell.load_dictionary(str(dict_path), 0, 1, separator=' ', encoding='utf-8')


# --- функции-исправлятор: ДОСЛОВНО из ispravlator.ipynb, НЕ МЕНЯТЬ ---

def correct_word_prefix(word, max_edit_distance=2):
    if word in dictionary:
        return word

    if len(word) >= 2:
        completions = trie.keys(word)
        if completions:
            return max(completions, key=lambda w: word_freq.get(w, 0))

    candidates = sym_spell.lookup(word, Verbosity.ALL, max_edit_distance=max_edit_distance)
    if candidates:
        best = max(candidates, key=lambda s: s.count / (DISTANCE_PENALTY ** s.distance))
        return best.term

    segmentation = sym_spell.word_segmentation(word, max_edit_distance=max_edit_distance)
    parts = segmentation.corrected_string.split()
    if (
        len(parts) > 1
        and all(p in dictionary for p in parts)
        and segmentation.distance_sum <= max_edit_distance
        and all(word_freq.get(p, 0) >= 3 for p in parts)
    ):
        return segmentation.corrected_string

    return word


def correct_query_prefix(query, max_edit_distance=2):
    query = query.strip()
    words = query.split()
    return ' '.join(correct_word_prefix(w, max_edit_distance) for w in words)


# --- удобный интерфейс поверх присланного кода ---

class TypoCorrector(Protocol):
    def correct(self, query: str) -> list[WordCorrection]:
        ...


class SymSpellCorrector:
    """Адаптер: инициализирует корректор и отдаёт пословный маппинг.

    Логику исправления НЕ меняет — переиспользует correct_word_prefix
    по каждому слову (ровно как correct_query_prefix внутри),
    сохраняя соответствие исходное слово -> исправление для подсветки.
    """

    def __init__(self, dict_path: Path) -> None:
        init_corrector(dict_path)

    def correct(self, query: str) -> list[WordCorrection]:
        words = query.strip().split()
        return [
            WordCorrection(original=word, corrected=correct_word_prefix(word))
            for word in words
        ]
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run:
```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
/Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_corrector.py -v
```
Expected: PASS (3 passed). Первый прогон медленнее — грузится словарь.

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/pipeline/corrector.py app/tests/test_corrector.py
git commit -m "feat: корректор опечаток (код из ноутбука) с адаптером SymSpellCorrector"
```

---

## Task 4: FastAPI-приложение

**Files:**
- Create: `app/backend/main.py`
- Test: `app/tests/test_api.py`

**Interfaces:**
- Consumes: `SymSpellCorrector` из `backend.pipeline.corrector`; `CorrectRequest`, `CorrectResponse`, `WordCorrection` из `backend.models`.
- Produces:
  - FastAPI-инстанс `app`.
  - `GET /` → отдаёт `frontend/index.html`.
  - Статика фронтенда смонтирована на `/static` (файлы `frontend/style.css`, `frontend/app.js`).
  - `POST /api/correct` (тело `CorrectRequest`) → `CorrectResponse`; при исключении корректора → HTTP 500 с телом `{"error": "..."}`.
  - Корректор создаётся один раз в lifespan и хранится в `app.state.corrector`.

- [ ] **Step 1: Написать падающий тест `app/tests/test_api.py`**

```python
from fastapi.testclient import TestClient

from backend.main import app


def test_correct_endpoint_returns_words():
    with TestClient(app) as client:
        resp = client.post("/api/correct", json={"query": "крсовки молоко"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["original"] == "крсовки молоко"
    assert body["corrected"] == "кроссовки молоко"
    assert body["words"][0] == {
        "original": "крсовки",
        "corrected": "кроссовки",
        "changed": True,
    }
    assert body["words"][1]["changed"] is False


def test_correct_endpoint_rejects_empty_query():
    with TestClient(app) as client:
        resp = client.post("/api/correct", json={"query": ""})
    assert resp.status_code == 422


def test_root_serves_html():
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run:
```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
/Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_api.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.main'`.

- [ ] **Step 3: Реализовать `app/backend/main.py`**

```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.models import CorrectRequest, CorrectResponse, WordCorrection
from backend.pipeline.corrector import SymSpellCorrector

BASE_DIR = Path(__file__).resolve().parent          # .../app/backend
PROJECT_ROOT = BASE_DIR.parents[1]                  # .../samokat
FRONTEND_DIR = BASE_DIR.parent / "frontend"         # .../app/frontend
DICT_PATH = PROJECT_ROOT / "data" / "domain_dictionary.txt"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.corrector = SymSpellCorrector(DICT_PATH)
    yield


app = FastAPI(title="Исправление опечаток", lifespan=lifespan)


@app.post("/api/correct", response_model=CorrectResponse)
async def correct(req: CorrectRequest, request: Request) -> CorrectResponse:
    corrector: SymSpellCorrector = request.app.state.corrector
    try:
        words: list[WordCorrection] = corrector.correct(req.query)
    except Exception as exc:  # noqa: BLE001 — отдаём понятную ошибку фронту
        return JSONResponse(status_code=500, content={"error": str(exc)})
    corrected = " ".join(w.corrected for w in words)
    return CorrectResponse(original=req.query, corrected=corrected, words=words)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
```

- [ ] **Step 4: Создать заглушки фронтенда, чтобы `GET /` не падал в тестах**

Создать минимальный `app/frontend/index.html` (будет заменён в Task 5):

```html
<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Исправление опечаток</title></head>
<body></body></html>
```

- [ ] **Step 5: Запустить тесты — убедиться, что проходят**

Run:
```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
/Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest tests/test_api.py -v
```
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/backend/main.py app/tests/test_api.py app/frontend/index.html
git commit -m "feat: FastAPI-эндпоинт /api/correct и раздача фронтенда"
```

---

## Task 5: Фронтенд (страница + стили + логика)

**Files:**
- Modify: `app/frontend/index.html` (заменить заглушку из Task 4)
- Create: `app/frontend/style.css`
- Create: `app/frontend/app.js`

**Interfaces:**
- Consumes: `POST /api/correct` → `{original, corrected, words: [{original, corrected, changed}]}`; статика по `/static/style.css`, `/static/app.js`.
- Produces: рабочая страница демо. Тестируется вручную в Task 6.

- [ ] **Step 1: Заменить `app/frontend/index.html`**

```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Исправление опечаток</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <main class="card">
    <h1>Исправление опечаток</h1>
    <form id="form" class="form">
      <input id="query" class="input" type="text" placeholder="Введите поисковый запрос" autocomplete="off" autofocus>
      <button id="submit" class="button" type="submit">Проверить</button>
    </form>
    <section id="result" class="result" hidden>
      <div class="row"><span class="label">Запрос</span><span id="original" class="value"></span></div>
      <div class="row"><span class="label">Исправлено</span><span id="corrected" class="value"></span></div>
    </section>
    <p id="error" class="error" hidden></p>
  </main>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Создать `app/frontend/style.css`**

```css
:root {
  --bg: #f5f6f8;
  --card: #ffffff;
  --text: #1b1b1f;
  --muted: #6b7280;
  --accent: #ff3d57;
  --changed-bg: #fff0d6;
  --changed-text: #b45309;
  --border: #e5e7eb;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.card {
  width: min(560px, 92vw);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.06);
}

h1 { margin: 0 0 20px; font-size: 22px; }

.form { display: flex; gap: 10px; }

.input {
  flex: 1;
  padding: 12px 14px;
  font-size: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  outline: none;
}
.input:focus { border-color: var(--accent); }

.button {
  padding: 12px 18px;
  font-size: 16px;
  color: #fff;
  background: var(--accent);
  border: none;
  border-radius: 10px;
  cursor: pointer;
}
.button:disabled { opacity: 0.6; cursor: default; }

.result { margin-top: 24px; display: grid; gap: 12px; }

.row { display: grid; grid-template-columns: 96px 1fr; align-items: baseline; gap: 12px; }
.label { color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; }
.value { font-size: 18px; line-height: 1.5; }

.word-changed {
  background: var(--changed-bg);
  color: var(--changed-text);
  border-radius: 6px;
  padding: 1px 5px;
  font-weight: 600;
}

.error {
  margin-top: 16px;
  color: var(--accent);
  font-size: 14px;
}
```

- [ ] **Step 3: Создать `app/frontend/app.js`**

```javascript
const form = document.getElementById("form");
const queryInput = document.getElementById("query");
const submitButton = document.getElementById("submit");
const resultBlock = document.getElementById("result");
const originalEl = document.getElementById("original");
const correctedEl = document.getElementById("corrected");
const errorEl = document.getElementById("error");

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
  resultBlock.hidden = true;
}

function renderResult(data) {
  errorEl.hidden = true;
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;

  submitButton.disabled = true;
  try {
    const response = await fetch("/api/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "Не удалось обработать запрос");
      return;
    }
    renderResult(data);
  } catch (err) {
    showError("Сеть недоступна: " + err.message);
  } finally {
    submitButton.disabled = false;
  }
});
```

- [ ] **Step 4: Прогнать все тесты — убедиться, что ничего не сломалось**

Run:
```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
/Users/maxos/PythonProjects/LSH/.venv/bin/python -m pytest -v
```
Expected: PASS (все тесты из Task 2–4).

- [ ] **Step 5: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/frontend/index.html app/frontend/style.css app/frontend/app.js
git commit -m "feat: фронтенд страницы исправления опечаток с подсветкой"
```

---

## Task 6: README и ручная проверка

**Files:**
- Create: `app/README.md`

**Interfaces:**
- Consumes: всё приложение.
- Produces: инструкция запуска; подтверждение, что сервер реально работает.

- [ ] **Step 1: Создать `app/README.md`**

````markdown
# Веб-приложение «Исправление опечаток»

Демо шага пайплайна: запрос → исправление опечаток с подсветкой изменений.

## Запуск

```bash
source /Users/maxos/PythonProjects/LSH/.venv/bin/activate
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
uvicorn backend.main:app --reload
```

Открыть http://127.0.0.1:8000

## Тесты

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
python -m pytest -v
```

## Структура

- `backend/pipeline/corrector.py` — код исправлятора (SymSpell) + адаптер `SymSpellCorrector`.
- `backend/main.py` — FastAPI: `POST /api/correct` и раздача фронтенда.
- `frontend/` — статическая страница (HTML/CSS/JS).

Словарь: `samokat/data/domain_dictionary.txt`.
````

- [ ] **Step 2: Запустить сервер в фоне и проверить эндпоинт**

Run:
```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat/app
/Users/maxos/PythonProjects/LSH/.venv/bin/uvicorn backend.main:app --port 8000 &
sleep 8
curl -s -X POST http://127.0.0.1:8000/api/correct -H "Content-Type: application/json" -d '{"query":"крсовки укропбатон"}'
echo
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/
echo
kill %1
```
Expected:
- JSON вида `{"original":"крсовки укропбатон","corrected":"кроссовки укроп батон","words":[{"original":"крсовки","corrected":"кроссовки","changed":true},{"original":"укропбатон","corrected":"укроп батон","changed":true}]}`
- второй `curl` печатает `200`.

- [ ] **Step 3: Commit**

```bash
cd /Users/maxos/PythonProjects/LSH/_project/samokat
git add app/README.md
git commit -m "docs: README запуска веб-приложения опечаток"
```

---

## Self-Review (выполнено при написании плана)

- **Покрытие спеки:** стек (Task 1), модели с `changed` (Task 2), корректор дословно + адаптер (Task 3), эндпоинт/ошибки/lifespan/раздача статики (Task 4), интерфейс с подсветкой (Task 5), запуск/README (Task 6). Разбиение слипшихся слов покрыто тестом в Task 3 и ручной проверкой в Task 6.
- **Заглушки:** нет TODO/«добавьте обработку ошибок» — весь код приведён целиком.
- **Согласованность типов:** `WordCorrection(original, corrected, changed)`, `SymSpellCorrector(dict_path).correct(query) -> list[WordCorrection]`, `CorrectResponse(original, corrected, words)` — имена совпадают во всех задачах и в тестах.
