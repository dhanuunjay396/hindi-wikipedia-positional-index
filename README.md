# Hindi Wikipedia Positional Inverted Index

## 1. Project Overview

This project implements a Positional Inverted Index-based Information Retrieval system using Hindi Wikipedia articles.

The system extracts Hindi Wikipedia articles, preprocesses the text, and builds an index that stores terms along with their document IDs and exact positions.

It also supports Boolean searching, phrase searching and BM25-based document ranking.

**Dataset:** Hindi Wikipedia  
**Repository:** https://github.com/dhanuunjay396/hindi-wikipedia-positional-index

## 2. Project Structure

```text
hindi-wikipedia-positional-index/
│
├── data/
├── tests/
│   └── test_ir.py
│
├── settings.py
├── prepare_data.py
├── ir_search.py
├── web_app.py
│
├── requirements.txt
├── README.md
├── output.txt
└── .gitignore
```

## 3. Description of Modules

| Module | Description |
|---|---|
| `settings.py` | Defines file paths, indexing configurations and BM25 parameters. |
| `prepare_data.py` | Extracts Wikipedia articles, cleans Hindi text, tokenizes documents and builds the positional index. |
| `ir_search.py` | Loads vocabulary, retrieves disk-based postings and implements Boolean search, phrase search, BM25 ranking and index validation. |
| `web_app.py` | Provides a Flask-based web interface for searching Hindi Wikipedia articles. |
| `tests/test_ir.py` | Contains automated tests for indexing, positions, CF, DF and search operations. |
| `requirements.txt` | Lists the required Python dependencies. |
| `output.txt` | Contains rare Hindi terms with positional postings and five sample test cases. |

## 4. Dataset

The project uses the Hindi Wikipedia XML dump.

**Download:** https://dumps.wikimedia.org/hiwiki/latest/

Download the file:

`hiwiki-latest-pages-articles.xml.bz2`

Place it inside the `data/` directory.

The extraction program processes the compressed XML file and extracts article IDs, titles and cleaned text.

## 5. Indexing and Storage

The system implements a positional inverted index.

Each vocabulary term stores:

- Collection Frequency (CF): Total occurrences of the term.
- Document Frequency (DF): Number of documents containing the term.
- Document IDs.
- Positions of the term in each document.

**Storage architecture:**

- Vocabulary metadata is loaded into main memory (RAM).
- Complete positional postings are stored on secondary storage.
- Each vocabulary entry maintains the byte offset and length of its postings record.
- During searching, only the required postings are retrieved from disk.

Generated index files include:

| File | Description |
|---|---|
| `lexicon.json` | Vocabulary, CF, DF and postings offsets. |
| `postings.jsonl` | Positional postings records. |
| `documents.jsonl` | Original document text. |
| `documents.catalog.json` | Document metadata and text offsets. |
| `metadata.json` | Index statistics and configuration. |

## 6. Installation and Execution

### Step 1: Clone the repository

```bash
git clone https://github.com/dhanuunjay396/hindi-wikipedia-positional-index.git
cd hindi-wikipedia-positional-index
```

### Step 2: Create a virtual environment

```bash
python -m venv venv
```

Activate on Windows:

```powershell
venv\Scripts\activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Extract articles and build the index

Place the Wikipedia dump inside `data/` and execute:

```bash
python prepare_data.py
```

To force fresh extraction:

```bash
python prepare_data.py --extract
```

### Step 5: Run the search engine

```bash
python ir_search.py
```

Enter Hindi search queries in the command-line interface.

## 7. Search Features

The search engine supports:

**Single-term search**
```text
भारत
```

**Boolean AND**
```text
भारत AND इतिहास
```

**Boolean OR**
```text
भारत OR नेपाल
```

**Boolean NOT**
```text
भारत NOT नेपाल
```

**Phrase search**
```text
"भारत की राजधानी"
```

BM25 is used to rank retrieved documents based on relevance.

## 8. Web Interface

Start the Flask application:

```bash
python web_app.py
```

Open:

`http://127.0.0.1:5000`

## 9. Testing and Validation

Run automated tests:

```bash
python -m unittest discover -s tests -v
```

Validate the generated index:

```bash
python ir_search.py --validate
```

Run sample queries:

```bash
python ir_search.py --evaluate
```

Generate the output report:

```bash
python ir_search.py --report
```

## 10. Output

The `output.txt` file contains:

- 10 rare Hindi terms.
- Collection Frequency and Document Frequency.
- Corresponding document IDs and positional indexes.
- Five sample search test cases with their results.

## 11. Note

The complete Wikipedia dataset, extracted articles and generated index files are not included in the GitHub repository because of their size. Download the dataset and build the index locally before running the search engine.
