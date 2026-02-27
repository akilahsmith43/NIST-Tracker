import streamlit as st
from src.scraper.publications_scraper import scrape_publications
from src.scraper.presentations_scraper import scrape_presentations
from src.scraper.news_scraper import scrape_news

def main():
    st.title("NIST Quantum Information Science Dashboard")

    # Scrape data
    publications = scrape_publications()
    presentations = scrape_presentations()
    news = scrape_news()

    # Display Publications
    st.header("Publications")
    for pub in publications:
        st.subheader(pub['document_name'])
        st.write(f"Number: {pub['document_number']}")
        st.write(f"Series: {pub['series']}")
        st.write(f"Status: {pub['status']}")
        st.write(f"Release Date: {pub['release_date']}")
        st.write(f"Resource Type: {pub['resource_type']}")
        st.write(f"[Link]({pub['link']})")
        st.write("---")

    # Display Presentations
    st.header("Presentations")
    for pres in presentations:
        st.subheader(pres['document_name'])
        st.write(f"Number: {pres['document_number']}")
        st.write(f"Series: {pres['series']}")
        st.write(f"Status: {pres['status']}")
        st.write(f"Release Date: {pres['release_date']}")
        st.write(f"Resource Type: {pres['resource_type']}")
        st.write(f"[Link]({pres['link']})")
        st.write("---")

    # Display News
    st.header("News")
    for article in news:
        st.subheader(article['title'])
        st.write(f"Published on: {article['publish_date']}")
        st.write(f"[Read more]({article['link']})")
        st.write("---")

if __name__ == "__main__":
    main()