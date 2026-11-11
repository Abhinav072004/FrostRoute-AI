"""Local BM25 retrieval: no embedding model, vector database or hosted service."""
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP = set('a an the is are of to for and in on what how must be with'.split())


def tokens(text):
    words = re.findall(r'[a-z0-9]+', text.lower())
    aliases = {'temperatures': 'temperature', 'rules': 'rule', 'perishables': 'perishable',
               'escalation': 'escalate', 'escalated': 'escalate', 'delays': 'delay'}
    return [aliases.get(w, w) for w in words if w not in STOP]


@lru_cache(maxsize=8)
def load_chunks(directory):
    chunks = []
    for path in sorted(Path(directory).iterdir()):
        if path.suffix.lower() in {'.md', '.txt'}:
            text = path.read_text(encoding='utf-8')
        elif path.suffix.lower() == '.pdf':
            from pypdf import PdfReader
            text = '\n'.join(f'Page {n + 1}\n{p.extract_text() or ""}'
                             for n, p in enumerate(PdfReader(path).pages))
        else:
            continue
        # Heading-aware blocks, then bounded windows for unstructured documents.
        for block in re.split(r'(?m)(?=^#{1,6} )', text):
            lines = block.strip().splitlines()
            if not lines:
                continue
            for start in range(0, len(block), 2400):
                body = block[start:start + 2600].strip()
                if body:
                    chunks.append({'source': path.name, 'section': lines[0].lstrip('# '),
                                   'text': body, 'id': f'{path.name}#{len(chunks)+1}'})
    return chunks


def search(query, directory=None, k=3):
    chunks = load_chunks(str(directory or ROOT / 'data/policy'))
    q = set(tokens(query))
    if not q or not chunks:
        return []
    counts = [Counter(tokens(c['text'])) for c in chunks]
    lengths = [sum(c.values()) for c in counts]
    average = sum(lengths) / len(lengths) or 1
    scored = []
    for chunk, count, length in zip(chunks, counts, lengths):
        score = 0.0
        for term in q:
            frequency = count[term]
            document_frequency = sum(term in c for c in counts)
            idf = math.log(1 + (len(chunks) - document_frequency + .5) / (document_frequency + .5))
            score += idf * frequency * 2.5 / (frequency + 1.5 * (.25 + .75 * length / average))
        if score > 0:
            scored.append(dict(chunk, score=round(score, 4)))
    return sorted(scored, key=lambda c: (-c['score'], c['id']))[:k]


def policy_namespace():
    import hashlib
    digest = hashlib.sha256()
    for path in sorted((ROOT / 'data/policy').iterdir()):
        if path.suffix.lower() in {'.md', '.txt', '.pdf'}:
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return 'sop-' + digest.hexdigest()[:24]
