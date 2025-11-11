# Pipeline

| Step    | Functions                      | Description                                                              |
| ------- | ------------------------------ | ------------------------------------------------------------------------ |
| ETL     | OCR, Standardize, SQL          | Extract data from .pdf; Get standard info from docs; Store in a Supabase |
| Analyze | Curate source doc, Gemini      | Use local LLM to clean docs; Give curated data to Gemini for analysis    |
| Deploy  | PDF docs, HTML templates, JSON | Push to supabase the differents forms of the results                     |

## ETL

Converting the raw `pdf` documents into formated text and images.

### Extract

Using Mistral OCR to [extract](https://docs.mistral.ai/capabilities/document_ai/basic_ocr#ocr-pdfs) all text from the PDFs from the [/data/1.raw](/data/1.raw) folder.

All the extracted documents should have the same standardized [JSON](/src/mawa/schemas/document_schema.py) formatted output.

Save the files in the [/data/2.ocr/]("/data/2.ocr) folder.

### Transform

Get the map of _page reference_ from the original document to each `zone` and `zoning`, while considering the `dispositions generales`.

The [prompt](/config/prompt/prompt_extract_zones.txt) and [JSON schema](/config/schemas/response_schema_pages.json) are defined in the [/config](/config/) folder.

### Load

Upload the final form to Supabase.

## Analyze

### Create the prompts
