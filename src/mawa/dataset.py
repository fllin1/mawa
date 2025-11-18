import json
import os
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

from mawa.config import (
    ANALYSIS_DATA_DIR,
    CONFIG_DIR,
    DATA_DIR,
    EXTERNAL_DATA_DIR,
    RAW_DATA_DIR,
    City,
)
from mawa.schemas import Analysis, Document
from mawa.utils import read_json

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TABLE_DOCUMENTS = "documents_test"
TABLE_SOURCES = "sources_test"

DOCUMENT_SAVE_PATH = DATA_DIR / "dataset_documents.csv"
SOURCE_SAVE_PATH = DATA_DIR / "dataset_sources.csv"

COLUMNS_SOURCE = [
    "city",
    "document_name",
    "source_data",  # raw source data (plu or dg)
    "source_images_path",  # {img_tag: img_path}
    "source_date",  # source document date
    "source_url",  # source document url
]

COLUMNS_DOC = [
    "city",
    "document_name",
    "has_dg",
    "zone",
    "analysis_data",  # analysis data
    "modified_at",
]


class Dataset:
    """Class to handle the dataset"""

    def __init__(self, city: City):
        self.city = city.value

        self.raw_data_dir = RAW_DATA_DIR / city.value
        self.analysis_data_dir = ANALYSIS_DATA_DIR / city.value
        self.external_data_dir = EXTERNAL_DATA_DIR / city.value

        self.ref_path = CONFIG_DIR / "references" / "references.json"
        self.references = read_json(self.ref_path)

    def upsert_dataset(self) -> None:
        """Upsert the dataset"""
        if self.city not in self.references:
            raise ValueError(f"Source PLU url not found in {self.ref_path}")

        df_doc, df_source = load_datasets()
        source_count, doc_count = 0, 0
        len_doc_df, len_source_df = len(df_doc), len(df_source)

        dg_path = self.raw_data_dir / "dispositions_generales.json"
        has_dg = dg_path.exists()
        if has_dg:
            dg_data = Document(**read_json(dg_path))
            df_source = self._add_source_row(df_source, dg_data)
            source_count += 1

        prev_plu_path = None

        for file in self.analysis_data_dir.glob("*.analysis.json"):
            analysis = Analysis(**read_json(file))
            df_doc = self._add_doc_row(df_doc, analysis, has_dg)
            doc_count += 1

            name_of_document = analysis.name_of_document
            plu_path = self.raw_data_dir / f"{name_of_document}.tags.json"

            if plu_path != prev_plu_path:
                plu_data = Document(**read_json(plu_path))
                df_source = self._add_source_row(df_source, plu_data)
                source_count += 1

                prev_plu_path = plu_path

        print(f"Processed {doc_count} documents and {source_count} sources")

        added_doc = doc_count - len_doc_df
        print(f"Document: {df_doc.shape[0]} rows, added {added_doc} rows")
        added_source = source_count - len_source_df
        print(f"Sources: {df_source.shape[0]} rows, added {added_source} rows")

        df_doc.to_csv(DOCUMENT_SAVE_PATH, index_label="id")
        df_source.to_csv(SOURCE_SAVE_PATH, index_label="id")

    def _get_images_path(self, document: Document) -> dict[str, str]:
        """Get the images path from the document"""
        name_of_document = document.name_of_document
        image_dir = f"{self.city}/{name_of_document}"

        images_path = {}
        for page in document.pages:
            for image in page.images:
                images_path[image.name_img] = f"{image_dir}/{image.name_img}"
        return images_path

    def _add_source_row(
        self, df_source: pd.DataFrame, document: Document
    ) -> pd.DataFrame:
        """Upsert the source row to the dataframe (update if exists, insert if not)"""
        row_source = {
            "city": self.city,
            "document_name": document.name_of_document,
            "source_data": json.dumps(
                document.model_dump(), ensure_ascii=False
            ),  # JSON dumps to ensure strings are properly double quoted
            "source_images_path": json.dumps(
                self._get_images_path(document), ensure_ascii=False
            ),  # JSON dumps to ensure strings are properly double quoted
            "source_date": document.date_of_document,
            "source_url": self.references[self.city]["source_plu_url"],
        }
        return self.__upsert_row(
            df_source, row_source, key_columns=["city", "document_name"]
        )

    def _add_doc_row(
        self, df_doc: pd.DataFrame, analysis: Analysis, has_dg: bool
    ) -> pd.DataFrame:
        """Upsert the document row to the dataframe (update if exists, insert if not)"""
        row_doc = {
            "city": self.city,
            "document_name": analysis.name_of_document,
            "has_dg": has_dg,
            "zone": analysis.zone,
            "analysis_data": json.dumps(
                analysis.model_dump(), ensure_ascii=False
            ),  # JSON dumps to ensure strings are properly double quoted
            "modified_at": analysis.modified_at,
        }
        return self.__upsert_row(df_doc, row_doc, key_columns=["city", "zone"])

    @staticmethod
    def __upsert_row(
        df: pd.DataFrame, row: dict, key_columns: list[str]
    ) -> pd.DataFrame:
        """Upsert a single row into a dataframe based on key columns.

        - If the dataframe is empty, return a new dataframe with the row.
        - If the row already exists in the dataframe, update the row.
        - If the row does not exist in the dataframe, insert the row.

        Args:
            df: The dataframe to upsert into
            row: Dictionary containing the row data
                (values should already be JSON strings for dict/list types)
            key_columns: List of column names to use as the unique key

        Returns:
            DataFrame with the row upserted (updated if exists, inserted if not)
        """
        if len(df) == 0:
            # Create new dataframe with the row
            return pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        mask = pd.Series([True] * len(df))
        for col in key_columns:
            if col not in row:
                raise ValueError(f"Key column '{col}' not found in row data")
            mask = mask & (df[col] == row[col])

        if mask.any():
            # Update existing row(s)
            for col, value in row.items():
                df.loc[mask, col] = value
            return df
        else:
            # Insert new row
            return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


