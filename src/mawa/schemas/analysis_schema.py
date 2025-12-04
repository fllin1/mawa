from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Rule(BaseModel):
    contenu: str = Field(description="Le contenu de la règle")
    source_ref: str = Field(description="La référence de la source de la règle")


class Analysis(BaseModel):
    chapters: dict[str, dict[str, list[Rule]]] = Field(
        description="Les chapitres de l'analyse, "
        "chaque chapitre est un objet avec des sections, "
        "chaque section est un objet avec des règles"
    )
    name_of_document: str = Field(description="Le nom du document")
    date_of_document: str = Field(description="La date du document")
    document_type: Literal["PLU", "DG", "PLU_AND_DG"] = Field(
        description="Le type de document"
    )
    city: str = Field(description="La ville du document")
    zone: Optional[str] = Field(description="La zone du document")
    modified_at: Optional[str] = Field(
        description="La date de modification du document"
    )
    model_metadata: dict[str, Any] = Field(description="Les données du modèle")
