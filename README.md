# MEWE Analysis

Mawa is an urban document analysis pipeline. It currently only supports French PLUs.

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![uv](https://img.shields.io/badge/uv-%23DE5FE9.svg?style=for-the-badge&logo=uv&logoColor=white)
![Google Gemini](https://img.shields.io/badge/google%20gemini-8E75B2?style=for-the-badge&logo=google%20gemini&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)

## Installation

This project requires [uv](https://docs.astral.sh/uv/guides/install-python/) and **Python>=3.12**.

```sh
git clone https://github.com/fllin1/mawa
cd mawa
uv sync
uv pip install -e .
```

## 🚶‍♀️‍➡️ Walkthrough

Due to the inconsistent formats of the PLUi of each intercommunality/city in France, this pipeline is not (yet) a plug any document and play the analysis machine. In fact, we'll continuously implement tools which will take into account each edgecases that come with each city.

The detailled process for each city will be written in the `./cli/city/` folder.

We'll still walk through the general process.

**NOTE**: This project do not address how the data is retrieved. To find that out, check the [archi-data](https://github.com/fllin1/archi-data) project.

### 🛸 Extract, Transform, Load

---

For each **city** and each updated **date** of your documents:

1. Create a directory `./data/1.external/{city}/{date}/`
2. Place a document of name **doc_name** at `./data/1.external/{city}/{date}/{doc_name}.pdf`
3. Then this command:

   ```sh
   uv run cli/data_cli.py tree
   ```

   It will save your data tree at `./config/data_tree.yaml`.

#### Step 1️⃣: OCR

The OCR is currently realized with [Mistral OCR](https://docs.mistral.ai/capabilities/document_ai/basic_ocr).

```sh
uv run cli/etl_cli.py extract $city $doc_name $doc_type --date $date
```

Where `$doc_name` will often either be "reglement", "{zoning}" or "{zone}".
And `$doc_type` is either "DG" (_Dispositions Générales_), "PLU" or "PLU_AND_DG".
Also `$date` is the updated date of the source document.

#### Step 2️⃣: Prepare the data

At this point, the text and images should have been successfuly extracted from the document and saved in the `./data/2.ocr/{city}/{doc_name}.json` file.

The first command which standardize, formats and saves in `./data/3.raw/{city}/{zoning}.json` the _ocr_response_ is mandatory, the second is optional:

```sh
uv run cli/etl_cli.py transform $city $doc_name format
uv run cli/etl_cli.py transform $city $doc_name clean  # Work in progress

```

The `clean` method removes all duplicated images, based on hasing. The goal would be to improve this step, and robustly remove all unnecessary text and images. **Note**: we should keep a copy of the raw formatted file.

Then, depending on the nature of `{doc_name}`, we proceed to one of the two steps:

1. If we are working with **reglement** or **zoning** documents, we need to split them into **zones** documents:

   ```sh
   uv run cli/etl_cli.py transform $city $zoning find_split
   uv run cli/etl_cli.py transform $city $zoning apply_split
   ```

   The splitted documents will be saved in the `./data/4.interim/{city}/` folder, by zone, along with a model response `./data/4.interim/{city}/{zoning}.page_split.json` detailling the page splits.

2. **TODO** (implement the method for zones documents):
   - Copy and paste the formatted files into the _4.interim/{city}_ folder;
   - Use the `mawa.etl.transform.Transform({city}, {doc_name})._save_images({doc_zone})` method to extract and save the images from _base64_ to _.jpg_.

#### Step 3️⃣: Supabase

This Data Loading actually happens "a posteriori".

The final analysis generated will contain tags, it is only after asserting that the tags in the analysis are rightly linked to the formatted document from the _4.interim/{city}_ folder, that we load the data.

### 🩻 Analyse

---

Update your data-tree.

```sh
uv run cli/data_cli.py tree
```

Using the latest Gemini Pro model (currently _gemini-3-pro-preview_), we run the analysis. To see how the API call is done, check the [Analysis class](./src/mawa/analyze/analyze.py), the [prompt](./config/prompt/prompt_synthesis.txt) and the [JSON Schema](./config/schemas/response_schema_synthese.json).

Anyway, run:

```sh
uv run cli/analyze_cli.py analyze $city $zone
uv run cli/analyze_cli.py format $city $zone
```

You should be able to check your prompt structure at `./data/5.prompt/{city}/{zone}.prompt.json` and the result of your analysis at `./data/6.analysis/{city}/{zone}.json`.

If all went well, you should be able to generate a _.pdf_ report from the analysis, using:

```sh
uv run cli/render_cli.py render $city $zone
```

The result should be saved at `./data/7.render/{city}/{zone}.pdf`.

### 🌐 Serve

---

This step consists on creating/updating the database table `documents` and `sources`.

First create the **local** CSV tables:

```sh
uv run cli/data_cli.py local upsert
```

Then push the data to Supabase:

```sh
uv run cli/data_cli.py supabase upsert
uv run cli/data_cli.py supabase upload_images
uv run cli/data_cli.py supabase upload_pdf
```

The data pushed to Supabase is based on the local tables. So you have to create and update them first.

## 📐 Architecture

### 🗃️ Data Folder Structure

TODO

### 🛺 Codebase Cheat Sheet

TODO
