import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from typing import List, Dict, Any


def clean_text(text: str) -> str:
    """Clean extracted text by removing extra whitespace and control characters."""
    if not text:
        return ""
    
    # Remove zero-width spaces and other invisible unicode characters
    text = text.replace('\u200b', '')  # zero-width space
    text = text.replace('\u200c', '')  # zero-width non-joiner
    text = text.replace('\u200d', '')  # zero-width joiner
    text = text.replace('\ufeff', '')  # zero-width no-break space
    
    # Collapse multiple whitespace into single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def scrape_pqc_publications():
    """Scrape Post-Quantum Cryptography publications from NIST CSRC.
    
    This function scrapes from multiple PQC-specific URLs:
    - Final Publications
    - Drafts open for comment
    - Drafts
    """
    
    # URLs for Post-Quantum Cryptography publications
    urls = [
        {
            'url': 'https://csrc.nist.gov/publications/final-pubs',
            'category': 'Final Publications'
        },
        {
            'url': 'https://csrc.nist.gov/publications/drafts-open-for-comment',
            'category': 'Drafts Open for Comment'
        },
        {
            'url': 'https://csrc.nist.gov/publications/draft-pubs',
            'category': 'Drafts'
        }
    ]
    
    publications = []
    visited = set()
    session = requests.Session()
    
    def _fetch_page(url):
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")
    
    for url_info in urls:
        base_url = url_info['url']
        category = url_info['category']
        
        print(f"Scraping {category} from {base_url}")
        
        with requests.Session() as session:
            try:
                soup = _fetch_page(base_url)
            except Exception as e:
                print(f"Error fetching {base_url}: {e}")
                continue
            
            # Try multiple selectors for different page layouts
            items = soup.select(".search-list-item")
            if not items:
                items = soup.select("article")
            if not items:
                items = soup.select(".publication-item")
            if not items:
                items = soup.select("[data-publication]")
            
            print(f"DEBUG: Found {len(items)} items on {base_url}")
            
            for item in items:
                # Try different selectors for title
                title_link = item.select_one("h4.search-results-title a")
                if not title_link:
                    title_link = item.select_one("h3 a")
                if not title_link:
                    title_link = item.select_one("a[data-title]")
                if not title_link:
                    title_link = item.select_one("a")
                
                if not title_link:
                    continue
                
                name = clean_text(title_link.get_text(strip=True))
                if not name:
                    continue
                    
                link = title_link.get("href", "")
                if link and not link.startswith("http"):
                    link = f"https://csrc.nist.gov{link}"
                
                # Try different selectors for series
                series_el = item.select_one(".sub-title strong")
                if not series_el:
                    series_el = item.select_one(".series")
                if not series_el:
                    series_el = item.select_one("[class*='series']")
                series = clean_text(series_el.get_text(strip=True)) if series_el else ""
                
                # Try different selectors for date
                date_el = item.select_one('strong[id^="date-container-"]')
                if not date_el:
                    date_el = item.select_one("time")
                if not date_el:
                    date_el = item.select_one(".date")
                if not date_el:
                    date_el = item.select_one("[class*='date']")
                release_date = clean_text(date_el.get_text(strip=True)) if date_el else ""
                
                # Try different selectors for summary
                summary_el = item.select_one('p[id^="content-area-"]')
                if not summary_el:
                    summary_el = item.select_one(".summary")
                if not summary_el:
                    summary_el = item.select_one(".description")
                if not summary_el:
                    summary_el = item.select_one("p")
                
                summary = ""
                if summary_el:
                    summary = clean_text(summary_el.get_text(strip=True))
                    if summary.lower().startswith("abstract:"):
                        summary = summary[len("abstract:"):].strip()
                
                if name:  # Only add if we have at least a title
                    # Convert formatted date to ISO for sorting
                    release_date_raw = ""
                    if release_date:
                        try:
                            # Parse "Month Day, Year" format to ISO
                            date_obj = datetime.strptime(release_date, '%B %d, %Y')
                            release_date_raw = date_obj.strftime('%Y-%m-%d')
                        except Exception:
                            # If parsing fails, use original
                            release_date_raw = release_date
                    
                    publications.append({
                        "document_name": name,
                        "document_number": "",
                        "series": series,
                        "release_date": release_date,
                        "release_date_raw": release_date_raw,
                        "resource_type": "Post-Quantum Cryptography Publication",
                        "link": link,
                        "summary": summary,
                        "category": category
                    })
    
    # Enrich missing summaries by fetching publication pages concurrently
    def _fetch_meta(pub):
        if pub.get('summary'):
            return pub['summary']
        link = pub.get('link')
        if not link:
            return ""
        try:
            resp = session.get(link, timeout=5)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            meta = soup.select_one('meta[name="description"]')
            if meta and meta.get('content'):
                return clean_text(meta['content'])
        except Exception:
            pass
        return ""
    
    from concurrent.futures import ThreadPoolExecutor
    # collect current summaries, will overwrite if new text fetched
    pubs_to_update = [pub for pub in publications if not pub.get('summary')]
    if pubs_to_update:
        with ThreadPoolExecutor(max_workers=8) as executor:
            for pub, new_summary in zip(pubs_to_update, executor.map(_fetch_meta, pubs_to_update)):
                if new_summary:
                    pub['summary'] = new_summary
    
    print(f"DEBUG: Retrieved {len(publications)} PQC publications")
    return publications


