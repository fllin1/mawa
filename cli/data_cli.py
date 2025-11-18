import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml

from mawa.config import CONFIG_DIR, DATA_DIR, City
from mawa.dataset import Dataset, Supabase

app = typer.Typer(help="CLI for data management")

local = typer.Typer(help="CLI for local data management")
supabase = typer.Typer(help="CLI for supabase data management")

app.add_typer(local, name="local")
app.add_typer(supabase, name="supabase")


@local.command("upsert")
def local_upsert_data_command(city: City) -> None:
    """Upsert the dataset for the city"""
    dataset = Dataset(city)
    dataset.upsert_dataset()
    typer.echo(f"Dataset upserted for {city.value}")


@supabase.command("upsert")
def supabase_upsert_data_command(
    documents: bool = typer.Option(True, help="Upsert the documents dataset"),
    sources: bool = typer.Option(True, help="Upsert the sources dataset"),
    city: Optional[City] = None,
    zone: Optional[str] = None,
    document_name: Optional[str] = None,
) -> None:
    """Upsert the dataset for the city"""
    supabase = Supabase()
    if documents:
        supabase.upsert_documents_dataset(city, zone)
    if sources:
        supabase.upsert_sources_dataset(city, document_name)


@app.command("tree")
def create_tree_command(
    output_file: str = typer.Option(
        "data_tree.yaml", "--output", "-o", help="Output filename"
    ),
):
    """
    Creates yaml file with the data tree structure,
    including all subdirectories and files
    """
    if not DATA_DIR.exists():
        typer.echo(f"Error: Directory {DATA_DIR} does not exist", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Building tree structure for: {DATA_DIR}")

    tree = {
        "root": str(DATA_DIR),
        "modified_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "structure": _build_tree_structure(DATA_DIR),
    }

    output_path = CONFIG_DIR / output_file
    with open(output_path, "w") as f:
        yaml.dump(tree, f, indent=4, default_flow_style=False, sort_keys=False)

    typer.echo(f"Tree structure saved to: {output_path}")


def _build_tree_structure(directory: Path) -> dict:
    """
    Recursively builds a tree structure of a directory.

    Args:
        directory: Path to the directory to scan

    Returns:
        Dictionary representing the directory structure
    """
    if not directory.exists():
        raise ValueError(f"Directory {directory} does not exist")

    structure = {}
    items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))

    for item in items:
        if item.is_dir():
            structure[item.name] = _build_tree_structure(item)
        else:
            structure[item.name] = {
                "type": "file",
                "size_bytes": item.stat().st_size,
                "file_path": str(item),
            }
    return structure


if __name__ == "__main__":
    app()
