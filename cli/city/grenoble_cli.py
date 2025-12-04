"""CLI for the Grenoble city"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from tqdm import tqdm

from mawa.analyze import Analyze
from mawa.config import (
    ANALYSIS_DATA_DIR,
    CONFIG_DIR,
    EXTERNAL_DATA_DIR,
    INTERIM_DATA_DIR,
    OCR_DATA_DIR,
    ROOT_DIR,
    City,
)
from mawa.etl import Extraction, Transform
from mawa.models import GeminiModel
from mawa.utils import read_json, save_json

app = typer.Typer(help="CLI for the Grenoble city")

CITY = City.GRENOBLE
NUMBER_OF_ZONES = 181


@app.command("extract")
def extract_command(date: str) -> None:
    """Extract the documents for the Grenoble city"""
    assert datetime.strptime(date, "%Y-%m-%d"), "Date must be in the format YYYY-MM-DD"

    external_dir = EXTERNAL_DATA_DIR / CITY.value / date

    files = list[Path](external_dir.glob("*.pdf"))
    assert external_dir / "dispositions_generales.pdf" in files, (
        "Dispositions générales file not found"
    )

    for file in tqdm(files, desc="Mistral OCR", total=len(files)):
        doc_type = "DG" if file.stem == "dispositions_generales" else "PLU"
        extractor = Extraction(
            doc_name=file.stem,
            city=CITY,
            doc_type=doc_type,
            date=date,
        )

        extractor.extraction_function()


@app.command("transform")
def transform_command(find_split: bool = False) -> None:
    """Transform the OCR data into a Document schema"""
    ocr_dir = OCR_DATA_DIR / CITY.value

    files = list[Path](ocr_dir.glob("*.json"))
    assert ocr_dir / "dispositions_generales.json" in files, (
        "Dispositions générales file not found"
    )

    interim_dir = INTERIM_DATA_DIR / CITY.value
    interim_dir.mkdir(exist_ok=True, parents=True)

    for file in tqdm(files, desc="Transform", total=len(files)):
        transformer = Transform(city=CITY, doc_name=file.name)
        zone = file.stem
        transformer.ocr_response_to_document(zone=zone)
        # transformer.clean_document()
        if find_split:
            transformer.pages_splitting()
        transformer.split_documents()


@app.command("analyze")
def analyze_command() -> None:
    """Analyze the documents for the Grenoble city"""
    interim_dir = INTERIM_DATA_DIR / CITY.value
    files = sorted(list[Path](interim_dir.glob("*.json")))
    assert interim_dir / "Dispositions Générales.json" in files, (
        "Dispositions générales file not found"
    )
    for file in tqdm(files, desc="Analyze", total=len(files)):
        analyzer = Analyze(
            city=CITY, zone=file.stem, dg="Dispositions Générales", model="flash"
        )
        analyzer.generate_analysis_plu()
        analyzer.format_analysis()
        break


# ============================================================================
# REFACTORING HELPERS
# ============================================================================

# Path to the backup directory containing old format JSON files
BACKUP_DATA_DIR = ROOT_DIR / "backup" / "data" / "processed" / "grenoble"


def refactor_analysis(
    old_json_path: Path,
    save_path: Path,
    model: str = "flash",
) -> dict:
    """
    Refactor old-format PLU JSON to new synthesized format.

    Uses GeminiModel with system prompt for JSON-to-JSON transformation.
    The LLM aggregates atomized rules and applies the "Architect Synthetic" style.

    Args:
        old_json_path: Path to the old format JSON file
        save_path: Path to save the refactored JSON
        model: Model to use ("flash" or "pro")

    Returns:
        The refactored JSON as a dictionary
    """
    # Skip if already processed
    if save_path.exists():
        print(f"Refactored analysis already exists at {save_path}, skipping...")
        return read_json(save_path)

    # Load the old JSON
    old_json = read_json(old_json_path)

    # Load system prompt and output schema
    prompts = read_json(CONFIG_DIR / "prompt" / "prompt.json")
    system_prompt = prompts["prompt_refacto"]
    json_schema = read_json(CONFIG_DIR / "schemas" / "response_schema_synthese.json")

    # Initialize the model
    gemini = GeminiModel(model=model)

    # Create prompt with the old JSON to refactor
    prompt_content = json.dumps(old_json, ensure_ascii=False, indent=2)

    # Generate the refactored analysis
    start_time = time.time()
    response = gemini.generate_content(
        prompt=[prompt_content],
        system_prompt=system_prompt,
        json_schema=json_schema,
    )
    end_time = time.time()

    # Process response
    json_response = response.model_dump()

    # Clean up thought_signature fields if present
    for candidate in json_response.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if isinstance(part, dict) and "thought_signature" in part:
                part.pop("thought_signature", None)

    # Add timing metadata
    json_response["usage_metadata"]["time_taken"] = end_time - start_time
    json_response["usage_metadata"] = gemini.output_tokens_metadata(
        json_response["usage_metadata"]
    )

    # Add refactoring metadata
    json_response["refactor_metadata"] = {
        "source_file": str(old_json_path),
        "refactored_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Save the result
    save_path.parent.mkdir(exist_ok=True, parents=True)
    save_json(json_response, save_path)

    return json_response


def list_backup_zones() -> list[tuple[str, Path]]:
    """
    List all available zones in the backup directory.

    Returns:
        List of tuples (zone_name, file_path)
    """
    zones = []
    for category_dir in BACKUP_DATA_DIR.iterdir():
        if category_dir.is_dir():
            for json_file in category_dir.glob("*.json"):
                zones.append((json_file.stem, json_file))
    return sorted(zones, key=lambda x: x[0])


@app.command("refactor")
def refactor_command(
    zone: Optional[str] = typer.Argument(
        None,
        help="Zone name to refactor (e.g., 'AUP1r'). If not provided, lists available zones.",
    ),
    model: str = typer.Option("flash", help="Model to use: 'flash' or 'pro'"),
    all_zones: bool = typer.Option(False, "--all", help="Refactor all zones"),
) -> None:
    """Refactor old PLU analysis JSON to the new synthesized format."""
    output_dir = ANALYSIS_DATA_DIR / CITY.value

    if all_zones:
        # Process all zones
        zones = list_backup_zones()
        print(f"Found {len(zones)} zones to refactor")

        for zone_name, old_path in tqdm(zones, desc="Refactoring"):
            save_path = output_dir / f"{zone_name}.refactored.json"
            try:
                refactor_analysis(old_path, save_path, model=model)
            except Exception as e:
                print(f"Error refactoring {zone_name}: {e}")
                continue

    elif zone is None:
        # List available zones
        zones = list_backup_zones()
        print(f"\nAvailable zones in backup ({len(zones)} total):\n")
        for zone_name, file_path in zones:
            print(f"  - {zone_name} ({file_path.parent.name})")
        print("\nUsage: grenoble refactor <zone_name> [--model flash|pro]")
        print("       grenoble refactor --all [--model flash|pro]")

    else:
        # Find and refactor a specific zone
        zones = list_backup_zones()
        zone_map = {name: path for name, path in zones}

        if zone not in zone_map:
            print(f"Zone '{zone}' not found in backup directory.")
            print(f"Available zones: {', '.join(sorted(zone_map.keys())[:10])}...")
            raise typer.Exit(1)

        old_path = zone_map[zone]
        save_path = output_dir / f"{zone}.refactored.json"

        print(f"Refactoring {zone}...")
        print(f"  Input:  {old_path}")
        print(f"  Output: {save_path}")

        refactor_analysis(old_path, save_path, model=model)
        print(f"Done! Refactored analysis saved to {save_path}")


if __name__ == "__main__":
    app()
