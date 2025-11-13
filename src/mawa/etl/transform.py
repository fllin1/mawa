from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from mawa.config import CONFIG_DIR, INTERIM_DATA_DIR, OCR_DATA_DIR, City, RAW_DATA_DIR
from mawa.models.gemini_model import GeminiModel
from mawa.schemas.document_schema import Document, Page, Paragraph
from mawa.utils import read_json, save_json


class Transform:
    """Class to handle the transformation of the OCR response into a Document schema.

    Args:
        city (City): The city of the document.
        doc_name (str): The name of the document.
    """

    def __init__(self, city: City, doc_name: str):
        self.city = city
        self.doc_name = doc_name
        self.ocr_path = (OCR_DATA_DIR / city.value / doc_name).with_suffix(".json")
        self.raw_path = (RAW_DATA_DIR / city.value / doc_name).with_suffix(".json")
        self.interim_path = (INTERIM_DATA_DIR / city.value / doc_name).with_suffix(
            ".json"
        )

    def ocr_response_to_document(self) -> None:
        """Format the OCR response into a Document schema."""
        ocr_response = read_json(self.ocr_path)

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
        model_metadata = {
            "model": ocr_response.get("model", ""),
            "pages_processed": usage_info.get("pages_processed", None),
            "doc_size_bytes": usage_info.get("doc_size_bytes", None),
            "document_annotation": ocr_response.get("document_annotation", {}),
        }

        document = Document(
            pages=pages,
            name_of_document=self.doc_name,
            date_of_document=ocr_response["date_of_document"],
            document_type=ocr_response["document_type"],
            city=self.city,
            zonage=ocr_response.get("zonage", None),
            zone=ocr_response.get("zone", None),
            modified_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            model_metadata=model_metadata,
        )

        # Overwrite the raw OCR response with the formatted document
        self.raw_path.parent.mkdir(exist_ok=True, parents=True)
        save_json(document.model_dump(), self.raw_path)

    def clean_document(self) -> None:
        """Clean the document by removing duplicates
        TODO: Remove all non necessary images and text
        """
        document = read_json(self.raw_path)
        document = Document(**document)

        # Count occurences of all page.content and images
        images_dict = {}
        pages_dict = {}

        for page in document.pages:
            content = "\n".join([paragraph.content for paragraph in page.paragraphs])
            if content in pages_dict:
                pages_dict[content].append(page.index)
            else:
                pages_dict[content] = [page.index]

            for image in page.images:
                b64 = image.image_base64
                if b64 in images_dict:
                    images_dict[b64].append((page.index, image))
                else:
                    images_dict[b64] = [(page.index, image)]

        # Remove duplicated pages
        pages_to_remove = set()
        for content, page_indexes in pages_dict.items():
            if len(page_indexes) > 1:
                pages_to_remove.update(page_indexes)

        # Remove pages in reverse order to avoid index shifting issues
        pages_to_remove_sorted = sorted(pages_to_remove, reverse=True)
        for page_index in pages_to_remove_sorted:
            # Find page by its index property, not list position
            page_to_remove = next(
                (p for p in document.pages if p.index == page_index), None
            )
            if page_to_remove:
                document.pages.remove(page_to_remove)

        # Create a mapping of page index to page object for quick lookup
        page_map = {page.index: page for page in document.pages}

        # Remove duplicated images
        for b64, images in images_dict.items():
            if len(images) <= 1:
                continue

            for page_index, image in images:
                # Skip if page was removed
                if page_index in pages_to_remove:
                    continue

                # Get page from map (using actual index property)
                page = page_map.get(page_index)
                if page is None:
                    continue

                # Find image in page by base64 (safer than object comparison)
                image_to_remove = next(
                    (
                        img
                        for img in page.images
                        if img.image_base64 == image.image_base64
                    ),
                    None,
                )
                if image_to_remove is None:
                    continue

                page.images.remove(image_to_remove)

                paragraphs_to_remove = []
                for paragraph in page.paragraphs:
                    if image.name_img in paragraph.content:
                        image_tag = f"![{image.name_img}]({image.image_base64})"
                        paragraph.content = paragraph.content.replace(image_tag, "")
                        paragraph.content = paragraph.content.strip()

                        if not paragraph.content:
                            paragraphs_to_remove.append(paragraph)

                for paragraph in paragraphs_to_remove:
                    page.paragraphs.remove(paragraph)

        save_json(document.model_dump(), self.save_path)

    def pages_splitting(self, model: Optional[str] = "flash") -> None:
        """Transform the formatted OCR output in a standard format.
        Extracts pages for each zone/zoning combination.

        Args:
            model (Optional[str]): The model to use for the Gemini model
        """
        # Load document from save_path (3.raw)
        if not self.save_path.exists():
            raise FileNotFoundError(
                f"File not found: {self.save_path}. Please run 'format' and 'clean' first."
            )

        document_data = read_json(self.save_path)
        document = Document(**document_data)

        system_prompt, parts, response_schema = _generate_prompt_parts(document)

        gemini_model = GeminiModel(model=model)
        response = gemini_model.generate_content(
            parts,
            system_prompt=system_prompt,
            json_schema=response_schema,
        )
        json_response = response.model_dump()

        self.interim_path.parent.mkdir(exist_ok=True, parents=True)
        save_json(json_response, self.interim_path)

    def split_documents(self):
        """Split the document into multiple documents based on the zoning and zone."""
        document = read_json(self.raw_path)
        document = Document(**document)

        page_splitting = read_json(self.interim_path)

        # Create a mapping of page index to page object for safe lookup
        page_map = {page.index: page for page in document.pages}

        for page_split in page_splitting["parsed"]:
            zoning = page_split["zoning"]
            zone = page_split["zone"]
            page_indices = page_split["pages"]

            # Get pages by their index property (not list position)
            selected_pages = [
                page_map[page_idx] for page_idx in page_indices if page_idx in page_map
            ]

            if not selected_pages:
                continue

            doc_zone = document.model_copy(
                update={"pages": selected_pages, "zoning": zoning, "zone": zone}
            )
            save_path = self.interim_path.parent / zoning / f"{zone}.json"
            save_path.parent.mkdir(exist_ok=True, parents=True)
            save_json(doc_zone.model_dump(), save_path)


def _generate_prompt_parts(document: Document) -> Tuple[str, list[str], dict]:
    """Returns system prompt, prompt's parts and json_schema.

    Reconstructs markdown from paragraphs by joining them with double newlines.

    Args:
        document: The Document object to extract pages from

    Returns:
        Tuple containing system prompt, list of page markdown strings, and response schema
    """
    prompt_template = read_json(CONFIG_DIR / "prompt" / "prompt.json")
    system_prompt = prompt_template["prompt_extract_zones"]

    # Reconstruct markdown from paragraphs (join with \n\n as in ocr_response_to_document)
    parts = [
        f"Page {page.index}: {'\n\n'.join(paragraph.content for paragraph in page.paragraphs)}"
        for page in document.pages
    ]

    schema_path = CONFIG_DIR / "schemas" / "response_schema_pages.json"
    response_schema_pages = read_json(schema_path)

    return system_prompt, parts, response_schema_pages
