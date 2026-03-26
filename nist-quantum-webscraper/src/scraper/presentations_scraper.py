import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

def scrape_presentations():
    # URL for NIST CSRC presentations with post-quantum cryptography filter
    base_url = 'https://csrc.nist.gov/search?ipp=25&sortBy=relevance&showOnly=presentations&topicsMatch=ANY&topics=27651%7cpost-quantum+cryptography'
    presentations = []
    cutoff_date = datetime.now() - timedelta(days=365)
    
    session = requests.Session()
    stale_pages = 0

    # Try multiple pages to find recent presentations.
    for page in range(50):
        if page == 0:
            url = base_url
        else:
            url = f"{base_url}&page={page}"
        
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if there are any results on this page
            items = soup.select('.search-list-item')
            
            if not items:
                break  # No more results

            added_this_page = 0
            
            # Find presentation items
            for item in items:
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
                    
                    # Try to parse the date to check if it's within the past year
                    try:
                        # Try different date formats
                        date_str = presentation['release_date']
                        parsed_date = None
                        
                        # Try common date formats
                        for fmt in ['%B %d, %Y', '%b %d, %Y', '%Y-%m-%d', '%B %Y', '%b %Y']:
                            try:
                                parsed_date = datetime.strptime(date_str, fmt)
                                break
                            except ValueError:
                                continue
                        
                        if parsed_date and parsed_date >= cutoff_date:
                            # Make link absolute if needed
                            if presentation['link'] and not presentation['link'].startswith('http'):
                                presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
                            presentations.append(presentation)
                            added_this_page += 1
                    except Exception:
                        # If we can't parse the date, include it anyway
                        if presentation['link'] and not presentation['link'].startswith('http'):
                            presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
                        presentations.append(presentation)
                        added_this_page += 1
                else:
                    # If no date available, include the presentation
                    if presentation['link'] and not presentation['link'].startswith('http'):
                        presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
                    presentations.append(presentation)
                    added_this_page += 1

            if added_this_page == 0:
                stale_pages += 1
            else:
                stale_pages = 0

            if stale_pages >= 3:
                break
                
        except Exception:
            continue
    
    # Remove duplicates based on document_name and link
    seen = set()
    unique_presentations = []
    for p in presentations:
        key = (p['document_name'], p['link'])
        if key not in seen:
            seen.add(key)
            unique_presentations.append(p)
    
    return unique_presentations

def main():
    presentations_data = scrape_presentations()
    print(presentations_data)

if __name__ == "__main__":
    main()