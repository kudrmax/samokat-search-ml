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
