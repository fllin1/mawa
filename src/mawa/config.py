from pathlib import Path
import enum


# Directories
ROOT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT_DIR / "data"
EXTERNAL_DATA_DIR = DATA_DIR / "1.external"
OCR_DATA_DIR = DATA_DIR / "2.ocr"
RAW_DATA_DIR = DATA_DIR / "3.raw"
INTERIM_DATA_DIR = DATA_DIR / "4.interim"
PROMPT_DATA_DIR = DATA_DIR / "5.prompt"
ANALYSIS_DATA_DIR = DATA_DIR / "6.analysis"
RENDER_DATA_DIR = DATA_DIR / "7.render"

CONFIG_DIR = ROOT_DIR / "config"

DOCS_DIR = ROOT_DIR / "docs"
IMAGES_DIR = DOCS_DIR / "images"


# Constants
class City(enum.Enum):
    RNU_NATIONAL = "rnu_national"
    BORDEAUX = "bordeaux métropole"
    CLERMONT = "clermont auvergne métropole"
    DIJON = "dijon métropole"
    GRENOBLE = "grenoble-alpes-métropole"
    LILLE = "métropole européenne delille"
    METZ = "metz métropole"
    MONTPELLIER = "montpellier méditerranée métropole"
    NANCY = "métropole du grand nancy"
    NANTES = "nantes métropole"
    NICE = "métropole nice côte d'azur"
    ORLEANS = "orleans métropole"
    RENNES = "rennes métropole"
    ROUEN = "métropole rouen normandie"
    SAINT_ETIENNE = "saint-étienne métropole"
    STRASBOURG = "eurométropole de strasbourg"
    TOULON = "métropole toulon-provence-méditerranée"
    TOULOUSE = "toulouse métropole"
    TOURS = "tours métropole val de loire"
    MARSEILLE = "métropole d'aix-marseille-provence"
    PARIS = "métropole du grand paris"


# Models
MISTRAL_OCR_MODEL = "mistral-ocr-latest"
GEMINI_FLASH_MODEL = "gemini-2.5-flash"
GEMINI_PRO_MODEL = "gemini-3-pro-preview"
