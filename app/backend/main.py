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
