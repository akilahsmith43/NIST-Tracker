import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
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


def parse_nist_date(date_str: str) -> datetime:
    """Parse various NIST date formats and return datetime object.
    
    Supports multiple date formats used by NIST:
    - "Month Day, Year" (e.g., "March 19, 2026")
    - "Month Day, Year" with ordinal suffixes (e.g., "March 19th, 2026")
    - "Month Year" (e.g., "March 2026")
    - "Day Month Year" (e.g., "19 March 2026")
    - ISO format "YYYY-MM-DD" (e.g., "2026-03-19")
    - Numeric formats like "MM/DD/YYYY" or "DD/MM/YYYY"
    - "Month Day Year" (e.g., "March 19 2026")
    
    Returns None if date cannot be parsed.
    """
    if not date_str:
        return None
    
    # Clean and normalize the date string
    date_str = clean_text(date_str)
    
    # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
    date_str = re.sub(r'(\d)(st|nd|rd|th)', r'\1', date_str)
    
    # Define multiple date format patterns to try
    date_formats = [
        '%B %d, %Y',      # March 19, 2026
        '%B %d %Y',       # March 19 2026
        '%B %Y',          # March 2026
        '%d %B %Y',       # 19 March 2026
        '%Y-%m-%d',       # 2026-03-19
        '%m/%d/%Y',       # 03/19/2026
        '%d/%m/%Y',       # 19/03/2026
        '%B %d,%Y',       # March 19,2026 (no space after comma)
    ]
    
    # Try each format
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # If no format worked, return None
    return None


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
            'url': 'https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Final&series-lg=FIPS%2CSP%2CIR%2CCSWP%2CTN%2CVTS%2CAI%2CGCR%2CProject+Description&topics-lg=27651%7Cpost-quantum+cryptography&topicsMatch-lg=ANY&controlsMatch-lg=ANY',
            'category': 'Final Publications'
        },
        {
            'url': 'https://csrc.nist.gov/publications/search?sortBy-lg=relevance&viewMode-lg=brief&ipp-lg=50&topics-lg=27651%7cpost-quantum+cryptography&topicsMatch-lg=ANY&controlsMatch-lg=ANY&page=2',
            'category': 'Drafts Open for Comment'
        },
        {
            'url': 'https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Draft&topics-lg=27651%7Cpost-quantum+cryptography&topicsMatch-lg=ANY&controlsMatch-lg=ANY',
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
            items = soup.select("tr[id^='result-']")
            if not items:
                items = soup.select(".search-list-item")
            if not items:
                items = soup.select("article")
            if not items:
                items = soup.select(".publication-item")
            if not items:
                items = soup.select("[data-publication]")
            
            print(f"DEBUG: Found {len(items)} items on {base_url}")
            
            for item in items:
                # For table rows, look for the title link in the appropriate cell
                title_link = item.select_one("td a")
                if not title_link:
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
                
                # For table rows, look for series in the appropriate cell
                series_el = item.select_one("td[id*='pub-series']")
                if not series_el:
                    series_el = item.select_one(".sub-title strong")
                if not series_el:
                    series_el = item.select_one(".series")
                if not series_el:
                    series_el = item.select_one("[class*='series']")
                series = clean_text(series_el.get_text(strip=True)) if series_el else ""
                
                # For table rows, look for date in the appropriate cell
                date_el = item.select_one("td[id*='pub-release-date']")
                if not date_el:
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
                    # Parse the publication date using enhanced date parsing
                    parsed_date = parse_nist_date(release_date)
                    
                    # Calculate cutoff date (365 days ago from today)
                    cutoff_date = datetime.now() - timedelta(days=365)
                    
                    # Filter publications: only include those within the past year
                    if parsed_date is None:
                        print(f"DEBUG: Excluding publication '{name}' - could not parse date: '{release_date}'")
                        continue
                    elif parsed_date < cutoff_date:
                        print(f"DEBUG: Excluding publication '{name}' - too old: {parsed_date.strftime('%Y-%m-%d')} (cutoff: {cutoff_date.strftime('%Y-%m-%d')})")
                        continue
                    else:
                        print(f"DEBUG: Including publication '{name}' - date: {parsed_date.strftime('%Y-%m-%d')} (within past year)")
                    
                    # Convert formatted date to ISO for sorting
                    release_date_raw = parsed_date.strftime('%Y-%m-%d') if parsed_date else ""
                    
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
    
    # Calculate cutoff date (365 days ago from today)
    cutoff_date = datetime.now() - timedelta(days=365)
    
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
            # Parse the presentation date using enhanced date parsing
            parsed_date = parse_nist_date(release_date)
            
            # Filter presentations: only include those within the past year
            if parsed_date is None:
                print(f"DEBUG: Including presentation '{name}' - could not parse date: '{release_date}' (defaulting to include)")
                presentations.append({
                    "document_name": name,
                    "series": series,
                    "status": status,
                    "resource_type": "Post-Quantum Cryptography Presentation",
                    "link": link,
                    "release_date": release_date
                })
            elif parsed_date < cutoff_date:
                print(f"DEBUG: Excluding presentation '{name}' - too old: {parsed_date.strftime('%Y-%m-%d')} (cutoff: {cutoff_date.strftime('%Y-%m-%d')})")
            else:
                print(f"DEBUG: Including presentation '{name}' - date: {parsed_date.strftime('%Y-%m-%d')} (within past year)")
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
    
    # Use the updated PQC-specific NIST news search URL.
    # This link includes topic-area-fieldset=248746 for PQC and uses the same day-based windowing logic below.
    url = 'https://www.nist.gov/news-events/news/search?key=quantum&topic-op=or&topic-area-fieldset%5B%5D=248746'
    
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
    
    # Calculate cutoff date (365 days ago from today)
    cutoff_date = datetime.now() - timedelta(days=365)
    
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
            # Parse the news date using enhanced date parsing
            parsed_date = parse_nist_date(publish_date)
            
            # Determine publish_date_raw consistently
            publish_date_raw = ""
            if publish_date:
                try:
                    date_obj = datetime.strptime(publish_date, '%B %d, %Y')
                    publish_date_raw = date_obj.strftime('%Y-%m-%d')
                except Exception:
                    publish_date_raw = publish_date

            if parsed_date is None:
                print(f"DEBUG: Including news '{title}' - could not parse date: '{publish_date}' (defaulting to include)")
            elif parsed_date < cutoff_date:
                print(f"DEBUG: News '{title}' is older than 1 year ({parsed_date.strftime('%Y-%m-%d')} < {cutoff_date.strftime('%Y-%m-%d')}), including for dashboard fallback")
            else:
                print(f"DEBUG: Including news '{title}' - date: {parsed_date.strftime('%Y-%m-%d')} (within past year)")

            # Keep all news items; dashboard filtering applies strict 1-year window with fallback
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
    
    # Save data to dashboard storage
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.data.data_storage import DataStorage
    storage = DataStorage()
    
    print(f"DEBUG: Saving {len(all_pqc_data['publications'])} PQC publications to dashboard storage")
    print(f"DEBUG: First publication: {all_pqc_data['publications'][0]['document_name'] if all_pqc_data['publications'] else 'None'}")
    
    storage.save_pqc_data_to_dashboard(all_pqc_data)
    storage.save_pqc_data(all_pqc_data)
    
    # Add notifications for new items
    new_items = storage.get_new_pqc_items(all_pqc_data)
    
    # Add notifications for new publications
    for pub in new_items['publications']:
        storage.add_notification('publication', pub)
        print(f"Added notification for publication: {pub['document_name']}")
    
    # Add notifications for new presentations
    for pres in new_items['presentations']:
        storage.add_notification('presentation', pres)
        print(f"Added notification for presentation: {pres['document_name']}")
    
    # Add notifications for new news
    for news in new_items['news']:
        storage.add_notification('news', news)
        print(f"Added notification for news: {news['title']}")
    
    # Get and display scrape session info
    scrape_info = storage.get_last_scrape_info()
    print(f"Last scrape: {scrape_info['last_scrape']}")
    print(f"Total notifications: {scrape_info['scrape_count']}")
    print(f"New items this session: {scrape_info['new_items_this_session']}")
    
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
