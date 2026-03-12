import requests
from bs4 import BeautifulSoup

def scrape_publications():
    """Return a list of quantum‑related publications scraped from the CSRC search
    interface.

    The site no longer exposes a simple table, so we hit the search endpoint and
    parse the `.search-list-item` blocks (the same pattern used by
    `scrape_presentations`).
    """

    search_url = (
        "https://csrc.nist.gov/search?ipp=100&sortBy=relevance&showOnly=publications"
        "&topicsMatch=ANY&topics=27501%7cquantum+information+science"
    )

    publications = []
    try:
        response = requests.get(search_url)
        soup = BeautifulSoup(response.content, "html.parser")

        for item in soup.select(".search-list-item"):
            title_link = item.select_one("h4.search-results-title a")
            if not title_link:
                continue

            name = title_link.get_text(strip=True)
            link = title_link.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://csrc.nist.gov{link}"

            # attempt to capture a subtitle/series label
            series_el = item.select_one(".sub-title strong")
            series = series_el.get_text(strip=True) if series_el else ""

            publications.append({
                "document_name": name,
                "document_number": "",
                "series": series,
                "status": "Unknown",
                "release_date": "",
                "resource_type": "Publication",
                "link": link,
            })
    except Exception as e:
        print(f"Error scraping publications: {e}")

    return publications

def main():
    urls = [
        'https://www.nist.gov/quantum/publication1',
        'https://www.nist.gov/quantum/publication2',
        # Add more URLs as needed
    ]
    
    all_publications = []
    for url in urls:
        all_publications.extend(scrape_publications(url))
    
    # Output or process the collected data as needed
    print(all_publications)

if __name__ == "__main__":
    main()