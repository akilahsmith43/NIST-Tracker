import requests
from bs4 import BeautifulSoup

def scrape_presentations():
    # URL for NIST CSRC presentations with quantum information science filter
    url = 'https://csrc.nist.gov/search?ipp=25&sortBy=relevance&showOnly=presentations&topicsMatch=ANY&topics=27501%7cquantum+information+science'
    presentations = []
    
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find presentation items
        for item in soup.select('.search-list-item'):
            # Get the title link
            title_link = item.select_one('a[id^="title-link-"]')
            if not title_link:
                continue
                
            # Extract presentation details
            presentation = {
                'document_name': title_link.get_text(strip=True),
                'document_number': '',  # Not available in search results
                'series': 'Presentation',
                'status': 'Available',
                'release_date': '',  # will fill below if available
                'resource_type': 'Presentation',
                'link': title_link['href'] if title_link.get('href') else ''
            }
            # extract date if provided
            date_el = item.select_one('strong[id^="date-container-"]')
            if date_el:
                presentation['release_date'] = date_el.get_text(strip=True)
            
            # Make link absolute if needed
            if presentation['link'] and not presentation['link'].startswith('http'):
                presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
            
            presentations.append(presentation)
    except Exception as e:
        print(f"Error scraping presentations: {e}")
    
    return presentations

def main():
    presentations_data = scrape_presentations()
    print(presentations_data)

if __name__ == "__main__":
    main()