# Дизайн: сетка релевантных товаров через ESCI (шаг 3)

Дата: 2026-07-15
Ветка: app/typo-correction-web (продолжение)

## Цель и контекст

Третий шаг демо-пайплайна. После определения топ-3 категорий берём самую уверенную,
достаём случайные товары этой категории из каталога, размечаем их релевантность к запросу
классификатором ESCI, оставляем только точные совпадения (`E`) и показываем сеткой (≤16).

Полный поток:
`query → исправление опечаток → топ-3 категории → самая уверенная → случайные товары
категории → predict_esci → только E → сетка ≤16`.

**КЛЮЧЕВОЕ ограничение:** из `DATA.csv` используем ТОЛЬКО каталог (`item_name` + категории).
Колонку `final_answer` (готовую ручную разметку) **не читаем и не используем**. Релевантность
**предсказываем** модулем `esci_classifier_module` на исправленном запросе — это и есть смысл
демо (наши веса, наша модель).

## Модуль ESCI — используем как есть

Источник: `samokat/esci/esci_classifier_module/` (176 МБ: два joblib-пайплайна + копия e5).
Интерфейс: `predict_esci(query: str, item_name: str) -> str` → `"E" | "S" | "C" | "I"`
(двухстадийный: stage1 релевантно/нет, stage2 E/S/C). При импорте грузит модели (~8 с).

Замер: загрузка 8 с (разово), прогон ~0.05–0.1 с после прогрева. Потолок 60 прогонов ≈
несколько секунд. Модуль не меняем.

## Ключевые решения

- **Набор сетки:** идём по перемешанному пулу товаров категории, копим `E`, пока не наберём
  **16** или не упрёмся в потолок **60** прогонов ESCI за запрос.
- **Два запроса на фронте:** `/api/analyze` отдаёт исправление и категории сразу (быстро);
  затем фронт шлёт `/api/products` за сеткой, показывая лоадер.
- **`/api/products` самодостаточен:** пересчитывает исправление и категорию от `query`, не
  доверяя промежуточным данным клиента.
- **Модуль ESCI остаётся в `esci/`**, в git не коммитим; бэкенд добавляет `esci/` в
  `sys.path` и импортирует один раз в lifespan.
- **Карточка товара:** `item_name` крупно + `category4_name` мелкой подписью.

## Структура (добавления к `app/`)

```
samokat/app/
├── backend/
│   ├── main.py                 # + /api/products, catalog + relevance в lifespan
│   ├── models.py               # + Product, ProductsResponse
│   └── pipeline/
│       ├── catalog.py          # НОВОЕ: ProductCatalog (DATA.csv → индекс category1 → товары)
│       └── relevance.py        # НОВОЕ: RelevanceClassifier (адаптер над predict_esci)
├── frontend/
│   ├── index.html              # + блок «Товары» (сетка + лоадер)
│   ├── style.css               # + стили сетки/карточек/лоадера
│   └── app.js                  # после analyze — запрос /api/products, рендер сетки
└── tests/
    ├── test_catalog.py         # НОВОЕ: юнит ProductCatalog (final_answer не используется)
    └── test_api.py             # + тест /api/products (skipif без модуля)
```

## 1. Каталог — `app/backend/pipeline/catalog.py`

Не зависит от HTTP.

- `Product(BaseModel)` — импорт из `backend.models`.
- `ProductCatalog`:
  - `__init__(self, data_path: Path)` — читает `DATA.csv` через `pd.read_csv`; берёт колонки
    `item_name`, `category1_name`, `category4_name` (**не** `final_answer`); дропает строки без
    `item_name`/`category1_name`; дедуп по `item_name`; строит `dict[str, list[Product]]`
    — `category1_name → товары`.
  - `sample(self, category: str, count: int, exclude: set[str]) -> list[Product]` — до `count`
    случайных товаров из категории, не входящих в `exclude` (по `item_name`). Использует
    `random.sample` (для демо выборка каждый раз разная).
  - `has_category(self, category: str) -> bool`.

## 2. Классификатор релевантности — `app/backend/pipeline/relevance.py`

Не зависит от HTTP. Адаптер над модулем ESCI (модуль не меняем).

- `RelevanceClassifier`:
  - `__init__(self, module_parent: Path)` — добавляет `module_parent` (= `samokat/esci`) в
    `sys.path`, импортирует `predict_esci` (тяжёлая загрузка один раз). Если модуля нет —
    `RuntimeError` с понятным сообщением.
  - `predict(self, query: str, item_name: str) -> str` — вызывает `predict_esci(query, item_name)`.
  - `is_exact(self, query: str, item_name: str) -> bool` — `predict(...) == "E"`.

## 3. Эндпоинт `/api/products` — `app/backend/main.py`

- `POST /api/products` (тело `CorrectRequest`):
  1. `corrected = " ".join(w.corrected for w in corrector.correct(query))`;
  2. `category = classifier.predict_top(corrected, k=3)[0].name`;
  3. если `not catalog.has_category(category)` → пустой список товаров;
  4. цикл добора: пока `len(selected) < GRID_SIZE (16)` и `scanned < CAP (60)` —
     берём следующую партию `catalog.sample(category, batch, exclude=seen)`; если партия пуста
     (товары кончились) — стоп; для каждого товара `scanned += 1`, если `relevance.is_exact(...)`
     → в `selected`; уважаем оба лимита внутри партии;
  5. ответ `ProductsResponse`.
- Константы: `GRID_SIZE = 16`, `CAP = 60`, `BATCH = 20`.
- `catalog` и `relevance` поднимаются в lifespan; `relevance` — graceful (при ошибке
  `app.state.relevance = None`, эндпоинт отвечает 503 с сообщением).
- Пример ответа:
  ```json
  {
    "category": "молочная продукция",
    "products": [{"item_name": "Молоко ...", "category4": "молоко питьевое"}],
    "scanned": 23,
    "reached_cap": false
  }
  ```

## 4. Модели — добавления в `app/backend/models.py`

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

## 5. Фронтенд

- После успешного `/api/analyze` `app.js` сразу шлёт `POST /api/products {query}` и показывает
  блок «Товары» с лоадером («подбираем товары…»).
- Ответ → рисуем **сетку** (CSS grid, до 16 карточек): `item_name` крупно + `category4`
  мелкой подписью.
- Если `reached_cap` и товаров мало — подпись «показаны все найденные релевантные».
- Ошибка/503 → сообщение в блоке товаров, остальная страница работает.

## 6. Ошибки и тесты

- Модуль ESCI недоступен → `/api/products` 503 `{"error": ...}`; `/api/analyze` независим.
- Ошибка прогона → 500 `{"error": ...}`.
- Тесты (ML-минимум):
  - `test_catalog.py`: `ProductCatalog` строится из мини-CSV; `sample` возвращает товары нужной
    категории; `exclude` исключает; проверка, что `final_answer` **не влияет** (в тестовом CSV
    разные метки, результат от них не зависит). Обязательно.
  - `test_api.py`: `/api/products` возвращает `category`, `products` (≤16), `scanned`,
    `reached_cap` — под `skipif` при отсутствии модуля ESCI.

## Явно вне объёма (YAGNI)

- Использование готовой разметки `final_answer` (запрещено условием задачи).
- Картинки товаров (в данных нет), пагинация, кэш результатов.
- Батч-инференс ESCI (модуль принимает по одной паре), тюнинг модели.
- Деплой, git-lfs, коммит весов.
