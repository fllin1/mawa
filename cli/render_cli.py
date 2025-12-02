from typing import Optional

import typer

from mawa.config import ANALYSIS_DATA_DIR, RENDER_DATA_DIR, City
from mawa.render import generate_pdf_report, get_references

app = typer.Typer(help="CLI for rendering")


@app.command("render")
def render_command(
    city: City, zone: str, custom_title: Optional[list[dict[str, str]]] = None
) -> None:
    """Render the document by zone

    Args:
        city (City): The city of the document
        zone (str): The zone of the document
    """
    input_path = ANALYSIS_DATA_DIR / city.value / f"{zone}.analysis.json"
    output_directory = RENDER_DATA_DIR / city.value
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = (output_directory / f"{zone}.pdf").as_posix()

    references = get_references(city.value)

    if not custom_title:
        custom_title = [
            {"text": f"{city.value.title()}", "style": "city"},
            {"text": "Plan Local d'Urbanisme intercommunal", "style": "zoning"},
            {"text": f"Zone {zone}", "style": "zone"},
        ]

    generate_pdf_report(
        input_path,
        output_path,
        references=references,
        custom_title=custom_title,
    )


if __name__ == "__main__":
    app()
