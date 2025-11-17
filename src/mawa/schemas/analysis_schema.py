from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Rule(BaseModel):
    contenu: str = Field(description="Le contenu de la règle")
    source_ref: str = Field(description="La référence de la source de la règle")


class Chapter(BaseModel):
    sections: dict[str, list[Rule]] = Field(
        description="Mapping of section IDs (e.g., 'section_1_1') to their regulation items"
    )


class Analysis(BaseModel):
    chapters: dict[str, Chapter] = Field(description="Les chapitres de l'analyse")
    name_of_document: str = Field(description="Le nom du document")
    date_of_document: str = Field(description="La date du document")
    document_type: Literal["PLU", "DG", "PLU_AND_DG"] = Field(
        description="Le type de document"
    )
    city: str = Field(description="La ville du document")
    zoning: Optional[str] = Field(description="Le zoning du document")
    zone: Optional[str] = Field(description="La zone du document")
    modified_at: Optional[str] = Field(
        description="La date de modification du document"
    )
    model_metadata: dict[str, Any] = Field(description="Les données du modèle")
