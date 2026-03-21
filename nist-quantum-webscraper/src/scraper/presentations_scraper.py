import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

def scrape_presentations():
    # URL for NIST CSRC presentations with post-quantum cryptography filter
    base_url = 'https://csrc.nist.gov/search?ipp=25&sortBy=relevance&showOnly=presentations&topicsMatch=ANY&topics=27651%7cpost-quantum+cryptography'
    presentations = []
    cutoff_date = datetime.now() - timedelta(days=365)
    
    # Try multiple pages to find recent presentations - go deeper if needed
    for page in range(50):  # Check up to 50 pages to find recent content
        if page == 0:
            url = base_url
        else:
            url = f"{base_url}&page={page}"
        
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if there are any results on this page
            items = soup.select('.search-list-item')
            
            if not items:
                break  # No more results
            
            page_has_any = False
            
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
                            page_has_any = True
                        elif parsed_date:
                            # If we find old dates, we can continue but don't stop
                            page_has_any = True
                    except Exception:
                        # If we can't parse the date, include it anyway
                        if presentation['link'] and not presentation['link'].startswith('http'):
                            presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
                        presentations.append(presentation)
                        page_has_any = True
                else:
                    # If no date available, include the presentation
                    if presentation['link'] and not presentation['link'].startswith('http'):
                        presentation['link'] = f"https://csrc.nist.gov{presentation['link']}"
                    presentations.append(presentation)
                    page_has_any = True
            
            # Continue crawling even if no recent presentations found
            # Only stop if we've found some presentations and this page has no items at all
            if not page_has_any:
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