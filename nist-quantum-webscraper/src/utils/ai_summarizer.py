import dspy
import re
import logging
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# GLOBALLY DISABLE ALL INFO/DEBUG LOGS FOR PRODUCTION
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

VALID_TOPICS = {"ai_publications", "qis", "pqc"}

# Global flag to ensure DSPy is configured only once
_DSPY_CONFIGURED = False

# ---------------------------------------------------------------------------
# DSPy Signature
# ---------------------------------------------------------------------------

class SummarizationSignature(dspy.Signature):
    """
    Extract high-density technical logic from NIST abstracts.
    
    MANDATORY RULES:
    1. NO URLs: Never output or reference any URL.
    2. NO TRUNCATION: Every statement must be a complete, grammatically correct thought. Never cut off mid-word or mid-sentence.
    3. NO SOURCE ATTRIBUTION: Never say 'NIST says', 'This publication', 'The paper presents'.
    4. EXACTLY 2 SENTENCES: Both must end with a period, not ellipsis. Each sentence must be a complete thought.
    5. COMPLETE SENTENCES: No fragments like '...single-cell lith.' - expand to full terms like 'lithium-ion batteries'.
    6. TECHNICAL DEPTH: What is being built/tested? What are the constraints? Why does it matter?
    7. PROPER CAPITALIZATION: First letter of summary must be uppercase.
    
    OUTPUT FORMAT:
    Two complete sentences separated by a period. First sentence describes what is being built/tested. Second sentence explains system constraints or operational impact.
    """
    content: str = dspy.InputField(desc="Scraped text from technical document (URLs must be stripped)")
    summary: str = dspy.OutputField(desc="Exactly 2 complete third-person sentences with no URLs, no truncation, high technical density, proper capitalization. Each sentence must be a full, meaningful thought ending with a period.")


class KnowledgeMapSignature(dspy.Signature):
    """
    Extract a structural, high-density summary of the provided NIST technical document.
    STRICTLY PROHIBITED: Conversational filler, introductory phrases, or contact information/metadata summaries.

    Target Output Format: Knowledge Map formatted for downstream DSPy program.
    """
    content: str = dspy.InputField(desc="Full content of the NIST technical document")
    domain_classification: str = dspy.OutputField(desc="Identify the specific sub-field, e.g., Post-Quantum Cryptography, Risk Management Framework, Zero Trust Architecture")
    core_ontology: str = dspy.OutputField(desc="List the primary system components, actors, and data objects defined in the text")
    functional_constraints: str = dspy.OutputField(desc="Convert requirements into logical triggers. Format: IF {condition} THEN {mandatory security control}")
    quantitative_metrics: str = dspy.OutputField(desc="Extract numerical thresholds, compliance levels, or performance benchmarks")
    adversarial_vectors: str = dspy.OutputField(desc="List specific threats or vulnerabilities the document aims to mitigate")
    dependency_graph: str = dspy.OutputField(desc="List other NIST SPs or external standards referenced or relied upon")


class TechnicalExtractionSignature(dspy.Signature):
    """
    Perform a high-density structural extraction of the provided abstract.
    STRICT DIRECTIVES: NO META-COMMENTARY, NO SOURCE ATTRIBUTION, NO CONTACT INFO.
    MANDATORY CONTENT: Every entry must result in a technical summary.
    """
    content: str = dspy.InputField(desc="The abstract or technical content to extract from")
    technical_core: str = dspy.OutputField(desc="State the primary problem and the specific solution/methodology in 1-2 dense sentences")
    system_entities: str = dspy.OutputField(desc="Comma-separated list of technical objects, protocols, or frameworks mentioned")
    logic_constraints: str = dspy.OutputField(desc="The Rules or Requirements defined in the text, formatted as: Requirement: [Action]")
    security_risk_vectors: str = dspy.OutputField(desc="Identify any specific vulnerabilities, threats, or mitigation strategies")
    target_environment: str = dspy.OutputField(desc="The specific domain: e.g., Cloud, IoT, ICS, Cryptographic Modules")


# ---------------------------------------------------------------------------
# Cache — one JSON file for AI summaries 
# ---------------------------------------------------------------------------

