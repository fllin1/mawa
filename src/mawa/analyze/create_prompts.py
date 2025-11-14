import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from google.genai.types import Blob, Part

from mawa.config import CONFIG_DIR, PROMPT_DATA_DIR, City
from mawa.models.gemini_model import GeminiModel
from mawa.schemas.document_schema import Document
from mawa.utils import read_data_tree, read_json, save_json


class Analyze:
    """Class to handle the analysis of the document.

    Args:
        city (City): The city of the document
        zone (str): The zone of the document
        dg (Optional[str]): The name of the dispositions generales file if it exists
    """

    def __init__(
        self,
        city: City,
        zone: str,
        dg: Optional[str] = None,
    ):
        self.city = city
        self.zone = zone
        self.dg = dg
        self.data_tree = read_data_tree("4.interim")[city.value]

    def create_prompts(self) -> Path:
        """Create the prompts for the analysis"""
        zone_path = self.data_tree[self.zone + ".json"]["file_path"]
        document = read_json(zone_path)
        document = Document(**document)
        if self.dg:
            dg_path = self.data_tree[self.dg + ".json"]["file_path"]
            doc_dg = read_json(dg_path)
            doc_dg = Document(**doc_dg)
        prompts = read_json(CONFIG_DIR / "prompt" / "prompt.json")
        instruction = prompts["prompt_plu"]

        parts = [Part(text=instruction)]
        parts.extend(_document_to_parts(document))
        if self.dg:
            parts.extend(_document_to_parts(doc_dg))

        return parts


# Helper functions


def _document_to_parts(document: Document) -> list[Part]:
    """
    Converts a Document object into a list of Parts for the Gemini API.

    This robust implementation:
    1. Correctly cleans and joins all page text into a single Part per page.
    2. Appends all images for that page AFTER the text Part.
    3. Wraps each image with explicit text delimiters for unambiguous linking.
    """
    parts = []

    for page in document.pages:
        # Step 1: Correctly clean paragraphs using a list comprehension.
        cleaned_paragraphs = [
            p.content.replace("\n", " ").strip() for p in page.paragraphs
        ]

        # Step 2: Join all cleaned paragraphs to form the complete text content for the page.
        page_content = "\n\n".join(cleaned_paragraphs)

        # Step 3: Create the main text Part for the page, including delimiters.
        header = f"\n--- DÉBUT PAGE {page.index} ({document.document_type}) ---\n"
        footer = f"\n--- FIN PAGE {page.index} ({document.document_type}) ---\n"
        full_text_for_page = header + page_content + footer
        parts.append(Part(text=full_text_for_page))
        # Adding all the page content in a single Part offers better context for the model.

        # Step 4: Append all images for that page, each wrapped in its own delimiters.
        if page.images:
            for image_data in page.images:
                name_img = image_data.name_img

                parts.append(Part(text=f"\n--- DÉBUT IMAGE: {name_img} ---\n"))

                # Add the image data Part.
                image_part = Part(
                    inline_data=Blob(
                        mime_type="image/jpeg",
                        data=base64.b64decode(image_data.image_base64),
                    )
                )
                parts.append(image_part)

                parts.append(Part(text=f"\n--- FIN IMAGE: {name_img} ---\n"))

    _save_prompt_to_json(document, parts)
    return parts


# Logging


def _save_prompt_to_json(document: Document, parts: list[Part]) -> Path:
    """
    Saves the generated prompt to a JSON file for review and tracing.
    """
    serializable_parts = _parts_to_json_serializable(parts)

    prompt_data = {
        "timestamp": datetime.now().isoformat(),
        "document_info": {"num_pages": len(document.pages), "num_parts": len(parts)},
        "count_tokens": GeminiModel(model="pro").input_tokens_metadata(parts),
        "parts": serializable_parts,
    }

    output_path = (PROMPT_DATA_DIR / document.city / document.zone).with_suffix(
        ".prompt.json"
    )
    output_path.parent.mkdir(exist_ok=True, parents=True)
    save_json(prompt_data, output_path)

    return output_path


def _parts_to_json_serializable(parts: list[Part]) -> list[dict[str, Any]]:
    """
    Converts a list of Gemini API Parts to a JSON-serializable format.
    """
    serializable_parts = []

    for part in parts:
        if part.text:
            # Text part
            serializable_parts.append({"type": "text", "content": part.text})
        elif part.inline_data:
            # Image part - re-encode binary data to base64 string
            serializable_parts.append(
                {
                    "type": "image",
                    "mime_type": part.inline_data.mime_type,
                    "data_base64": base64.b64encode(part.inline_data.data).decode(
                        "utf-8"
                    ),
                }
            )

    return serializable_parts
