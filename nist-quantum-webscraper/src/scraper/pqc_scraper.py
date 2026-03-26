import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor


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
    
    # Try ISO datetime values such as 2025-08-29T11:34-04:00
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        pass

    # If no format worked, return None
    return None


def _extract_meta_date_value(soup: BeautifulSoup, selectors: List[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        value = (node.get('content') or node.get('datetime') or node.get_text(' ', strip=True) or '').strip()
        if value:
            return value
    return ""


def _extract_news_dates_from_article(session: requests.Session, link: str, fallback_publish_raw: str) -> Dict[str, str]:
    """Extract published and last-edited dates from article metadata."""
    result = {
        'publish_date': '',
        'publish_date_raw': fallback_publish_raw or '',
        'last_edited_date': '',
        'last_edited_date_raw': '',
    }

    if not link:
        if result['publish_date_raw']:
            parsed = parse_nist_date(result['publish_date_raw'])
            if parsed:
                result['publish_date'] = parsed.strftime('%B %d, %Y')
        return result

    try:
        resp = session.get(link, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
    except Exception:
        if result['publish_date_raw']:
            parsed = parse_nist_date(result['publish_date_raw'])
            if parsed:
                result['publish_date'] = parsed.strftime('%B %d, %Y')
        return result

    published_candidate = _extract_meta_date_value(
        soup,
        [
            'meta[property="article:published_time"]',
            'meta[property="article:published"]',
            'meta[name="publish_date"]',
            'meta[name="date"]',
            '[itemprop="datePublished"]',
        ],
    )

    modified_candidate = _extract_meta_date_value(
        soup,
        [
            'meta[property="article:modified_time"]',
            'meta[property="og:updated_time"]',
            'meta[name="last-updated"]',
            'meta[name="last_modified"]',
            '[itemprop="dateModified"]',
        ],
    )

    if not modified_candidate:
        for time_node in soup.select('time[datetime]'):
            label = clean_text(time_node.get_text(' ', strip=True)).lower()
            if any(token in label for token in ('updated', 'edited', 'modified', 'last')):
                modified_candidate = (time_node.get('datetime') or '').strip()
                if modified_candidate:
                    break

    publish_raw_candidate = published_candidate or result['publish_date_raw']
    if publish_raw_candidate:
        parsed_publish = parse_nist_date(publish_raw_candidate)
        if parsed_publish:
            result['publish_date_raw'] = parsed_publish.strftime('%Y-%m-%d')
            result['publish_date'] = parsed_publish.strftime('%B %d, %Y')

    if modified_candidate:
        parsed_modified = parse_nist_date(modified_candidate)
        if parsed_modified:
            result['last_edited_date_raw'] = parsed_modified.strftime('%Y-%m-%d')
            result['last_edited_date'] = parsed_modified.strftime('%B %d, %Y')

    return result


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
    
    # URL for NIST CSRC presentations with post-quantum cryptography filter
    base_url = 'https://csrc.nist.gov/search?ipp=25&sortBy=relevance&showOnly=presentations&topicsMatch=ANY&topics=27651%7cpost-quantum+cryptography'
    presentations = []
    cutoff_date = datetime.now() - timedelta(days=365)
    
    session = requests.Session()
    
    def _fetch_page(url):
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")
    
    print(f"Scraping PQC presentations from {base_url}")
    
    stale_pages = 0

    # Try multiple pages to find recent presentations.
    for page in range(50):
        if page == 0:
            url = base_url
        else:
            url = f"{base_url}&page={page}"
        
        print(f"Checking page {page + 1}: {url}")
        
        try:
            soup = _fetch_page(url)
            
            # Check if there are any results on this page
            items = soup.select('.search-list-item')
            print(f"Found {len(items)} items on page {page + 1}")
            
            if not items:
                print(f"No more results found after page {page + 1}")
                break  # No more results

            added_this_page = 0
            
            # Find presentation items
            for item in items:
                # Get the title link
                title_link = item.select_one('a[id^="title-link-"]')
                if not title_link:
                    continue
                
                # Extract presentation details
                presentation = {
                    'document_name': clean_text(title_link.get_text(strip=True)),
                    'document_number': '',  # Not available in search results
                    'series': 'Presentation',
                    'status': 'Available',
                    'release_date': '',  # will fill below if available
                    'resource_type': 'Post-Quantum Cryptography Presentation',
                    'link': title_link['href'] if title_link.get('href') else ''
                }
                
                # extract date if provided
                date_el = item.select_one('strong[id^="date-container-"]')
                if date_el:
                    presentation['release_date'] = clean_text(date_el.get_text(strip=True))
                    
                    # Try to parse the date to check if it's within the past year
                    try:
                        # Try different date formats
                        date_str = presentation['release_date']
                        parsed_date = None
                        
                        # Try common date formats
                        for fmt in ['%B %d, %Y', '%b %d, %Y', '%Y-%m-%d', '%B %Y', '%b %Y']:
                            try:
                                parsed_date = datetime.strptime(date_str, fmt)
                                break
                            except ValueError:
                                continue
                        
                        if parsed_date and parsed_date >= cutoff_date:
                            # Make link absolute if needed
                            if presentation['link'] and not presentation['link'].startswith('http'):
                                presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
                            presentations.append(presentation)
                            added_this_page += 1
                    except Exception:
                        # If we can't parse the date, include it anyway
                        if presentation['link'] and not presentation['link'].startswith('http'):
                            presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
                        presentations.append(presentation)
                        added_this_page += 1
                else:
                    # If no date available, include the presentation
                    if presentation['link'] and not presentation['link'].startswith('http'):
                        presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
                    presentations.append(presentation)

                    added_this_page += 1

            print(f"  Page {page + 1} added: {added_this_page}, total presentations so far: {len(presentations)}")

            if added_this_page == 0:
                stale_pages += 1
            else:
                stale_pages = 0

            if stale_pages >= 3:
                print(f"Stopping at page {page + 1} - no in-range additions for 3 consecutive pages")
                break
                
        except Exception as e:
            print(f"Error scraping page {page + 1}: {e}")
            continue
    
    # Remove duplicates based on document_name and link
    seen = set()
    unique_presentations = []
    for p in presentations:
        key = (p['document_name'], p['link'])
        if key not in seen:
            seen.add(key)
            unique_presentations.append(p)
    
    print(f"DEBUG: Retrieved {len(unique_presentations)} PQC presentations")
    return unique_presentations


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

            news.append({
                "title": title,
                "summary": summary,
                "publish_date": publish_date,
                "publish_date_raw": publish_date_raw,
                "last_edited_date": "",
                "last_edited_date_raw": "",
                "link": link,
                "resource_type": "Post-Quantum Cryptography News"
            })

    # Enrich article publish/edited dates concurrently to reduce end-to-end scrape time.
    def _enrich_news_item(item):
        link = item.get('link', '')
        publish_date_raw = item.get('publish_date_raw', '')
        article_dates = _extract_news_dates_from_article(session, link, publish_date_raw)
        if article_dates.get('publish_date'):
            item['publish_date'] = article_dates['publish_date']
        if article_dates.get('publish_date_raw'):
            item['publish_date_raw'] = article_dates['publish_date_raw']
        item['last_edited_date'] = article_dates.get('last_edited_date', '')
        item['last_edited_date_raw'] = article_dates.get('last_edited_date_raw', '')
        return item

    if news:
        max_workers = min(8, len(news)) or 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            news = list(executor.map(_enrich_news_item, news))
    
    print(f"DEBUG: Retrieved {len(news)} PQC news items")
    return news


def scrape_all_pqc_data():
    """Scrape all Post-Quantum Cryptography data from NIST sources."""
    
    print("=" * 50)
    print("Starting Post-Quantum Cryptography data scraping...")
    print("=" * 50)
    
    # Scrape independent sections concurrently.
    with ThreadPoolExecutor(max_workers=3) as executor:
        publications_future = executor.submit(scrape_pqc_publications)
        presentations_future = executor.submit(scrape_pqc_presentations)
        news_future = executor.submit(scrape_pqc_news)

        publications = publications_future.result()
        presentations = presentations_future.result()
        news = news_future.result()
    
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
        print(f"{pres['document_name']}")
    
    for article in all_pqc_data['news'][:3]:  # Print first 3 as example
        print(f"News: {article['title']}")


if __name__ == "__main__":
    main()
