"""Data models passed between the pipeline steps."""

from pydantic import BaseModel, Field, computed_field


class RawDoc(BaseModel):
    """The schema every raw document must satisfy."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    url: str
    license: str
    text: str


class CleanDoc(BaseModel):
    id: str
    title: str
    source: str
    url: str
    license: str
    text: str
    doc_hash: str
    removed: dict[str, int]  # characters removed per cleaning step


class CheckResult(BaseModel):
    name: str
    passed: bool
    detail: str = ""
    blocking: bool = True  # a failed non-blocking check flags the document but keeps it


class DocReport(BaseModel):
    id: str
    title: str
    source: str
    checks: list[CheckResult]

    @computed_field
    @property
    def failed(self) -> list[str]:
        return [c.name for c in self.checks if not c.passed and c.blocking]

    @computed_field
    @property
    def flagged(self) -> list[str]:
        return [c.name for c in self.checks if not c.passed and not c.blocking]

    @computed_field
    @property
    def quarantined(self) -> bool:
        return bool(self.failed)
