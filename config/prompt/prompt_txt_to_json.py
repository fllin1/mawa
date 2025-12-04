# -*- coding: utf-8 -*-
"""Text file to JSON converter for prompts.

Simply run this file to convert text format prompt located in the `/references/` folder
to JSON format in the `/config/` folder.

Version: 1.1
Date: 2025-05-20
Author: Grey Panda
"""

from pathlib import Path

from mawa.config import CONFIG_DIR
from mawa.utils import save_json


def convert_prompts_txt_to_json():
    """
    Convert text files to JSON format in the `/config/` folder.
    """
    # Define the paths to the text files
    path_prompt_plu: Path = CONFIG_DIR / "prompt" / "prompt_synthesis.txt"
    path_prompt_extract_zones: Path = CONFIG_DIR / "prompt" / "prompt_extract_zones.txt"
    path_prompt_refacto: Path = CONFIG_DIR / "prompt" / "prompt_refacto.txt"

    # Read the text files and convert them to JSON format
    prompt_plu: str = path_prompt_plu.read_text(encoding="utf-8")
    prompt_extract_zones: str = path_prompt_extract_zones.read_text(encoding="utf-8")
    prompt_refacto: str = path_prompt_refacto.read_text(encoding="utf-8")

    prompt_json = {
        "prompt_plu": prompt_plu,
        "prompt_extract_zones": prompt_extract_zones,
        "prompt_refacto": prompt_refacto,
    }

    # Save the JSON data to a file
    save_path: Path = CONFIG_DIR / "prompt" / "prompt.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(prompt_json, save_path)


if __name__ == "__main__":
    convert_prompts_txt_to_json()
