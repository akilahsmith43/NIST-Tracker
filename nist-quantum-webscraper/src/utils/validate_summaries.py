#!/usr/bin/env python3
"""
NIST Summary Validator
Audits existing summaries against the new quality standards
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path


class SummaryValidator:
    """Validates summaries against NIST quality standards."""
    
    # Quality rule violations
    TRUNCATION_PATTERN = r'\.\.\.|[a-z]\.$'  # Ellipsis or single letter + period
    URL_PATTERN = r'https?://|www\.'
    BOILERPLATE_PHRASES = [
        'applied cybersecurity division',
        'national cybersecurity center of excellence',
        'ncce and nice focus on cybersecurity',
        'this dual effort aims to enhance',
        'practical solutions and education',
        'conducted by researchers at the',
        'an official website of the united states government',
    ]
    GENERIC_AI_FILLER = [
        'has progressed significantly',
        'impacted various aspects',
        'increasingly integrated',
        'growing need to',
        'various aspects of their daily life',
    ]
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.results = []
    
    def validate(self, summary: str, title: str = '', publication_id: str = '') -> dict:
        """Run all validation checks on a single summary."""
        
        if not summary:
            return {
                'id': publication_id,
                'title': title,
                'summary': summary,
                'status': 'FAIL',
                'issues': ['Empty summary'],
                'score': 0.0
            }
        
        issues = []
        score = 1.0  # Start at 100%
        
        # Check 1: URL-only summary
        if self._is_url_only(summary):
            issues.append('❌ URL-ONLY: Summary is just a URL')
            score -= 1.0
        
        # Check 2: Contains URLs
        if self._has_urls(summary):
            issues.append('❌ URL CONTAMINATION: Summary contains URLs')
            score -= 0.15
        
        # Check 3: Truncation
        if self._has_truncation(summary):
            issues.append('❌ TRUNCATION: Summary ends mid-word or with ellipsis')
            score -= 0.20
        
        # Check 4: Gibberish (repeated tokens)
        if self._has_gibberish(summary):
            issues.append('❌ GIBBERISH: Excessive token repetition detected')
            score -= 0.20
        
        # Check 5: Complete sentences
        sentences = self._count_complete_sentences(summary)
        if sentences < 2:
            issues.append(f'❌ INCOMPLETE: Only {sentences} sentence(s) (need 2+)')
            score -= 0.25
        
        # Check 6: Boilerplate
        if self._has_boilerplate(summary):
            issues.append('⚠️  BOILERPLATE: Generic filler detected')
            score -= 0.15
        
        # Check 7: Generic AI filler
        if self._has_generic_ai_filler(summary):
            issues.append('⚠️  GENERIC AI: Irrelevant generic AI filler')
            score -= 0.15
        
        # Check 8: Grammatical errors (basic)
        if self._has_grammar_errors(summary):
            issues.append('⚠️  GRAMMAR: Grammar errors detected')
            score -= 0.10
        
        # Ensure score doesn't go below 0
        score = max(0.0, score)
        
        status = 'PASS' if score >= 0.70 else 'FAIL'
        
        result = {
            'id': publication_id,
            'title': title,
            'summary': summary[:100] + '...' if len(summary) > 100 else summary,
            'full_summary': summary,
            'status': status,
            'score': round(score, 2),
            'issues': issues,
            'sentence_count': sentences
        }
        
        self.results.append(result)
        return result
    
    def _is_url_only(self, text: str) -> bool:
        """Check if summary is just a URL."""
        clean = text.strip()
        return bool(re.match(r'^https?://\S+$|^www\.\S+$', clean))
    
    def _has_urls(self, text: str) -> bool:
        """Check if summary contains URLs."""
        return bool(re.search(self.URL_PATTERN, text))
    
    def _has_truncation(self, text: str) -> bool:
        """Check for truncation patterns."""
        if not text:
            return False
        
        # Check for ellipsis
        if '...' in text:
            return True
        
        # Check for incomplete sentences (ends without period/punctuation)
        text_stripped = text.strip()
        if text_stripped and text_stripped[-1] not in '.!?':
            return True
        
        # Check for abrupt endings (last word incomplete or single capital letter)
        words = text_stripped.split()
        if len(words) > 0:
            last_word = words[-1].rstrip('.,!?;:')
            # Single letters not at start = likely truncation
            if len(last_word) == 1 and last_word.isupper():
                return True
            # Word ending with period but only a few chars (like "lith.")
            if text_stripped[-1] == '.' and len(last_word) <= 3 and last_word.isalpha():
                return True
        
        return False
    
    def _has_gibberish(self, text: str) -> bool:
        """Check for token repetition (gibberish)."""
        tokens = text.lower().split()
        if len(tokens) < 5:
            return False
        
        counts = Counter(tokens)
        max_freq = max(counts.values())
        # If any token appears >30% of the time, likely gibberish
        return max_freq > len(tokens) * 0.3
    
    def _count_complete_sentences(self, text: str) -> int:
        """Count complete sentences."""
        sentences = re.findall(r'[^.!?]*[.!?]', text)
        return len(sentences)
    
    def _has_boilerplate(self, text: str) -> bool:
        """Check for known boilerplate phrases."""
        text_lower = text.lower()
        for phrase in self.BOILERPLATE_PHRASES:
            if phrase in text_lower:
                return True
        return False
    
    def _has_generic_ai_filler(self, text: str) -> bool:
        """Check for generic AI filler."""
        text_lower = text.lower()
        for phrase in self.GENERIC_AI_FILLER:
            if phrase in text_lower:
                return True
        return False
    
    def _has_grammar_errors(self, text: str) -> bool:
        """Check for obvious grammar errors."""
        # Common grammar issues
        grammar_patterns = [
            r'\bthese\s+system\b',  # should be "systems"
            r'\bthee\b',            # typo
            r'\bth\s+e\b',          # spacing issue
        ]
        for pattern in grammar_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        return False
    
    def generate_report(self) -> str:
        """Generate a summary report."""
        if not self.results:
            return "No summaries validated yet."
        
        passed = sum(1 for r in self.results if r['status'] == 'PASS')
        failed = sum(1 for r in self.results if r['status'] == 'FAIL')
        total = len(self.results)
        avg_score = sum(r['score'] for r in self.results) / total if total > 0 else 0
        
        report = f"""
