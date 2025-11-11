import os
from pathlib import Path

from dotenv import load_dotenv
from mistralai import Mistral
from mistralai.models.ocrresponse import OCRResponse

from mawa.config import MISTRAL_OCR_MODEL

load_dotenv()


class MistralOCR:
    def __init__(self):
        self.client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

    def upload_file(self, file_path: Path) -> str:
        """Upload a file to Mistral OCR.

        Args:
            file_path: Path to the file to upload.

        Returns:
            The ID of the uploaded file.
        """
        return self.client.files.upload(
            file={
                "file_name": file_path.name,
                "content": open(file_path, mode="rb"),
            },
            purpose="ocr",
        ).id

    def process_ocr(self, file_id: str) -> OCRResponse:
        """Process OCR on a file.

        Args:
            file_id: The ID of the file.

        Returns:
            The OCR response.
        """
        signed_url = self._get_signed_url(file_id)
        return self.client.ocr.process(
            model=MISTRAL_OCR_MODEL,
            document={
                "type": "document_url",
                "document_url": signed_url,
            },
            include_image_base64=True,
        )

    def _get_signed_url(self, file_id: str) -> str:
        """Get a signed URL for a file.

        Args:
            file_id: The ID of the file.

        Returns:
            The signed URL.
        """
        return self.client.files.get_signed_url(file_id=file_id).url
