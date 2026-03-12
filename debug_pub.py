import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'nist-quantum-webscraper', 'src'))
import requests
from bs4 import BeautifulSoup
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'nist-quantum-webscraper', 'src'))
from scraper.publications_scraper import scrape_publications

# run the scraper
print('starting call')
items = scrape_publications()
print('got', len(items))
for i,item in enumerate(items[:10]):
    print(i, item)
print('last few items:')
for i,item in enumerate(items[-5:], start=len(items)-5):
    print(i, item.get('document_name'), 'summary:', item.get('summary','')[:60])

# inspect one of the CSRC pages
url = 'https://csrc.nist.gov/publications/final-pubs'
print('\nfetching raw page for diagnostics')
r = requests.get(url, timeout=10)
print('status', r.status_code, 'len', len(r.text))
print('look for pub-title-link substring:', 'pub-title-link' in r.text)
# print first chunk
print('--- head snippet ---')
print(r.text[:2000])
print('--------------------')

# check for any div with class or other markers
soup = BeautifulSoup(r.text, 'html.parser')
print('total tr tags', len(soup.find_all('tr')))
trs = soup.find_all('tr')
print('sample tr attrs', [tag.attrs for tag in trs[:5]])

# show first few rows html
for idx, tr in enumerate(trs[:3], start=1):
    print(f'--- row {idx} html ---')
    print(tr.prettify()[:1000])
    print('-------------------')

# inspect the NIST search topic page
url2 = 'https://www.nist.gov/publications/search/topic/249281'
r2 = requests.get(url2, timeout=10)
print('\nfetching search page diagnostics')
print('status', r2.status_code, 'len', len(r2.text))
print('--- search head snippet ---')
print(r2.text[:2000])
print('--------------------')
soup2 = BeautifulSoup(r2.text, 'html.parser')
print('views-row count', len(soup2.select('div.views-row')))
print('any h3 a?', len(soup2.select('h3 a')))
texts = [a.get_text(strip=True) for a in soup2.select('h3 a')[:5]]
print('sample h3 a text', texts)
print('nist-teaser count', len(soup2.select('.nist-teaser')))
if soup2.select('.nist-teaser'):
    teaser = soup2.select_one('.nist-teaser')
    print('first teaser html snippet:')
    print(teaser.prettify()[:1000])
# dump surrounding html for first h3 link
if texts:
    first = texts[0]
    idx = r2.text.find(first)
    if idx != -1:
        snippet = r2.text[idx-200:idx+200]
        print('around first title:', snippet)
print('contains /pubs/ links?', '/pubs/' in r2.text)
print('contains IR ', 'IR ' in r2.text)
