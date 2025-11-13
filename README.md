# MEWE Analysis

Mawa is an urban document analysis pipeline. It currently only supports French PLUs.

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![uv](https://img.shields.io/badge/uv-%23DE5FE9.svg?style=for-the-badge&logo=uv&logoColor=white)
![Google Gemini](https://img.shields.io/badge/google%20gemini-8E75B2?style=for-the-badge&logo=google%20gemini&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)

## Installation

This project requires [uv](https://docs.astral.sh/uv/guides/install-python/) and **Python>=3.12**.

Then simply run this few lines of code, and you're ready to go.

```sh
git clone https://github.com/fllin1/mawa
cd mawa

uv sync
```

## Run the engine

Due to the inconsistent formats of the PLU of each city in France, this pipeline is not yet a plug any document and play the analysis machine. In fact, we'll keep implementing tools to take into account each edgecases that come with each city.

However, there is still a general process :

### Extract, Transform, Load

Client `uv run cli/etl_cli.py`.

1. `extract` has two features, _(if no flag is provided, it will run both these steps at once)_:

   1. `ocr` extract the text from a _.pdf_ document in the [1.raw](./data/1.raw/) folder, and save it in the [2.ocr](./data/2.ocr/) folder.
   2. `pre-process` pre-process the ocr results, creating sub-divisions of the _pages_ into _paragraphs_.

2. `transform` will perform a first analysis of the documents, and return _list_ of page numbers, indicating which pages of the original documents corresponds to which _urban zone_. This _list_ will be saved in the [3.interim](./data/3.interim/) folder.

3. `load` upload this data to the Supabase Database, with the respective images that will be stored in a Bucket. (**NOT_IMPLEMENTED_YET**)

### Analyse

Client `uv run cli/analyze_cli.py`.

### Serve

## Architecture

### Data

All folders and files name should be lowercase, and except for the 5 main subdirectories, they shall only contain characters.

#### 1.raw

Contains the raw PLU _.pdf_ files for each city. Use consistent and "official" names.

Suppose the folder "./data/1.raw/" is the level 0 folder.

**Rules**:

1. the 1st level folders should hold the names of the city;
2. the 2nd level should hold the dates of modification of the files;
3. the 3rd level should be the files themselves;

#### 2.ocr

#### 3.interim

#### 4.prompt

#### 5.analysis
