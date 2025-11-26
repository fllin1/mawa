from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from mawa.config import OCR_DATA_DIR, City
from mawa.models import MistralOCR
from mawa.utils import read_data_tree, save_json


class Extraction:
    """
    Class to handle text extraction from PDF files using Mistral OCR.

    Args:
        doc_name (str): name of raw pdf file, may not have suffix.
        city (str): The city of the document.
        document_type (Literal["PLU", "DG", "PLU_AND_DG"]): The type of document.
        zonage (Optional[str]): The zonage of the document.
        zone (Optional[str]): The zone of the document.
    """

    def __init__(
        self,
        city: City,
        doc_name: str,
        doc_type: Literal["PLU", "DG", "PLU_AND_DG"],
        date: Optional[str] = None,
    ):
        self.doc_name = Path(doc_name)
        self.city = city
        self.doc_type = doc_type

        self.data_tree_external = read_data_tree("1.external")[city.value]
        if date:
            self.data_tree_external = self.data_tree_external[date]

    def _find_raw_document_path(self) -> Path:
        """
        TODO: Test this method
        Finds recursively the path of the document in the raw data tree.

        Returns:
            Path: Path to the document
        """
        doc_name = self.doc_name.with_suffix(".pdf")
        for key, values in self.data_tree_external.items():
            if doc_name in values:
                return Path(values[doc_name]["file_path"])
            return self._find_raw_document_path()

    def extraction_function(self) -> Path:
        """Extract and format content from a file using Mistral OCR.

        This function expects a particular directory structure for the raw data.
        Refer to the README.md for more details.

        Returns:
            Path: Path to the saved data
        """
        raw_file_path = self._find_raw_document_path()

        mistral_ocr = MistralOCR()
        file_id = mistral_ocr.upload_file(raw_file_path)
        ocr_response = mistral_ocr.process_ocr(file_id)

        save_file_path = OCR_DATA_DIR / self.city / raw_file_path.stem + ".json"
        save_file_path.parent.mkdir(parents=True, exist_ok=True)

        json_data = ocr_response.model_dump()

        date_of_document = raw_file_path.parents[-2]
        assert datetime.strptime(date_of_document, "%Y-%m-%d")
        json_data["date_of_document"] = date_of_document.as_posix()

        json_data["document_type"] = self.doc_type

        save_json(json_data, save_file_path)
        return save_file_path
