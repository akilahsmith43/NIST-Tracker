#!/usr/bin/env python3
"""Backfill missing publication summaries in dashboard JSON files.

Usage:
  python src/utils/backfill_publication_summaries.py
"""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.summary_manager import SummaryManager

DATA_TARGETS = [
    {
        "topic": "qis",
        "path": ROOT / "src" / "dashboard" / "data_storage" / "qis_data.json",
    },
    {
        "topic": "pqc",
        "path": ROOT / "src" / "dashboard" / "data_storage" / "pqc_data.json",
    },
    {
        "topic": "ai_publications",
        "path": ROOT / "src" / "dashboard" / "data_storage" / "ai_data.json",
    },
    {
        "topic": "qis",
        "path": ROOT / "data_storage" / "dashboard" / "data_storage" / "qis_data.json",
    },
    {
        "topic": "pqc",
        "path": ROOT / "data_storage" / "dashboard" / "data_storage" / "pqc_data.json",
    },
    {
        "topic": "ai_publications",
        "path": ROOT / "data_storage" / "dashboard" / "data_storage" / "ai_data.json",
    },
]

BAD_START_PATTERN = (
    r'^(is|are|was|were|be|being|been|has|have|had|can|could|should|would|may|might|must|will|'
    r'do|does|did|using|based|focused|designed|aimed|intended|developed|built|created)\b'
)


def _to_max_two_full_sentences(text: str) -> str:
    cleaned = ' '.join((text or '').strip().split())
    if not cleaned:
        return ""

    import re
    sentences = [s.strip() for s in re.findall(r'[^.!?]*[.!?]', cleaned, flags=re.DOTALL) if s.strip()]
    if not sentences:
        return ""

    return ' '.join(sentences[:2]).strip()


def _looks_mid_phrase(summary_text: str) -> bool:
    cleaned = ' '.join((summary_text or '').strip().split())
    if not cleaned:
        return False

    import re
    first_sentence = re.split(r'(?<=[.!?])\s+', cleaned, maxsplit=1)[0].strip().lstrip('"\'([{').strip()
    if not first_sentence:
        return False

    return bool(re.match(BAD_START_PATTERN, first_sentence.lower()))


def _best_summary(item: dict, manager: SummaryManager) -> str:
    generated = _to_max_two_full_sentences((manager.generate_summary(item) or "").strip())
    if generated and not _looks_mid_phrase(generated):
        return generated

    existing = _to_max_two_full_sentences((item.get("summary") or "").strip())
    title = (item.get("document_name") or item.get("title") or "").strip()
    if existing and existing.lower() != title.lower() and not _looks_mid_phrase(existing):
        return existing

    return ""


def backfill_file(topic: str, path: Path) -> tuple[int, int]:
    if not path.exists():
        return (0, 0)

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    publications = payload.get("data", {}).get("publications", [])
    if not isinstance(publications, list) or not publications:
        return (0, 0)

    manager = SummaryManager(topic=topic)
    total_candidates = 0
    updated = 0

    updated_publications = []
    for publication in publications:
        if not isinstance(publication, dict):
            continue

        item = dict(publication)
        current_summary = (item.get("summary") or "").strip()
        normalized_current = _to_max_two_full_sentences(current_summary)
        needs_repair = (not current_summary) or _looks_mid_phrase(current_summary) or (normalized_current != current_summary)
        if needs_repair:
            total_candidates += 1
            summary_text = _best_summary(item, manager)
            if summary_text:
                item["summary"] = summary_text
                updated += 1
            elif normalized_current and not _looks_mid_phrase(normalized_current):
                item["summary"] = normalized_current
                updated += 1

        updated_publications.append(item)

    if updated:
        payload["data"]["publications"] = updated_publications
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    return (total_candidates, updated)


def main() -> None:
    print("Backfilling publication summaries...")
    for target in DATA_TARGETS:
        topic = target["topic"]
        path = target["path"]
        candidates, updated = backfill_file(topic, path)
        if candidates == 0 and updated == 0:
            print(f"- {path}: skipped (missing file or no publications)")
            continue
        print(f"- {path}: updated {updated}/{candidates} publication summaries (missing or repaired)")


if __name__ == "__main__":
    main()
