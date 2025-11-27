import base64
from datetime import datetime
from io import BytesIO
from typing import Optional, Tuple

import imagehash
from PIL import Image

from mawa.config import (
    CONFIG_DIR,
    INTERIM_DATA_DIR,
    OCR_DATA_DIR,
    RAW_DATA_DIR,
    City,
)
from mawa.models import GeminiModel
from mawa.schemas.document_schema import Document, Page, Paragraph
from mawa.utils import read_json, save_json


class Transform:
    """Class to handle the transformation of the OCR response into a Document schema.

    The pre-processed data is saved in the /data/3.raw/ folder.

    The page-split data is saved in the /data/4.interim/ folder with the suffix .page_split.json.

    The split documents are saved in the /data/4.interim/ folder with the suffix .json.

    Args:
        city (City): The city of the document.
        doc_name (str): The name of the document.
    """

    def __init__(self, city: City, doc_name: str):
        self.city = city.value
        self.doc_name = doc_name

        file_path = f"{city.value}/{doc_name}.json"
        self.ocr_path = OCR_DATA_DIR / file_path
        self.raw_path = RAW_DATA_DIR / file_path
        self.page_split_path = self.raw_path.with_suffix(".page_split.json")

        self.interim_dir = INTERIM_DATA_DIR / city.value

    def ocr_response_to_document(self, zone: Optional[str] = None) -> None:
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
            zone=zone,
            modified_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            model_metadata=model_metadata,
        )

        # Overwrite the raw OCR response with the formatted document
        self.raw_path.parent.mkdir(exist_ok=True, parents=True)
        save_json(document.model_dump(), self.raw_path)

    def clean_document(self) -> None:
        """Clean the document by removing duplicates
        TODO: Improve funciton to remove all non necessary images and text
        """
        document = read_json(self.raw_path)
        document = Document(**document)

        # Count occurences of all page.content and images
        images_dict = {}

        for page in document.pages:
            for image in page.images:
                b64 = image.image_base64
                hash = _get_image_hash_from_base64(b64)
                name_img = image.name_img
                images_dict[name_img] = {
                    "page_index": page.index,
                    "image_hash": hash,
                    "image": image,
                }

        # Create a mapping of page index to page object for quick lookup
        page_map = {page.index: page for page in document.pages}

        # Get duplicated images
        duplicated_images = []
        img_name_set = set[str]()
        for name_img1, image_data1 in images_dict.items():
            for name_img2, image_data2 in images_dict.items():
                if name_img1 >= name_img2:
                    continue

                if image_data1["image_hash"] - image_data2["image_hash"] < 5:
                    if image_data1["image"].name_img not in img_name_set:
                        img_name_set.add(image_data1["image"].name_img)
                        duplicated_images.append(image_data1)
                    if image_data2["image"].name_img not in img_name_set:
                        img_name_set.add(image_data2["image"].name_img)
                        duplicated_images.append(image_data2)

        # Remove duplicated images
        for image_data in duplicated_images:
            # Remove image from page
            page = page_map[image_data["page_index"]]
            page.images.remove(image_data["image"])

            # Remove image tag from paragraph
            image_name = image_data["image"].name_img
            image_tag = f"![{image_name}]({image_name})"
            for paragraph in page.paragraphs:
                if image_tag in paragraph.content:
                    paragraph.content = paragraph.content.replace(image_tag, "")
                    paragraph.content = paragraph.content.strip()
                    break

        save_json(document.model_dump(), self.raw_path)

    def pages_splitting(self, model: Optional[str] = "flash") -> None:
        """Transform the formatted OCR output in a standard format.
        Extracts pages for each zone/zoning combination.

        Args:
            model (Optional[str]): The model to use for the Gemini model
        """
        # Load document from save_path (3.raw)
        document_data = read_json(self.raw_path)
        document = Document(**document_data)

        parts, response_schema = _generate_prompt_parts_split(document)

        gemini_model = GeminiModel(model=model)
        response = gemini_model.generate_content(
            prompt=parts,
            json_schema=response_schema,
        )
        json_response = response.model_dump()

        self.page_split_path.mkdir(exist_ok=True, parents=True)
        save_json(json_response, self.page_split_path)

    def split_documents(self):
        """Split the document into multiple documents based on the zoning and zone."""
        document = read_json(self.raw_path)
        document = Document(**document)

        page_splitting = read_json(self.page_split_path)

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
            save_path = self.interim_dir / f"{zone}.json"
            save_path.parent.mkdir(exist_ok=True, parents=True)
            save_json(doc_zone.model_dump(), save_path)

            self.save_images(zone)

    def save_images(self, zone: str) -> None:
        """Save the images to the /data/interim/city/zone/ folder"""
        doc_zone = read_json(self.interim_dir / f"{zone}.json")
        doc_zone = Document(**doc_zone)

        assert doc_zone.zone == zone, f"Expected {zone}, got {doc_zone.zone}"

        for page in doc_zone.pages:
            for image in page.images:
                image_base64 = image.image_base64
                image_dir = self.interim_dir / zone
                image_dir.mkdir(exist_ok=True, parents=True)
                image_path = (image_dir / image.name_img).with_suffix(".jpg")
                with open(image_path, "wb") as f:
                    f.write(base64.b64decode(image_base64))


# Helper functions


def _generate_prompt_parts_split(document: Document) -> Tuple[list[str], dict]:
    """Returns system prompt, prompt's parts and json_schema.
    Reconstructs markdown from paragraphs by joining them with double newlines.
    Args:
        document: The Document object to extract pages from
    Returns:
        Tuple containing list of page markdown strings, and response schema
    """
    prompt_template = read_json(CONFIG_DIR / "prompt" / "prompt.json")
    instruction = prompt_template["prompt_extract_zones"]

    # Reconstruct markdown from paragraphs (join with \n\n as in ocr_response_to_document)
    parts = [instruction] + [
        f"Page {page.index}: {'\n\n'.join(paragraph.content for paragraph in page.paragraphs)}"
        for page in document.pages
    ]

    schema_path = CONFIG_DIR / "schemas" / "response_schema_pages.json"
    response_schema_pages = read_json(schema_path)

    return parts, response_schema_pages


def _get_image_hash_from_base64(base64_string: str) -> imagehash.ImageHash:
    img_data = base64.b64decode(base64_string)
    img = Image.open(BytesIO(img_data))
    return imagehash.phash(img)
