import json
import html
import re
import time
from flask import Flask, request, render_template_string
from config import FLASK_DEBUG, METADATA_PATH
from search import load_index, search

app = Flask(__name__)
HTML = '''<!doctype html><html lang="hi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hindi Wikipedia Search Engine</title><style>body{font:16px system-ui;background:#f3f6fb;color:#182338;margin:0}.wrap{max-width:900px;margin:7vh auto;padding:24px}h1{color:#173b70}form{display:flex;gap:8px}input{flex:1;padding:14px;border:1px solid #ccd5e2;border-radius:10px;font-size:1rem}button{padding:0 22px;border:0;border-radius:10px;background:#2056a1;color:white;font-size:1rem}.card{background:white;padding:18px;margin:14px 0;border-radius:12px;box-shadow:0 2px 12px #172d4810}.muted{color:#66758a}mark{background:#ffeb99}</style><div class="wrap"><h1>Hindi Wikipedia Search Engine</h1><p class="muted">{{ count }} indexed articles</p><form><input name="q" value="{{ q }}" placeholder='जैसे भारत AND इतिहास या "भारत की राजधानी"'><button>Search</button></form>{% if q %}<p class="muted">{{ elapsed }} seconds · {{ results|length }} results</p>{% endif %}{% for r in results %}<article class="card"><h2>{{ r.title }}</h2><div class="muted">ID {{ r.id }} · BM25 {{ '%.4f'|format(r.score) }}</div><p>{{ r.snippet|safe }}</p></article>{% endfor %}{% if error %}<p>{{ error }}</p>{% endif %}</div></html>'''

@app.route("/", methods=["GET"])
def home():
    q = request.args.get("q", "").strip()
    results, error, elapsed, count = [], "", 0.0, 0
    try:
        if METADATA_PATH.exists(): count = json.loads(METADATA_PATH.read_text(encoding="utf-8")).get("document_count", 0)
        if q:
            start = time.perf_counter()
            results = search(load_index(), q)
            for result in results:
                escaped = html.escape(result["snippet"])
                result["snippet"] = re.sub(r"\*\*(.*?)\*\*", r"<mark>\1</mark>", escaped)
            elapsed = time.perf_counter() - start
    except (FileNotFoundError, ValueError, OSError) as exc:
        error = str(exc)
    return render_template_string(HTML, q=q, results=results, error=error, elapsed=f"{elapsed:.4f}", count=count)

if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG)