def scrape_pqc_presentations():
    """Scrape Post-Quantum Cryptography presentations from NIST CSRC."""
    
    url = 'https://csrc.nist.gov/search?ipp=25&sortBy=relevance&showOnly=presentations&topicsMatch=ANY&topics=27651%7cpost-quantum+cryptography'
    
    presentations = []
    session = requests.Session()
    
    def _fetch_page(url):
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")
    
    print(f"Scraping PQC presentations from {url}")
    
    try:
        soup = _fetch_page(url)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return presentations
    
    # Try multiple selectors for different page layouts
    items = soup.select(".search-list-item")
    if not items:
        items = soup.select("article")
    if not items:
        items = soup.select(".presentation-item")
    if not items:
        items = soup.select("[data-presentation]")
    
    print(f"DEBUG: Found {len(items)} presentation items")
    
    for item in items:
        # Try different selectors for title
        title_link = item.select_one("h4.search-results-title a")
        if not title_link:
            title_link = item.select_one("h3 a")
        if not title_link:
            title_link = item.select_one("a[data-title]")
        if not title_link:
            title_link = item.select_one("a")
        
        if not title_link:
            continue
        
        name = clean_text(title_link.get_text(strip=True))
        if not name:
            continue
            
        link = title_link.get("href", "")
        if link and not link.startswith("http"):
            link = f"https://csrc.nist.gov{link}"
        
        # Try different selectors for series
        series_el = item.select_one(".sub-title strong")
        if not series_el:
            series_el = item.select_one(".series")
        if not series_el:
            series_el = item.select_one("[class*='series']")
        series = clean_text(series_el.get_text(strip=True)) if series_el else ""
        
        # Try different selectors for date
        date_el = item.select_one('strong[id^="date-container-"]')
        if not date_el:
            date_el = item.select_one("time")
        if not date_el:
            date_el = item.select_one(".date")
        if not date_el:
            date_el = item.select_one("[class*='date']")
        release_date = clean_text(date_el.get_text(strip=True)) if date_el else ""
        
        # Try different selectors for status
        status_el = item.select_one(".status")
        if not status_el:
            status_el = item.select_one("[class*='status']")
        status = clean_text(status_el.get_text(strip=True)) if status_el else ""
        
        if name:  # Only add if we have at least a title
            presentations.append({
                "document_name": name,
                "series": series,
                "status": status,
                "resource_type": "Post-Quantum Cryptography Presentation",
                "link": link,
                "release_date": release_date
            })
    
    print(f"DEBUG: Retrieved {len(presentations)} PQC presentations")
    return presentations


