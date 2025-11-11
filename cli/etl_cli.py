from pathlib import Path
import typer
from typing import Literal, Optional

from mawa.etl.extraction import extraction_function
from mawa.config import City
from mawa.utils import read_data_tree
from mawa.etl.transform import transform_function

app = typer.Typer(help="CLI for text extraction from PDFs")


@app.command("extract")
def extraction_command(
    city: City,
    doc_name: str,
    doc_type: Literal["PLU", "DG", "PLU_AND_DG"],
    zonage: Optional[str] = None,
    zone: Optional[str] = None,
) -> Path:
    """Extract text from a PDF file.

    Args:
        city: The city of the document.
        doc_name: The name of the document.
    """
    city = city.value
    doc_name = Path(doc_name).with_suffix(".pdf").name
    data_tree = read_data_tree("1.raw")[city]

    for documents in data_tree.values():
        if doc_name not in documents:
            continue
        doc_path = Path(documents[doc_name]["file_path"])
        save_path = extraction_function(doc_path, city, doc_type, zonage, zone)
        typer.echo(f"Extracted text from {doc_path} to {save_path}")
        return save_path

    typer.echo(f"Error: Document {doc_name} not found in data tree", err=True)
    raise typer.Exit(code=1)


@app.command("transform")
def transform_command(
    city: City,
    doc_name: str,
    apply_extract_zones: Optional[bool] = True,
) -> Path:
    """Formats the raw OCR output in a standard format

    Args:
        city (City): The city of the document
        doc_name (str): The name of the document
        apply_extract_zones (bool): Whether to apply the extract zones prompt
            In some cases, the document is already in the desired format
    """
    doc_name = Path(doc_name).with_suffix(".json").name
    data_tree = read_data_tree("2.ocr")[city.value]

    for key, value in data_tree.items():
        if doc_name != key:
            continue
        doc_path = Path(value["file_path"])
        save_path = transform_function(doc_path, apply_extract_zones)
        typer.echo(f"Saved data to {save_path}")
        return save_path

    typer.echo(f"Error: Document {doc_name} not found in data tree", err=True)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
