import requests
from bs4 import BeautifulSoup

def scrape_news():
    url = "https://www.nist.gov/news-events/news"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    news_data = []

    articles = soup.find_all('article')
    for article in articles:
        title = article.find('h3').get_text(strip=True)
        link = article.find('a')['href']
        if not link.startswith('http'):
            link = f"https://www.nist.gov{link}"
        date = article.find('time')['datetime']
        summary = article.find('p').get_text(strip=True)

        news_data.append({
            'title': title,
            'link': link,
            'date': date,
            'summary': summary
        })

    return news_data