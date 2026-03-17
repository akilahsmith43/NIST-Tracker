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
    
    # Initialize data storage with correct path
    storage_dir = os.path.join(os.path.dirname(__file__), 'data_storage')
    storage = DataStorage(storage_dir=storage_dir)
    
    # Sidebar for notifications
    st.sidebar.header("Notifications")
    
    # Scrape data
    with st.spinner('Scraping NIST data...'):
        # use the helper that runs all relevant queries (final/draft/open)
        publications = scrape_all_publications()
        presentations = scrape_presentations()
        news = scrape_news()
    
    # keep only publications from the past year
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=365)
    recent_pubs = []
    for pub in publications:
        raw = pub.get('release_date_raw')
        if raw:
            try:
                d = datetime.fromisoformat(raw)
                # normalize to naive datetime for comparison
                if d.tzinfo:
                    d = d.replace(tzinfo=None)
            except Exception:
                continue
            if d >= cutoff:
                recent_pubs.append(pub)
        # if we can't parse date, drop it
    publications = recent_pubs

    # keep only presentations from the past year
    recent_pres = []
    for pres in presentations:
        raw = pres.get('release_date')
        if raw:
            try:
                # Parse date in format "Month DD, YYYY"
                d = datetime.strptime(raw, '%B %d, %Y')
            except Exception:
                continue
            if d >= cutoff:
                recent_pres.append(pres)
        # if we can't parse date, drop it
    presentations = recent_pres

    # keep only news from the past year
    recent_news = []
    for article in news:
        raw = article.get('publish_date_raw')
        if raw:
            try:
                d = datetime.fromisoformat(raw)
                # normalize to naive datetime for comparison
                if d.tzinfo:
                    d = d.replace(tzinfo=None)
            except Exception:
                continue
            if d >= cutoff:
                recent_news.append(article)
        # if we can't parse date, drop it
    news = recent_news

    # Sort by date - newest first
    publications = sorted(publications, key=lambda x: x.get('release_date_raw', '') or x.get('release_date', ''), reverse=True)
    presentations = sorted(presentations, key=lambda x: x.get('release_date', ''), reverse=True)
    news = sorted(news, key=lambda x: x.get('publish_date_raw', ''), reverse=True)
    
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
    
    # Get all notifications (not just active ones)
    all_notifications = storage.load_notifications()
    
    # Filter notifications to only show items from the past year
    cutoff = datetime.now() - timedelta(days=365)
    filtered_notifications = []
    for n in all_notifications:
        item = n.get('item', {})
        item_date = None
        
        # Try to get the item's release/publish date
        if item.get('release_date_raw'):
            try:
                item_date = datetime.fromisoformat(item['release_date_raw'])
                if item_date.tzinfo:
                    item_date = item_date.replace(tzinfo=None)
            except Exception:
                continue
        elif item.get('publish_date_raw'):
            try:
                item_date = datetime.fromisoformat(item['publish_date_raw'])
                if item_date.tzinfo:
                    item_date = item_date.replace(tzinfo=None)
            except Exception:
                continue
        elif item.get('release_date'):
            try:
                item_date = datetime.strptime(item['release_date'], '%B %d, %Y')
            except Exception:
                continue
        
        if item_date and item_date >= cutoff:
            filtered_notifications.append(n)
    
    all_notifications = filtered_notifications
    
    # Save current data
    storage.save_data('publications', publications)
    storage.save_data('presentations', presentations)
    storage.save_data('news', news)
    
    # Display notifications
    notification_count = len(all_notifications)
    
    if notification_count > 0:
        # Separate notifications by type
        pub_notifications = [n for n in all_notifications if n.get('type') == 'publication']
        pres_notifications = [n for n in all_notifications if n.get('type') == 'presentation']
        news_notifications = [n for n in all_notifications if n.get('type') == 'news']
        
        # Separate by time periods — filter by the item's actual release/publish date,
        # not by when it was first scraped (notification timestamp).
        from datetime import datetime, timedelta
        now = datetime.now()

        def get_item_date(n):
            """Return a naive datetime for the item's release/publish date, or None."""
            item = n.get('item', {})
            raw = item.get('release_date_raw') or item.get('publish_date_raw')
            if raw:
                try:
                    d = datetime.fromisoformat(raw)
                    return d.replace(tzinfo=None) if d.tzinfo else d
                except Exception:
                    pass
            # fallback: presentations use a formatted string
            rel = item.get('release_date')
            if rel:
                try:
                    return datetime.strptime(rel, '%B %d, %Y')
                except Exception:
                    pass
            return None

        # Last week (7 days) — based on item release date
        week_ago = now - timedelta(days=7)
        week_notifications = [
            n for n in all_notifications
            if (d := get_item_date(n)) is not None and d >= week_ago
        ]

        week_pub = [n for n in week_notifications if n.get('type') == 'publication']
        week_pres = [n for n in week_notifications if n.get('type') == 'presentation']
        week_news = [n for n in week_notifications if n.get('type') == 'news']

        # Last two weeks (14 days) — based on item release date
        two_weeks_ago = now - timedelta(days=14)
        two_week_notifications = [
            n for n in all_notifications
            if (d := get_item_date(n)) is not None and d >= two_weeks_ago
        ]

        two_week_pub = [n for n in two_week_notifications if n.get('type') == 'publication']
        two_week_pres = [n for n in two_week_notifications if n.get('type') == 'presentation']
        two_week_news = [n for n in two_week_notifications if n.get('type') == 'news']
        
        # Last week section
        st.sidebar.subheader("📅 Last Week (7 days)")
        if week_notifications:
            if week_pub:
                st.sidebar.write("**📄 Publications:**")
                for notif in week_pub:
                    from html import escape
                    pub = notif.get('item', {})
                    title = escape(pub.get('document_name', 'Untitled')).replace('_','&#95;')
                    title = f"<span style=\"color:black\">{title}</span>"
                    st.sidebar.markdown(f"• {title}", unsafe_allow_html=True)
            
            if week_pres:
                st.sidebar.write("**🎤 Presentations:**")
                for notif in week_pres:
                    pres = notif.get('item', {})
                    st.sidebar.write(f"• {pres.get('document_name', 'Untitled')}")
            
            if week_news:
                st.sidebar.write("**📰 News:**")
                for notif in week_news:
                    article = notif.get('item', {})
                    st.sidebar.write(f"• {article.get('title', 'Untitled')}")
                    if article.get('summary'):
                        st.sidebar.caption(f"   Summary: {article['summary'][:100]}...")
        else:
            st.sidebar.write("No new items in the last week.")
        
        # Last two weeks section
        st.sidebar.subheader("📅 Last Two Weeks (14 days)")
        if two_week_notifications:
            if two_week_pub:
                st.sidebar.write("**📄 Publications:**")
                for notif in two_week_pub:
                    from html import escape
                    pub = notif.get('item', {})
                    title = escape(pub.get('document_name', 'Untitled')).replace('_','&#95;')
                    title = f"<span style=\"color:black\">{title}</span>"
                    st.sidebar.markdown(f"• {title}", unsafe_allow_html=True)
            
            if two_week_pres:
                st.sidebar.write("**🎤 Presentations:**")
                for notif in two_week_pres:
                    pres = notif.get('item', {})
                    st.sidebar.write(f"• {pres.get('document_name', 'Untitled')}")
            
            if two_week_news:
                st.sidebar.write("**📰 News:**")
                for notif in two_week_news:
                    article = notif.get('item', {})
                    st.sidebar.write(f"• {article.get('title', 'Untitled')}")
                    if article.get('summary'):
                        st.sidebar.caption(f"   Summary: {article['summary'][:100]}...")
        else:
            st.sidebar.write("No new items in the last two weeks.")
    else:
        st.sidebar.info("No new items found since last check.")
    
    # Display data sections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.header("📄 Publications")
        st.write(f"Total: {len(publications)} items")
        if new_publications:
            st.success(f"🆕 {len(new_publications)} new publication(s)")
        
        from html import escape
        for pub in publications:
            # header is just the title (no snippet)
            title = pub.get('document_name','Publication')
            # escape any HTML characters and replace underscores so markdown won't style
            safe_title = escape(title).replace('_','&#95;')
            header = safe_title
            with st.expander(header):
                # inside dropdown we no longer re-show the title
                if pub.get('summary'):
                    st.info(f"**Summary:** {pub['summary']}")
                else:
                    st.warning("No summary available for this publication.")
                st.divider()
                st.write(f"**Type:** {pub['resource_type']}")
                if pub.get('release_date'):
                    st.write(f"**Published:** {pub['release_date']}")
                if pub['link']:
                    st.markdown(f"[📄 View Document]({pub['link']})")
                st.write("---")
    
    with col2:
        st.header("🎤 Presentations")
        st.write(f"Total: {len(presentations)} items")
        if new_presentations:
            st.success(f"🆕 {len(new_presentations)} new presentation(s)")
        
        for pres in presentations:
            header = f"{pres['series']}: {pres['document_name']}"
            with st.expander(header):
                st.write(f"**Status:** {pres['status']}")
                st.write(f"**Type:** {pres['resource_type']}")
                if pres.get('release_date'):
                    st.write(f"**Published:** {pres['release_date']}")
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
                if article['summary']:
                    st.info(f"**Summary:** {article['summary']}")
                    st.divider()
                if article['publish_date']:
                    st.write(f"**Published:** {article['publish_date']}")
                if article['link']:
                    st.markdown(f"[📰 Read Article]({article['link']})")
                st.write("---")
    
    # Last update info
    st.sidebar.divider()
    st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()