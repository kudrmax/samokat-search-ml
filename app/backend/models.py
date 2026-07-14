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
