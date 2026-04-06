#!/usr/bin/env python3
"""
clear_bad_cache.py
------------------
Scans all 3 topic summary cache files and removes entries that are:
- Boilerplate (.gov / HTTPS / lock icon text)
- Cut off mid-thought (no ending punctuation)
- Too short to be a real summary
- Contain known bad phrases

Run this ONCE after updating ai_summarizer.py, then restart your app.
The next time the dashboard loads, missing summaries will be regenerated.

Usage:
    /opt/homebrew/bin/python3 clear_bad_cache.py
    /opt/homebrew/bin/python3 clear_bad_cache.py --dry-run   # preview only
"""

import os
import json
import re
import argparse
from datetime import datetime

TOPICS = ["ai_publications", "qis", "pqc"]

# ---------------------------------------------------------------------------
# Find cache directory
# ---------------------------------------------------------------------------

def find_cache_dir() -> str:
    candidate = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        path = os.path.join(candidate, 'data_storage', 'summaries')
        if os.path.isdir(path):
            return path
        candidate = os.path.dirname(candidate)
    # fallback — same directory as this script
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_storage', 'summaries')


# ---------------------------------------------------------------------------
# Bad summary detection — catches everything seen in the dashboard
# ---------------------------------------------------------------------------

BAD_SUBSTRINGS = [
    # .gov page chrome
    'secure .gov',
    '.gov websites use https',
    'a lock (',
    'lock a locked padlock',
    'locked padlock',
    'means you\'ve safely connected',
    "means you've safely connected",
    'safely connected to the .',
    'official website of the united states',
    'you are being redirected',
    'redirecting to',
    'please enable javascript',
    'javascript disabled',
    'this site is not secure',
    'potential security issue',
    # errors
    'access denied',
    '403 forbidden',
    '404 not found',
    '500 internal server',
    'error occurred',
    'not found',
    # generic failures
    'no meaningful content available',
    'summary generation failed',
    'no content available',
]

BAD_PATTERNS = [
    r'https?://\s+means\s+you',
    r'a\s+lock\s*\(',
    r'locked\s+padlock',
    r'secure\s*\.?\s*gov\s+websites',
    r'safely\s+connected\s+to\s+the\s+\.',
]


def is_bad_summary(summary: str) -> tuple:
    """
    Returns (is_bad: bool, reason: str).
    """
    if not summary or not summary.strip():
        return True, "empty"

    s = summary.strip()
    low = s.lower()

    # Too short
    if len(s) < 25:
        return True, f"too short ({len(s)} chars)"

    # Boilerplate substrings
    for sub in BAD_SUBSTRINGS:
        if sub in low:
            return True, f"boilerplate: '{sub}'"

    # Boilerplate regex patterns
    for pat in BAD_PATTERNS:
        if re.search(pat, low):
            return True, f"boilerplate pattern: {pat}"

    # Incomplete thought — doesn't end with sentence-ending punctuation
    if s[-1] not in '.!?':
        return True, f"incomplete — ends with '{s[-1]}'"

    # Ends with an abbreviation period that's actually a cut-off
    # e.g. "...single-cell lith." or "...battery tech."
    cut_off_pattern = r'\b[a-z]{2,6}\.\s*$'
    if re.search(cut_off_pattern, s, re.IGNORECASE):
        # Make sure it's not a real sentence ending like "...algorithm."
        # A real ending usually has more than 6 chars before the final word
        last_word = re.search(r'\b(\w+)\.\s*$', s)
        if last_word:
            word = last_word.group(1).lower()
            # Known abbreviations that signal a cut-off
            abbrevs = {
                'lith', 'alum', 'approx', 'temp', 'freq', 'max', 'min',
                'avg', 'std', 'dept', 'univ', 'inst', 'corp', 'fig',
                'vol', 'eq', 'ref', 'sec', 'tech', 'mech', 'chem',
            }
            if word in abbrevs:
                return True, f"cut off at abbreviation '{word}.'"

    return False, ""


# ---------------------------------------------------------------------------
# Main cleaner
# ---------------------------------------------------------------------------

def clean_cache(cache_dir: str, dry_run: bool = False):
    total_removed = 0
    total_kept = 0

    for topic in TOPICS:
        path = os.path.join(cache_dir, f"{topic}.json")

        if not os.path.exists(path):
            print(f"\n[{topic}] No cache file found at {path} — skipping.")
            continue

        with open(path, 'r') as f:
            cache = json.load(f)

        original_count = len(cache)
        to_remove = []

        print(f"\n[{topic}] Scanning {original_count} entries...")

        for key, entry in cache.items():
            summary = entry.get('summary', '')
            bad, reason = is_bad_summary(summary)
            if bad:
                preview = summary[:80].replace('\n', ' ') if summary else '(empty)'
                print(f"  REMOVE ({reason}): {preview}")
                to_remove.append(key)
            else:
                total_kept += 1

        if to_remove:
            if not dry_run:
                for key in to_remove:
                    del cache[key]
                with open(path, 'w') as f:
                    json.dump(cache, f, indent=2)
                print(f"  Removed {len(to_remove)} bad entries. {len(cache)} remain.")
            else:
                print(f"  [DRY RUN] Would remove {len(to_remove)} entries. {original_count - len(to_remove)} would remain.")
            total_removed += len(to_remove)
        else:
            print(f"  All {original_count} entries look good.")

    print(f"\n{'='*50}")
    if dry_run:
        print(f"DRY RUN complete. Would remove {total_removed} bad entries, keep {total_kept}.")
        print("Run without --dry-run to apply changes.")
    else:
        print(f"Done. Removed {total_removed} bad entries across all topics.")
        print("Restart your Streamlit app — summaries will regenerate on next load.")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove bad/boilerplate summaries from cache.")
    parser.add_argument('--dry-run', action='store_true', help="Preview without making changes")
    args = parser.parse_args()

    cache_dir = find_cache_dir()
    print(f"Cache directory: {cache_dir}")

    clean_cache(cache_dir, dry_run=args.dry_run)