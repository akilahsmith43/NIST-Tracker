import requests
from bs4 import BeautifulSoup

def scrape_news():
    url = "https://www.nist.gov/news-events/news"
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

        news_data.append({
            'title': title,
            'link': link,
            'publish_date': date,
            'summary': summary
        })

    return news_data