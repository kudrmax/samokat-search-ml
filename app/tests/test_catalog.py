from pathlib import Path

from backend.catalog_testdata import write_sample_csv
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
    assert cat.has_category("мебель") is True
    assert cat.has_category("техника") is False


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
