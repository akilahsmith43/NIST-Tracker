import requests
from bs4 import BeautifulSoup

def scrape_publications(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    publications = []
    
    # Assuming the publications are listed in a specific HTML structure
    for item in soup.select('.publication-item'):
        publication = {
            'document_name': item.select_one('.document-name').text.strip(),
            'document_number': item.select_one('.document-number').text.strip(),
            'series': item.select_one('.series').text.strip(),
            'document_status': item.select_one('.status').text.strip(),
            'document_release_date': item.select_one('.release-date').text.strip(),
            'resource_type': item.select_one('.resource-type').text.strip(),
            'document_link': item.select_one('a')['href']
        }
        publications.append(publication)
    
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