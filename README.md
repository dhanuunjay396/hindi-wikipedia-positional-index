# Hindi Wikipedia Positional Inverted Index Search Engine

This Information Retrieval project extracts Hindi Wikipedia articles, builds a positional inverted index, and supports Boolean, exact-phrase, and BM25 ranked search. Hindi Wikipedia was selected to apply IR techniques to an Indian language and its Devanagari script.

## Dataset

The project uses the Wikimedia Hindi `pages-articles` XML dump from [the official Hindi Wikipedia dump directory](https://dumps.wikimedia.org/hiwiki/latest/). Download the `hiwiki-latest-pages-articles.xml.bz2` file and put it at `data/hiwiki-latest-pages-articles.xml.bz2`. Keep it compressed; extraction streams it with Python's `bz2` and `xml.etree.ElementTree` modules. The extractor accepts namespace-zero pages, skips redirects and short/disambiguation pages, and writes stable Wikipedia page IDs. Its article limit defaults to 10,000.

The verified local input is present. The extracted corpus contains 10,000 unique articles from that dump. The full dump and extracted corpus are local working data and are excluded from the submission archives. No separate hosting link is configured.

## Project layout

```text
.
├── app.py                 # Flask search interface
├── build_index.py         # builds positional postings and metadata
├── config.py              # paths, limits, and BM25 settings
├── evaluate.py            # editable queries and optional P@10 judgments
├── extract_articles.py    # streaming BZ2 XML extraction and markup cleaning
├── prepare_output.py      # reproducible real-corpus output.txt generator
├── preprocess.py          # Unicode normalization, tokenization, stop words
├── search.py              # disk-backed retrieval, Boolean, phrase, BM25
├── validate_index.py      # validates all saved CF/DF and positions
├── tests/test_ir.py       # deterministic synthetic Hindi tests
├── README.md
├── requirements.txt
└── data/                  # local inputs and generated index files (not submitted)
```

## Modules

- `config.py` defines the expected dump/corpus paths, 10,000 article limit, minimum article size, and BM25 parameters.
- `extract_articles.py` streams the compressed MediaWiki XML, cleans common markup, retains page IDs and titles, and saves `data/articles.json`.
- `preprocess.py` applies Unicode NFC normalization, tokenizes Devanagari and ASCII alphanumeric sequences, and filters a small Hindi stop-word list for ranked search. Positions are 1-based offsets in the full token sequence, before stop-word removal.
- `build_index.py` computes per-term collection frequency (CF: total term occurrences) and document frequency (DF: number of distinct documents containing the term), then writes vocabulary, postings, and a document store.
- `search.py` loads vocabulary and document catalog metadata into RAM. It reads an individual term's posting record from the postings file using the byte offset and byte length in the vocabulary. It does not load or retain the complete postings file or a full postings dictionary in RAM. Snippet text is fetched from the document store by document offset.
- `validate_index.py` scans the saved records and checks every term's CF, DF, document IDs, sorted positions, and file statistics.
- `evaluate.py` runs example queries. Precision@10 is shown only for queries with manually entered relevance judgments.
- `app.py` serves the Flask interface.
- `prepare_output.py` creates the 10-term, five-query report from the current real index.

## Index format and positional details

`data/lexicon.json` is the vocabulary metadata loaded into RAM. Each term maps to `cf`, `df`, `offset`, and `length`. `data/postings.jsonl` is the secondary-storage postings file; each byte range is a UTF-8 JSON object mapping document IDs to ascending 1-based token positions. The JSON object is written compactly without a delimiter, so the recorded byte length determines exactly what to read. Query processing opens the file, seeks to the requested offset, and reads only that term's bytes. Missing terms return an empty posting map; malformed metadata or posting records produce an error that asks for an index rebuild.

`data/documents.catalog.json` keeps titles, searchable document lengths, and document-store offsets in memory. `data/documents.jsonl` contains article text and is read at the specific document offset only when a result snippet is needed. `data/metadata.json` stores corpus counts and average searchable document length. The builder's temporary vocabulary/postings structures exist only while constructing the index; normal search has no complete postings dictionary.

All terms, including stop words, have positional postings so exact phrases can match contiguous original token positions (for example, phrase matching respects the position of `की`). Stop words are excluded from ordinary single-term and Boolean tokenization and from searchable document lengths. CF and DF in the lexicon count all indexed tokens, including stop words. Repeated occurrences have multiple sorted positions; CF is the sum of all posting position counts and DF is the number of posting documents. Wikipedia page IDs are preserved as document IDs and duplicate IDs are ignored during indexing.

## Install and run

Python 3.10 or newer is recommended. From the project directory:

```shell
python -m pip install -r requirements.txt
python extract_articles.py                 # up to 10,000 valid articles
python extract_articles.py --limit 20      # optional smaller extraction
python build_index.py
python search.py
```

At the interactive prompt, try:

```text
भारत
भारत AND इतिहास
भारत OR नेपाल
भारत NOT नेपाल
"भारत की राजधानी"
```

Boolean operators are binary and evaluated from left to right. Exact phrases require double quotes around the entire phrase. Results use BM25 with `k1=1.5` and `b=0.75` and show title, Wikipedia page ID, score, and a text snippet.

Run the synthetic tests and optional query evaluator with:

```shell
python -m unittest discover -s tests -v
python validate_index.py
python evaluate.py
```

The test suite builds a small synthetic Hindi corpus in a temporary directory. It verifies in-memory vocabulary metadata, disk-based postings retrieval, CF/DF, positions, repeated terms, phrase matching, AND/OR, unknown terms, and reopening the index. Run the web interface with `python app.py`; Flask serves it at `http://127.0.0.1:5000` with debug mode disabled by default.

## Verified local corpus and sample output

The current local dump produced 10,000 unique indexed articles, 3,888,126 searchable tokens, 222,126 vocabulary terms, average searchable length 388.8126, and a 43,199,068-byte postings file. These values describe the available 10,000-article sample, not the full Hindi Wikipedia dump. Regenerate the required actual-data rare-term and test-case report after building the index:

```shell
python prepare_output.py
```

It writes `output.txt` with ten lowest-DF Hindi vocabulary terms (including their CF, DF, document IDs, and positions) and five reproducible test cases. The submission copy is generated from the current index; synthetic tests are clearly kept separate from these corpus results.

Example positional form (illustrative only):

```text
Term: भारत
CF: 4
DF: 3
Document 101 → [1, 2]
Document 202 → [1]
Document 303 → [2]
```

## Limitations and next steps

Markup cleaning covers common references, templates, links, tables, and tags but is not a complete MediaWiki parser. The stop-word list is intentionally small and manually maintained. The configured corpus cap is 10,000 articles; increase `MAX_ARTICLES` in `config.py` to index more of the dump, subject to available disk and build memory. The current BM25 output is retrieval ranking, not a relevance evaluation: add manual judgments in `evaluate.py` before interpreting P@10. Host the dump or generated index separately if required; neither is included in the submission archive.
