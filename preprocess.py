"""Small Hindi tokenizer and stop-word list; positions are 1-based original token offsets."""
import re
import unicodedata

STOP_WORDS = set("और या का की के को में से पर है हैं था थी थे यह वह एक इस उस इन उन भी ही तो तक लिए लिए द्वारा तथा लेकिन नहीं अपना अपनी अपने जो कि जैसा जैसी जैसे बहुत सभी कुछ कोई क्या कैसे कब कहाँ क्यों जब तब".split())
TOKEN_RE = re.compile(r"[\u0900-\u097F]+|[a-zA-Z0-9]+")


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text or "").split())


def tokenize(text):
    return [token for token in TOKEN_RE.findall(normalize(text).lower())
            if any(unicodedata.category(char).startswith("L") for char in token)]


def positioned_tokens(text, include_stop_words=False):
    return [(token, pos) for pos, token in enumerate(tokenize(text), 1)
            if include_stop_words or token not in STOP_WORDS]


def preprocess(text):
    """Return searchable (term, original_position) pairs."""
    return positioned_tokens(text)
