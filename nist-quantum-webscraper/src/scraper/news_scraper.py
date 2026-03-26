import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor


def format_date(date_str: str) -> str:
    """Convert ISO format date to written out format (e.g., January 15, 2026)."""
    if not date_str:
        return ""
    
    try:
        # Parse the ISO format date
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        # Format as "Month Day, Year"
        return date_obj.strftime('%B %d, %Y')
    except Exception as e:
        print(f"Error formatting date '{date_str}': {e}")
        return date_str


def generate_news_summary(title: str, summary: str) -> str:
    """Generate or enhance a news summary.
    
    Uses the extracted summary if available, otherwise creates one from the title.
    """
    if summary:
        return summary
    
    # If no summary extracted, create a basic one from title
    if len(title) > 50:
        return title[:80] + "..."
    
    return f"News article about {title.lower()}."


def parse_nist_date(date_str: str):
    """Parse common NIST date strings and return datetime when possible."""
    if not date_str:
        return None

    cleaned = ' '.join((date_str or '').strip().split())
    cleaned = re.sub(r'(\d)(st|nd|rd|th)', r'\1', cleaned)

    for fmt in (
        '%B %d, %Y',
        '%B %d %Y',
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
    ):
        try:
            return datetime.strptime(cleaned, fmt)
        except Exception:
            continue

    try:
        return datetime.fromisoformat(cleaned.replace('Z', '+00:00'))
    except Exception:
        return None


def to_display_and_raw(date_str: str):
    """Return (display_date, raw_date) from a scraped date value."""
    parsed = parse_nist_date(date_str)
    if not parsed:
        return '', ''

    parsed = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    return parsed.strftime('%B %d, %Y'), parsed.strftime('%Y-%m-%d')


def extract_article_dates(article_soup, fallback_publish_raw: str):
    """Extract published and last-edited dates from an article page.

    Returns
    -------
    tuple[str, str, str, str]
        (publish_date, publish_date_raw, last_edited_date, last_edited_date_raw)
    """
    publish_raw = (fallback_publish_raw or '').strip()

    def _content_for_selectors(selectors):
        for selector in selectors:
            node = article_soup.select_one(selector)
            if not node:
                continue

            value = (node.get('content') or node.get('datetime') or node.get_text(' ', strip=True) or '').strip()
            if value:
                return value
        return ''

    publish_candidate = _content_for_selectors([
        'meta[property="article:published_time"]',
        'meta[property="article:published"]',
        'meta[name="publish_date"]',
        'meta[name="date"]',
        '[itemprop="datePublished"]',
    ])
    if publish_candidate:
        _, publish_candidate_raw = to_display_and_raw(publish_candidate)
        if publish_candidate_raw:
            publish_raw = publish_candidate_raw

    modified_candidate = _content_for_selectors([
        'meta[property="article:modified_time"]',
        'meta[property="og:updated_time"]',
        'meta[name="last-updated"]',
        'meta[name="last_modified"]',
        '[itemprop="dateModified"]',
    ])

    if not modified_candidate:
        for time_node in article_soup.select('time[datetime]'):
            label = (time_node.get_text(' ', strip=True) or '').lower()
            if any(token in label for token in ('updated', 'edited', 'modified', 'last')):
                modified_candidate = (time_node.get('datetime') or '').strip()
                if modified_candidate:
                    break

    publish_date, publish_date_raw = to_display_and_raw(publish_raw)
    last_edited_date, last_edited_date_raw = to_display_and_raw(modified_candidate)
    return publish_date, publish_date_raw, last_edited_date, last_edited_date_raw


def scrape_news():
    # start with first page url; subsequent pages will be discovered via 'rel=next'
    # Use quantum information science topic area for QIS news collection
    base_url = "https://www.nist.gov/news-events/news/search?key=quantum&topic-op=or&topic-area-fieldset%5B%5D=249281"
    session = requests.Session()

    news_data = []
    next_url = base_url
    while next_url:
        response = session.get(next_url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')

        articles = soup.find_all('article')
        if not articles:
            break

        page_entries = []
        for article in articles:
            # Safely extract title
            title_el = article.find('h3')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
        
            # Safely extract link
            link_el = article.find('a')
            if not link_el or not link_el.get('href'):
                continue
            link = link_el['href']
            if not link.startswith('http'):
                link = f"https://www.nist.gov{link}"
        
            # Safely extract date
            date_el = article.find('time')
            date = date_el['datetime'] if date_el else ""

            page_entries.append({
                'title': title,
                'link': link,
                'date': date,
            })

        def _build_news_item(entry):
            title = entry['title']
            link = entry['link']
            date = entry['date']

            summary = ""
            article_soup = None
            try:
                article_response = session.get(link, timeout=5)
                article_soup = BeautifulSoup(article_response.content, 'html.parser')

                meta = article_soup.select_one('meta[name="description"]')
                if meta and meta.get('content'):
                    summary = meta['content'].strip()

                if not summary:
                    content = article_soup.select_one('main') or article_soup.select_one('[role="main"]') or article_soup.select_one('.field-type-text-long')
                    if content:
                        p = content.find('p')
                        if p:
                            summary = p.get_text(strip=True)
            except Exception:
                pass

            publish_date = format_date(date)
            publish_date_raw = date
            last_edited_date = ""
            last_edited_date_raw = ""

            if article_soup is not None:
                extracted_publish, extracted_publish_raw, extracted_last_edited, extracted_last_edited_raw = extract_article_dates(
                    article_soup,
                    date,
                )
                if extracted_publish:
                    publish_date = extracted_publish
                if extracted_publish_raw:
                    publish_date_raw = extracted_publish_raw
                if extracted_last_edited:
                    last_edited_date = extracted_last_edited
                if extracted_last_edited_raw:
                    last_edited_date_raw = extracted_last_edited_raw

            return {
                'title': title,
                'link': link,
                'publish_date': publish_date,
                'publish_date_raw': publish_date_raw,
                'last_edited_date': last_edited_date,
                'last_edited_date_raw': last_edited_date_raw,
                'summary': generate_news_summary(title, summary),
            }

        if page_entries:
            max_workers = min(8, len(page_entries)) or 1
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                news_data.extend(executor.map(_build_news_item, page_entries))
        # find next page link
        next_link = soup.select_one('a[rel="next"]')
        if next_link and next_link.get('href'):
            from urllib.parse import urljoin
            next_url = urljoin(next_url, next_link.get('href'))
        else:
            next_url = None
    return news_data
