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
