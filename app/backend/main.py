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
