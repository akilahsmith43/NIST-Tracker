import requests
from bs4 import BeautifulSoup
from datetime import datetime


def format_date(date_str: str) -> str:
    """Convert ISO format date to written out format (e.g., January 15, 2026)."""
    if not date_str:
        return ""
    
    try:
        # Parse the ISO format date
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        # Format as "Month Day, Year"
        return date_obj.strftime('%B %d, %Y')
    except Exception as e:
        print(f"Error formatting date '{date_str}': {e}")
        return date_str


def generate_news_summary(title: str, summary: str) -> str:
    """Generate or enhance a news summary.
    
    Uses the extracted summary if available, otherwise creates one from the title.
    """
    if summary:
        return summary
    
    # If no summary extracted, create a basic one from title
    if len(title) > 50:
        return title[:80] + "..."
    
    return f"News article about {title.lower()}."


def scrape_news():
    # start with first page url; subsequent pages will be discovered via 'rel=next'
    # Use PQC-specific topic area for consistent PQC news collection
    base_url = "https://www.nist.gov/news-events/news/search?key=quantum&topic-op=or&topic-area-fieldset%5B%5D=248746"
    session = requests.Session()

    news_data = []
    next_url = base_url
    while next_url:
        response = session.get(next_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        articles = soup.find_all('article')
        if not articles:
            break

        for article in articles:
            # Safely extract title
            title_el = article.find('h3')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
        
            # Safely extract link
            link_el = article.find('a')
            if not link_el or not link_el.get('href'):
                continue
            link = link_el['href']
            if not link.startswith('http'):
                link = f"https://www.nist.gov{link}"
        
            # Safely extract date
            date_el = article.find('time')
            date = date_el['datetime'] if date_el else ""
        
            # Try to fetch real summary from the article page
            summary = ""
            try:
                article_response = session.get(link, timeout=5)
                article_soup = BeautifulSoup(article_response.content, 'html.parser')
                
                # First try meta description
                meta = article_soup.select_one('meta[name="description"]')
                if meta and meta.get('content'):
                    summary = meta['content'].strip()
                
                # If no meta description, try to extract first paragraph from content
                if not summary:
                    # Look for main content area
                    content = article_soup.select_one('main') or article_soup.select_one('[role="main"]') or article_soup.select_one('.field-type-text-long')
                    if content:
                        p = content.find('p')
                        if p:
                            summary = p.get_text(strip=True)
            except Exception:
                # If fetching fails, fall back to empty summary
                pass
        
            # Format date and generate summary
            formatted_date = format_date(date)
            final_summary = generate_news_summary(title, summary)

            news_data.append({
                'title': title,
                'link': link,
                'publish_date': formatted_date,
                'publish_date_raw': date,  # Keep raw ISO for sorting
                'summary': final_summary
            })
        # find next page link
        next_link = soup.select_one('a[rel="next"]')
        if next_link and next_link.get('href'):
            from urllib.parse import urljoin
            next_url = urljoin(next_url, next_link.get('href'))
        else:
            next_url = None
    return news_data