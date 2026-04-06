import requests
import time
import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging
from newspaper import Article
from langdetect import detect, LangDetectException

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContentFetcher:
    """Fetches and extracts content from URLs for AI summarization."""
    
    def __init__(self, cache_dir: str = "data_storage/cache"):
        self.cache_dir = cache_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def _get_cache_key(self, url: str) -> str:
        """Generate a cache key for the URL."""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cache_path(self, url: str) -> str:
        """Get the full cache file path for a URL."""
        cache_key = self._get_cache_key(url)
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def _is_cache_valid(self, cache_path: str, max_age_hours: int = 24) -> bool:
        """Check if cached content is still valid."""
        if not os.path.exists(cache_path):
            return False
        
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
            
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            max_age = timedelta(hours=max_age_hours)
            
            return datetime.now() - cache_time < max_age
        except Exception:
            return False
    
    def _save_to_cache(self, url: str, content: Dict[str, Any]):
        """Save content to cache."""
        try:
            cache_path = self._get_cache_path(url)
            cache_data = {
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'content': content
            }
            
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache for {url}: {e}")
    
    def _load_from_cache(self, url: str) -> Optional[Dict[str, Any]]:
        """Load content from cache if valid."""
        cache_path = self._get_cache_path(url)
        
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)
                return cache_data['content']
            except Exception as e:
                logger.warning(f"Failed to load cache for {url}: {e}")
        
        return None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = ' '.join(text.split())
        
        # Remove common artifacts
        text = text.replace('\u200b', '')  # Zero-width space
        text = text.replace('\u200c', '')  # Zero-width non-joiner
        text = text.replace('\u200d', '')  # Zero-width joiner
        text = text.replace('\ufeff', '')  # BOM
        
        return text.strip()
    
    def _extract_nist_content(self, url: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract content from NIST-specific pages."""
        content = {
            'title': '',
            'authors': [],
            'abstract': '',
            'body': '',
            'publication_date': '',
            'language': 'en'
        }
        
        # Check for redirect or error indicators in the HTML
        # But be more conservative to avoid false positives
        html_text = soup.get_text().lower()
        error_indicators = [
            'redirect', 'error', 'not found', '404', '500', 'maintenance',
            'you are being redirected', 'potential security issue',
            'access denied', 'forbidden', 'temporarily unavailable'
        ]
        
        # Count how many error indicators we find
        error_count = sum(1 for indicator in error_indicators if indicator in html_text)
        
        # Only consider it an error if we find multiple indicators or very specific ones
        critical_indicators = ['404', '500', 'not found', 'access denied', 'forbidden']
        critical_found = any(indicator in html_text for indicator in critical_indicators)
        
        # Special case: JavaScript disabled pages should not be considered errors
        js_disabled_indicators = ['javascript disabled', 'requires javascript', 'unauthorized frame window']
        js_disabled_found = any(indicator in html_text for indicator in js_disabled_indicators)
        
        if (critical_found or error_count >= 3) and not js_disabled_found:
            return {'error': 'Page appears to be a redirect or error page'}
        
        # Extract title
        title_selectors = [
            'h1.title', 'h1', 'h1.document-title', 
            '.title', '.document-title', 'title'
        ]
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                content['title'] = self._clean_text(title_elem.get_text())
                break
        
        # Extract abstract/summary - prioritize specific abstract selectors
        abstract_selectors = [
            '.field-name-field-document-abstract', '.field-document-abstract', 
            '.document-abstract', '.field-name-field-abstract', '.field-abstract',
            '.abstract', '.summary', '.description'
        ]
        for selector in abstract_selectors:
            abstract_elem = soup.select_one(selector)
            if abstract_elem:
                candidate_abstract = self._clean_text(abstract_elem.get_text())
                # Validate that this looks like an abstract, not boilerplate or topics
                if self._is_likely_abstract(candidate_abstract):
                    content['abstract'] = candidate_abstract
                    break
        
        # Extract body content
        body_selectors = [
            '.content', '.body', '.article-body', '.field-body',
            '.main-content', '.content-area', 'article', 'main'
        ]
        body_text = ""
        for selector in body_selectors:
            body_elem = soup.select_one(selector)
            if body_elem:
                # Remove navigation, ads, and other non-content elements
                for unwanted in body_elem.select('.navigation, .sidebar, .ad, .footer, .related'):
                    unwanted.decompose()
                
                body_text = self._clean_text(body_elem.get_text())
                if body_text and len(body_text) > 100:  # Ensure we have substantial content
                    break
        
        # If we didn't get good body content, try to extract all text
        if not body_text:
            # Remove common navigation and footer elements
            for unwanted in soup.select('nav, header, footer, aside, .navigation, .sidebar, .ad, .related'):
                unwanted.decompose()
            
            body_text = self._clean_text(soup.get_text())
        
        # Filter out very short or obviously bad content
        if len(body_text) < 100:
            return {'error': 'Content too short or empty'}
            
        # Check for error patterns in the extracted content
        # But be more conservative to avoid false positives for JavaScript-disabled pages
        error_patterns = [
            r'error.*occurred', r'not found', r'page not found', r'404', r'500',
            r'internal server error', r'maintenance', r'temporarily unavailable',
            r'access denied', r'forbidden', r'you are being redirected'
        ]
        
        # Special case: JavaScript disabled pages should not be considered errors
        js_disabled_patterns = [
            r'javascript disabled', r'requires javascript', r'unauthorized frame window'
        ]
        
        js_disabled_found = any(re.search(pattern, body_text, re.IGNORECASE) for pattern in js_disabled_patterns)
        
        if not js_disabled_found:
            for pattern in error_patterns:
                if re.search(pattern, body_text, re.IGNORECASE):
                    return {'error': 'Content appears to be an error page'}
        
        content['body'] = body_text
        
        # Extract publication date
        date_selectors = [
            '.publication-date', '.date', '.published', 
            '.field-date', 'time', '[datetime]'
        ]
        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                date_text = date_elem.get('datetime') or date_elem.get_text()
                if date_text:
                    content['publication_date'] = self._clean_text(date_text)
                    break
        
        # Detect language
        try:
            if content['body']:
                content['language'] = detect(content['body'])
        except LangDetectException:
            content['language'] = 'en'
        
        return content
    
    def _extract_newspaper_content(self, url: str) -> Dict[str, Any]:
        """Extract content using newspaper3k library."""
        try:
            article = Article(url)
            article.download()
            article.parse()
            
            content = {
                'title': self._clean_text(article.title),
                'authors': article.authors,
                'abstract': self._clean_text(article.summary),
                'body': self._clean_text(article.text),
                'publication_date': article.publish_date.isoformat() if article.publish_date else '',
                'language': article.meta_lang or 'en'
            }
            
            return content
        except Exception as e:
            logger.warning(f"Newspaper extraction failed for {url}: {e}")
            return {}
    
    def _is_likely_abstract(self, text: str) -> bool:
        """Check if text looks like a research abstract rather than boilerplate or topics."""
        if not text or len(text.strip()) < 50:
            return False
        
        text_lower = text.lower().strip()
        
        # Reject obvious boilerplate
        boilerplate_phrases = [
            'official website of the united states government',
            'secure .gov websites use https',
            'lock ( lock',
            'locked padlock',
            'an official website',
            'u.s. department of commerce',
            'national institute of standards and technology',
            'here\'s how you know',
            'contact us', 'about nist', 'news', 'events'
        ]
        if any(phrase in text_lower for phrase in boilerplate_phrases):
            return False
        
        # Reject if it looks like a list of topics/categories
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) > 5 and all(len(line) < 50 for line in lines):
            # Check if most lines look like topic names (short, title case)
            topic_like = sum(1 for line in lines if line.istitle() and len(line.split()) <= 4)
            if topic_like / len(lines) > 0.7:
                return False
        
        # Reject if mostly URLs or short fragments
        words = text.split()
        if len(words) < 10:
            return False
        
        # Should contain some research-like language
        research_indicators = [
            'research', 'study', 'method', 'approach', 'system', 'technique',
            'algorithm', 'framework', 'model', 'analysis', 'evaluation',
            'security', 'cryptography', 'quantum', 'ai', 'machine learning'
        ]
        if not any(indicator in text_lower for indicator in research_indicators):
            return False
        
        return True
    
    def fetch_content(self, url: str) -> Dict[str, Any]:
        """Fetch and extract content from a URL."""
        if not url:
            return {'error': 'No URL provided'}
        
        # Check cache first
        cached_content = self._load_from_cache(url)
        if cached_content:
            logger.info(f"Loaded cached content for {url}")
            return cached_content
        
        try:
            # Fetch the page
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract content based on domain
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            if 'nist.gov' in domain or 'csrc.nist.gov' in domain:
                content = self._extract_nist_content(url, soup)
            else:
                # Try newspaper extraction for other domains
                content = self._extract_newspaper_content(url)
                
                # If newspaper failed, fall back to basic extraction
                if not content or not content.get('body'):
                    content = self._extract_nist_content(url, soup)
            
            # Ensure we have some content
            if not content.get('body') and not content.get('abstract'):
                # Last resort: extract all text
                for unwanted in soup.select('nav, header, footer, aside, .navigation, .sidebar, .ad, .related'):
                    unwanted.decompose()
                
                content['body'] = self._clean_text(soup.get_text())
            
            # Save to cache
            self._save_to_cache(url, content)
            
            logger.info(f"Successfully fetched content for {url}")
            return content
            
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return {'error': f'Request failed: {str(e)}'}
        except Exception as e:
            logger.error(f"Content extraction failed for {url}: {e}")
            return {'error': f'Extraction failed: {str(e)}'}