def scrape_pqc_news():
    """Scrape Post-Quantum Cryptography news from NIST."""
    
    url = 'https://www.nist.gov/news-events/news?key=quantum&topic-op=or'
    
    news = []
    session = requests.Session()
    
    def _fetch_page(url):
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")
    
    print(f"Scraping PQC news from {url}")
    
    try:
        soup = _fetch_page(url)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return news
    
    # Try multiple selectors for different page layouts
    items = soup.select(".search-result")
    if not items:
        items = soup.select("article")
    if not items:
        items = soup.select(".news-item")
    if not items:
        items = soup.select("[data-news]")
    
    print(f"DEBUG: Found {len(items)} news items")
    
    for item in items:
        # Try different selectors for title
        title_link = item.select_one("h3 a")
        if not title_link:
            title_link = item.select_one("h4 a")
        if not title_link:
            title_link = item.select_one("a[data-title]")
        if not title_link:
            title_link = item.select_one("a")
        
        if not title_link:
            continue
        
        title = clean_text(title_link.get_text(strip=True))
        if not title:
            continue
            
        link = title_link.get("href", "")
        if link and not link.startswith("http"):
            link = f"https://www.nist.gov{link}"
        
        # Try different selectors for summary
        summary_el = item.select_one(".summary")
        if not summary_el:
            summary_el = item.select_one(".description")
        if not summary_el:
            summary_el = item.select_one("p")
        
        summary = ""
        if summary_el:
            summary = clean_text(summary_el.get_text(strip=True))
        
        # Try different selectors for date
        date_el = item.select_one(".date")
        if not date_el:
            date_el = item.select_one("time")
        if not date_el:
            date_el = item.select_one("[class*='date']")
        publish_date = clean_text(date_el.get_text(strip=True)) if date_el else ""
        
        if title:  # Only add if we have at least a title
            # Convert formatted date to ISO for sorting
            publish_date_raw = ""
            if publish_date:
                try:
                    # Parse "Month Day, Year" format to ISO
                    date_obj = datetime.strptime(publish_date, '%B %d, %Y')
                    publish_date_raw = date_obj.strftime('%Y-%m-%d')
                except Exception:
                    # If parsing fails, use original
                    publish_date_raw = publish_date
            
            news.append({
                "title": title,
                "summary": summary,
                "publish_date": publish_date,
                "publish_date_raw": publish_date_raw,
                "link": link,
                "resource_type": "Post-Quantum Cryptography News"
            })
    
    print(f"DEBUG: Retrieved {len(news)} PQC news items")
    return news


def scrape_all_pqc_data():
    """Scrape all Post-Quantum Cryptography data from NIST sources."""
    
    print("=" * 50)
    print("Starting Post-Quantum Cryptography data scraping...")
    print("=" * 50)
    
    # Scrape all PQC data
    publications = scrape_pqc_publications()
    presentations = scrape_pqc_presentations()
    news = scrape_pqc_news()
    
    print("=" * 50)
    print(f"PQC Scraping complete!")
    print(f"Publications: {len(publications)}")
    print(f"Presentations: {len(presentations)}")
    print(f"News: {len(news)}")
    print("=" * 50)
    
    return {
        'publications': publications,
        'presentations': presentations,
        'news': news
    }


def main():
    """Scrape all Post-Quantum Cryptography data from NIST sources."""
    all_pqc_data = scrape_all_pqc_data()
    
    # Output or process the collected data as needed
    print(f"Scraped {len(all_pqc_data['publications'])} PQC publications")
    print(f"Scraped {len(all_pqc_data['presentations'])} PQC presentations")
    print(f"Scraped {len(all_pqc_data['news'])} PQC news items")
    
    for pub in all_pqc_data['publications'][:3]:  # Print first 3 as example
        print(f"Publication: {pub['document_name']}")
    
    for pres in all_pqc_data['presentations'][:3]:  # Print first 3 as example
        print(f"Presentation: {pres['document_name']}")
    
    for article in all_pqc_data['news'][:3]:  # Print first 3 as example
        print(f"News: {article['title']}")


if __name__ == "__main__":
    main()