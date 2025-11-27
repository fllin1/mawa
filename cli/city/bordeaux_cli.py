"""CLI for the Bordeaux city

Extraction:
    - Consider the date of the PLUi for all documents,
      regardless of the specific date for a zone.

"""

from datetime import datetime
from pathlib import Path
import shutil

import typer
from tqdm import tqdm

from mawa.analyze import Analyze
from mawa.config import (
    ANALYSIS_DATA_DIR,
    EXTERNAL_DATA_DIR,
    INTERIM_DATA_DIR,
    OCR_DATA_DIR,
    PROMPT_DATA_DIR,
    RAW_DATA_DIR,
    RENDER_DATA_DIR,
    City,
)
from mawa.etl import Extraction, Transform

app = typer.Typer(help="CLI for the Bordeaux city")

CITY = City.BORDEAUX
NUMBER_OF_ZONES = 181


@app.command("extract")
def extract_command(date: str) -> None:
    """Extract the documents for the Bordeaux city"""
    assert datetime.strptime(date, "%Y-%m-%d"), (
        "Date must be in the format YYYY-MM-DD"
    )

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
def transform_command() -> None:
    """Transform the OCR data into a Document schema"""
    ocr_dir = OCR_DATA_DIR / CITY.value

    files = list[Path](ocr_dir.glob("*.json"))
    assert len(files) == NUMBER_OF_ZONES, (
        "Number of files does not match the number of zones: "
        f"{len(files)} != {NUMBER_OF_ZONES}"
    )

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
    assert len(files) == NUMBER_OF_ZONES, (
        "Number of files does not match the number of zones: "
        f"{len(files)} != {NUMBER_OF_ZONES}"
    )


if __name__ == "__main__":
    app()
