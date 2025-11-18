"""
CLI for the RNU National city
"""

import re
from shutil import copyfile

import typer

from cli.analyze_cli import analyze_command
from cli.etl_cli import extraction_command
from cli.render_cli import render_command
from mawa.config import RAW_DATA_DIR, City
from mawa.schemas.document_schema import Document
from mawa.utils import read_json, save_json

app = typer.Typer(help="CLI for the RNU National city")

CITY = City.RNU_NATIONAL
ZONE = "rnu_national"


@app.command("pipeline")
def rnu_pipeline_command() -> None:
    """Run the pipeline for the RNU National city"""
    ocr_path = extraction_command(CITY, ZONE)
    copyfile(ocr_path, RAW_DATA_DIR / CITY.value / f"{ZONE}.json")
    analyze_command(CITY, ZONE)
    custom_title = [
        {"text": "Réglement National d'Urbanisme", "style": "city"},
        {"text": "Code de l'urbanisme", "style": "zone"},
    ]
    render_command(CITY, ZONE, custom_title)


@app.command("standardize")
def rnu_standardize_command() -> None:
    """Standardize RNU Data

    - Add tag to /data/3.raw/rnu_national/rnu_national.json
    """
    raw_data_path = RAW_DATA_DIR / CITY.value / f"{ZONE}.json"
    raw_data = read_json(raw_data_path)
    raw_doc = Document(**raw_data)

    pattern = r"Article R111-\d{1,2}-?\d{,2}"
    tags: list[str] = []

    for page in raw_doc.pages:
        for paragraph in page.paragraphs:
            content = paragraph.content
            if match := re.search(pattern, content):
                paragraph.tag = match.group().split(" ")[1].strip()
                tags.append(paragraph.tag)

                source_ref = (
                    f"{raw_doc.document_type}, "
                    f"Page {page.index}.{paragraph.tag}"
                )
                paragraph.source_ref = source_ref

    save_json(raw_doc.model_dump(), raw_data_path.with_suffix(".tags.json"))
    print(f"Tags found: {tags}")


if __name__ == "__main__":
    app()
    """Analyze the document by zone"""
