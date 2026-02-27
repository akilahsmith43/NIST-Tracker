def fetch_html(url):
    import requests
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def parse_html(html_content):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html_content, 'html.parser')

def extract_data_from_element(element, selectors):
    return {key: element.select_one(selector).get_text(strip=True) for key, selector in selectors.items()}

def format_date(date_string):
    from datetime import datetime
    return datetime.strptime(date_string, '%Y-%m-%d').date() if date_string else None

def clean_text(text):
    return text.strip() if text else ''