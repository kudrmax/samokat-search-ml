# Дизайн: классификатор категории в веб-приложении (шаг 2)

Дата: 2026-07-15
Ветка: app/typo-correction-web (продолжение)

## Цель и контекст

Расширяем существующее демо-веб-приложение. Пайплайн:
`query → исправление опечаток → предобработка → эмбеддер → KNN → топ-3 категории`.

Пользователь вводит запрос, видит исправление опечаток (уже сделано) и **топ-3
предсказанных категории верхнего уровня** (`category1_name`). Демо для презентации
мастерской.

Источник модели: `samokat/categories/classificator.ipynb`. Модель и предобработку
**НЕ улучшаем** — переносим и вызываем как есть.

## Что за модель

Две модели последовательно:

1. **Эмбеддер** `d0rj/e5-small-en-ru` (SentenceTransformer, ~176 МБ, уже в HF-кэше).
   Кодирует текст в вектор 384. Вход префиксится строкой `"query: "`.
2. **KNN** `KNeighborsClassifier(n_neighbors=3, weights='distance', metric='euclidean')`
   поверх эмбеддингов. Лучший вариант из ноутбука (accuracy ≈ 0.88). Обучается на
   эмбеддингах названий товаров (`item_name` → `category1_name`).

Дообучение эмбеддера в ноутбуке признано неэффективным — в веб не тащим.

## Ключевые решения

- **Путь получения модели: офлайн-обучение → артефакт.** Отдельный скрипт один раз
  обучает KNN и сохраняет `.joblib`; веб при старте грузит готовое. Инференс не зависит
  от обучающего CSV, старт быстрый.
- **Эмбеддер: копия в папке проекта** (`save_pretrained`), грузится локально, офлайн.
- **Артефакты в `app/models/`, весь каталог — в `.gitignore`** (в git не коммитим).
- **Классифицируется исправленный запрос** (выход опечаточника), с той же
  предобработкой и префиксом, что в обучении.
- **Показываем топ-3 категории** с долями (`predict_proba`).

## Структура (добавления к существующему `app/`)

```
samokat/app/
├── train_classifier.py         # НОВОЕ: офлайн-обучение KNN + сохранение артефактов
├── models/                     # НОВОЕ: артефакты (в .gitignore)
│   ├── category1_knn.joblib
│   └── e5-small-en-ru/         # сохранённая копия эмбеддера
├── .gitignore                  # НОВОЕ: models/, __pycache__/
├── backend/
│   ├── main.py                 # + эндпоинт /api/analyze, classifier в lifespan
│   ├── models.py               # + CategoryScore, AnalyzeResponse
│   └── pipeline/
│       ├── corrector.py        # без изменений
│       └── classifier.py       # НОВОЕ: preprocess_query + CategoryClassifier
├── frontend/
│   ├── index.html              # + блок «Категории»
│   ├── style.css               # + стили блока категорий
│   └── app.js                  # переключение на /api/analyze, рендер топ-3
└── tests/
    ├── test_classifier.py      # НОВОЕ: юнит preprocess_query + smoke (skip без артефакта)
    └── test_api.py             # + тест /api/analyze
```

## 1. Обучение и артефакты — `app/train_classifier.py`

Разовый скрипт (запуск руками). Дословно воспроизводит логику ноутбука:

- читает `DATA.csv` (корень `samokat/`), приводит `query`/`item_name` к нижнему регистру и
  чистит регулярками как в ноутбуке;
- строит `item_names`: `item_name → category1_name`, дроп NA по `category1_name`,
  дедуп по названию, переименование колонки в `query`;
- грузит эмбеддер `d0rj/e5-small-en-ru`, кодирует `f"query: {q}"` в numpy;
- обучает `KNeighborsClassifier(n_neighbors=3, weights='distance', metric='euclidean')`
  на эмбеддингах названий → `category1_name`;
- `joblib.dump` обученного KNN в `app/models/category1_knn.joblib`;
- `embedder.save('app/models/e5-small-en-ru')` (копия эмбеддера).

Гиперпараметры и предобработка — как в ноутбуке, без тюнинга.

## 2. Серверный слой — `app/backend/pipeline/classifier.py`

Не зависит от HTTP.

- `preprocess_query(text: str) -> str` — чистая функция: `text.lower()`, убрать всё кроме
  букв (`\p{L}` через модуль `regex`), пробелов и дефиса. Повторяет чистку `query` из
  ноутбука байт-в-байт.
- `CategoryScore(BaseModel)` — см. раздел моделей (импорт из `backend.models`).
- `CategoryClassifier`:
  - `__init__(self, model_dir: Path)` — грузит эмбеддер из `model_dir / "e5-small-en-ru"`
    и KNN из `model_dir / "category1_knn.joblib"` (тяжёлое — один раз при старте).
  - `predict_top(self, query: str, k: int = 3) -> list[CategoryScore]`:
    `preprocess_query → "query: " + text → embedder.encode → knn.predict_proba`,
    берём `k` классов с наибольшей вероятностью, возвращаем как `CategoryScore`
    (name = класс KNN, score = доля). Сортировка по убыванию score.

## 3. API — `app/backend/main.py`

- Существующий `/api/correct` — без изменений.
- Новый `POST /api/analyze` (тело `CorrectRequest`):
  1. `corrector.correct(query)` → `words`, `corrected = " ".join(...)`;
  2. `classifier.predict_top(corrected, k=3)` → `categories`;
  3. ответ `AnalyzeResponse`.
- Корректор и классификатор поднимаются в `lifespan`, хранятся в `app.state`.
- Пример ответа:
  ```json
  {
    "original": "кока кола",
    "corrected": "кока кола",
    "words": [{"original": "кока", "corrected": "кока", "changed": false},
              {"original": "кола", "corrected": "кола", "changed": false}],
    "categories": [
      {"name": "безалкогольные напитки", "score": 1.0},
      {"name": "снэки", "score": 0.0},
      {"name": "бакалея", "score": 0.0}
    ]
  }
  ```

## 4. pydantic-модели — добавления в `app/backend/models.py`

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

## 5. Фронтенд

- `app.js` переключается с `/api/correct` на `/api/analyze`.
- Под блоком «Исправлено» — новый блок **«Категории»**: топ-3 списком, первая выделена
  как основная, рядом доля в процентах.
- Стили блока категорий в `style.css` в существующей палитре.

## 6. Ошибки и тесты

- Артефактов нет в `app/models/` → классификатор при старте кидает понятную ошибку
  («сначала запусти `python train_classifier.py`»), сервер не стартует молча.
- Ошибка инференса → 500 `{"error": "..."}`, фронт показывает сообщение.
- Тесты (ML-минимум):
  - `test_classifier.py`: юнит на `preprocess_query` (чистая функция) — обязательно;
    smoke-тест `CategoryClassifier` / `/api/analyze` со `skip`, если артефакта нет
    (CI не должен требовать 176 МБ модели).
  - `test_api.py`: тест `/api/analyze` возвращает `categories` из 3 элементов
    (под `skipif` при отсутствии артефакта).

## Явно вне объёма (YAGNI)

- Классификатор «еда/не еда» (`category0`) и иерархия ниже `category1`.
- Тюнинг гиперпараметров, дообучение эмбеддера, смена эмбеддера.
- Коммит артефактов в git, git-lfs, деплой.