def _find_project_root() -> str:
    candidate = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        if os.path.isdir(os.path.join(candidate, 'src')) or \
           os.path.isdir(os.path.join(candidate, 'data_storage')) or \
           os.path.isfile(os.path.join(candidate, 'requirements.txt')):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    return os.path.dirname(os.path.abspath(__file__))


_PROJECT_ROOT = _find_project_root()
_DEFAULT_CACHE_DIR = os.path.join(_PROJECT_ROOT, 'data_storage', 'summaries')


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _topic_cache_path(cache_dir: str, topic: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{topic}.json")


def _load_topic_cache(cache_dir: str, topic: str) -> Dict[str, Any]:
    path = _topic_cache_path(cache_dir, topic)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_topic_cache(cache_dir: str, topic: str, cache: Dict[str, Any]):
    path = _topic_cache_path(cache_dir, topic)
    try:
        with open(path, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save cache for topic '{topic}': {e}")


def _read_cache(cache_dir: str, topic: str, key: str, max_age_hours: int = 24) -> Optional[str]:
    cache = _load_topic_cache(cache_dir, topic)
    entry = cache.get(key)
    if not entry:
        return None
    try:
        ts = datetime.fromisoformat(entry['timestamp'])
        if datetime.now() - ts < timedelta(hours=max_age_hours):
            return entry.get('summary', '')
    except Exception:
        pass
    return None


def _write_cache(cache_dir: str, topic: str, key: str, summary: str):
    cache = _load_topic_cache(cache_dir, topic)
    cache[key] = {
        'timestamp': datetime.now().isoformat(),
        'summary': summary
    }
    _save_topic_cache(cache_dir, topic, cache)


# ---------------------------------------------------------------------------
# URL and Gibberish Detection
# ---------------------------------------------------------------------------

def _extract_urls(text: str) -> list:
    """Extract all URLs from text."""
    if not text:
        return []
    # More comprehensive URL patterns
    url_patterns = [
        r'https?://[^\s]+',  # http:// or https://
        r'www\.[^\s]+',      # www.
        r'\b\d+\.\d+\.\d+\.\d+\b',  # IP addresses
        r'\bdoi\.org/[^\s]+',  # DOI links
        r'\bnist\.gov/[^\s]+',  # NIST links
        r'\btsapps\.nist\.gov/[^\s]+',  # NIST tsapps
        r'[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?',  # general domain patterns
    ]
    urls = []
    for pattern in url_patterns:
        urls.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return list(set(urls))  # remove duplicates

def _strip_urls(text: str) -> str:
    """Remove all URLs from text."""
    if not text:
        return ''
    # Remove various URL patterns
    text = re.sub(r'https?://[^\s]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'www\.[^\s]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\d+\.\d+\.\d+\.\d+\b', '', text)  # IP addresses
    text = re.sub(r'\bdoi\.org/[^\s]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnist\.gov/[^\s]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\btsapps\.nist\.gov/[^\s]*', '', text, flags=re.IGNORECASE)
    # Remove any remaining domain-like patterns that might be URLs
    text = re.sub(r'\b[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?', '', text)
    return ' '.join(text.split()).strip()

def _has_gibberish(text: str) -> bool:
    """Detect common gibberish patterns."""
    if not text:
        return False
    low = text.lower().strip()
    
    # Check for truncation mid-word (ellipsis patterns)
    if re.search(r'\.\.\.', low):
        return True
    
    # Check for incomplete abbreviations (words ending with . that are too short)
    words = re.findall(r'\b\w+\b', low)
    if words:
        last_word = words[-1]
        # If last word ends with . and is very short (likely abbreviation), and total text is short, likely truncated
        if last_word.endswith('.') and len(last_word) <= 5 and len(low) < 100:
            # Allow common abbreviations like "etc.", "i.e.", "e.g."
            if last_word.lower() not in ['etc.', 'i.e.', 'e.g.', 'al.', 'fig.', 'vol.', 'no.', 'pp.']:
                return True
    
    # Check for words that end abruptly (not followed by punctuation)
    if words and not low.endswith(('.', '!', '?')):
        last_word = words[-1]
        if len(last_word) < 3 and not re.search(r'\b(?:a|an|the|is|are|was|were|be|been|being|have|has|had|do|does|did|will|would|can|could|should|may|might|must|shall|it|he|she|they|we|I|you|this|that|these|those|and|or|but|if|then|when|where|why|how|what|which|who|all|some|any|no|not|yes|no|ok|hi|bye|thanks|please|sorry|excuse|me|my|your|his|her|its|our|their)\b', last_word):
            return True
    
    # Check for repeated tokens (sign of model failure)
    tokens = low.split()
    if len(tokens) > 0:
        # If any word appears more than 30% of the time, likely gibberish
        from collections import Counter
        counts = Counter(tokens)
        if counts and max(counts.values()) > len(tokens) * 0.3:
            return True
    
    # Check for randomness indicators
    nonsense_patterns = [
        r'[a-z]{20,}',  # Long unbroken strings of letters
        r'\d{10,}',     # Long number sequences
        r'[^a-z0-9\s\.,:;!?\'\-()]{5,}',  # Many special chars
    ]
    for pattern in nonsense_patterns:
        if re.search(pattern, low):
            return True
    
    return False

def _is_complete_sentences(text: str) -> bool:
    """Verify text is 2+ complete sentences (not fragments)."""
    if not text or len(text.strip()) < 20:
        return False
    
    # Must have proper sentence endings
    sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
    if len(sentences) < 2:
        return False
    
    # Each sentence must be meaningful (at least 3 words)
    for sentence in sentences[:2]:
        if len(sentence.split()) < 3:
            return False
    
    return True


def _has_mid_phrase_start(text: str) -> bool:
    """Detect summaries that appear to start mid-phrase."""
    if not text:
        return False

    cleaned = ' '.join((text or '').strip().split())
    if not cleaned:
        return False

    first_sentence = re.split(r'(?<=[.!?])\s+', cleaned, maxsplit=1)[0].strip()
    first_sentence = first_sentence.lstrip('"\'([{').strip()
    if not first_sentence:
        return False

    bad_start_pattern = (
        r'^(is|are|was|were|be|being|been|has|have|had|can|could|should|would|may|might|must|will|'
        r'do|does|did|using|based|focused|designed|aimed|intended|developed|built|created)\b'
    )
    return bool(re.match(bad_start_pattern, first_sentence.lower()))

# ---------------------------------------------------------------------------
# Text cleanup
# ---------------------------------------------------------------------------

_UNINFORMATIVE_INDICATORS = [
    'potential security issue', 'you are being redirected', 'redirecting to',
    'this site is not secure', 'please enable javascript', 'javascript disabled',
    'official websites use .gov', '.gov website',
    '404', '500', 'not found', 'access denied', 'forbidden', 'error occurred',
    'no meaningful content available',
    'secure . gov websites use',  # NEW: catches the specific boilerplate
    'lock ( lock',  # NEW: catches "lock ( Lock" pattern
    'locked padlock',  # NEW: catches padlock references
    'httpsa lock',  # NEW: catches OCR error "HTTPSA"
    'safely connected to the website',  # NEW: catches connection message
    'contact us', 'contact the', 'for questions', 'if you have questions',
    'if you have any questions', 'encounter issues', 'issues accessing',
    'email address', 'serves as the point of contact', 'point of contact',
]


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
    low = (text or '').lower().strip()
    return any(low.startswith(prefix) for prefix in _FORBIDDEN_SUMMARY_PREFIXES)


def _has_researcher_placeholder(text: str) -> bool:
    if not text:
        return False
    low = (text or '').lower().strip()
    return 'conducted by researchers at the' in low


def _has_junk_security_keyword_block(text: str) -> bool:
    if not text:
        return False
    low = (text or '').lower().strip()
    needed = [
        'computer security division',
        'cryptographic technology',
        'secure systems and applications',
        'security components and mechanisms',
        'security engineering and risk management',
        'security testing'
    ]
    return all(x in low for x in needed)


def _has_researcher_conduct_mention(text: str) -> bool:
    if not text:
        return False
    low = (text or '').lower().strip()
    bad_phrases = [
        'conducted by researchers',
        'researchers at the',
        'study conducted by',
        'research conducted by',
        'authors of the study',
        'the researchers',
        'conducted by',
    ]
    return any(phrase in low for phrase in bad_phrases)


def _is_uninformative(text: str) -> bool:
    low = (text or '').lower().strip()
    if _has_forbidden_prefix(low):
        return True
    if _has_researcher_placeholder(low):
        return True
    if _has_junk_security_keyword_block(low):
        return True
    if _has_researcher_conduct_mention(low):
        return True
    if 'nist' in low and 'security concern' in low:
        return True

    # Reject summaries that are just URLs
    import re
    url_pattern = r'^https?://[^\s]*$'
    if re.match(url_pattern, low):
        return True

    # Reject short summaries that are mostly URLs
    if len(low) < 50 and re.search(r'https?://', low):
        return True

    # Reject summaries containing email addresses
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
        return True

    return any(i in low for i in _UNINFORMATIVE_INDICATORS)


# First-person verb phrases → third-person rewrites
_FIRST_PERSON_REWRITES = {
    r'\bwe present\b': 'The study presents',
    r'\bwe propose\b': 'The study proposes',
    r'\bwe introduce\b': 'The study introduces',
    r'\bwe demonstrate\b': 'The study demonstrates',
    r'\bwe develop\b': 'The study develops',
    r'\bwe show\b': 'The study shows',
    r'\bwe analyze\b': 'The study analyzes',
    r'\bwe investigate\b': 'The study investigates',
    r'\bwe evaluate\b': 'The study evaluates',
    r'\bwe explore\b': 'The study explores',
    r'\bwe describe\b': 'The study describes',
    r'\bwe report\b': 'The study reports',
    r'\bwe find\b': 'The study finds',
    r'\bwe conclude\b': 'The study concludes',
    r'\bwe discuss\b': 'The study discusses',
    r'\bwe provide\b': 'The study provides',
    r'\bwe examine\b': 'The study examines',
    r'\bwe compare\b': 'The study compares',
    r'\bwe implement\b': 'The study implements',
    r'\bwe test\b': 'The study tests',
    r'\bwe build\b': 'The study builds',
    r'\bwe create\b': 'The study creates',
    r'\bwe identify\b': 'The study identifies',
    r'\bwe measure\b': 'The study measures',
    r'\bwe perform\b': 'The study performs',
    r'\bwe conduct\b': 'The study conducts',
    r'\bwe use\b': 'The study uses',
    r'\bwe apply\b': 'The study applies',
    r'\bwe highlight\b': 'The study highlights',
    r'\bwe address\b': 'The study addresses',
    r'\bwe suggest\b': 'The study suggests',
    r'\bwe recommend\b': 'The study recommends',
}


def _strip_prefatory_phrases(text: str) -> str:
    if not text:
        return ''

    text = text.strip()
    text = re.sub(r'^(this\s+abstract\s+outlines(\s+key\s+areas(\s+of)?)?)\s*[:,]?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(the|this)\s+(paper|article|study)\s+presents\s*[:,]?\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def _ensure_third_person(text: str) -> str:
    """
    Rewrite first-person phrases to third-person.
    NOTE: Does NOT remove 'The researchers' or 'The authors' — those are correct third-person.
    """
    if not text:
        return text

    # Strip emoji prefixes
    text = re.sub(r'🤖\s*(AI\s*)?(Summary\s*)?[:\-]?\s*', '', text, flags=re.IGNORECASE)
    text = _strip_prefatory_phrases(text)

    # Rewrite known first-person verb patterns first
    for pattern, replacement in _FIRST_PERSON_REWRITES.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Catch remaining standalone "we" → "the researchers"
    text = re.sub(r'\bwe\b', 'the researchers', text, flags=re.IGNORECASE)

    # Rewrite first-person pronouns
    text = re.sub(r'\bour\b', 'their', text, flags=re.IGNORECASE)
    text = re.sub(r'\bours\b', 'theirs', text, flags=re.IGNORECASE)
    text = re.sub(r'\bus\b', 'them', text, flags=re.IGNORECASE)

    # Only remove standalone "I" (not part of words like "Artificial Intelligence")
    text = re.sub(r'(?<!\w)\bI\b(?!\w)', 'the researcher', text)

    # Remove NIST attribution language (keep summary focused on content)
    text = re.sub(r'\bNIST\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'National Institute of Standards and Technology', '', text, flags=re.IGNORECASE)

    # Clean up double spaces from removals
    text = re.sub(r'\s{2,}', ' ', text).strip()

    # Fix punctuation artifacts: ". ." or " ." at start
    text = re.sub(r'\s+\.', '.', text)
    text = re.sub(r'^\.\s*', '', text)

    # Capitalize first letter
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text


def _truncate_to_full_sentence(text: str, max_chars: int = 800) -> str:
    text = text.strip()
    if not text or len(text) <= max_chars:
        return text
    snippet = text[:max_chars]
    match = re.search(r'[.!?][^.!?]*$', snippet)
    if match:
        snippet = snippet[:match.start() + 1]
    return snippet.strip()


def _limit_to_two_sentences(text: str) -> str:
    text = ' '.join((text or '').strip().split())
    if not text:
        return ''

    sentences = [s.strip() for s in re.findall(r'[^.!?]*[.!?]', text, flags=re.DOTALL) if s.strip()]
    if not sentences:
        return ''
    text = ' '.join(sentences[:2])
    if text and text[-1] not in '.!?':
        text += '.'
    return text


# ---------------------------------------------------------------------------
# AISummarizer
# ---------------------------------------------------------------------------

class AISummarizer:
    """
    AI summarization module using DSPy with Ollama (qwen2.5:7b).

    Produces 2-sentence third-person summaries.
    Cache is consolidated into one JSON file per topic instead of one file per item.

    Parameters
    ----------
    topic : str
        One of 'ai_publications', 'qis', 'pqc'. Controls which cache file is used.
    model_name : str
        Ollama model. Defaults to qwen2.5:7b.
    cache_dir : str
        Directory for topic cache JSON files.
    """

    def __init__(
        self,
        topic: str = 'qis',
        model_name: str = "qwen2.5:7b",
        cache_dir: str = _DEFAULT_CACHE_DIR,
    ):
        if topic not in VALID_TOPICS:
            raise ValueError(f"topic must be one of {VALID_TOPICS}, got '{topic}'")

        self.topic = topic
        self.model_name = model_name
        self.cache_dir = cache_dir

        try:
            self.model = dspy.LM(f"ollama/{model_name}", api_base="http://localhost:11434", max_tokens=300)
            global _DSPY_CONFIGURED
            if not _DSPY_CONFIGURED:
                try:
                    dspy.configure(lm=self.model)
                    _DSPY_CONFIGURED = True
                    # Production silent mode - no info logs
                except Exception as config_e:
                    if "can only be changed by the thread" in str(config_e):
                        logger.warning(f"DSPy already configured by another thread, skipping: {config_e}")
                        _DSPY_CONFIGURED = True  # Mark as configured to avoid retries
                    else:
                        raise
            else:
                # Production silent mode - no info logs
                pass
        except Exception as e:
            logger.error(f"Failed to configure Ollama model {model_name}: {e}")
            raise

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_summary(self, summary: str) -> bool:
        if not summary or len(summary.strip()) < 20:
            return False
        
        # Check for URLs (enhanced)
        urls = _extract_urls(summary)
        if urls:
            logger.warning(f"Rejecting summary with URLs: {urls} in {summary[:60]}")
            return False
        
        # Additional check for any URL-like patterns
        if '://' in summary or 'www.' in summary.lower() or 'http' in summary.lower():
            logger.warning(f"Rejecting summary with URL indicators: {summary[:60]}")
            return False
        
        # Check for proper capitalization (first letter should be uppercase)
        stripped = summary.strip()
        if stripped and stripped[0].islower():
            logger.warning(f"Rejecting summary with lowercase start: {summary[:60]}")
            return False
        
        # Check for gibberish
        if _has_gibberish(summary):
            logger.warning(f"Rejecting summary with gibberish: {summary[:60]}")
            return False
        
        # Check for complete sentences
        if not _is_complete_sentences(summary):
            logger.warning(f"Rejecting incomplete sentences: {summary[:60]}")
            return False

        if _has_mid_phrase_start(summary):
            logger.warning(f"Rejecting mid-phrase start: {summary[:60]}")
            return False
        
        if _is_uninformative(summary):
            return False
        
        if summary.strip()[-1] not in '.!?':
            return False
        
        return True

    # ------------------------------------------------------------------
    # DSPy generation
    # ------------------------------------------------------------------

    def _generate_with_dspy(self, content: str) -> str:
        try:
            # Strip URLs from input before processing
            clean_content = _strip_urls(content)
            if not clean_content:
                logger.warning("Content became empty after stripping URLs")
                return ''
            
            predictor = dspy.ChainOfThought(SummarizationSignature)
            result = predictor(content=clean_content)
            summary = result.summary or ''
            
            # Reject if output contains URLs
            if _extract_urls(summary):
                logger.warning("Model output contained URLs, rejecting")
                return ''
            
            return summary
        except Exception as e:
            logger.error(f"DSPy generation failed: {e}")
            return ''

    def _generate_fallback(self, content: str) -> str:
        """Direct model call if DSPy predict fails."""
        try:
            # Strip URLs from input
            clean_content = _strip_urls(content)
            if not clean_content:
                logger.warning("Content became empty after stripping URLs")
                return ''
            
            prompt = (
                "TASK: Write exactly 2 complete sentences summarizing the following technical content.\n\n"
                "MANDATORY RULES:\n"
                "1. NO URLs: Do not include or reference any website addresses.\n"
                "2. NO TRUNCATION: Every sentence must be complete with a period. Never end mid-word or cut off thoughts. Expand abbreviations fully (e.g., 'lith.' becomes 'lithium-ion batteries').\n"
                "3. NO SOURCE ATTRIBUTION: Never say 'NIST says', 'This paper', or 'The study presents'.\n"
                "4. EXACTLY 2 SENTENCES: Both must end with a period. Each must be a full, meaningful thought.\n"
                "5. COMPLETE THOUGHTS: Sentence 1 = what is being built/tested (complete description). Sentence 2 = system constraints or impact (complete explanation).\n"
                "6. USE THIRD PERSON ONLY: Never use 'I', 'we', 'our', or 'this article'.\n"
                "7. PROPER CAPITALIZATION: Start with uppercase letter.\n\n"
                f"Content:\n{clean_content[:4000]}\n\n"
                "OUTPUT FORMAT: Two complete sentences separated by a period.\n\n"
                "SUMMARY (exactly 2 complete sentences, no URLs, no truncation, high technical density):"
            )
            response = self.model(prompt)
            if isinstance(response, list):
                text = response[0].get('content', '') if isinstance(response[0], dict) else str(response[0])
            else:
                text = str(response)
            
            summary = text.replace('SUMMARY:', '').replace('Summary:', '').strip()
            
            # Reject if output contains URLs
            if _extract_urls(summary):
                logger.warning("Fallback output contained URLs, rejecting")
                return ''
            
            return summary
        except Exception as e:
            logger.error(f"Fallback generation failed: {e}")
            return ''

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate_summary(self, content: str, cache_id: str = '', max_content_length: int = 8000) -> str:
        """
        Generate a 2-sentence third-person summary.

        Parameters
        ----------
        content : str
            The text to summarize (abstract, body, etc.)
        cache_id : str
            A stable identifier for this item (URL or title).
            If empty, falls back to hashing the content itself.
        max_content_length : int
            Max chars to send to the model.
        """
        if not content or not content.strip():
            return ''

        # Strip URLs from input upfront
        content = _strip_urls(content)
        if not content:
            logger.warning("Content became empty after stripping URLs")
            return ''

        # Reject uninformative input content
        if _is_uninformative(content):
            # Production silent mode
            return ''

        # Cache lookup
        key = _cache_key(cache_id if cache_id else content)
        cached = _read_cache(self.cache_dir, self.topic, key)
        if cached is not None:
            cleaned = _ensure_third_person(cached)
            if self._validate_summary(cleaned):
                # Production silent mode
                return cleaned
            # Cached value is bad — regenerate
            pass

        # Truncate content
        if len(content) > max_content_length:
            content = _truncate_to_full_sentence(content, max_content_length)

        # Generate with retry for completeness
        max_retries = 3
        for attempt in range(max_retries):
            if attempt == 0:
                summary = self._generate_with_dspy(content)
            else:
                # Production silent mode
                summary = self._generate_fallback(content)
            
            if not summary:
                continue
            
            # Clean and enforce third person + 2 sentences
            summary = _ensure_third_person(summary)
            summary = _limit_to_two_sentences(summary)
            
            # Check if complete
            if self._validate_summary(summary):
                break
            else:
                pass
        
        if not summary or not self._validate_summary(summary):
            logger.warning("All generation attempts failed.")
            return ''

        _write_cache(self.cache_dir, self.topic, key, summary)
        # Production silent mode
        return summary

    def generate_knowledge_map(self, content: str, cache_id: str = '', max_content_length: int = 8000) -> dict:
        """
        Generate a structured knowledge map extraction from NIST technical documents.

        Returns a dict with keys: domain_classification, core_ontology, functional_constraints,
        quantitative_metrics, adversarial_vectors, dependency_graph
        """
        if not content or not content.strip():
            return {}

        # Reject uninformative input content upfront
        if _is_uninformative(content):
            # Production silent mode
            return {}

        # Cache lookup (using same cache but different key prefix)
        key = f"km_{_cache_key(cache_id if cache_id else content)}"
        cached = _read_cache(self.cache_dir, self.topic, key)
        if cached is not None:
            try:
                import json
                km_data = json.loads(cached)
                # Production silent mode
                return km_data
            except:
                pass

        # Truncate content
        if len(content) > max_content_length:
            content = _truncate_to_full_sentence(content, max_content_length)

        # Generate with DSPy
        try:
            predictor = dspy.Predict(KnowledgeMapSignature)
            result = predictor(content=content)
            
            km_data = {
                'domain_classification': result.domain_classification or '',
                'core_ontology': result.core_ontology or '',
                'functional_constraints': result.functional_constraints or '',
                'quantitative_metrics': result.quantitative_metrics or '',
                'adversarial_vectors': result.adversarial_vectors or '',
                'dependency_graph': result.dependency_graph or ''
            }
            
            # Cache the result
            import json
            _write_cache(self.cache_dir, self.topic, key, json.dumps(km_data))
            # Production silent mode
            return km_data
            
        except Exception as e:
            logger.error(f"Knowledge map generation failed: {e}")
            return {}

    def generate_technical_extraction(self, content: str, cache_id: str = '', max_content_length: int = 8000) -> dict:
        """
        Generate a structured technical extraction from content.
        
        Returns a dict with keys: technical_core, system_entities, logic_constraints,
        security_risk_vectors, target_environment
        """
        if not content or not content.strip():
            return {}

        # Reject uninformative input content upfront
        if _is_uninformative(content):
            # Production silent mode
            return {}

        # Cache lookup (using same cache but different key prefix)
        key = f"te_{_cache_key(cache_id if cache_id else content)}"
        cached = _read_cache(self.cache_dir, self.topic, key)
        if cached is not None:
            try:
                import json
                te_data = json.loads(cached)
                # Production silent mode
                return te_data
            except:
                pass

        # Truncate content
        if len(content) > max_content_length:
            content = _truncate_to_full_sentence(content, max_content_length)

        # Generate with DSPy
        try:
            predictor = dspy.Predict(TechnicalExtractionSignature)
            result = predictor(content=content)
            
            te_data = {
                'technical_core': result.technical_core or '',
                'system_entities': result.system_entities or '',
                'logic_constraints': result.logic_constraints or '',
                'security_risk_vectors': result.security_risk_vectors or '',
                'target_environment': result.target_environment or ''
            }
            
            # Cache the result
            import json
            _write_cache(self.cache_dir, self.topic, key, json.dumps(te_data))
            # Production silent mode
            return te_data
            
        except Exception as e:
            logger.error(f"Technical extraction failed: {e}")
            return {}

    def test_connection(self) -> bool:
        try:
            response = self.model("Say 'ok'")
            return bool(response)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _ensure_third_person(summary: str) -> str:
    """Convert first-person references to third-person."""
    if not summary:
        return ''

    # Remove "Summary:" prefix if present
    summary = re.sub(r'^\s*summary\s*[:\-]?\s*', '', summary, flags=re.IGNORECASE)

    # Strip prefatory phrases
    summary = re.sub(r'^(this\s+abstract\s+outlines(\s+key\s+areas(\s+of)?)?)\s*[:,]?\s*', '', summary, flags=re.IGNORECASE)
    summary = re.sub(r'^(the|this)\s+(paper|article)\s+presents\s*[:,]?\s*', '', summary, flags=re.IGNORECASE)
    summary = re.sub(r'^(the|this)\s+study\s+presents\s*[:,]?\s*', '', summary, flags=re.IGNORECASE)
    summary = re.sub(r'^(the|this)\s+abstract\s+is\s+about\s*[:,]?\s*', '', summary, flags=re.IGNORECASE)

    # First-person verb rewrites
    phrase_rewrites = {
        r'\bwe present\b': 'The study presents',
        r'\bwe propose\b': 'The study proposes',
        r'\bwe introduce\b': 'The study introduces',
        r'\bwe demonstrate\b': 'The study demonstrates',
        r'\bwe develop\b': 'The study develops',
        r'\bwe show\b': 'The study shows',
        r'\bwe analyze\b': 'The study analyzes',
        r'\bwe investigate\b': 'The study investigates',
        r'\bwe evaluate\b': 'The study evaluates',
        r'\bwe explore\b': 'The study explores',
        r'\bwe describe\b': 'The study describes',
        r'\bwe report\b': 'The study reports',
        r'\bwe find\b': 'The study finds',
        r'\bwe conclude\b': 'The study concludes',
        r'\bwe discuss\b': 'The study discusses',
        r'\bwe provide\b': 'The study provides',
        r'\bwe examine\b': 'The study examines',
        r'\bwe compare\b': 'The study compares',
        r'\bwe implement\b': 'The study implements',
        r'\bwe test\b': 'The study tests',
        r'\bwe build\b': 'The study builds',
        r'\bwe create\b': 'The study creates',
    }
    for pat, repl in phrase_rewrites.items():
        summary = re.sub(pat, repl, summary, flags=re.IGNORECASE)

    # Pronoun replacement
    summary = re.sub(r"\bour\b", 'their', summary, flags=re.IGNORECASE)
    summary = re.sub(r"\bours\b", 'theirs', summary, flags=re.IGNORECASE)
    summary = re.sub(r"\bus\b", 'them', summary, flags=re.IGNORECASE)
    summary = re.sub(r"\bI\b", 'The researcher', summary, flags=re.IGNORECASE)

    return summary.strip()


def _limit_to_two_sentences(text: str) -> str:
    """Limit text to exactly 2 complete sentences."""
    if not text:
        return ''
    
    sentences = re.findall(r'[^.!?]*[.!?]', text, flags=re.DOTALL)
    if len(sentences) >= 2:
        return ' '.join(sentences[:2]).strip()
    elif sentences:
        return sentences[0].strip()
    else:
        return text.strip() + ('.' if not text.strip().endswith(('.', '!', '?')) else '')


def _truncate_to_full_sentence(text: str, max_length: int) -> str:
    """Truncate text to max_length while preserving sentence boundaries."""
    if len(text) <= max_length:
        return text
    
    truncated = text[:max_length]
    # Find the last complete sentence
    sentences = re.findall(r'[^.!?]*[.!?]', truncated, flags=re.DOTALL)
    if sentences:
        return sentences[-1].strip()
    
    # If no complete sentence, cut at word boundary
    words = truncated.split()
    if len(words) > 1:
        return ' '.join(words[:-1]) + '.'
    
    return truncated.strip()