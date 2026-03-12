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
    url = "https://www.nist.gov/news-events/news/search?key=quantum&topic-op=or&topic-area-fieldset%5B%5D=249281"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    news_data = []

    articles = soup.find_all('article')
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
        
        # Safely extract summary
        summary_el = article.find('p')
        summary = summary_el.get_text(strip=True) if summary_el else ""
        
        # Format date and generate summary
        formatted_date = format_date(date)
        final_summary = generate_news_summary(title, summary)

        news_data.append({
            'title': title,
            'link': link,
            'publish_date': formatted_date,
            'summary': final_summary
        })

    return news_data