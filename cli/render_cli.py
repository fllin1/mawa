import typer

from mawa.config import City, ANALYSIS_DATA_DIR, RENDER_DATA_DIR
from mawa.render.pdf_generator import generate_pdf_report
from mawa.render.utils import get_references

app = typer.Typer(help="CLI for rendering")


@app.command("render")
def render_command(city: City, zone: str) -> None:
    """Render the document by zone

    Args:
        city (City): The city of the document
        zone (str): The zone of the document
    """
    input_path = ANALYSIS_DATA_DIR / city.value / f"{zone}.analysis.json"
    output_directory = RENDER_DATA_DIR / city.value / "pdf"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = (output_directory / f"{zone}.pdf").as_posix()

    references = get_references(city.value)

    generate_pdf_report(
        input_path,
        output_path,
        references=references,
        custom_title=[
            {"text": "Réglement National d'Urbanisme", "style": "city"},
            # {"text": "Plan Local d'Urbanisme", "style": "zoning"},
            {"text": "Code de l'urbanisme", "style": "zone"},
        ],
    )


if __name__ == "__main__":
    app()
