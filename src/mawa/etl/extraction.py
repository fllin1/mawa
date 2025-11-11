from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from mawa.config import OCR_DATA_DIR, City
from mawa.models.mistral_ocr import MistralOCR
from mawa.schemas.document_schema import Document, Page, Paragraph
from mawa.utils import save_json


def extraction_function(
    file_path: Path,
    city: str,
    document_type: Literal["PLU", "DG", "PLU_AND_DG"],
    zonage: Optional[str] = None,
    zone: Optional[str] = None,
) -> Path:
    """Extract and format content from a file using Mistral OCR.

    Args:
        file_path (Path): Path to the file to extract text from.
        document_type (Literal["PLU", "DG", "PLU_AND_DG"]): The type of document.
        zonage (Optional[str]): The zonage of the document.
        zone (Optional[str]): The zone of the document.

    Returns:
        Path: Path to the saved data
    """
    mistral_ocr = MistralOCR()
    file_id = mistral_ocr.upload_file(file_path)
    ocr_response = mistral_ocr.process_ocr(file_id)

    save_file_path = OCR_DATA_DIR / city / file_path.stem + ".json"
    save_file_path.parent.mkdir(parents=True, exist_ok=True)

    json_data = ocr_response.model_dump()
    # Checkpoint save the raw OCR response
    save_json(json_data, save_file_path)

    document = _format_ocr_response(json_data, file_path, document_type, zonage, zone)

    # Overwrite the raw OCR response with the formatted document
    save_json(document.model_dump(), save_file_path)
    return save_file_path


def _format_ocr_response(
    ocr_response: dict,
    file_path: Path,
    document_type: Literal["PLU", "DG", "PLU_AND_DG"],
    zonage: Optional[str] = None,
    zone: Optional[str] = None,
) -> Document:
    """Format the OCR response into a Document schema"""
    pages: list[Page] = []
    for index, page in enumerate(ocr_response["pages"]):
        paragraphs: list[Paragraph] = []
        for sub_index, paragraph in enumerate(page["markdown"].split("\n\n")):
            paragraphs.append(Paragraph(index=sub_index + 1, content=paragraph))
        pages.append(
            Page(
                index=index + 1,
                paragraphs=paragraphs,
                images=page["images"],
                dimensions=page["dimensions"],
            )
        )

    usage_info = ocr_response.get("usage_info", {})
    name_of_document = file_path.stem
    date_of_document = file_path.parent.name
    assert datetime.strptime(date_of_document, "%Y-%m-%d")
    city = file_path.parent.parent.name
    assert city in City

    document = Document(
        pages=pages,
        name_of_document=name_of_document,
        date_of_document=date_of_document,
        document_type=document_type,
        city=city,
        zonage=zonage,
        zone=zone,
        date_of_ocr=datetime.now().strftime("%Y-%m-%d"),
        model_metadata={
            "model": ocr_response.get("model", ""),
            "pages_processed": usage_info.get("pages_processed", None),
            "doc_size_bytes": usage_info.get("doc_size_bytes", None),
            "document_annotation": ocr_response.get("document_annotation", {}),
        },
    )
    return document