╔════════════════════════════════════════════════════════════════╗
║           NIST SUMMARY VALIDATION REPORT                       ║
╚════════════════════════════════════════════════════════════════╝

OVERALL RESULTS:
  Total Summaries Audited: {total}
  ✅ Passing (score ≥ 0.70): {passed} ({100*passed//total if total else 0}%)
  ❌ Failing (score < 0.70): {failed} ({100*failed//total if total else 0}%)
  Average Score: {avg_score:.2f} / 1.00

FAILURE BREAKDOWN:
"""
        
        # Count issue types
        issue_counts = {}
        for result in self.results:
            for issue in result['issues']:
                key = issue.split(':')[0]  # Get the check type
                issue_counts[key] = issue_counts.get(key, 0) + 1
        
        for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = 100 * count // total if total else 0
            report += f"  {issue_type}: {count} ({percentage}%)\n"
        
        report += "\n" + "="*65 + "\n"
        return report
    
    def print_results(self, failures_only=False):
        """Print validation results."""
        print(self.generate_report())
        
        print("\nDETAILED RESULTS:\n")
        for result in self.results:
            if failures_only and result['status'] == 'PASS':
                continue
            
            status_icon = '❌' if result['status'] == 'FAIL' else '✅'
            print(f"{status_icon} [{result['score']}] {result['title'][:60]}")
            
            if result['issues']:
                for issue in result['issues']:
                    print(f"     {issue}")
            
            if self.verbose:
                print(f"     Summary: {result['summary']}")
            print()


def main():
    """Main entry point for validation."""
    
    # Check if cache files exist
    cache_base = Path(__file__).parent.parent / 'data_storage' / 'summaries'
    topics = ['ai_publications', 'qis', 'pqc']
    
    validator = SummaryValidator(verbose='--verbose' in sys.argv)
    
    total_audited = 0
    for topic in topics:
        cache_file = cache_base / f"{topic}.json"
        
        if not cache_file.exists():
            print(f"⚠️  Cache not found: {cache_file}")
            continue
        
        print(f"\n📄 Validating {topic}...")
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            
            for cache_key, entry in cache.items():
                summary = entry.get('summary', '')
                # Try to extract title from context (usually not available in cache)
                # Use cache_key as placeholder
                title = f"{topic}#{cache_key[:8]}"
                
                validator.validate(summary, title, cache_key)
                total_audited += 1
        
        except Exception as e:
            print(f"❌ Error reading {cache_file}: {e}")
    
    print(f"\n{'='*65}")
    print(f"Total summaries audited: {total_audited}")
    validator.print_results(failures_only='--failures' in sys.argv)
    
    # Exit with code 1 if any failures
    failed_count = sum(1 for r in validator.results if r['status'] == 'FAIL')
    sys.exit(1 if failed_count > 0 else 0)


if __name__ == '__main__':
    main()
