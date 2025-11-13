from pydantic import BaseModel
from typing import Literal, Optional


class Image(BaseModel):
    name_img: str
    top_left_x: int
    top_left_y: int
    bottom_right_x: int
    bottom_right_y: int
    image_base64: str


class Dimensions(BaseModel):
    dpi: int
    width: int
    height: int


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
