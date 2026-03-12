import requests
from bs4 import BeautifulSoup
from datetime import datetime

def parse_date(date_str):
    """Parse various date formats and return datetime object for sorting.
    Handles formats like '1/29/2026', 'March 10, 2026', 'January 2026', etc.
    Returns datetime object, or None if unparseable."""
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    
    # Try MM/DD/YYYY format first (e.g., "1/29/2026")
    try:
        return datetime.strptime(date_str, '%m/%d/%Y')
    except ValueError:
        pass
    
    # Try "Month DD, YYYY" format (e.g., "March 10, 2026")
    try:
        return datetime.strptime(date_str, '%B %d, %Y')
    except ValueError:
        pass
    
    # Try "Month DD YYYY" format without comma
    try:
        return datetime.strptime(date_str, '%B %d %Y')
    except ValueError:
        pass
    
    # Try just "Month YYYY" format (e.g., "January 2026")
    try:
        return datetime.strptime(date_str, '%B %Y')
    except ValueError:
        pass
    
    return None

def scrape_publications():
    # URLs for NIST CSRC publications filtered for quantum information science
    urls = [
        'https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Final&series-lg=FIPS%2CSP%2CIR%2CCSWP%2CTN%2CVTS%2CAI%2CGCR%2CProject+Description&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY',
        'https://csrc.nist.gov/publications/search?sortBy-lg=relevance&viewMode-lg=brief&ipp-lg=50&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY',
        'https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Draft&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY',
        'https://www.nist.gov/publications/search/topic/249281'
    ]
    
    all_publications = []
    seen_items = set()  # Track (title + link) to deduplicate within this scrape
    
    for url in urls:
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # the CSRC pages use table rows that have ids like result-1
            if 'csrc.nist.gov' in url:
                rows = soup.select('tr[id^="result-"]')
                for row in rows:
                    link_elem = row.select_one('a[id^="pub-title-link-"]')
                    if not link_elem:
                        continue

                    series_elem = row.select_one('td[id^="pub-series-"]')
                    number_elem = row.select_one('td[id^="pub-number-"]')
                    status_elem = row.select_one('td[id^="pub-status-"]')
                    date_elem = row.select_one('td[id^="pub-release-date-"]')

                    title = link_elem.get_text(strip=True)
                    link = link_elem['href'] if link_elem.get('href') else ''
                    if link and not link.startswith('http'):
                        link = f"https://csrc.nist.gov{link}"
                    
                    # Check for duplicates within this scrape run
                    item_key = (title + link).lower()
                    if item_key in seen_items:
                        continue
                    seen_items.add(item_key)

                    publication = {
                        'document_name': title,
                        'document_number': number_elem.get_text(strip=True) if number_elem else '',
                        'series': series_elem.get_text(strip=True) if series_elem else '',
                        'status': status_elem.get_text(strip=True) if status_elem else ('Final' if 'final-pubs' in url else 'Draft'),
                        'release_date': date_elem.get_text(strip=True) if date_elem else '',
                        'resource_type': 'Publication',
                        'link': link
                    }
                    all_publications.append(publication)
            else:
                # NIST publications search page with teaser articles
                teasers = soup.select('article.nist-teaser')
                count = 0
                for teaser in teasers:
                    if count >= 20:
                        break
                    title_elem = teaser.select_one('h3.nist-teaser__title a')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    if link and not link.startswith('http'):
                        link = f"https://www.nist.gov{link}"
                    
                    # Check for duplicates within this scrape run
                    item_key = (title + link).lower()
                    if item_key in seen_items:
                        continue
                    seen_items.add(item_key)

                    # grab a short description/explanation if available
                    summary_elem = teaser.select_one('.nist-teaser__content')
                    summary = summary_elem.get_text(strip=True) if summary_elem else ''

                    # optional date field
                    date_elem = teaser.select_one('.nist-teaser__date')
                    date = date_elem.get_text(strip=True) if date_elem else ''

                    all_publications.append({
                        'document_name': title,
                        'document_number': '',
                        'series': '',
                        'status': '',
                        'release_date': date,
                        'resource_type': 'Publication',
                        'link': link,
                        'summary': summary
                    })
                    count += 1
        except Exception as e:
            pass  # Silently skip any URLs that fail or have no content
    
    # Sort by release_date (newest first), putting unparseable dates at the end
    def sort_key(item):
        date_obj = parse_date(item.get('release_date', ''))
        if date_obj is None:
            return (False, None)  # Unparseable dates go to end
        return (True, -date_obj.timestamp())  # Negate timestamp for descending order
    
    all_publications.sort(key=sort_key)
    
    return all_publications

