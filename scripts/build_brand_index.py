"""
One-time script: build the brand index used by the Search agent.

Reads data/brand_guidelines.md, splits it into rule chunks at the "## Rule"
markers, calls text-embedding-3-large via Compass for each chunk, and writes
data/brand_index.json with {rule_id, title, text, embedding}.

Run once after editing brand_guidelines.md:
    python scripts/build_brand_index.py
"""
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Repo-root .env (script lives in scripts/, .env lives in repo root)
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

GUIDELINES_PATH = ROOT / "data" / "brand_guidelines.md"
INDEX_PATH = ROOT / "data" / "brand_index.json"
EMBED_MODEL = "text-embedding-3-large"


def split_rules(markdown_text: str) -> list[dict]:
    """Split the guidelines doc into rule chunks at '## Rule N — Title' headers."""
    # Match "## Rule 1 — Title" through the next "## Rule" or end-of-file
    pattern = re.compile(
        r"^##\s+Rule\s+(\d+)\s+[—-]\s+(.+?)$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(markdown_text))
    rules = []
    for i, m in enumerate(matches):
        rule_id = int(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)
        body = markdown_text[start:end].strip()
        rules.append({
            "rule_id": rule_id,
            "title": title,
            "text": body,
        })
    return rules


def embed_text(text: str) -> list[float]:
    """Single text-embedding-3-large call via Compass."""
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=text,
    )
    return response.data[0].embedding


def main():
    if not GUIDELINES_PATH.exists():
        print(f"ERROR: {GUIDELINES_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    markdown = GUIDELINES_PATH.read_text(encoding="utf-8")
    rules = split_rules(markdown)
    print(f"Parsed {len(rules)} rules from {GUIDELINES_PATH.name}")

    indexed = []
    for rule in rules:
        # Embed "title + body" together so retrieval matches both topic and content
        embed_input = f"{rule['title']}\n\n{rule['text']}"
        embedding = embed_text(embed_input)
        indexed.append({
            "rule_id": rule["rule_id"],
            "title": rule["title"],
            "text": rule["text"],
            "embedding": embedding,
            "embedding_model": EMBED_MODEL,
            "embedding_dim": len(embedding),
        })
        print(f"  ✓ Rule {rule['rule_id']:2d} — {rule['title']!r} ({len(embedding)}-dim)")

    INDEX_PATH.write_text(json.dumps(indexed, indent=2), encoding="utf-8")
    print(f"\nWrote {len(indexed)} indexed rules to {INDEX_PATH}")
    print(f"Total tokens used: see Compass dashboard.")


if __name__ == "__main__":
    main()
