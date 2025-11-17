from mawa.config import CONFIG_DIR
from mawa.utils import read_json


def get_references(city_name: str) -> str:
    """
    Retrieve the references for a given city from the references.json configuration.

    Args:
        city_name (str): The name of the city

    Returns:
        dict: The references for the city
    """
    config_file = CONFIG_DIR / "references" / "references.json"
    config = read_json(config_file)

    global_references = config.get("mwplu", {})
    vocabulaire = global_references.get("vocabulaire")
    politiques_vente = global_references.get("politiques_vente")
    politique_confidentialite = global_references.get("politique_confidentialite")
    cgu = global_references.get("cgu")

    city_data = config.get(city_name, {})
    source_url = city_data.get("source_plu_url")

    references = {
        "source_plu_url": source_url,
        "vocabulaire": vocabulaire,
        "politiques_vente": politiques_vente,
        "politique_confidentialite": politique_confidentialite,
        "cgu": cgu,
    }

    return references
