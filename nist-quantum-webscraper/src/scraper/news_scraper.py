import requests
from bs4 import BeautifulSoup

def scrape_news():
    # URL for NIST news with quantum search filter
    url = "https://www.nist.gov/news-events/news/search?key=quantum&topic-op=or"
    news_data = []

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find news articles
        articles = soup.select('article[class*="nist-teaser"]')
        for article in articles:
            # Get the title link
            title_link = article.select_one('a[href*="/news-events/news/"]')
            if not title_link:
                continue
                
            title = title_link.get_text(strip=True)
            link = title_link['href']
            
            # Make link absolute if needed
            if link and not link.startswith('http'):
                link = f"https://www.nist.gov{link}"
            
            # Try to get publish date
            date_elem = article.select_one('time')
            date = date_elem.get('datetime', '') if date_elem else ''
            
            # Try to get summary
            summary_elem = article.select_one('p')
            summary = summary_elem.get_text(strip=True) if summary_elem else ''

            news_data.append({
                'title': title,
                'link': link,
                'publish_date': date,
                'summary': summary
            })
    except Exception as e:
        print(f"Error scraping news: {e}")

    return news_data
