import json
from pathlib import Path
from typing import Optional

import yaml

from mawa.config import CONFIG_DIR


def save_json(data: dict, file_path: Path) -> None:
    """Save a dictionary to a JSON file.

    Args:
        data (dict): The dictionary to save.
        file_path (Path): Path to the file to save the dictionary to.
    """
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def read_json(file_path: Path) -> dict:
    """Read a JSON file and return the dictionary.

    Args:
        file_path (Path): Path to the file to read the dictionary from.
    """
    with open(file_path, "r") as f:
        return json.load(f)


def read_data_tree(subtree: Optional[str] = None) -> dict:
    """Read the data tree from a YAML file.

    Args:
        file_path (Path): Path to the file to read the data tree from.

    Returns:
        The data tree.
    """
    with open(CONFIG_DIR / "data_tree.yaml", "r") as f:
        data_tree = yaml.load(f, Loader=yaml.FullLoader)["structure"]
    if subtree is not None:
        return data_tree[subtree]
    return data_tree
