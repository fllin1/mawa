from typing import Literal, Optional

from pydantic import BaseModel

from mawa.schemas.ocr_schema import Dimensions, Image


class Paragraph(BaseModel):
    index: int
    content: str


class Page(BaseModel):
    index: int
    paragraphs: list[Paragraph]
    images: list[Image]
    dimensions: Dimensions


class Document(BaseModel):
    pages: list[Page]
    name_of_document: str
    date_of_document: str
    document_type: Literal["PLU", "DG", "PLU_AND_DG"]
    city: str
    zoning: Optional[str] = None
    zone: Optional[str] = None
    modified_at: Optional[str] = None
    model_metadata: dict
