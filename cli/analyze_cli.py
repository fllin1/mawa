import typer

from mawa.config import City
from mawa.analyze.create_prompts import Analyze

app = typer.Typer(help="CLI for analysis")


@app.command("create_prompts")
def analyze_command(city: City, zone: str) -> None:
    """Analyze the document by zone

    Args:
        city (City): The city of the document
        zone (str): The zone of the document
    """
    analyze = Analyze(city, zone)
    analyze.create_prompts()


if __name__ == "__main__":
    app()
