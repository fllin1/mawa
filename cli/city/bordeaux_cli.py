"""CLI for the Bordeaux city

Extraction:
    - Consider the date of the PLUi for all documents,
      regardless of the specific date for a zone.

"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from tqdm import tqdm

from mawa.analyze import Analyze
from mawa.config import (
    EXTERNAL_DATA_DIR,
    INTERIM_DATA_DIR,
    OCR_DATA_DIR,
    RAW_DATA_DIR,
    City,
)
from mawa.dataset import Dataset, Supabase
from mawa.etl import Extraction, Transform
from mawa.etl.table_utils import replace_tables_with_images
from mawa.schemas.document_schema import Document
from mawa.utils import read_json, save_json

app = typer.Typer(help="CLI for the Bordeaux city")
data = typer.Typer(help="Data management for Bordeaux")
app.add_typer(data, name="data")

CITY = City.BORDEAUX
NUMBER_OF_ZONES = 181


@app.command("extract")
def extract_command(date: str) -> None:
    """Extract the documents for the Bordeaux city"""
    assert datetime.strptime(date, "%Y-%m-%d"), "Date must be in the format YYYY-MM-DD"

    external_dir = EXTERNAL_DATA_DIR / CITY.value / date

    files = list[Path](external_dir.glob("*.pdf"))
    assert len(files) == NUMBER_OF_ZONES, (
        "Number of files does not match the number of zones"
    )

    for file in tqdm(files, desc="Mistral OCR", total=len(files)):
        extractor = Extraction(
            doc_name=file.stem,
            city=CITY,
            doc_type="PLU_AND_DG",
            date=date,
        )
        extractor.extraction_function()


@app.command("transform")
def transform_command(date: str) -> None:
    """Transform the OCR data into a Document schema"""
    ocr_dir = OCR_DATA_DIR / CITY.value

    files = list[Path](ocr_dir.glob("*.json"))
    assert len(files) == NUMBER_OF_ZONES, (
        "Number of files does not match the number of zones: "
        f"{len(files)} != {NUMBER_OF_ZONES}"
    )

    external_dir = EXTERNAL_DATA_DIR / CITY.value / date
    raw_dir = RAW_DATA_DIR / CITY.value
    interim_dir = INTERIM_DATA_DIR / CITY.value
    interim_dir.mkdir(exist_ok=True, parents=True)

    for file in tqdm(files, desc="Transform", total=len(files)):
        transformer = Transform(city=CITY, doc_name=file.name)
        zone = file.stem
        transformer.ocr_response_to_document(zone=zone)
        transformer.clean_document()  # Doesn't seem to do anything

        # No need to split the documents, as we have one document per zone
        raw_path = raw_dir / file.name
        interim_path = interim_dir / file.name
        shutil.copy(raw_path, interim_path)

        document = Document(**read_json(interim_path))
        external_path = external_dir / file.with_suffix(".pdf").name
        document = replace_tables_with_images(document=document, pdf_path=external_path)
        save_json(document.model_dump(), interim_path)

        # Image saving isn't mandatory, but it's there for visual inspection
        transformer.save_images(zone=zone)


@app.command("prompt")
def prompt_command() -> None:
    """Generate the prompts for the documents for the Bordeaux city"""
    interim_dir = INTERIM_DATA_DIR / CITY.value
    files = list[Path](interim_dir.glob("*.json"))
    assert len(files) == NUMBER_OF_ZONES, (
        "Number of files does not match the number of zones: "
        f"{len(files)} != {NUMBER_OF_ZONES}"
    )

    for file in tqdm(files, desc="Prompt", total=len(files)):
        analyze = Analyze(city=CITY, zone=file.stem)
        analyze.create_prompt_plu()


@app.command("analyze")
def analyze_command() -> None:
    """Analyze the documents for the Bordeaux city"""
    interim_dir = INTERIM_DATA_DIR / CITY.value
    files = list[Path](interim_dir.glob("*.json"))
    files = sorted(files)
    assert len(files) == NUMBER_OF_ZONES, (
        "Number of files does not match the number of zones: "
        f"{len(files)} != {NUMBER_OF_ZONES}"
    )

    for file in tqdm(files, desc="Analyze", total=len(files)):
        analyze = Analyze(city=CITY, zone=file.stem)
        analyze.generate_analysis_plu()
        try:
            analyze.format_analysis()
        except KeyError:
            print(f"KeyError for {file.stem}, skipping...")
            continue


# ============================================================================
# DATA MANAGEMENT COMMANDS
# ============================================================================


@data.command("local-upsert")
def data_local_upsert_command() -> None:
    """Upsert Bordeaux dataset to local CSV files.

    Saves documents to data/dataset_documents.csv and sources to data/dataset_sources.csv.
    """
    dataset = Dataset(CITY)
    dataset.upsert_dataset()
    typer.echo(f"Dataset upserted for {CITY.value}")


@data.command("supabase-upsert")
def data_supabase_upsert_command(
    documents: bool = typer.Option(True, help="Upsert the documents dataset"),
    sources: bool = typer.Option(True, help="Upsert the sources dataset"),
    zone: Optional[str] = typer.Option(None, "--zone", "-z", help="Filter by zone"),
    document_name: Optional[str] = typer.Option(
        None, "--document-name", "-n", help="Filter by document name"
    ),
) -> None:
    """Upsert Bordeaux dataset to Supabase database.

    Upserts documents and/or sources tables. Use filters to target specific records.
    """
    supabase = Supabase()
    if documents:
        supabase.upsert_documents_dataset(CITY, zone)
        typer.echo(f"Documents upserted for {CITY.value}")
    if sources:
        supabase.upsert_sources_dataset(CITY, document_name)
        typer.echo(f"Sources upserted for {CITY.value}")


if __name__ == "__main__":
    app()
