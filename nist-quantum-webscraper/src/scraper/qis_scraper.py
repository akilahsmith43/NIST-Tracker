import re
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from datetime import datetime, timedelta
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Shared text helpers
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _generate_summary(pub: dict) -> str:
    if pub.get('summary'):
        existing = pub['summary'].strip()
        title = pub.get('document_name', '').strip()
        if existing and title and existing.lower() != title.lower():
            return existing
    title = pub.get('document_name', '')
    if not title:
        return "Publication detailing quantum information science research."
    summary = title[:200] + "..." if len(title) > 200 else title
    series = pub.get('series', 'Publication')
    if series and series.lower() not in summary.lower():
        summary = f"{series}: {summary}"
    if summary.strip().lower() == title.strip().lower():
        return ""
    return summary


# ---------------------------------------------------------------------------
# Publications
# ---------------------------------------------------------------------------

def _scrape_publications_from_url(
    url: str,
    cutoff_date: datetime | None = None,
    category: str | None = None,
) -> list[dict]:
    """Fetch all pages for a single NIST publications search URL."""
    base_url = url
    publications = []
    visited: set[str] = set()
    session = requests.Session()

    def _fetch_page(page_url):
        resp = session.get(page_url, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")

    futures: dict = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures[executor.submit(_fetch_page, base_url)] = base_url
        while futures:
            done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                page_url = futures.pop(fut)
                try:
                    soup = fut.result()
                except Exception as e:
                    print(f"Error fetching {page_url}: {e}")
                    continue

                if page_url in visited:
                    continue
                visited.add(page_url)

                items = (
                    soup.select(".search-list-item")
                    or soup.select("article")
                    or soup.select(".publication-item")
                    or soup.select("[data-publication]")
                )
                print(f"DEBUG: Found {len(items)} items on {page_url}")

                for item in items:
                    title_link = (
                        item.select_one("h4.search-results-title a")
                        or item.select_one("h3 a")
                        or item.select_one("a[data-title]")
                        or item.select_one("a")
                    )
                    if not title_link:
                        continue
                    name = _clean_text(title_link.get_text(strip=True))
                    if not name:
                        continue

                    link = title_link.get("href", "")
                    if link and not link.startswith("http"):
                        link = f"https://csrc.nist.gov{link}" if "csrc.nist.gov" in base_url else f"https://www.nist.gov{link}"

                    series_el = (
                        item.select_one(".sub-title strong")
                        or item.select_one(".series")
                        or item.select_one("[class*='series']")
                    )
                    series = _clean_text(series_el.get_text(strip=True)) if series_el else ""

                    date_el = (
                        item.select_one('strong[id^="date-container-"]')
                        or item.select_one("time")
                        or item.select_one(".date")
                        or item.select_one("[class*='date']")
                    )
                    release_date = _clean_text(date_el.get_text(strip=True)) if date_el else ""

                    summary_el = (
                        item.select_one('p[id^="content-area-"]')
                        or item.select_one(".summary")
                        or item.select_one(".description")
                        or item.select_one("p")
                    )
                    summary = ""
                    if summary_el:
                        summary = _clean_text(summary_el.get_text(strip=True))
                        if summary.lower().startswith("abstract:"):
                            summary = summary[len("abstract:"):].strip()

                    release_date_raw = ""
                    if release_date:
                        try:
                            release_date_raw = datetime.strptime(release_date, '%B %d, %Y').strftime('%Y-%m-%d')
                        except Exception:
                            release_date_raw = release_date

                    if cutoff_date:
                        try:
                            raw = release_date_raw or release_date
                            pub_date = datetime.strptime(raw, '%Y-%m-%d') if raw else None
                            if pub_date and pub_date < cutoff_date:
                                continue
                        except Exception:
                            pass

                    publications.append({
                        "document_name": name,
                        "document_number": "",
                        "series": series,
                        "release_date": release_date,
                        "release_date_raw": release_date_raw,
                        "resource_type": "Publication",
                        "link": link,
                        "summary": summary,
                        "category": category or "",
                    })

                # follow pagination
                for selector in ('a[rel="next"]', 'a.pagination-next', 'li.next a', '.pager-next a'):
                    el = soup.select_one(selector)
                    if el and el.get('href'):
                        full_next = urljoin(page_url, el['href'])
                        if full_next not in visited and full_next not in futures.values():
                            futures[executor.submit(_fetch_page, full_next)] = full_next
                        break

    # Enrich missing summaries concurrently
    def _fetch_meta(pub):
        if pub.get('summary'):
            return pub['summary']
        lnk = pub.get('link')
        if not lnk:
            return ""
        try:
            resp = session.get(lnk, timeout=5)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            meta = soup.select_one('meta[name="description"]')
            if meta and meta.get('content'):
                return _clean_text(meta['content'])
        except Exception:
            pass
        return ""

    pubs_to_update = [p for p in publications if not p.get('summary')]
    if pubs_to_update:
        with ThreadPoolExecutor(max_workers=8) as executor:
            for pub, new_summary in zip(pubs_to_update, executor.map(_fetch_meta, pubs_to_update)):
                if new_summary:
                    pub['summary'] = new_summary

    for pub in publications:
        pub['summary'] = _generate_summary(pub)

    print(f"DEBUG: Retrieved {len(publications)} publications from {base_url}")
    return publications


def scrape_qis_publications() -> list[dict]:
    """Scrape QIS publications from all four NIST QIS sources."""
    sources = [
        {
            "url": "https://www.nist.gov/publications/search/topic/249281",
            "category": "General Publications",
        },
        {
            "url": "https://csrc.nist.gov/publications/search?sortBy-lg=relevance&viewMode-lg=brief&ipp-lg=50&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
            "category": "All Publications",
        },
        {
            "url": "https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Draft&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
            "category": "Drafts Open for Comment",
        },
        {
            "url": "https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Final&series-lg=FIPS%2CSP%2CIR%2CCSWP%2CTN%2CVTS%2CAI%2CGCR%2CProject+Description&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
            "category": "Final Publications",
        },
    ]

    seen: set[str] = set()
    all_pubs: list[dict] = []

    print("=" * 50)
    print("Starting QIS publication scraping...")
    print("=" * 50)

    futures: dict = {}
    with ThreadPoolExecutor(max_workers=min(4, len(sources))) as executor:
        for source in sources:
            futures[executor.submit(_scrape_publications_from_url, source["url"], None, source["category"])] = source["url"]
        for future in as_completed(futures):
            url = futures[future]
            try:
                pubs = future.result()
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue
            count = 0
            for pub in pubs:
                link = pub.get("link")
                if link in seen:
                    continue
                seen.add(link)
                all_pubs.append(pub)
                count += 1
            print(f"Scraped {url[:80]} -> added {count} (total: {len(all_pubs)})")

    print("=" * 50)
    print(f"QIS publications complete: {len(all_pubs)}")
    print("=" * 50)
    return all_pubs


# ---------------------------------------------------------------------------
# Presentations
# ---------------------------------------------------------------------------

def scrape_qis_presentations() -> list[dict]:
    """Scrape QIS presentations from NIST CSRC."""
    base_url = (
        "https://csrc.nist.gov/search?ipp=25&sortBy=relevance"
        "&showOnly=presentations&topicsMatch=ANY"
        "&topics=27501%7cquantum+information+science"
    )
    presentations: list[dict] = []
    cutoff_date = datetime.now() - timedelta(days=365)
    session = requests.Session()
    stale_pages = 0

    for page in range(50):
        url = base_url if page == 0 else f"{base_url}&page={page}"
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            items = soup.select('.search-list-item')
            if not items:
                break

            added_this_page = 0
            for item in items:
                title_link = item.select_one('a[id^="title-link-"]')
                if not title_link:
                    continue

                presentation = {
                    'document_name': title_link.get_text(strip=True),
                    'document_number': '',
                    'series': 'Presentation',
                    'status': 'Available',
                    'release_date': '',
                    'resource_type': 'Quantum Information Science Presentation',
                    'link': title_link['href'] if title_link.get('href') else '',
                }

                date_el = item.select_one('strong[id^="date-container-"]')
                if date_el:
                    presentation['release_date'] = date_el.get_text(strip=True)
                    parsed_date = None
                    for fmt in ('%B %d, %Y', '%b %d, %Y', '%Y-%m-%d', '%B %Y', '%b %Y'):
                        try:
                            parsed_date = datetime.strptime(presentation['release_date'], fmt)
                            break
                        except ValueError:
                            continue

                    if presentation['link'] and not presentation['link'].startswith('http'):
                        presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"

                    if parsed_date is None or parsed_date >= cutoff_date:
                        presentations.append(presentation)
                        added_this_page += 1
                else:
                    if presentation['link'] and not presentation['link'].startswith('http'):
                        presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
                    presentations.append(presentation)
                    added_this_page += 1

            stale_pages = 0 if added_this_page > 0 else stale_pages + 1
            if stale_pages >= 3:
                break

        except Exception:
            continue

    seen: set[tuple] = set()
    unique: list[dict] = []
    for p in presentations:
        key = (p['document_name'], p['link'])
        if key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"DEBUG: Retrieved {len(unique)} QIS presentations")
    return unique


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def _parse_nist_date_news(date_str: str) -> datetime | None:
    if not date_str:
        return None
    cleaned = ' '.join(date_str.strip().split())
    cleaned = re.sub(r'(\d)(st|nd|rd|th)', r'\1', cleaned)
    for fmt in ('%B %d, %Y', '%B %d %Y', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(cleaned, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(cleaned.replace('Z', '+00:00'))
    except Exception:
        return None


def _to_display_and_raw(date_str: str) -> tuple[str, str]:
    parsed = _parse_nist_date_news(date_str)
    if not parsed:
        return '', ''
    parsed = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    return parsed.strftime('%B %d, %Y'), parsed.strftime('%Y-%m-%d')


def _extract_article_dates(article_soup, fallback_publish_raw: str) -> tuple[str, str, str, str]:
    publish_raw = (fallback_publish_raw or '').strip()

    def _content_for(selectors):
        for selector in selectors:
            node = article_soup.select_one(selector)
            if not node:
                continue
            value = (node.get('content') or node.get('datetime') or node.get_text(' ', strip=True) or '').strip()
            if value:
                return value
        return ''

    publish_candidate = _content_for([
        'meta[property="article:published_time"]',
        'meta[property="article:published"]',
        'meta[name="publish_date"]',
        'meta[name="date"]',
        '[itemprop="datePublished"]',
    ])
    if publish_candidate:
        _, raw = _to_display_and_raw(publish_candidate)
        if raw:
            publish_raw = raw

    modified_candidate = _content_for([
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

    publish_date, publish_date_raw = _to_display_and_raw(publish_raw)
    last_edited_date, last_edited_date_raw = _to_display_and_raw(modified_candidate)
    return publish_date, publish_date_raw, last_edited_date, last_edited_date_raw


def scrape_qis_news() -> list[dict]:
    """Scrape QIS news from NIST."""
    base_url = "https://www.nist.gov/news-events/news/search?key=quantum&topic-op=or&topic-area-fieldset%5B%5D=249281"
    session = requests.Session()
    news_data: list[dict] = []
    next_url: str | None = base_url

    while next_url:
        response = session.get(next_url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')

        articles = soup.find_all('article')
        if not articles:
            break

        page_entries = []
        for article in articles:
            title_el = article.find('h3')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link_el = article.find('a')
            if not link_el or not link_el.get('href'):
                continue
            link = link_el['href']
            if not link.startswith('http'):
                link = f"https://www.nist.gov{link}"
            date_el = article.find('time')
            page_entries.append({'title': title, 'link': link, 'date': date_el['datetime'] if date_el else ""})

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
                    content = (
                        article_soup.select_one('main')
                        or article_soup.select_one('[role="main"]')
                        or article_soup.select_one('.field-type-text-long')
                    )
                    if content:
                        p = content.find('p')
                        if p:
                            summary = p.get_text(strip=True)
            except Exception:
                pass

            parsed = _parse_nist_date_news(date)
            publish_date = parsed.strftime('%B %d, %Y') if parsed else ''
            publish_date_raw = parsed.strftime('%Y-%m-%d') if parsed else date
            last_edited_date = ""
            last_edited_date_raw = ""

            if article_soup is not None:
                ep, epr, el, elr = _extract_article_dates(article_soup, date)
                if ep:
                    publish_date = ep
                if epr:
                    publish_date_raw = epr
                if el:
                    last_edited_date = el
                if elr:
                    last_edited_date_raw = elr

            return {
                'title': title,
                'link': link,
                'publish_date': publish_date,
                'publish_date_raw': publish_date_raw,
                'last_edited_date': last_edited_date,
                'last_edited_date_raw': last_edited_date_raw,
                'summary': summary or (title[:80] + "..." if len(title) > 50 else f"News article about {title.lower()}."),
            }

        if page_entries:
            max_workers = min(8, len(page_entries)) or 1
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                news_data.extend(executor.map(_build_news_item, page_entries))

        next_link = soup.select_one('a[rel="next"]')
        next_url = urljoin(next_url, next_link['href']) if next_link and next_link.get('href') else None

    print(f"DEBUG: Retrieved {len(news_data)} QIS news items")
    return news_data


# ---------------------------------------------------------------------------
# Consolidated entry point
# ---------------------------------------------------------------------------

def scrape_all_qis_data() -> dict:
    """Scrape all QIS data (publications, presentations, news) concurrently."""
    print("=" * 50)
    print("Starting Quantum Information Science data scraping...")
    print("=" * 50)

    with ThreadPoolExecutor(max_workers=3) as executor:
        publications_future = executor.submit(scrape_qis_publications)
        presentations_future = executor.submit(scrape_qis_presentations)
        news_future = executor.submit(scrape_qis_news)

        publications = publications_future.result()
        presentations = presentations_future.result()
        news = news_future.result()

    print("=" * 50)
    print("QIS Scraping complete!")
    print(f"Publications: {len(publications)}")
    print(f"Presentations: {len(presentations)}")
    print(f"News: {len(news)}")
    print("=" * 50)

    return {
        'publications': publications,
        'presentations': presentations,
        'news': news,
    }


def main():
    data = scrape_all_qis_data()
    print(
        f"QIS data scraped: {len(data['publications'])} publications, "
        f"{len(data['presentations'])} presentations, "
        f"{len(data['news'])} news"
    )
    return data


if __name__ == "__main__":
    main()
