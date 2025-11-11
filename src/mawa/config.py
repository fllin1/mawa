from pathlib import Path
import enum


# Directories
ROOT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "1.raw"
OCR_DATA_DIR = DATA_DIR / "2.ocr"
INTERIM_DATA_DIR = DATA_DIR / "3.interim"
PROMPT_DATA_DIR = DATA_DIR / "4.prompt"
ANALYSIS_DATA_DIR = DATA_DIR / "5.analysis"

CONFIG_DIR = ROOT_DIR / "config"


# Constants
class City(enum.Enum):
    RNU_NATIONAL = "rnu_national"
    BORDEAUX = "bordeaux"
    GRENOBLE = "grenoble"
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
