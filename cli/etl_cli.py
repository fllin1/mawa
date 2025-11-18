from pathlib import Path
from typing import Literal, Optional

import typer

from mawa.config import City
from mawa.etl import Extraction, Transform

app = typer.Typer(
    help="CLI for text extraction from PDFs", pretty_exceptions_enable=False
)


@app.command("extract")
def extraction_command(
    city: City,
    doc_name: str,
    doc_type: Literal["PLU", "DG", "PLU_AND_DG"],
    date: Optional[str] = None,
) -> Path:
    """Extract text from a PDF file.

    Args:
        city (City): The city of the document.
        doc_name (str): The name of the document.
        doc_type (Literal["PLU", "DG", "PLU_AND_DG"]): The type of document.
        date (Optional[str]): The date of the document.
    """
    extractor = Extraction(
        doc_name=doc_name,
        city=city.value,
        doc_type=doc_type,
        date=date,
    )

    file_path = extractor.extraction_function()
    typer.echo(f"Extraction completed. OCR data saved to {file_path}")
    return file_path


@app.command("transform")
def transform_command(
    city: City,
    doc_name: str,
    method: Literal["format", "clean", "find_split", "apply_split"],
) -> None:
    """Formats the raw OCR output in a standard format

    Args:
        city (City): The city of the document
        doc_name (str): The name of the document
        method (Literal["format", "clean", "find_split", "apply_split"]): The method to use for the transformation
    """
    transformer = Transform(city, doc_name)

    if method == "format":
        transformer.ocr_response_to_document()
    elif method == "clean":
        transformer.clean_document()
    elif method == "find_split":
        transformer.pages_splitting()
    elif method == "apply_split":
        transformer.split_documents()


if __name__ == "__main__":
    app()
