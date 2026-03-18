import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime


def generate_summary(pub: dict) -> str:
    """Generate a meaningful summary for a publication.
    
    Creates a summary from the title and available metadata.
    """
    if pub.get('summary'):
        # if the existing summary is just the title, treat it as empty
        existing = pub['summary'].strip()
        title = pub.get('document_name', '').strip()
        if existing and title and existing.lower() == title.lower():
            # fall through to regenerate
            pass
        else:
            return existing
    
    # Create a meaningful summary from the title
    title = pub.get('document_name', '')
    if not title:
        return "Publication detailing quantum information science research."
    
    # Use title as base summary but limit length for readability
    if len(title) > 200:
        summary = title[:200] + "..."
    else:
        summary = title
    
    # Add context about document type
    series = pub.get('series', 'Publication')
    if series and series.lower() not in summary.lower():
        summary = f"{series}: {summary}"
    
    # if summary equals title (no extra info), return empty
    if summary.strip().lower() == title.strip().lower():
        return ""
    
    return summary


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

def scrape_publications(url: str | None = None, query: str | None = None, cutoff_date: datetime | None = None):
    """Scrape publications from a given URL or the default CSRC search interface.

    Parameters
    ----------
    url
        The base URL to scrape from. If None, uses the default CSRC search URL.
    query
        Optional query string to append to the URL (e.g. "draft" or
        "open for comment"). Only used if url is None.
    cutoff_date
        Optional datetime object to filter publications. Only publications
        with release_date >= cutoff_date will be included.

    The search endpoint is used because the standalone publication pages are
    rendered client‑side.  By supplying a `query` string (e.g. "draft" or
        "open for comment") you can broaden the results to include drafts or
    other non‑final items; omitting it returns the default set, which at the
    moment consists mostly of final publications.

    This function also follows pagination links ("next" buttons) so that all
    available pages are crawled.

    Returns a list of dictionaries with the same structure used elsewhere in
    the project.
    """

    # build the initial URL
    if url is None:
        base_url = (
            "https://csrc.nist.gov/search?ipp=100&sortBy=relevance&showOnly=publications"
            "&topicsMatch=ANY&topics=27501%7cquantum+information+science"
        )
        if query:
            # url‑encode the query term; requests will handle most characters but
            # we'll be explicit.
            from urllib.parse import quote_plus
            base_url += "&q=" + quote_plus(query)
    else:
        base_url = url
        if query:
            from urllib.parse import quote_plus
            base_url += "&q=" + quote_plus(query)

    publications = []
    visited = set()
    session = requests.Session()  # reuse connection

    # helper to fetch a page and return soup, or raise
    def _fetch_page(url):
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")

    # build a dynamic crawling queue so we can fetch multiple pages at once
    from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
    futures = {}
    # start with base url
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures[executor.submit(_fetch_page, base_url)] = base_url
        while futures:
            done, _ = wait(
                futures.keys(), return_when=FIRST_COMPLETED
            )
            for fut in done:
                url = futures.pop(fut)
                try:
                    soup = fut.result()
                except Exception as e:
                    print(f"Error fetching {url}: {e}")
                    continue

                if url in visited:
                    continue
                visited.add(url)

                # Try multiple selectors for different page layouts
                items = soup.select(".search-list-item")
                if not items:
                    items = soup.select("article")
                if not items:
                    items = soup.select(".publication-item")
                if not items:
                    items = soup.select("[data-publication]")

                print(f"DEBUG: Found {len(items)} items on {url}")

                # iterate over items inside try block
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
                        if "csrc.nist.gov" in base_url:
                            link = f"https://csrc.nist.gov{link}"
                        else:
                            link = f"https://www.nist.gov{link}"

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
                        # store summary now; may fetch meta later
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
                        
                        # Apply date filtering if cutoff_date is provided
                        if cutoff_date:
                            try:
                                # Parse the release date to compare with cutoff
                                if release_date_raw:
                                    pub_date = datetime.strptime(release_date_raw, '%Y-%m-%d')
                                elif release_date:
                                    pub_date = datetime.strptime(release_date, '%B %d, %Y')
                                else:
                                    # If no date available, include it (default behavior)
                                    pub_date = None
                                
                                # Only include if publication date is after cutoff
                                if pub_date and pub_date < cutoff_date:
                                    continue  # Skip this publication
                            except Exception:
                                # If date parsing fails, include it (default behavior)
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
                        })

                # schedule next page if available
                next_link = None
                for selector in [
                    'a[rel="next"]',
                    'a.pagination-next',
                    'li.next a',
                    '.pager-next a'
                ]:
                    el = soup.select_one(selector)
                    if el and el.get('href'):
                        next_link = el.get('href')
                        break
                if next_link:
                    from urllib.parse import urljoin
                    full_next = urljoin(url, next_link)
                    if full_next not in visited and full_next not in futures.values():
                        futures[executor.submit(_fetch_page, full_next)] = full_next


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

    # Generate or normalize final summaries
    for pub in publications:
        pub['summary'] = generate_summary(pub)
    
    print(f"DEBUG: Retrieved {len(publications)} publications from {base_url}")
    return publications


