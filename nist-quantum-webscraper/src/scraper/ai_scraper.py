import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace('\u200b', '')
    text = text.replace('\u200c', '')
    text = text.replace('\u200d', '')
    text = text.replace('\ufeff', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_nist_date(date_str: str) -> datetime:
    if not date_str:
        return None
    date_str = clean_text(date_str)
    date_str = re.sub(r'(\d)(st|nd|rd|th)', r'\1', date_str)
    date_formats = [
        '%B %d, %Y',
        '%B %d %Y',
        '%B %Y',
        '%d %B %Y',
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%B %d,%Y',
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            continue
    # Try ISO with time
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        pass
    return None


def format_date_for_display(date_obj: datetime) -> str:
    """Convert datetime object to 'Month, DD, YYYY' format"""
    if not date_obj:
        return ""
    return date_obj.strftime('%B %d, %Y')


def _parse_link(href: str, base: str = "") -> str:
    if not href:
        return ""
    href = href.strip()
    if href.startswith('http'):
        return href
    if href.startswith('/'):
        # For General Publications category, use www.nist.gov instead of csrc.nist.gov
        if base == "www.nist.gov":
            return f"https://{base}{href}"
        else:
            return f"https://{base}{href}" if base else f"https://csrc.nist.gov{href}"
    return href


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
    """Read article metadata and return published/last-edited date fields."""
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
                result['publish_date'] = format_date_for_display(parsed)
        return result

    try:
        resp = session.get(link, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
    except Exception:
        if result['publish_date_raw']:
            parsed = parse_nist_date(result['publish_date_raw'])
            if parsed:
                result['publish_date'] = format_date_for_display(parsed)
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
            result['publish_date'] = format_date_for_display(parsed_publish)

    if modified_candidate:
        parsed_modified = parse_nist_date(modified_candidate)
        if parsed_modified:
            result['last_edited_date_raw'] = parsed_modified.strftime('%Y-%m-%d')
            result['last_edited_date'] = format_date_for_display(parsed_modified)

    return result


def scrape_ai_publications() -> List[Dict[str, Any]]:
    urls = [
        {
            'url': 'https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Final&series-lg=FIPS%2CSP%2CIR%2CCSWP%2CTN%2CVTS%2CAI%2CGCR%2CProject+Description&topics-lg=27491%7Cartificial+intelligence&topicsMatch-lg=ANY&controlsMatch-lg=ANY',
            'category': 'Final Publications'
        },
        {
            'url': 'https://csrc.nist.gov/publications/search?sortBy-lg=relevance&viewMode-lg=brief&ipp-lg=50&topics-lg=27491%7Cartificial+intelligence&topicsMatch-lg=ANY&controlsMatch-lg=ANY',
            'category': 'Drafts Open for Comment'
        },
        {
            'url': 'https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Draft&topics-lg=27491%7Cartificial+intelligence&topicsMatch-lg=ANY&controlsMatch-lg=ANY',
            'category': 'Drafts'
        },
        {
            'url': 'https://www.nist.gov/publications/search?k=&t=&a=&ps=All&ta%5B%5D=2753736&n=&d%5Bmin%5D=&d%5Bmax%5D=',
            'category': 'General Publications'
        }
    ]
    publications = []
    session = requests.Session()

    def _fetch(url):
        r = session.get(url, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.content, 'html.parser')

    for info in urls:
        url = info['url']
        cat = info['category']
        base_domain = 'www.nist.gov' if 'www.nist.gov' in url else 'csrc.nist.gov'
        print(f"Scraping AI publications {cat}: {url}")
        try:
            soup = _fetch(url)
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            continue

        items = soup.select("tr[id^='result-']")
        if not items:
            items = soup.select(".search-list-item")
        if not items:
            items = soup.select("article")
        if not items:
            items = soup.select(".publication-item")
        if not items:
            items = soup.select("[data-publication]")

        for item in items:
            title_el = item.select_one("h4.search-results-title a") or item.select_one("h3 a") or item.select_one("a[data-title]") or item.select_one("a")
            if not title_el:
                continue
            name = clean_text(title_el.get_text(strip=True))
            if not name:
                continue
            link = _parse_link(title_el.get('href', ''), base=base_domain)

            series = ""
            for sel in ["td[id*='pub-series']", ".sub-title strong", ".series", "[class*='series']"]:
                s = item.select_one(sel)
                if s:
                    series = clean_text(s.get_text(strip=True))
                    break

            release_date = ""
            for sel in ["td[id*='pub-release-date']", "strong[id^='date-container-']", "time", ".date", "[class*='date']"]:
                d = item.select_one(sel)
                if d:
                    release_date = clean_text(d.get_text(strip=True))
                    break

            summary = ""
            for sel in [".summary", ".description", "p"]:
                p = item.select_one(sel)
                if p:
                    summary = clean_text(p.get_text(strip=True))
                    break

            if not name:
                continue

            parsed = parse_nist_date(release_date)
            if parsed:
                release_date_raw = parsed.strftime('%Y-%m-%d')
                # Convert to consistent display format
                release_date = format_date_for_display(parsed)
            else:
                release_date_raw = ""

            publications.append({
                "document_name": name,
                "document_number": "",
                "series": series,
                "release_date": release_date,
                "release_date_raw": release_date_raw,
                "resource_type": "Artificial Intelligence Publication",
                "link": link,
                "summary": summary,
                "category": cat
            })

    print(f"DEBUG: Retrieved {len(publications)} AI publications")
    return publications


def scrape_ai_presentations() -> List[Dict[str, Any]]:
    url = 'https://csrc.nist.gov/search?ipp=25&sortBy=relevance&showOnly=presentations&topicsMatch=ANY&topics=27491%7cartificial+intelligence'
    print(f"Scraping AI presentations from {url}")
    presentations = []
    session = requests.Session()

    def _fetch(url):
        r = session.get(url, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.content, 'html.parser')

    try:
        soup = _fetch(url)
    except Exception as e:
        print(f"Error scraping AI presentations: {e}")
        return presentations

    items = soup.select(".search-list-item")
    if not items:
        items = soup.select("article")
    if not items:
        items = soup.select(".presentation-item")
    if not items:
        items = soup.select("[data-presentation]")

    cutoff = datetime.now() - timedelta(days=365)
    for item in items:
        title_el = item.select_one("h4.search-results-title a") or item.select_one("h3 a") or item.select_one("a[data-title]") or item.select_one("a")
        if not title_el:
            continue
        name = clean_text(title_el.get_text(strip=True))
        if not name:
            continue
        link = _parse_link(title_el.get('href', ''), base='csrc.nist.gov')

        series = ""
        for sel in [".sub-title strong", ".series", "[class*='series']"]:
            s = item.select_one(sel)
            if s:
                series = clean_text(s.get_text(strip=True))
                break

        release_date = ""
        for sel in ["strong[id^='date-container-']", "time", ".date", "[class*='date']"]:
            d = item.select_one(sel)
            if d:
                release_date = clean_text(d.get_text(strip=True))
                break

        status = ""
        for sel in [".status", "[class*='status']"]:
            s = item.select_one(sel)
            if s:
                status = clean_text(s.get_text(strip=True))
                break

        parsed = parse_nist_date(release_date)
        if parsed and parsed < cutoff:
            continue
        
        # Convert to consistent display format
        if parsed:
            release_date = format_date_for_display(parsed)

        presentations.append({
            "document_name": name,
            "series": series,
            "status": status,
            "resource_type": "Artificial Intelligence Presentation",
            "link": link,
            "release_date": release_date
        })

    print(f"DEBUG: Retrieved {len(presentations)} AI presentations")
    return presentations


def scrape_ai_news() -> List[Dict[str, Any]]:
    url = 'https://www.nist.gov/news-events/news/search?key=&topic-op=or&topic-area-fieldset%5B%5D=2753736'
    print(f"Scraping AI news from {url}")
    news = []
    session = requests.Session()

    def _fetch(url):
        r = session.get(url, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.content, 'html.parser')

    try:
        soup = _fetch(url)
    except Exception as e:
        print(f"Error scraping AI news: {e}")
        return news

    items = soup.select(".search-result")
    if not items:
        items = soup.select("article")
    if not items:
        items = soup.select(".news-item")
    if not items:
        items = soup.select("[data-news]")

    cutoff = datetime.now() - timedelta(days=365)
    for item in items:
        title_el = item.select_one("h3 a") or item.select_one("h4 a") or item.select_one("a[data-title]") or item.select_one("a")
        if not title_el:
            continue
        title = clean_text(title_el.get_text(strip=True))
        if not title:
            continue
        link = _parse_link(title_el.get('href', ''), base='www.nist.gov')

        summary = ""
        for sel in [".summary", ".description", "p"]:
            s = item.select_one(sel)
            if s:
                summary = clean_text(s.get_text(strip=True))
                break

        publish_date = ""
        for sel in [".date", "time", "[class*='date']"]:
            d = item.select_one(sel)
            if d:
                publish_date = clean_text(d.get_text(strip=True))
                break

        parsed = parse_nist_date(publish_date)
        if parsed and parsed < cutoff:
            continue

        if parsed:
            publish_date_raw = parsed.strftime('%Y-%m-%d')
            # Convert to consistent display format
            publish_date = format_date_for_display(parsed)
        else:
            publish_date_raw = ""

        article_dates = _extract_news_dates_from_article(session, link, publish_date_raw)
        if article_dates.get('publish_date'):
            publish_date = article_dates['publish_date']
        if article_dates.get('publish_date_raw'):
            publish_date_raw = article_dates['publish_date_raw']

        news.append({
            "title": title,
            "summary": summary,
            "publish_date": publish_date,
            "publish_date_raw": publish_date_raw,
            "last_edited_date": article_dates.get('last_edited_date', ''),
            "last_edited_date_raw": article_dates.get('last_edited_date_raw', ''),
            "link": link,
            "resource_type": "Artificial Intelligence News"
        })

    print(f"DEBUG: Retrieved {len(news)} AI news items")
    return news


def scrape_ai_projects() -> List[Dict[str, Any]]:
    url = 'https://csrc.nist.gov/projects?sortBy-lg=Name+ASC&ipp-lg=25&topics-lg=27491%7Cartificial+intelligence&topicsMatch-lg=ANY'
    print(f"Scraping AI projects from {url}")
    projects = []
    session = requests.Session()

    def _fetch(url):
        r = session.get(url, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.content, 'html.parser')

    try:
        soup = _fetch(url)
    except Exception as e:
        print(f"Error scraping AI projects: {e}")
        return projects

    items = soup.select(".search-list-item")
    if not items:
        items = soup.select("article")
    if not items:
        items = soup.select(".project-item")

    for item in items:
        title_el = item.select_one("h3 a") or item.select_one("a")
        if not title_el:
            continue
        title = clean_text(title_el.get_text(strip=True))
        if not title:
            continue
        link = _parse_link(title_el.get('href', ''), base='csrc.nist.gov')

        summary_el = item.select_one(".summary") or item.select_one("p")
        summary = clean_text(summary_el.get_text(strip=True)) if summary_el else ""

        projects.append({
            "title": title,
            "summary": summary,
            "link": link,
            "resource_type": "Artificial Intelligence Project"
        })

    print(f"DEBUG: Retrieved {len(projects)} AI projects")
    return projects


def scrape_all_ai_data() -> Dict[str, List[Dict[str, Any]]]:
    publications = scrape_ai_publications()
    presentations = scrape_ai_presentations()
    news = scrape_ai_news()
    projects = scrape_ai_projects()
    return {
        'publications': publications,
        'presentations': presentations,
        'news': news,
        'projects': projects
    }


def main():
    data = scrape_all_ai_data()
    print(f"AI data scraped: {len(data['publications'])} publications, {len(data['presentations'])} presentations, {len(data['news'])} news, {len(data['projects'])} projects")
    return data
