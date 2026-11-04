import argparse
import bz2
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from config import DATASET_PATH, ARTICLES_PATH, MAX_ARTICLES, MIN_ARTICLE_LENGTH

NS = "{http://www.mediawiki.org/xml/export-0.11/}"


def clean_wikitext(text):
    text = re.sub(r"(?is)<ref\b[^>]*>.*?</ref\s*>|<ref\b[^>]*/\s*>", " ", text)
    text = re.sub(r"(?is)<(nowiki|gallery|math)\b[^>]*>.*?</\1\s*>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"(?ms)^\s*\{\|.*?^\s*\|\}\s*$", " ", text)
    text = re.sub(r"(?m)^\s*\[\[(?:File|Image|Category|चित्र|श्रेणी):[^\]]*\]\]\s*$", " ", text, flags=re.I)
    text = re.sub(r"(?s)\{\{.*?\}\}", " ", text)
    text = re.sub(r"\[\[([^]|]+\|)?([^]]+)\]\]", lambda m: (m.group(2) or m.group(1) or ""), text)
    text = re.sub(r"\[(?:https?://\S+\s*)?([^\]]*)\]", r"\1", text)
    text = re.sub(r"'{2,5}", "", text)
    text = re.sub(r"(?m)^\s*\*+\s*", "", text)
    return " ".join(text.split())


def extract(limit=MAX_ARTICLES, dataset_path=DATASET_PATH, articles_path=ARTICLES_PATH):
    if not dataset_path.exists():
        raise FileNotFoundError(f"Wikipedia dump not found: {dataset_path}. Download it from https://dumps.wikimedia.org/hiwiki/latest/")
    start = time.time()
    pages = accepted = redirects = short = 0
    articles = []
    seen_ids = set()
    with bz2.open(dataset_path, "rb") as stream:
        for _, elem in ET.iterparse(stream, events=("end",)):
            if elem.tag != NS + "page":
                continue
            pages += 1
            title = elem.findtext(NS + "title", "")
            redirect = elem.find(NS + "redirect")
            ns = elem.findtext(NS + "ns", "")
            revision = elem.find(NS + "revision")
            page_id = elem.findtext(NS + "id", "")
            raw = revision.findtext(NS + "text", "") if revision is not None else ""
            if ns == "0" and redirect is None:
                clean = clean_wikitext(raw)
                if "{{disambiguation}}" in raw.lower() or "{{dab}}" in raw.lower() or "बहुविकल्पी" in title.lower():
                    pass
                elif len(clean) >= MIN_ARTICLE_LENGTH and page_id not in seen_ids:
                    articles.append({"id": int(page_id), "title": title, "text": clean})
                    seen_ids.add(page_id)
                    accepted += 1
                else:
                    short += 1
            elif redirect is not None:
                redirects += 1
            elem.clear()
            if accepted >= limit:
                break
    articles_path.parent.mkdir(parents=True, exist_ok=True)
    articles_path.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pages examined: {pages}; articles saved: {len(articles)}; redirects skipped: {redirects}; short/disambiguation skipped: {short}; elapsed: {time.time()-start:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=MAX_ARTICLES, help="maximum valid articles (small values are useful for a smoke run)")
    parser.add_argument("--output", type=str, default=str(ARTICLES_PATH), help="output JSON path (defaults to data/articles.json)")
    args = parser.parse_args()
    extract(max(1, args.limit), articles_path=Path(args.output))
