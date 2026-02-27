import requests
from bs4 import BeautifulSoup

def scrape_presentations(url):
    presentations = []
    
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Assuming presentations are listed in a specific HTML structure
    for item in soup.select('.presentation-item'):
        presentation = {
            'document_name': item.select_one('.document-name').text.strip(),
            'document_number': item.select_one('.document-number').text.strip(),
            'series': item.select_one('.series').text.strip(),
            'document_status': item.select_one('.status').text.strip(),
            'document_release_date': item.select_one('.release-date').text.strip(),
            'resource_type': item.select_one('.resource-type').text.strip(),
            'document_link': item.select_one('a')['href']
        }
        presentations.append(presentation)
    
    return presentations

def main():
    url = 'https://www.nist.gov/quantum/presentations'  # Example URL
    presentations_data = scrape_presentations(url)
    print(presentations_data)

if __name__ == "__main__":
    main()