"""Summary manager for NIST Quantum Tracker.

This module implements a robust summarization pipeline with DSL + Ollama.

Requirements addressed:
- A: always summarize when abstract exists
- B: fallback to cleaned abstract when LLM fails
- C: no summary when no abstract and no useful page scrape
- D: no mid-word/sentence truncation
- E: 3-topic consolidated JSON cache (ai_publications, qis, pqc)
- F: strict third-person conversion without deleting valid phrases
- G: default Ollama model qwen2.5:7b, api_base localhost
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BASE_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data_storage', 'summaries')
TOPICS = {'ai_publications', 'qis', 'pqc'}
CACHE_TTL_HOURS = 48


def _ensure_cache_dir():
    os.makedirs(BASE_CACHE_DIR, exist_ok=True)


def _topic_cache_path(topic: str) -> str:
    _ensure_cache_dir()
    if topic not in TOPICS:
        raise ValueError(f"Unknown topic '{topic}'. Allowed: {sorted(TOPICS)}")
    return os.path.join(BASE_CACHE_DIR, f"{topic}.json")


def _load_topic_cache(topic: str) -> Dict[str, dict]:
    path = _topic_cache_path(topic)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load cache for topic {topic}: {e}")
        return {}


def _save_topic_cache(topic: str, cache_obj: Dict[str, dict]):
    path = _topic_cache_path(topic)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cache_obj, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save cache for topic {topic}: {e}")


def _cache_key(text: str) -> str:
    return hashlib.md5(text.strip().encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# URL and Gibberish Detection
# ---------------------------------------------------------------------------

def _extract_urls(text: str) -> list:
    """Extract all URLs from text."""
    if not text:
        return []
    url_pattern = r'https?://[^\s]+|www\.[^\s]+'
    return re.findall(url_pattern, text, flags=re.IGNORECASE)


def _strip_urls(text: str) -> str:
    """Remove all URLs from text."""
    if not text:
        return ''
    text = re.sub(r'https?://[^\s]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'www\.[^\s]+', '', text, flags=re.IGNORECASE)
    return ' '.join(text.split()).strip()


def _has_gibberish(text: str) -> bool:
    """Detect common gibberish patterns, but allow technical terminology."""
    if not text:
        return False
    low = text.lower().strip()
    
    # Check for truncation mid-word (ellipsis patterns)
    if re.search(r'\.\.\.|\.+$', low):
        return True
    
    # Check for repeated tokens, but allow technical terms that might repeat
    tokens = low.split()
    if len(tokens) > 0:
        from collections import Counter
        counts = Counter(tokens)
        if counts and max(counts.values()) > len(tokens) * 0.4:  # Increased threshold
            # Allow if it's technical content with repeated terms
            if any(term in low for term in ['quantum', 'algorithm', 'system', 'model', 'data', 'analysis', 'research', 'study', 'method', 'technique', 'performance', 'results', 'evaluation', 'implementation']):
                return False
            return True
    
    return False


def _is_search_index_url(url: str) -> bool:
    if not url:
        return False
    return bool(re.search(r'(/publications/search|/search\b)', url, flags=re.IGNORECASE))


_FORBIDDEN_SUMMARY_PREFIXES = [
    'this abstract outlines',
    'this paper presents',
    'the paper presents',
    'this article presents',
    'the abstract is about',
]

def _has_forbidden_prefix(text: str) -> bool:
    if not text:
        return False
    normalized = _clean_text(text.lower())
    for prefix in _FORBIDDEN_SUMMARY_PREFIXES:
        if normalized.startswith(prefix):
            # Only reject if the prefix is followed by uninformative content
            # Allow if the text contains technical terms after the prefix
            if len(normalized) > len(prefix) + 10:  # At least 10 more characters
                remaining = normalized[len(prefix):].strip()
                # Check if remaining content contains technical terms
                technical_terms = ['evaluation', 'analysis', 'study', 'research', 'method', 'algorithm', 'system', 'model', 'framework', 'approach', 'technique', 'benchmark', 'performance', 'results', 'data', 'experiment', 'implementation']
                if any(term in remaining for term in technical_terms):
                    return False  # Allow it - contains technical content
            return True
    return False


def _has_researcher_placeholder(text: str) -> bool:
    if not text:
        return False
    normalized = _clean_text(text.lower())
    return 'conducted by researchers at the' in normalized


def _has_junk_security_keyword_block(text: str) -> bool:
    if not text:
        return False
    normalized = _clean_text(text.lower())
    junk_phrases = [
        'computer security division',
        'cryptographic technology',
        'secure systems and applications',
        'security components and mechanisms',
        'security engineering and risk management',
        'security testing'  # catch generic header-like lists
    ]
    return all(phrase in normalized for phrase in junk_phrases)


def _has_researcher_conduct_mention(text: str) -> bool:
    if not text:
        return False
    normalized = _clean_text(text.lower())
    bad_phrases = [
        'conducted by researchers',
        'researchers at the',
        'study conducted by',
        'research conducted by',
        'authors of the study',
        'the researchers',
        'conducted by',
    ]
    return any(phrase in normalized for phrase in bad_phrases)


def _is_uninformative_summary(text: str) -> bool:
    if not text:
        return True

    normalized = _clean_text(text.lower())
    normalized_no_space = re.sub(r'\s+', ' ', normalized)

    # Only reject summaries with clear security warnings or error messages
    bad_indicators = [
        'potential security issue',
        'you are being redirected',
        'redirecting to',
        'this site is not secure',
        'javascript disabled',
        '404',
        '500',
        'not found',
        'access denied',
        'forbidden',
        'error occurred',
        'no meaningful content available',
        'contact us',
        'contact the',
        'for questions',
        'if you have questions',
        'if you have any questions',
        'encounter issues',
        'issues accessing',
        'email address',
        'serves as the point of contact',
        'point of contact',
    ]

    for indicator in bad_indicators:
        if indicator in normalized_no_space:
            logger.debug(f"Rejected due to bad indicator: {indicator}")
            return True

    # Reject summaries that are just URLs
    url_pattern = r'^https?://[^\s]*$'
    if re.search(url_pattern, normalized.strip()):
        logger.debug("Rejected due to URL-only summary")
        return True

    # Reject summaries containing email addresses
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
        logger.debug("Rejected due to email address")
        return True

    # Only reject URLs that are not NIST-related
    urls = _extract_urls(text)
    if urls:
        # Allow NIST URLs but reject others
        for url in urls:
            if not url.lower().startswith('https://www.nist.gov') and not url.lower().startswith('http://www.nist.gov'):
                logger.debug(f"Rejected due to non-NIST URL: {url}")
                return True

    # Allow technical content even if it contains some patterns that might look like gibberish
    # Technical terms often get flagged incorrectly
    if _has_gibberish(text):
        # Only reject if it's clearly gibberish and not technical content
        if len(text.split()) < 10 or not any(term in text.lower() for term in ['quantum', 'algorithm', 'system', 'model', 'data', 'analysis', 'research', 'study', 'method', 'technique']):
            logger.debug("Rejected due to gibberish")
            return True

    logger.debug("Summary passed all checks")
    return False


def _clean_text(text: str) -> str:
    if not text:
        return ''
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
    text = ' '.join(text.split())
    return text.strip()


def _strip_summary_prefix(text: str) -> str:
    if not text:
        return ''
    text = re.sub(r'^\s*summary\s*[:\-]?\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def _split_into_full_sentences(text: str) -> list:
    text = _clean_text(text)
    if not text:
        return []
    # Include punctuation as sentence terminator
    sentences = re.findall(r'[^.!?]*[.!?]', text, flags=re.DOTALL)
    if not sentences:
        return [text.strip() + ('.' if not text.strip().endswith(('.', '!', '?')) else '')]
    return [s.strip() for s in sentences if s.strip()]


def _format_two_sentences(text: str) -> str:
    sentences = _split_into_full_sentences(text)
    if not sentences:
        return text.strip() + ('.' if not text.strip().endswith(('.', '!', '?')) else '')  # Return single sentence if only one exists
    
    selected = sentences[:2]
    result = ' '.join(selected)
    if result and result[-1] not in '.!?':
        result += '.'
    return result.strip()


def _clean_summary_output(text: str) -> str:
    if not text:
        return ''
    if _is_uninformative_summary(text):
        return ''
    clean = _ensure_third_person(text)
    formatted = _format_two_sentences(clean)
    if _is_uninformative_summary(formatted):
        return ''
    return formatted


def _is_padding_verbose(summary: str, abstract: str) -> bool:
    """Check if summary is padded/verbose compared to abstract (Rule 5: summary should be shorter)."""
    if not summary or not abstract:
        return False
    
    # Summary should be significantly shorter than abstract
    # If summary is more than 50% the length of abstract, it's likely padded
    summary_len = len(summary.split())
    abstract_len = len(abstract.split())
    
    if abstract_len > 30:  # For longer abstracts
        if summary_len > abstract_len * 0.5:
            return True
    
    return False


def _strip_contact_info(text: str) -> str:
    """Remove contact information, emails, and related phrases from text."""
    if not text:
        return ''
    
    # Remove email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    
    # Split into sentences, but handle text without proper endings
    sentences = re.findall(r'[^.!?]*[.!?]', text, flags=re.DOTALL)
    if not sentences:
        # If no complete sentences, treat the whole text as one sentence
        sentences = [text]
    
    cleaned_sentences = []
    
    contact_phrases = [
        'contact us', 'contact the', 'for questions', 'if you have questions',
        'if you have any questions', 'encounter issues', 'issues accessing',
        'email address', 'serves as the point of contact', 'point of contact',
        'please contact', 'reach out', 'get in touch', 'contact support'
    ]
    
    for sentence in sentences:
        sentence_lower = sentence.lower().strip()
        has_contact = any(phrase in sentence_lower for phrase in contact_phrases)
        if not has_contact:
            cleaned_sentences.append(sentence.strip())
    
    result = ' '.join(cleaned_sentences).strip()
    
    # If we removed too much and result is too short, try a more surgical approach
    if len(result.split()) < 10 and len(sentences) > 1:
        # Keep sentences but remove contact phrases surgically
        surgical_sentences = []
        for sentence in sentences:
            for phrase in contact_phrases:
                sentence = re.sub(re.escape(phrase), '', sentence, flags=re.IGNORECASE)
            # Clean up the sentence
            sentence = re.sub(r'\s+', ' ', sentence)
            sentence = re.sub(r'\.\s*\.', '.', sentence)
            sentence = sentence.strip()
            if sentence and len(sentence.split()) > 3:  # Keep if meaningful
                surgical_sentences.append(sentence)
        result = ' '.join(surgical_sentences).strip()
    
    return result


def _strip_prefatory_phrases(text: str) -> str:
    if not text:
        return ''

    text = text.strip()
    # Remove wordy lead-ins that do not add value to summary content
    text = re.sub(r'^(this\s+abstract\s+outlines(\s+key\s+areas(\s+of)?)?)\s*[:,]?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(the|this)\s+(paper|article)\s+presents\s*[:,]?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(the|this)\s+study\s+presents\s*[:,]?\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def _ensure_third_person(summary: str) -> str:
    if not summary:
        return ''

    s = _strip_summary_prefix(summary)
    s = _strip_prefatory_phrases(s)

    # Exact phrase rewrites for academic style
    phrase_rewrites = {
        r'\bwe present\b': 'The study presents',
        r'\bwe propose\b': 'The study proposes',
        r'\bwe show\b': 'The study shows',
        r'\bwe develop\b': 'The study develops',
        r'\bwe introduce\b': 'The study introduces',
    }
    for pat, repl in phrase_rewrites.items():
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)

    # Pronoun replacement
    s = re.sub(r"\bour\b", 'their', s, flags=re.IGNORECASE)
    s = re.sub(r"\bours\b", 'theirs', s, flags=re.IGNORECASE)
    s = re.sub(r"\bus\b", 'them', s, flags=re.IGNORECASE)
    s = re.sub(r"\bI\b", 'The researcher', s, flags=re.IGNORECASE)
    s = re.sub(r"\bwe\b", 'the researchers', s, flags=re.IGNORECASE)

    # Remove explicit NIST branding in sentence to keep summaries neutral
    s = re.sub(r'\bNIST\b', '', s, flags=re.IGNORECASE)
    s = re.sub(r'National Institute of Standards and Technology', '', s, flags=re.IGNORECASE)

    # Keep valid third-person phrases safe
    # No removal of 'The researchers', 'The study', 'The authors'.

    s = _clean_text(s)
    return s


def _fetch_page_summary(url: str) -> str:
    if not url or _is_search_index_url(url):
        return ''

    try:
        sess = requests.Session()
        sess.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; SummaryBot/1.0)'})
        resp = sess.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')

        # Try meta description first
        for meta_name in ['description', 'dcterms.description']:
            meta = soup.select_one(f'meta[name="{meta_name}"]')
            if meta and meta.get('content'):
                desc = _strip_summary_prefix(_clean_text(meta.get('content')))
                if len(desc) > 20:
                    # Clean contact info and check if still meaningful
                    desc = _strip_contact_info(desc)
                    if desc and len(desc) > 20 and not _is_uninformative_summary(desc):
                        return _format_two_sentences(desc)

        # Try Open Graph description
        for og_prop in ['og:description', 'dcterms.description']:
            og_desc = soup.select_one(f'meta[property="{og_prop}"]')
            if og_desc and og_desc.get('content'):
                desc = _strip_summary_prefix(_clean_text(og_desc.get('content')))
                if len(desc) > 20:
                    desc = _strip_contact_info(desc)
                    if desc and len(desc) > 20 and not _is_uninformative_summary(desc):
                        return _format_two_sentences(desc)

        # Look for abstract or summary sections
        abstract_selectors = [
            '[class*="abstract"]', '[id*="abstract"]',
            '[class*="summary"]', '[id*="summary"]',
            'div.abstract', 'div.summary',
            'section.abstract', 'section.summary'
        ]
        
        for selector in abstract_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = _strip_summary_prefix(_clean_text(elem.get_text()))
                if len(text) > 30:
                    text = _strip_contact_info(text)
                    if text and len(text) > 30 and not _is_uninformative_summary(text):
                        return _format_two_sentences(text)

        # Look for main content paragraphs
        main_content = soup.select_one('main') or soup.select_one('[role="main"]') or soup.select_one('article')
        if main_content:
            paragraphs = main_content.find_all('p')
        else:
            # Fallback to all paragraphs
            paragraphs = soup.find_all('p')

        for p in paragraphs:
            text = _strip_summary_prefix(_clean_text(p.get_text()))
            # Be less restrictive - accept shorter paragraphs if they seem meaningful
            if len(text) > 40 and not any(word in text.lower() for word in ['copyright', 'terms of use', 'privacy policy']):
                text = _strip_contact_info(text)
                if text and len(text) > 30 and not _is_uninformative_summary(text):
                    return _format_two_sentences(text)

        # Last resort: try to extract from any div with substantial text
        for div in soup.find_all('div'):
            text = _strip_summary_prefix(_clean_text(div.get_text()))
            if len(text) > 100 and len(text.split()) > 15:
                text = _strip_contact_info(text)
                if text and len(text) > 50 and not _is_uninformative_summary(text):
                    return _format_two_sentences(text)

    except Exception as e:
        logger.debug(f"Fetch page summary failed for {url}: {e}")

    return ''


def _ollama_summarize(content: str) -> str:
    try:
        import dspy

        # Strip URLs from input upfront
        clean_content = _strip_urls(content)
        if not clean_content:
            logger.warning("Content became empty after stripping URLs")
            return ''

        class Summarize(dspy.Signature):
            content = dspy.InputField()
            summary = dspy.OutputField()

        lm = dspy.LM('ollama/qwen2.5:7b', api_base='http://localhost:11434')
        dspy.configure(lm=lm)

        prompt = (
            "TASK: Write exactly 2 complete sentences summarizing the following technical content.\n\n"
            "MANDATORY RULES:\n"
            "1. NO URLs: Do not include or reference any website addresses.\n"
            "2. NO TRUNCATION: Every sentence must be complete with a period. Never end mid-word.\n"
            "3. NO SOURCE ATTRIBUTION: Never say 'NIST says', 'This paper', or 'The study presents'.\n"
            "4. EXACTLY 2 SENTENCES: Both must end with a period.\n"
            "5. COMPLETE THOUGHTS: Sentence 1 = what is being built/tested. Sentence 2 = system constraints or impact.\n"
            "6. USE THIRD PERSON ONLY: Never use 'I', 'we', 'our', or 'this article'.\n\n"
            f"Content:\n{clean_content[:4000]}\n\n"
            "SUMMARY (exactly 2 complete sentences, no URLs, high technical density):\n"
        )

        result = dspy.Predict(Summarize)(content=prompt)
        if hasattr(result, 'summary') and result.summary:
            summary = _clean_text(result.summary).strip()
            
            # Reject if output contains URLs or gibberish
            if _extract_urls(summary):
                logger.warning("Ollama output contained URLs, rejecting")
                return ''
            if _has_gibberish(summary):
                logger.warning("Ollama output had gibberish patterns, rejecting")
                return ''
            
            return summary
        return ''

    except Exception as e:
        logger.warning(f"Ollama summarization failed: {e}")
        return ''


class SummaryManager:
    def __init__(self, topic: str = 'qis'):
        if topic not in TOPICS:
            raise ValueError(f"topic must be one of {sorted(TOPICS)}")
        self.topic = topic

    def _load_cache(self, key: str) -> Optional[str]:
        cache_obj = _load_topic_cache(self.topic)
        entry = cache_obj.get(key)
        if not entry:
            return None

        try:
            ts = datetime.fromisoformat(entry.get('timestamp', ''))
            if datetime.now() - ts > timedelta(hours=CACHE_TTL_HOURS):
                return None
        except Exception:
            return None

        summary = entry.get('summary', '')
        if summary and _is_uninformative_summary(summary):
            return None

        return summary

    def _save_cache(self, key: str, summary: str) -> None:
        if not summary:
            return
        cache_obj = _load_topic_cache(self.topic)
        cache_obj[key] = {
            'timestamp': datetime.now().isoformat(),
            'summary': summary,
        }
        _save_topic_cache(self.topic, cache_obj)

    def generate_summary(self, item: Dict[str, str]) -> str:
        """Generate concise 1-2 sentence summary (Rule 5: every non-presentation must have summary)."""
        if not item or not isinstance(item, dict):
            return ''

        # RULE 4: Skip presentations entirely
        resource_type = str(item.get('resource_type', '')).strip().lower()
        if 'presentation' in resource_type or any(x in resource_type for x in ['slide', 'poster', 'conference talk']):
            return ''

        abstract = _clean_text(str(item.get('abstract') or item.get('description') or item.get('summary') or '')).strip()
        link = str(item.get('link') or '').strip()
        title = _clean_text(str(item.get('title') or item.get('document_name') or ''))

        if not abstract and not link:
            return ''

        cache_key_input = abstract or link or title
        cache_key = _cache_key(cache_key_input)

        cached = self._load_cache(cache_key)
        if cached:
            out = _ensure_third_person(cached)
            return _format_two_sentences(out)

        if abstract:
            # Clean contact info from abstract first
            cleaned_abstract = _strip_contact_info(abstract)
            if not cleaned_abstract or _is_uninformative_summary(cleaned_abstract):
                return ''

            trimmed = _format_two_sentences(cleaned_abstract)
            
            # Use technical extraction for more reliable summarization
            te = self.generate_technical_extraction(item)
            if te and te.get('technical_core'):
                # Format technical extraction as a readable summary
                summary = te['technical_core']
                if len(summary.split('.')) < 2 and te.get('system_entities'):
                    # Add system entities if summary is too short
                    entities = te['system_entities']
                    if entities:
                        summary += f' Key components include {entities.lower()}.'
                
                summary = _ensure_third_person(summary)
                summary = _format_two_sentences(summary)
                
                if summary and not _is_uninformative_summary(summary):
                    self._save_cache(cache_key, summary)
                    return summary
            
            # Fallback to traditional AI summarization
            try:
                from .ai_summarizer import AISummarizer
                summarizer = AISummarizer(topic=self.topic)
                out = summarizer.generate_summary(cleaned_abstract, cache_id=cache_key_input)
                out = _ensure_third_person(out)
                out = _format_two_sentences(out)
            except Exception:
                out = ''

            if not out:
                # RULE 5: Fallback to cleaned abstract if no AI summary generated
                out = _format_two_sentences(_ensure_third_person(trimmed))

            if out:
                self._save_cache(cache_key, out)
                return out
            
            # RULE 5: Last resort - return first sentence of cleaned abstract for every publication
            if cleaned_abstract:
                fallback = _split_into_full_sentences(cleaned_abstract)
                if fallback:
                    summary = fallback[0].strip()
                    if summary and not _is_uninformative_summary(summary):
                        self._save_cache(cache_key, summary)
                        return summary
            
            return ''

        # no abstract; try page scraping (RULE 5: must find summary for every non-presentation)
        if link:
            scraped = _fetch_page_summary(link)
            if scraped:
                try:
                    from .ai_summarizer import AISummarizer
                    summarizer = AISummarizer(topic=self.topic)
                    out = summarizer.generate_summary(scraped, cache_id=cache_key_input)
                    out = _ensure_third_person(out)
                    out = _format_two_sentences(out)
                except Exception:
                    out = _format_two_sentences(_ensure_third_person(scraped))

                if out and not _is_uninformative_summary(out):
                    self._save_cache(cache_key, out)
                    return out
            
            # Scraping failed or returned empty; try technical extraction from title/metadata
            if title:
                # Create context from available metadata
                metadata_parts = []
                if title:
                    metadata_parts.append(f"Title: {title}")
                if item.get('resource_type'):
                    metadata_parts.append(f"Type: {item['resource_type']}")
                if item.get('category'):
                    metadata_parts.append(f"Category: {item['category']}")
                if item.get('series'):
                    metadata_parts.append(f"Series: {item['series']}")
                
                context = '. '.join(metadata_parts)
                if len(context) > 30:  # Only if we have meaningful metadata
                    try:
                        te = self.generate_technical_extraction({'abstract': context, 'title': title})
                        if te and te.get('technical_core'):
                            summary = te['technical_core']
                            if len(summary.split('.')) < 2 and te.get('system_entities'):
                                entities = te['system_entities']
                                if entities:
                                    summary += f' Key components include {entities.lower()}.'
                            
                            summary = _ensure_third_person(summary)
                            summary = _format_two_sentences(summary)
                            
                            if summary and not _is_uninformative_summary(summary):
                                self._save_cache(cache_key, summary)
                                return summary
                    except Exception as e:
                        logger.debug(f"Technical extraction from metadata failed: {e}")

        return ''


    def generate_knowledge_map(self, item: Dict[str, str]) -> Dict[str, str]:
        """
        Generate a structured knowledge map from a NIST publication item.
        
        Returns a dict with keys: domain_classification, core_ontology, functional_constraints,
        quantitative_metrics, adversarial_vectors, dependency_graph
        """
        if not item or not isinstance(item, dict):
            return {}

        abstract = _clean_text(str(item.get('abstract') or item.get('description') or item.get('summary') or '')).strip()
        link = str(item.get('link') or '').strip()
        title = _clean_text(str(item.get('title') or item.get('document_name') or ''))

        if not abstract and not link:
            return {}

        # For knowledge map, we need content. If no abstract, try to fetch from link
        content = abstract
        if not content and link:
            content = _fetch_page_summary(link)
        
        if not content:
            return {}

        # Use AISummarizer for knowledge map
        from .ai_summarizer import AISummarizer
        summarizer = AISummarizer(topic=self.topic)
        cache_id = abstract or link or title
        km = summarizer.generate_knowledge_map(content, cache_id=cache_id)
        
        return km


    def generate_technical_extraction(self, item: Dict[str, str]) -> Dict[str, str]:
        """
        Generate a structured technical extraction from a NIST publication item.
        
        Returns a dict with keys: technical_core, system_entities, logic_constraints,
        security_risk_vectors, target_environment
        """
        if not item or not isinstance(item, dict):
            return {}

        abstract = _clean_text(str(item.get('abstract') or item.get('description') or item.get('summary') or '')).strip()
        link = str(item.get('link') or '').strip()
        title = _clean_text(str(item.get('title') or item.get('document_name') or ''))

        if not abstract and not link:
            return {}

        # For technical extraction, we need content. If no abstract, try to fetch from link
        content = abstract
        if not content and link:
            content = _fetch_page_summary(link)
        
        if not content:
            return {}

        # Use AISummarizer for technical extraction
        from .ai_summarizer import AISummarizer
        summarizer = AISummarizer(topic=self.topic)
        cache_id = abstract or link or title
        te = summarizer.generate_technical_extraction(content, cache_id=cache_id)
        
        return te


if __name__ == '__main__':
    # quick local smoke test
    m = SummaryManager(topic='qis')
    test_item = {
        'title': 'Challenges to the monitoring of deployed AI systems',
        'link': 'https://csrc.nist.gov/publications/detail/example',
        'abstract': 'As artificial intelligence (AI) systems are increasingly integrated into critical infrastructure, monitoring and governance need systematic methods.',
    }
    print('summary:', m.generate_summary(test_item))
