import requests
from bs4 import BeautifulSoup

# Test the new CSRC filtered search URL for quantum
url_final = 'https://csrc.nist.gov/publications/search?sortBy-lg=releasedate+DESC&viewMode-lg=brief&ipp-lg=all&status-lg=Final&series-lg=FIPS%2CSP%2CIR%2CCSWP%2CTN%2CVTS%2CAI%2CGCR%2CProject+Description&topics-lg=27501%7Cquantum+information+science&topicsMatch-lg=ANY&controlsMatch-lg=ANY'

print('Fetching CSRC filtered Final publications URL...')
r = requests.get(url_final, timeout=10)
print(f'Status: {r.status_code}, Length: {len(r.text)}')

soup = BeautifulSoup(r.text, 'html.parser')

# Check if content is actually in the page
print(f'Checking page content...')
print(f'Body text length: {len(soup.body.get_text() if soup.body else "")}')
print(f'Looking for quantum in text: {"quantum" in r.text.lower()}')

# Look at the actual visible text
body_text = soup.get_text()[:1000]
print(f'First 500 chars of page text:\n{body_text}')

# Check for specific publication identifiers
print(f'\nLooking for "IR " (publication series): {"IR " in r.text}')
print(f'Looking for "NIST": {"NIST" in r.text}')

# Print full HTML snippet to understand structure
print('\nFull head + partial body:')
print(r.text[1000:3000])
    
# Also test the 4th link
print('\n' + '='*60)
url_topic = 'https://www.nist.gov/publications/search/topic/249281'
print(f'\nFetching topic search URL...')
r2 = requests.get(url_topic, timeout=10)
print(f'Status: {r2.status_code}, Length: {len(r2.text)}')

soup2 = BeautifulSoup(r2.text, 'html.parser')
teasers = soup2.select('article.nist-teaser')
print(f'Found {len(teasers)} nist-teaser articles')

if teasers:
    print('\nFirst teaser titles:')
    for t in teasers[:5]:
        title = t.select_one('h3.nist-teaser__title a')
        if title:
            print(f'  - {title.get_text(strip=True)[:60]}')
