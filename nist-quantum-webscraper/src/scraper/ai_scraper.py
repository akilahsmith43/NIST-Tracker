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
        return f"https://{base}{href}" if base else f"https://csrc.nist.gov{href}"
    return href


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
            link = _parse_link(title_el.get('href', ''), base='csrc.nist.gov')

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

        news.append({
            "title": title,
            "summary": summary,
            "publish_date": publish_date,
            "publish_date_raw": publish_date_raw,
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
