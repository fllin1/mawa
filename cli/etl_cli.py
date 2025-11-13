from pathlib import Path
import typer
from typing import Literal, Optional

from mawa.etl.extraction import Extraction
from mawa.config import City
from mawa.utils import read_data_tree
from mawa.etl.transform import transform_function

app = typer.Typer(help="CLI for text extraction from PDFs")


@app.command("extract")
def extraction_command(
    city: City,
    doc_name: str,
    doc_type: Literal["PLU", "DG", "PLU_AND_DG"],
    date: Optional[str] = None,
) -> Path:
    """Extract text from a PDF file.

    Args:
        city: The city of the document.
        doc_name: The name of the document.
        doc_type: The type of document.
        step: The step to execute ("extract", "transform", or "all").
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

    document = data_tree[doc_name]
    doc_path = Path(document["file_path"])

    save_path = transform_function(doc_path, apply_extract_zones)
    typer.echo(f"Saved data to {save_path}")
    return save_path


if __name__ == "__main__":
    app()