def filter_publications(publications, *, include_drafts: bool = False,
                        include_final: bool = True) -> list[dict]:
    """Return a subset of *publications* based on status keywords.

    Parameters
    ----------
    publications
        List produced by :func:`scrape_publications` or
        :func:`scrape_all_publications`.
    include_drafts
        If ``True`` keep items whose ``series`` field contains the word
        "draft" (case‑insensitive).
    include_final
        If ``True`` keep items whose ``series`` field contains the word
        "final".

    The two flags are combined with OR logic; you can set both ``True`` to
    return everything (no filtering) or one of them to get only that class.
    """

    if not (include_drafts or include_final):
        return []

    out = []
    for pub in publications:
        series = pub.get("series", "").lower()
        is_draft = "draft" in series
        is_final = "final" in series
        if is_draft and include_drafts:
            out.append(pub)
        elif is_final and include_final:
            out.append(pub)
    return out


def scrape_publications_past_year():
    """Scrape publications from the past year only.
    
    Uses the same URLs as scrape_all_publications but applies date filtering
    during scraping to only include publications from the past year.
    """
    from datetime import datetime, timedelta
    
    # Calculate cutoff date (1 year ago from today)
    cutoff_date = datetime.now() - timedelta(days=365)
    
    urls = [
        "https://www.nist.gov/publications/search/topic/249281",
        "https://csrc.nist.gov/publications/search?sortBy-lg=relevance&viewMode-lg=brief&ipp-lg=50&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
        "https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Draft&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
        "https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Final&series-lg=FIPS%2CSP%2CIR%2CCSWP%2CTN%2CVTS%2CAI%2CGCR%2CProject+Description&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
    ]
    
    seen = set()
    all_pubs = []
    
    print("=" * 50)
    print("Starting publication scraping (past year only)...")
    print(f"Will scrape {len(urls)} URLs with cutoff date: {cutoff_date.strftime('%Y-%m-%d')}")
    print("=" * 50)
    
    # Scrape from the specified URLs in parallel to save time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    futures = {}
    with ThreadPoolExecutor(max_workers=min(4, len(urls))) as executor:
        for url in urls:
            futures[executor.submit(scrape_publications, url=url, cutoff_date=cutoff_date)] = url
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
            print(f"Scraped {url[:80]} -> added {count} new publications (total: {len(all_pubs)})")
    
    print("=" * 50)
    print(f"Scraping complete! Total unique publications from past year: {len(all_pubs)}")
    print("=" * 50)
    return all_pubs


def scrape_all_publications():
    """Convenience wrapper that scrapes publications from 4 specified NIST sources.

    Scrapes from 4 NIST publication URLs and de‑duplicates by link.
    """

    urls = [
        "https://www.nist.gov/publications/search/topic/249281",
        "https://csrc.nist.gov/publications/search?sortBy-lg=relevance&viewMode-lg=brief&ipp-lg=50&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
        "https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Draft&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
        "https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Final&series-lg=FIPS%2CSP%2CIR%2CCSWP%2CTN%2CVTS%2CAI%2CGCR%2CProject+Description&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
    ]
    
    seen = set()
    all_pubs = []
    
    print("=" * 50)
    print("Starting publication scraping...")
    print(f"Will scrape {len(urls)} URLs")
    print("=" * 50)
    
    # Scrape from the specified URLs in parallel to save time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    futures = {}
    with ThreadPoolExecutor(max_workers=min(4, len(urls))) as executor:
        for url in urls:
            futures[executor.submit(scrape_publications, url=url)] = url
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
            print(f"Scraped {url[:80]} -> added {count} new publications (total: {len(all_pubs)})")
    
    print("=" * 50)
    print(f"Scraping complete! Total unique publications: {len(all_pubs)}")
    print("=" * 50)
    return all_pubs

def main():
    """Scrape all publications from multiple NIST sources."""
    all_publications = scrape_all_publications()
    
    # Output or process the collected data as needed
    print(f"Scraped {len(all_publications)} publications")
    for pub in all_publications[:5]:  # Print first 5 as example
        print(pub)

if __name__ == "__main__":
    main()