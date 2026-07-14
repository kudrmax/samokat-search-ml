# Веб-приложение «Опечатки → категория → товары»

Демо пайплайна: запрос → исправление опечаток → топ-3 категории верхнего уровня → сетка релевантных товаров (ESCI).

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
- `backend/pipeline/catalog.py` — каталог товаров из DATA.csv (без final_answer).
- `backend/pipeline/relevance.py` — разметка релевантности через esci_classifier_module.
- `backend/main.py` — FastAPI: `/api/correct`, `/api/analyze`, `/api/products`, раздача фронтенда.
- `frontend/` — статическая страница (исправление, категории, сетка товаров).

Данные: `samokat/DATA.csv`, словарь `samokat/data/domain_dictionary.txt`,
модуль релевантности: `samokat/esci/esci_classifier_module/` (не в git).
