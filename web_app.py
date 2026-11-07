"""Small responsive Flask interface for Hindi Wikipedia search."""
import html
import json
import re
import time

from flask import Flask, render_template_string, request

from ir_search import load_index, search
from settings import FLASK_DEBUG, METADATA_PATH

app = Flask(__name__)

PAGE = """<!doctype html>
<html lang="hi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hindi Wikipedia Search</title>
  <style>
    :root { color-scheme: light; font: 16px/1.55 system-ui, sans-serif; color: #17243a; background: #f3f6fb; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    main { width: min(900px, calc(100% - 32px)); margin: 7vh auto; }
    header, .result { background: white; border: 1px solid #e3e9f1; border-radius: 16px; padding: 22px; }
    header { box-shadow: 0 8px 28px #1933540d; }
    h1 { margin: 0; color: #173b70; font-size: clamp(1.5rem, 4vw, 2rem); }
    .muted { color: #66758a; }
    form { display: flex; gap: 10px; margin-top: 20px; }
    input { min-width: 0; flex: 1; padding: 13px 15px; border: 1px solid #cad4e2; border-radius: 10px; font: inherit; }
    button { padding: 0 22px; border: 0; border-radius: 10px; background: #2056a1; color: white; font: inherit; cursor: pointer; }
    .result { margin-top: 14px; }
    .result h2 { margin: 0 0 4px; font-size: 1.2rem; }
    mark { background: #ffeb99; border-radius: 3px; }
    @media (max-width: 520px) { form { flex-direction: column; } button { min-height: 46px; } }
  </style>
</head>
<body><main>
  <header>
    <h1>Hindi Wikipedia Search</h1>
    <div class="muted">{{ count }} indexed articles</div>
    <form method="get">
      <input name="q" value="{{ query }}" placeholder='Try भारत AND इतिहास or "भारत की राजधानी"' aria-label="Search query">
      <button type="submit">Search</button>
    </form>
  </header>
  {% if query %}<p class="muted">{{ elapsed }} seconds · {{ results|length }} results</p>{% endif %}
  {% if error %}<p class="result">{{ error }}</p>{% endif %}
  {% for result in results %}
    <article class="result">
      <h2>{{ result.title }}</h2>
      <div class="muted">ID {{ result.id }} · BM25 {{ '%.4f'|format(result.score) }}</div>
      <p>{{ result.snippet|safe }}</p>
    </article>
  {% endfor %}
</main></body></html>"""


@app.get("/")
def home():
    query = request.args.get("q", "").strip()
    results, error, elapsed, count = [], "", 0.0, 0
    try:
        if METADATA_PATH.is_file():
            count = json.loads(METADATA_PATH.read_text(encoding="utf-8")).get("document_count", 0)
        if query:
            started = time.perf_counter()
            results = search(load_index(), query)
            elapsed = time.perf_counter() - started
            for result in results:
                escaped = html.escape(result["snippet"])
                result["snippet"] = re.sub(r"\*\*(.*?)\*\*", r"<mark>\1</mark>", escaped)
    except (FileNotFoundError, ValueError, OSError) as exc:
        error = str(exc)
    return render_template_string(PAGE, query=query, results=results, error=error,
                                  elapsed=f"{elapsed:.4f}", count=count)


if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG)
