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
