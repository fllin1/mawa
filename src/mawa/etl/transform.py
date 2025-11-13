from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from mawa.config import CONFIG_DIR, INTERIM_DATA_DIR, OCR_DATA_DIR, City
from mawa.models.gemini_model import GeminiModel
from mawa.schemas.document_schema import Document, Page, Paragraph
from mawa.utils import read_json, save_json


def format_ocr_response(doc_name: str, city: City) -> Path:
    """Format the OCR response into a Document schema.

    Returns:
        Path: Path to the saved formatted document
    """
    doc_name = doc_name.with_suffix(".json")
    file_path = OCR_DATA_DIR / city.value / doc_name
    ocr_response = read_json(file_path)

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

    document = Document(
        pages=pages,
        name_of_document=doc_name.stem,
        date_of_document=ocr_response["date_of_document"],
        document_type=ocr_response["document_type"],
        city=city,
        zonage=ocr_response.get("zonage", None),
        zone=ocr_response.get("zone", None),
        modified_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        model_metadata={
            "model": ocr_response.get("model", ""),
            "pages_processed": usage_info.get("pages_processed", None),
            "doc_size_bytes": usage_info.get("doc_size_bytes", None),
            "document_annotation": ocr_response.get("document_annotation", {}),
        },
    )

    # Overwrite the raw OCR response with the formatted document
    save_json(document.model_dump(), file_path)
    return file_path


def transform_function(
    document_path: Path,
    apply_extract_zones: Optional[bool] = True,
    model: Optional[str] = "flash",
) -> Path:
    """Transform the raw OCR output in a standard format

    Args:
        document_path (Path): Path to the raw OCR output
        apply_extract_zones (Optional[bool]): Whether to apply the extract zones prompt
        model (Optional[str]): The model to use for the Gemini model
    """
    ocr_response = read_json(document_path)
    document = Document(**ocr_response)

    save_file_path = INTERIM_DATA_DIR / document_path.relative_to(OCR_DATA_DIR)
    save_file_path.parent.mkdir(exist_ok=True, parents=True)

    if not apply_extract_zones:
        save_json(document.model_dump(), save_file_path)
        return save_file_path

    system_prompt, parts, response_schema = _generate_prompt_parts(document)

    gemini_model = GeminiModel(model=model)
    response = gemini_model.generate_content(
        parts,
        system_prompt=system_prompt,
        json_schema=response_schema,
    )

    json_response = response.model_dump()
    page_split_path = save_file_path.with_suffix(".page_split.json")
    save_json(json_response, page_split_path)

    for page_split in json_response["parsed"]:
        zoning = page_split["zoning"]
        zone = page_split["zone"]
        pages = page_split["pages"]

        doc_zone = document.model_copy(
            update={
                "pages": [document.pages[page - 1] for page in pages],
                "zoning": zoning,
                "zone": zone,
            }
        )
        save_json(
            doc_zone.model_dump(), save_file_path.parent / zoning / f"{zone}.json"
        )

    return page_split_path


def _generate_prompt_parts(document: Document) -> Tuple[str, list[str], dict]:
    """Returns system prompt, prompt's parts and json_schema"""
    prompt_template = read_json(CONFIG_DIR / "prompt" / "prompt.json")
    system_prompt = prompt_template["prompt_extract_zones"]

    parts = [f"Page {page.index}: {page.markdown}" for page in document.pages]

    schema_path = CONFIG_DIR / "schemas" / "response_schema_pages.json"
    response_schema_pages = read_json(schema_path)

    return system_prompt, parts, response_schema_pages
