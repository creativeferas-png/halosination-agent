"""
Build a policy index for any HALO agent.

Reads a markdown policy file, splits it into rule chunks at the "## Rule N — Title"
markers, calls text-embedding-3-large via Compass for each chunk, and writes a
JSON index file with {rule_id, title, text, embedding} per rule.

Each HALO agent has its own policy file:
  - Agent 01 (Brand & Brief)   -> data/brand_guidelines.md
  - Agent 02 (Productivity)    -> data/meeting_policy.md
  - Agent 03 (Task & KPI)      -> data/task_policy.md       (planned)
  - Agent 04 (Social)          -> data/social_policy.md     (planned)
  - Agent 05 (Wellness)        -> data/wellness_policy.md   (planned)

Usage:
    python scripts/build_policy_index.py <input_md> <output_json>
"""
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

EMBED_MODEL = "text-embedding-3-large"


def split_rules(markdown_text):
    """Split a policy doc into rule chunks at '## Rule N — Title' headers."""
    pattern = re.compile(r"^##\s+Rule\s+(\d+)\s+[\u2014-]\s+(.+?)$", re.MULTILINE)
    matches = list(pattern.finditer(markdown_text))
    rules = []
    for i, m in enumerate(matches):
        rule_id = int(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)
        body = markdown_text[start:end].strip()
        rules.append({"rule_id": rule_id, "title": title, "text": body})
    return rules


def embed_text(text):
    """Single embedding call via Compass."""
    response = client.embeddings.create(model=EMBED_MODEL, input=text)
    return response.data[0].embedding


def build_index(input_path, output_path):
    if not input_path.exists():
        print(f"ERROR: {input_path} not found.", file=sys.stderr)
        sys.exit(1)

    markdown = input_path.read_text(encoding="utf-8")
    rules = split_rules(markdown)
    print(f"Parsed {len(rules)} rules from {input_path.name}")

    indexed = []
    for rule in rules:
        embed_input = rule["title"] + "\n\n" + rule["text"]
        embedding = embed_text(embed_input)
        indexed.append({
            "rule_id": rule["rule_id"],
            "title": rule["title"],
            "text": rule["text"],
            "embedding": embedding,
            "embedding_model": EMBED_MODEL,
            "embedding_dim": len(embedding),
        })
        print(f"  Rule {rule['rule_id']:2d} — {rule['title']!r} ({len(embedding)}-dim)")

    output_path.write_text(json.dumps(indexed, indent=2), encoding="utf-8")
    print(f"\nWrote {len(indexed)} indexed rules to {output_path}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/build_policy_index.py <input_md> <output_json>", file=sys.stderr)
        sys.exit(1)
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    build_index(input_path, output_path)


if __name__ == "__main__":
    main()
