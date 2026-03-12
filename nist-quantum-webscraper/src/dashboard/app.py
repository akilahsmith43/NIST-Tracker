import streamlit as st
import sys
import os
from datetime import datetime

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from scraper.publications_scraper import (
    scrape_publications,
    scrape_all_publications,
    filter_publications,
)
from scraper.presentations_scraper import scrape_presentations
from scraper.news_scraper import scrape_news
from data.data_storage import DataStorage

def main():
    st.set_page_config(page_title="NIST Quantum Tracker", page_icon="🔬", layout="wide")
    st.title("🔬 NIST Quantum Information Science Tracker")
    
    # Initialize data storage
    storage = DataStorage()
    
    # Sidebar for notifications
    st.sidebar.header("Notifications")
    
    # Scrape data
    with st.spinner('Scraping NIST data...'):
        # use the helper that runs all relevant queries (final/draft/open)
        publications = scrape_all_publications()
        presentations = scrape_presentations()
        news = scrape_news()
    
    # Check for new items and save data
    new_publications = storage.get_new_items('publications', publications)
    new_presentations = storage.get_new_items('presentations', presentations)
    new_news = storage.get_new_items('news', news)

    # split publication sets for display
    finals = filter_publications(publications, include_final=True, include_drafts=False)
    drafts = filter_publications(publications, include_final=False, include_drafts=True)
    new_finals = filter_publications(new_publications, include_final=True, include_drafts=False)
    new_drafts = filter_publications(new_publications, include_final=False, include_drafts=True)
    
    # Save current data
    storage.save_data('publications', publications)
    storage.save_data('presentations', presentations)
    storage.save_data('news', news)
    
    # Display notifications
    notification_count = len(new_publications) + len(new_presentations) + len(new_news)
    
    if notification_count > 0:
        st.sidebar.success(f"🎉 {notification_count} new item(s) found!")
        
        if new_finals:
            st.sidebar.subheader("📄 New Final Publications:")
            for pub in new_finals:
                st.sidebar.write(f"• {pub['document_name']}")
        if new_drafts:
            st.sidebar.subheader("📝 New Draft Publications:")
            for pub in new_drafts:
                st.sidebar.write(f"• {pub['document_name']}")
        
        if new_presentations:
            st.sidebar.subheader("🎤 New Presentations:")
            for pres in new_presentations:
                st.sidebar.write(f"• {pres['document_name']}")
        
        if new_news:
            st.sidebar.subheader("📰 New News:")
            for article in new_news:
                st.sidebar.write(f"• {article['title']}")
    else:
        st.sidebar.info("No new items found since last check.")
    
    # Display data sections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.header("📄 Publications")
        st.write(f"Total: {len(publications)} items")
        if new_publications:
            st.success(f"🆕 {len(new_publications)} new publication(s)")
        
        st.subheader("Final documents")
        st.write(f"Total: {len(finals)} items")
        if new_finals:
            st.success(f"🆕 {len(new_finals)} new final publication(s)")
        for pub in finals:
            with st.expander(f"{pub['series']} {pub['document_number']}: {pub['document_name']}"):
                # status is not needed for publications; omit it
                st.write(f"**Type:** {pub['resource_type']}")
                if pub['link']:
                    st.markdown(f"[📄 View Document]({pub['link']})")
                st.write("---")

        st.subheader("Drafts / open for comment")
        st.write(f"Total: {len(drafts)} items")
        if new_drafts:
            st.success(f"🆕 {len(new_drafts)} new draft publication(s)")
        for pub in drafts:
            with st.expander(f"{pub['series']} {pub['document_number']}: {pub['document_name']}"):
                # status is not needed for publications; omit it
                st.write(f"**Type:** {pub['resource_type']}")
                if pub['link']:
                    st.markdown(f"[📄 View Document]({pub['link']})")
                st.write("---")
    
    with col2:
        st.header("🎤 Presentations")
        st.write(f"Total: {len(presentations)} items")
        if new_presentations:
            st.success(f"🆕 {len(new_presentations)} new presentation(s)")
        
        for pres in presentations:
            with st.expander(f"{pres['series']}: {pres['document_name']}"):
                st.write(f"**Status:** {pres['status']}")
                st.write(f"**Type:** {pres['resource_type']}")
                if pres['link']:
                    st.markdown(f"[🎤 View Presentation]({pres['link']})")
                st.write("---")
    
    with col3:
        st.header("📰 News")
        st.write(f"Total: {len(news)} items")
        if new_news:
            st.success(f"🆕 {len(new_news)} new news item(s)")
        
        for article in news:
            with st.expander(f"{article['title']}"):
                if article['publish_date']:
                    st.write(f"**Published:** {article['publish_date']}")
                if article['summary']:
                    st.write(f"**Summary:** {article['summary']}")
                if article['link']:
                    st.markdown(f"[📰 Read Article]({article['link']})")
                st.write("---")
    
    # Last update info
    st.sidebar.divider()
    st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
