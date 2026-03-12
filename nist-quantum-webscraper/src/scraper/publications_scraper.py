import requests
from bs4 import BeautifulSoup

def scrape_publications(url: str | None = None, query: str | None = None):
    """Scrape publications from a given URL or the default CSRC search interface.

    Parameters
    ----------
    url
        The base URL to scrape from. If None, uses the default CSRC search URL.
    query
        Optional query string to append to the URL (e.g. "draft" or
        "open for comment"). Only used if url is None.

    The search endpoint is used because the standalone publication pages are
    rendered client‑side.  By supplying a `query` string (e.g. "draft" or
    "open for comment") you can broaden the results to include drafts or
    other non‑final items; omitting it returns the default set, which at the
    moment consists mostly of final publications.

    Returns a list of dictionaries with the same structure used elsewhere in
    the project.
    """

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
    try:
        response = requests.get(base_url)
        soup = BeautifulSoup(response.content, "html.parser")

        for item in soup.select(".search-list-item"):
            title_link = item.select_one("h4.search-results-title a")
            if not title_link:
                continue

            name = title_link.get_text(strip=True)
            link = title_link.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://csrc.nist.gov{link}"

            series_el = item.select_one(".sub-title strong")
            series = series_el.get_text(strip=True) if series_el else ""

            # date and abstract/summary appear in predictable elements
            date_el = item.select_one('strong[id^="date-container-"]')
            release_date = date_el.get_text(strip=True) if date_el else ""

            summary_el = item.select_one('p[id^="content-area-"]')
            # remove leading "Abstract:" if present and trim
            summary = ""
            if summary_el:
                summary = summary_el.get_text(strip=True)
                if summary.lower().startswith("abstract:"):
                    summary = summary[len("abstract:"):].strip()

            publications.append({
                "document_name": name,
                "document_number": "",
                "series": series,
                "release_date": release_date,
                "resource_type": "Publication",
                "link": link,
                "summary": summary,
            })
    except Exception as e:
        print(f"Error scraping publications: {e}")

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


def scrape_all_publications():
    """Convenience wrapper that attempts to fetch publications from multiple sources.

    Scrapes from multiple NIST publication URLs and de‑duplicates by link.
    """

    urls = [
        "https://csrc.nist.gov/search?ipp=100&sortBy=relevance&showOnly=publications",
        "https://www.nist.gov/publications/search?k=&t=&a=&ps=All&ta%5B%5D=249281&n=&d%5Bmin%5D=&d%5Bmax%5D=",
        "https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Final&series-lg=FIPS%2CSP%2CIR%2CCSWP%2CTN%2CVTS%2CAI%2CGCR%2CProject+Description%2CBook+Section&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
        "https://csrc.nist.gov/publications/search?sortBy-lg=relevance&viewMode-lg=brief&ipp-lg=50&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
        "https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Draft&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY",
    ]
    
    seen = set()
    all_pubs = []
    
    # Scrape from multiple URLs
    for url in urls:
        for pub in scrape_publications(url=url):
            link = pub.get("link")
            if link in seen:
                continue
            seen.add(link)
            all_pubs.append(pub)
    
    # Also keep the original query-based approach for backward compatibility
    queries = [None, "draft", "open for comment"]
    for q in queries:
        for pub in scrape_publications(query=q):
            link = pub.get("link")
            if link in seen:
                continue
            seen.add(link)
            all_pubs.append(pub)
    
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