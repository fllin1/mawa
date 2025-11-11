from pathlib import Path
import json
from typing import Optional, Tuple

from google.genai.types import GenerateContentResponse

from mawa.config import CONFIG_DIR, INTERIM_DATA_DIR, OCR_DATA_DIR
from mawa.models.gemini_model import GeminiModel
from mawa.schemas.document_schema import Document
from mawa.utils import read_json, save_json


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
    save_json(json_response, save_file_path)

    return save_file_path


def _generate_prompt_parts(document: Document) -> Tuple[str, list[str], dict]:
    """Returns system prompt, prompt's parts and json_schema"""
    prompt_template = read_json(CONFIG_DIR / "prompt" / "prompt.json")
    system_prompt = prompt_template["prompt_extract_zones"]

    parts = [f"Page {page.index}: {page.markdown}" for page in document.pages]

    schema_path = CONFIG_DIR / "schemas" / "response_schema_pages.json"
    response_schema_pages = read_json(schema_path)

    return system_prompt, parts, response_schema_pages
