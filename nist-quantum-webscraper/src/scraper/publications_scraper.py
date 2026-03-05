import requests
from bs4 import BeautifulSoup

def scrape_publications():
    # URLs for NIST CSRC publications
    urls = [
        'https://csrc.nist.gov/publications/final-pubs',
        'https://csrc.nist.gov/publications/drafts-open-for-comment',
        'https://csrc.nist.gov/publications/draft-pubs'
    ]
    
    all_publications = []
    
    for url in urls:
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find publication rows in the table
            for row in soup.select('tr[id^="pub-title-link-"]'):
                # Get the link element
                link_elem = row.select_one('a[id^="pub-title-link-"]')
                if not link_elem:
                    continue
                    
                # Extract publication details from the row
                series_elem = row.select_one('td[id^="pub-series-"]')
                number_elem = row.select_one('td[id^="pub-number-"]')
                
                publication = {
                    'document_name': link_elem.get_text(strip=True),
                    'document_number': number_elem.get_text(strip=True) if number_elem else '',
                    'series': series_elem.get_text(strip=True) if series_elem else '',
                    'status': 'Final' if 'final-pubs' in url else 'Draft',
                    'release_date': '',  # Not easily extractable from this page
                    'resource_type': 'Publication',
                    'link': link_elem['href'] if link_elem.get('href') else ''
                }
                
                # Make link absolute if needed
                if publication['link'] and not publication['link'].startswith('http'):
                    publication['link'] = f"https://csrc.nist.gov{publication['link']}"
                
                all_publications.append(publication)
        except Exception as e:
            print(f"Error scraping publications from {url}: {e}")
    
    return all_publications

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