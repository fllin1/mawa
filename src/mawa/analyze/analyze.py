import base64
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.genai.types import Blob, Part

from mawa.config import (
    ANALYSIS_DATA_DIR,
    CONFIG_DIR,
    INTERIM_DATA_DIR,
    PROMPT_DATA_DIR,
    City,
)
from mawa.models import GeminiModel
from mawa.schemas import Analysis, Document
from mawa.utils import read_json, save_json


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
        model: Optional[str] = "pro",
    ):
        self.city = city.value
        self.zone = zone
        self.dg = dg

        self.doc_path = INTERIM_DATA_DIR / self.city / f"{self.zone}.json"
        self.doc = Document(**read_json(self.doc_path))

        self.save_path = ANALYSIS_DATA_DIR / self.city / f"{self.zone}.analysis.json"

        self.model = GeminiModel(model=model)

    def create_prompt_plu(self) -> Path:
        """Create the prompts for the analysis"""
        if self.dg:
            dg_path = INTERIM_DATA_DIR / self.city / f"{self.dg}.json"
            doc_dg = Document(**read_json(dg_path))
        prompts = read_json(CONFIG_DIR / "prompt" / "prompt.json")
        instruction = prompts["prompt_plu"]

        parts = [Part(text=instruction)]
        parts.extend(self._document_to_parts())
        if self.dg:
            parts.extend(self._document_to_parts(doc_dg))

        self._save_prompt_to_json(parts)
        return parts

    def generate_analysis_plu(self) -> Path:
        """Generate the analysis of the PLU"""
        if self.save_path.exists():
            print(f"Analysis already exists for {self.zone}, skipping...")
            return self.save_path

        parts = self.create_prompt_plu()
        json_schema = read_json(
            CONFIG_DIR / "schemas" / "response_schema_synthese.json"
        )

        start_time = time.time()
        response = self.model.generate_content(parts, json_schema=json_schema)
        end_time = time.time()

        json_response = response.model_dump()
        # Remove thought_signature fields from response parts to avoid warnings
        for candidate in json_response.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if isinstance(part, dict) and "thought_signature" in part:
                    part.pop("thought_signature", None)
        json_response["usage_metadata"]["time_taken"] = end_time - start_time

        json_response["usage_metadata"] = self.model.output_tokens_metadata(
            json_response["usage_metadata"]
        )

        self.save_path.parent.mkdir(exist_ok=True, parents=True)
        save_json(json_response, self.save_path)
        return self.save_path

    def format_analysis(self) -> Analysis:
        """Format the analysis into a Analysis schema"""
        if not self.save_path.exists():
            print(f"The analysis for {self.zone} does not exist")
            return None
        json_response = read_json(self.save_path)
        analysis = Analysis(
            chapters=json_response["parsed"],
            name_of_document=self.doc.name_of_document,
            date_of_document=self.doc.date_of_document,
            document_type=self.doc.document_type,
            city=self.city,
            zoning=self.doc.zoning,
            zone=self.doc.zone,
            modified_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            model_metadata={k: v for k, v in json_response.items() if k != "parsed"},
        )
        self.save_path.parent.mkdir(exist_ok=True, parents=True)
        save_json(analysis.model_dump(), self.save_path)
        return analysis

    # Helper functions

    def _document_to_parts(self, document: Optional[Document] = None) -> list[Part]:
        """
        Converts a Document object into a list of Parts for the Gemini API.

        This robust implementation:
        1. Correctly cleans and joins all page text into a single Part per page.
        2. Appends all images for that page AFTER the text Part.
        3. Wraps each image with explicit text delimiters for unambiguous linking.
        """
        if document is None:
            document = self.doc

        parts = []

        for page in document.pages:
            # Step 1: Correctly clean paragraphs using a list comprehension, adding paragraph tags.
            cleaned_paragraphs = [
                f"[P{page.index}.{p.index}] {p.content.replace('\n', ' ').strip()}"
                for p in page.paragraphs
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

        return parts

    def _save_prompt_to_json(self, parts: list[Part]) -> Path:
        """
        Saves the generated prompt to a JSON file for review and tracing.
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

        prompt_data = {
            "timestamp": datetime.now().isoformat(),
            "document_info": {
                "num_pages": len(self.doc.pages),
                "num_parts": len(parts),
            },
            "count_tokens": self.model.input_tokens_metadata(parts),
            "parts": serializable_parts,
        }

        output_dir = PROMPT_DATA_DIR / self.doc.city
        output_dir.mkdir(exist_ok=True, parents=True)

        output_path = output_dir / f"{self.zone}.prompt.json"
        save_json(prompt_data, output_path)

        return output_path
