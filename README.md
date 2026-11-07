# Hindi Wikipedia Search

A small Information Retrieval project built on the Hindi Wikipedia dump. It extracts articles, builds a positional inverted index, ranks results with BM25, and provides command-line and Flask search.

## Project layout

```text
.
├── settings.py       # shared paths and options
├── prepare_data.py   # XML extraction, Hindi preprocessing, index build
├── ir_search.py      # search, BM25, evaluation, index validation, report
├── web_app.py        # Flask search page
├── tests/
│   └── test_ir.py    # small index and search tests
├── output.txt        # generated sample-corpus report
└── data/
    ├── hiwiki-latest-pages-articles.xml.bz2  # downloaded dump
    ├── articles.json                         # extracted article text
    ├── lexicon.json                          # term statistics and posting offsets
    ├── postings.jsonl                        # positional postings
    ├── documents.jsonl                       # article text store
    ├── documents.catalog.json                # titles and document offsets
    └── metadata.json                         # corpus statistics
```

The Python files stay in the project root. `settings.py` keeps paths and BM25 options in one place. Generated data and the downloaded dump are excluded from Git.

## Dataset

Download `hiwiki-latest-pages-articles.xml.bz2` from the [official Wikimedia Hindi dump directory](https://dumps.wikimedia.org/hiwiki/latest/) and save it under `data/`. The extractor reads the compressed file directly. It streams XML pages and saves up to 10,000 valid main-namespace articles.

The current local index has 10,000 documents, 3,905,676 searchable tokens, and 223,053 vocabulary terms. Stop words remain in positional postings for phrase checks, so vocabulary size can include terms excluded from ordinary search and document length counts.

## Install and run

```shell
python -m pip install -r requirements.txt
```

Build the index. If `articles.json` is present, it is reused; otherwise the dump is extracted first:

```shell
python prepare_data.py
```

To refresh extracted articles from the dump and rebuild the index:

```shell
python prepare_data.py --extract
```

Start interactive CLI search:

```shell
python ir_search.py
```

Enter a query and press Enter on an empty line to quit. The app and other search tools are:

```shell
python ir_search.py --evaluate
python ir_search.py --validate
python ir_search.py --report
python web_app.py
```

The report defaults to `output.txt`; pass a path after `--report` to write it elsewhere. The Flask app runs at `http://127.0.0.1:5000` with debug mode off by default.

Run the existing small test suite with:

```shell
python -m unittest discover -s tests -v
```

## Search and ranking

Preprocessing applies Unicode NFC normalization, whitespace cleanup, Hindi tokenization, and the stop-word list in `prepare_data.py`. Positions are assigned before stop-word removal. Exact phrase queries use the original token positions, so a phrase cannot skip over a stop word.

Supported query examples:

```text
भारत
भारत AND इतिहास
भारत OR नेपाल
भारत NOT नेपाल
"भारत की राजधानी"
```

`AND` intersects document sets, `OR` combines them, and binary `NOT` subtracts the right set from the left. Boolean operators are evaluated from left to right. Phrase queries require consecutive original-token positions. Search reads requested posting records from disk instead of loading the full postings file into memory.

BM25 uses `k1 = 1.5` and `b = 0.75`:

```text
IDF(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

score(D,Q) = Σ IDF(t) × tf(t,D) × (k1 + 1)
             / (tf(t,D) + k1 × (1 - b + b × |D| / avgdl))
```

`N` is the indexed document count, `df(t)` is the number of documents containing a term, and `|D|`/`avgdl` use stop-word-filtered lengths. Results show document IDs, titles, BM25 scores, and highlighted snippets.

## Evaluation and reports

`python ir_search.py --evaluate` runs 20 Hindi example queries and reports time and top results. Add manually judged IDs to `SAMPLE_QUERIES` in `ir_search.py` to calculate Precision@10; unjudged queries are labeled N/A. `python ir_search.py --report` writes rare-term postings and example search cases using the actual local index. `python ir_search.py --validate` checks every saved posting record against its term statistics.

## Git

Keep the source files and README in version control. `.gitignore` excludes the compressed dump, extracted articles, generated index files, virtual environments, and Python cache. Do not commit the Wikipedia dump or generated corpus data.