class Supabase:
    """Class to handle the Supabase database"""

    def __init__(self):
        self.client = create_client(
            supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY
        )
        self.df_doc, self.df_source = load_datasets()

    def upsert_documents_dataset(
        self, city: Optional[City] = None, zone: Optional[str] = None
    ) -> None:
        """Upsert the documents dataset to the Supabase database"""
        df_doc = self.df_doc.copy()
        if city is not None:
            df_doc = df_doc[df_doc["city"] == city.value]
        if zone is not None:
            df_doc = df_doc[df_doc["zone"] == zone]

        self.client.table(TABLE_DOCUMENTS).upsert(
            df_doc.to_dict(orient="records")
        ).execute()

    def upsert_sources_dataset(
        self, city: Optional[City] = None, document_name: Optional[str] = None
    ) -> None:
        """Upsert the sources dataset to the Supabase database"""
        df_source = self.df_source.copy()
        if city is not None:
            df_source = df_source[df_source["city"] == city.value]
        if document_name is not None:
            df_source = df_source[df_source["document_name"] == document_name]

        self.client.table(TABLE_SOURCES).upsert(
            df_source.to_dict(orient="records")
        ).execute()


def load_datasets() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the datasets"""
    if DOCUMENT_SAVE_PATH.exists():
        df_doc = pd.read_csv(DOCUMENT_SAVE_PATH, index_col="id")
        df_doc["analysis_data"] = df_doc["analysis_data"].apply(
            lambda x: json.loads(x) if isinstance(x, str) else x
        )
    else:
        df_doc = pd.DataFrame(columns=COLUMNS_DOC)

    if SOURCE_SAVE_PATH.exists():
        df_source = pd.read_csv(SOURCE_SAVE_PATH, index_col="id")
        df_source["source_data"] = df_source["source_data"].apply(
            lambda x: json.loads(x) if isinstance(x, str) else x
        )
        df_source["source_images_path"] = df_source["source_images_path"].apply(
            lambda x: json.loads(x) if isinstance(x, str) else x
        )
    else:
        df_source = pd.DataFrame(columns=COLUMNS_SOURCE)

    return df_doc, df_source
