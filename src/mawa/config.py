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
    BORDEAUX = "bordeaux"
    GRENOBLE = "grenoble-alpes"
    LILLE = "lille"
    MONTPELLIER = "montpellier"
    NANTES = "nantes"
    NICE = "nice"
    RENNES = "rennes"
    ROUEN = "rouen"
    STRASBOURG = "strasbourg"
    TOULOUSE = "toulouse"


# Models
MISTRAL_OCR_MODEL = "mistral-ocr-latest"
GEMINI_FLASH_MODEL = "gemini-2.5-flash"
GEMINI_PRO_MODEL = "gemini-2.5-pro"
