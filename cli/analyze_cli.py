import typer

from mawa.config import City
from mawa.analyze import Analyze

app = typer.Typer(help="CLI for analysis")


@app.command("create_prompts")
def create_prompts_command(city: City, zone: str) -> None:
    """Create the prompts for the document by zone

    Args:
        city (City): The city of the document
        zone (str): The zone of the document
    """
    analyze = Analyze(city, zone)
    analyze.create_prompt_plu()


@app.command("analyze")
def analyze_command(city: City, zone: str) -> None:
    """Analyze the document by zone

    Args:
        city (City): The city of the document
        zone (str): The zone of the document
    """
    analyze = Analyze(city, zone)
    analyze.generate_analysis_plu()


@app.command("format")
def format_command(city: City, zone: str) -> None:
    """Format the analysis for the document by zone

    Args:
        city (City): The city of the document
        zone (str): The zone of the document
    """
    analyze = Analyze(city, zone)
    analyze.format_analysis()


if __name__ == "__main__":
    app()
