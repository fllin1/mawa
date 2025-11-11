from pathlib import Path
import datetime

import typer
import yaml

from mawa.config import CONFIG_DIR, DATA_DIR

app = typer.Typer(help="CLI for data management")


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


def _build_tree_structure(directory: Path, current_depth: int = 0) -> dict:
    """
    Recursively builds a tree structure of a directory.

    Args:
        directory: Path to the directory to scan
        current_depth: Current depth in the traversal

    Returns:
        Dictionary representing the directory structure
    """
    if not directory.exists():
        raise ValueError(f"Directory {directory} does not exist")

    structure = {}
    items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))

    for item in items:
        if item.is_dir():
            structure[item.name] = _build_tree_structure(item, current_depth + 1)
        else:
            structure[item.name] = {
                "type": "file",
                "size_bytes": item.stat().st_size,
                "file_path": str(item),
            }
    return structure


if __name__ == "__main__":
    app()
