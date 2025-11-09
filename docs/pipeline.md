# Pipeline

| Step    | Functions                      | Description                                                              |
| ------- | ------------------------------ | ------------------------------------------------------------------------ |
| ETL     | OCR, Standardize, SQL          | Extract data from .pdf; Get standard info from docs; Store in a Supabase |
| Analyze | Curate source doc, Gemini      | Use local LLM to clean docs; Give curated data to Gemini for analysis    |
| Deliver | PDF docs, HTML templates, JSON | Push to supabase the differents forms of the results                     |

## ETL

### Extract

Using Mistral OCR to [extract](https://docs.mistral.ai/capabilities/document_ai/basic_ocr#ocr-pdfs) all text from the PDFs.

### Transform

All the extracted documents should have the same standardized [JSON](./pipeline/etl_transform_schema.json) formatted output.

### Load

Upload the final form to Supabase.

## Analyze

### Curate raw data

1. `Dispositions Générales`: From the list of available zones, extract the main information in a raw DG. Inject the curated result for each analysis.
2. `Plan Local d'Urbanisme`:
   1. À garder (fortement utile) : Règlement écrit (articles, définitions, prescriptions par zone), OAP (lorsqu’elles contiennent des règles opposables), servitudes d’utilité publique, annexes réglementaires, tableaux de gabarits/emprises, cartes/croquis s’ils sont référencés par des articles.
   2. À retirer (faible valeur) : page de garde/mentions légales, crédits, signatures, sommaires/“Table des matières”, pages blanches, pages de séparation, logos/bandeaux décoratifs, filigranes, numéros de page, en-têtes/pieds récurrents, “listes de révisions”, remerciements.
   3. Cas à trier : PADD & rapport de présentation (souvent non opposables) — garde-les seulement si tu fais de l’analyse de contexte, sinon filtre-les.
