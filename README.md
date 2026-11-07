# Hindi Wikipedia Search Engine

A compact Information Retrieval project for Hindi Wikipedia. It builds a positional index, supports Boolean and exact phrase queries, ranks results with BM25, and provides a command-line search and a Flask web page.

## Project structure

```text
.
├── settings.py       # shared paths and options
├── prepare_data.py   # dump extraction, Hindi preprocessing, and index building
├── ir_search.py      # search, BM25, evaluation, validation, and report commands
├── web_app.py        # Flask search interface
├── tests/
│   └── test_ir.py
├── output.txt        # generated corpus report
└── data/
    ├── hiwiki-latest-pages-articles.xml.bz2  # downloaded dump
    ├── articles.json                         # extracted articles
    ├── lexicon.json                          # term statistics and file offsets
    ├── postings.jsonl                        # positional postings
    ├── documents.jsonl                       # article text
    ├── documents.catalog.json                # titles and document offsets
    └── metadata.json                         # index statistics
```

The four project scripts stay at the root. Paths and ranking options are kept in `settings.py`. The dump and generated data files are ignored by Git.

## Get the dataset

Download `hiwiki-latest-pages-articles.xml.bz2` from the [official Hindi Wikipedia dump directory](https://dumps.wikimedia.org/hiwiki/latest/) and put it in `data/`. Keep the file compressed; the extractor reads it as a BZ2 stream.

The project extracts up to 10,000 valid main-namespace articles. The current local index contains 10,000 articles, 3,905,676 searchable tokens, and 223,053 terms. The vocabulary also contains stop words for phrase matching, while document lengths count searchable tokens only.

## Install and build

Install Flask:

```shell
python -m pip install -r requirements.txt
```

Build the index from existing `data/articles.json`. If that file is missing, the script extracts articles from the dump first:

```shell
python prepare_data.py
```

To refresh the article file from the dump before rebuilding:

```shell
python prepare_data.py --extract
```

For a small extraction, add `--limit 20`, for example `python prepare_data.py --extract --limit 20`.

## Search

Start the interactive command-line search:

```shell
python ir_search.py
```

Enter a query at the prompt. Submit an empty line to quit. Supported examples:

```text
भारत
भारत AND इतिहास
भारत OR नेपाल
भारत NOT नेपाल
"भारत की राजधानी"
```

`AND` returns documents containing both sides, `OR` combines the sides, and binary `NOT` subtracts the right side from the left. Boolean operators are evaluated from left to right. Quotes request an exact phrase, using original token positions so a phrase cannot skip a stop word. Parentheses are not supported.

Results are sorted by BM25 and include the article title, page ID, score, and a matching text snippet.

## How indexing and ranking work

Hindi text is Unicode NFC normalized, whitespace is cleaned, and Devanagari and ASCII tokens are extracted. Stop words are removed for ordinary term search, but their positions remain in the index for exact phrase checks.

The lexicon stores each term's collection frequency (CF), document frequency (DF), and byte offset in the postings file. Search reads only the posting records it needs; it does not load the full postings file into memory. Article text is also read by offset when a result snippet is needed.

BM25 uses `k1 = 1.5` and `b = 0.75`:

```text
IDF(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

score(D,Q) = Σ IDF(t) × tf(t,D) × (k1 + 1)
             / (tf(t,D) + k1 × (1 - b + b × |D| / avgdl))
```

`N` is the indexed document count, `df(t)` is the number of documents containing term `t`, and `|D|` and `avgdl` are stop-word-filtered document lengths.

## Evaluation, validation, and web app

Run the 20 sample queries, validate all saved posting records, or regenerate `output.txt` from the local corpus:

```shell
python ir_search.py --evaluate
python ir_search.py --validate
python ir_search.py --report
```

The sample queries do not have relevance labels, so Precision@10 is shown as N/A. No relevance judgments are invented.

Run the tests:

```shell
python -m unittest discover -s tests -v
```

Start the Flask application:

```shell
python web_app.py
```

Open `http://127.0.0.1:5000`. The page shows ranked results, highlighted snippets, query time, and the indexed document count. Debug mode is disabled by default.

## Git

Commit the source files and documentation. Do not commit the downloaded dump, extracted articles, or generated index files; `.gitignore` excludes them.
