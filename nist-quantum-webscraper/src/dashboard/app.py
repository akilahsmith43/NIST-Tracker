import streamlit as st
import sys
import os
from datetime import datetime

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from scraper.publications_scraper import scrape_publications
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
        publications = scrape_publications()
        presentations = scrape_presentations()
        news = scrape_news()
    
    # Check for new items and save data
    new_publications = storage.get_new_items('publications', publications)
    new_presentations = storage.get_new_items('presentations', presentations)
    new_news = storage.get_new_items('news', news)
    
    # Add new items to persistent notifications
    for pub in new_publications:
        storage.add_notification('publication', pub)
    for pres in new_presentations:
        storage.add_notification('presentation', pres)
    for article in new_news:
        storage.add_notification('news', article)
    
    # Get active notifications (within 24 hours)
    active_notifications = storage.get_active_notifications()
    
    # Save current data
    storage.save_data('publications', publications)
    storage.save_data('presentations', presentations)
    storage.save_data('news', news)
    
    # Display notifications
    notification_count = len(active_notifications)
    
    if notification_count > 0:
        st.sidebar.success(f"🎉 {notification_count} new item(s) found!")
        
        # Sort notifications by timestamp (newest first)
        active_notifications.sort(key=lambda x: x['timestamp'], reverse=True)
        
        for notification in active_notifications:
            item = notification['item']
            timestamp = notification['timestamp'].strftime("%m/%d %H:%M")
            
            if notification['type'] == 'publication':
                title = item.get('document_name', 'Unknown Publication')
                date_info = f" ({item.get('release_date', 'No date')})" if item.get('release_date') else ""
                st.sidebar.write(f"📄 [{timestamp}] {title}{date_info}")
            elif notification['type'] == 'presentation':
                title = item.get('document_name', 'Unknown Presentation')
                st.sidebar.write(f"🎤 [{timestamp}] {title}")
            elif notification['type'] == 'news':
                title = item.get('title', 'Unknown News')
                st.sidebar.write(f"📰 [{timestamp}] {title}")
    else:
        st.sidebar.info("No new items found since last check.")
    
    # Display data sections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.header("📄 Publications")
        st.write(f"Total: {len(publications)} items")
        if new_publications:
            st.success(f"🆕 {len(new_publications)} new publication(s)")
        
        for pub in publications:
            title_line = pub['document_name']
            if pub.get('series') or pub.get('document_number'):
                title_line = f"{pub.get('series','')} {pub.get('document_number','')}: {pub['document_name']}"
            with st.expander(title_line):
                if pub.get('status'):
                    st.write(f"**Status:** {pub['status']}")
                st.write(f"**Type:** {pub['resource_type']}")
                if pub.get('release_date'):
                    st.write(f"**Date:** {pub['release_date']}")
                if pub.get('summary'):
                    st.write(f"**Summary:** {pub['summary']}")
                if pub.get('link'):
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
