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


class CategoryScore(BaseModel):
    name: str
    score: float
    subcategory: str | None = None


class AnalyzeResponse(BaseModel):
    original: str
    corrected: str
    words: list[WordCorrection]
    categories: list[CategoryScore]


class Product(BaseModel):
    item_name: str
    category4: str | None = None


class ProductsResponse(BaseModel):
    category: str
    products: list[Product]
    scanned: int
    reached_cap: bool
