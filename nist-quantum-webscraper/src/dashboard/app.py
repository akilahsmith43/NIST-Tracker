import streamlit as st
import sys
import os
import re
from datetime import datetime

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import from the scraper modules
try:
    # Try importing with the src directory in path
    from scraper.publications_scraper import (
        scrape_publications,
        scrape_all_publications,
        scrape_publications_past_year,
        filter_publications,
    )
    from scraper.presentations_scraper import scrape_presentations
    from scraper.news_scraper import scrape_news
    from scraper.pqc_scraper import scrape_all_pqc_data
    from scraper.ai_scraper import scrape_all_ai_data
    from data.data_storage import DataStorage
except ImportError as e:
    print(f"Import error: {e}")
    # Try absolute imports
    try:
        from src.scraper.publications_scraper import (
            scrape_publications,
            scrape_all_publications,
            scrape_publications_past_year,
            filter_publications,
        )
        from src.scraper.presentations_scraper import scrape_presentations
        from src.scraper.news_scraper import scrape_news
        from src.scraper.pqc_scraper import scrape_all_pqc_data
        from src.scraper.ai_scraper import scrape_all_ai_data
        from src.data.data_storage import DataStorage
    except ImportError as e2:
        print(f"Absolute import error: {e2}")
        # Final attempt - check if we can import the module directly
        import importlib.util
        import os
        
        # Try to load the module directly
        publications_scraper_path = os.path.join(src_dir, 'scraper', 'publications_scraper.py')
        spec = importlib.util.spec_from_file_location("publications_scraper", publications_scraper_path)
        publications_scraper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(publications_scraper)
        
        # Get the functions we need
        scrape_publications = publications_scraper.scrape_publications
        scrape_all_publications = publications_scraper.scrape_all_publications
        scrape_publications_past_year = publications_scraper.scrape_publications_past_year
        filter_publications = publications_scraper.filter_publications
        
        # Load other modules similarly
        presentations_scraper_path = os.path.join(src_dir, 'scraper', 'presentations_scraper.py')
        spec2 = importlib.util.spec_from_file_location("presentations_scraper", presentations_scraper_path)
        presentations_scraper = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(presentations_scraper)
        scrape_presentations = presentations_scraper.scrape_presentations
        
        news_scraper_path = os.path.join(src_dir, 'scraper', 'news_scraper.py')
        spec3 = importlib.util.spec_from_file_location("news_scraper", news_scraper_path)
        news_scraper = importlib.util.module_from_spec(spec3)
        spec3.loader.exec_module(news_scraper)
        scrape_news = news_scraper.scrape_news
        
        pqc_scraper_path = os.path.join(src_dir, 'scraper', 'pqc_scraper.py')
        spec4 = importlib.util.spec_from_file_location("pqc_scraper", pqc_scraper_path)
        pqc_scraper = importlib.util.module_from_spec(spec4)
        spec4.loader.exec_module(pqc_scraper)
        scrape_all_pqc_data = pqc_scraper.scrape_all_pqc_data

        ai_scraper_path = os.path.join(src_dir, 'scraper', 'ai_scraper.py')
        spec_ai = importlib.util.spec_from_file_location("ai_scraper", ai_scraper_path)
        ai_scraper = importlib.util.module_from_spec(spec_ai)
        spec_ai.loader.exec_module(ai_scraper)
        scrape_all_ai_data = ai_scraper.scrape_all_ai_data
        
        data_storage_path = os.path.join(src_dir, 'data', 'data_storage.py')
        spec5 = importlib.util.spec_from_file_location("data_storage", data_storage_path)
        data_storage = importlib.util.module_from_spec(spec5)
        spec5.loader.exec_module(data_storage)
        DataStorage = data_storage.DataStorage

def sanitize_link(link):
    """Sanitize links to prevent corruption in markdown rendering"""
    if not link:
        return link
    
    # Pattern to detect corrupted links in format [](url)<url>
    corrupted_pattern = r'^\[\]\((.*?)\)<\1>$'
    match = re.match(corrupted_pattern, link)
    if match:
        # Extract the clean URL
        return match.group(1)
    
    return link

def main():
    st.set_page_config(page_title="NIST Quantum Tracker", page_icon="🔬", layout="wide")
    
    # Sidebar navigation
    st.sidebar.title("🔬 Navigation")
    page = st.sidebar.selectbox("Choose a page:", ["Quantum Information Science", "Post-Quantum Cryptography", "Artificial Intelligence"])
    
    if page == "Quantum Information Science":
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
    
    elif page == "Post-Quantum Cryptography":
        st.title("🔐 NIST Post-Quantum Cryptography Tracker")
        
        # Initialize data storage with correct path
        storage_dir = os.path.join(os.path.dirname(__file__), 'data_storage')
        storage = DataStorage(storage_dir=storage_dir)
        
        # Sidebar for notifications
        st.sidebar.header("Notifications")
        
        # Scrape PQC data - use ONLY the PQC-specific URLs
        with st.spinner('Scraping Post-Quantum Cryptography data...'):
            # Get publications ONLY from PQC-specific URLs (past year only)
            pqc_publications = scrape_all_pqc_data().get('publications', [])
            
            # Get PQC presentations and news from the general PQC scraper
            pqc_data = scrape_all_pqc_data()
            pqc_presentations = pqc_data.get('presentations', [])
            pqc_news = pqc_data.get('news', [])

        # keep only PQC presentations from the past year
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=365)
        recent_pqc_pres = []
        for pres in pqc_presentations:
            raw = pres.get('release_date')
            if raw:
                try:
                    d = datetime.strptime(raw, '%B %d, %Y')
                except Exception:
                    continue
                if d >= cutoff:
                    recent_pqc_pres.append(pres)
        pqc_presentations = recent_pqc_pres

        # keep only PQC news from the past year
        recent_pqc_news = []
        for article in pqc_news:
            raw = article.get('publish_date_raw')
            if raw:
                try:
                    d = datetime.fromisoformat(raw)
                    if d.tzinfo:
                        d = d.replace(tzinfo=None)
                except Exception:
                    continue
                if d >= cutoff:
                    recent_pqc_news.append(article)
        
        # If nothing is found in strict 1-year window, fall back to 2 years to provide a populated view
        if not recent_pqc_news:
            fallback_cutoff = datetime.now() - timedelta(days=730)
            for article in pqc_news:
                raw = article.get('publish_date_raw')
                if raw:
                    try:
                        d = datetime.fromisoformat(raw)
                        if d.tzinfo:
                            d = d.replace(tzinfo=None)
                    except Exception:
                        continue
                    if d >= fallback_cutoff:
                        recent_pqc_news.append(article)

        pqc_news = recent_pqc_news

        # Sort by date - newest first
        pqc_publications = sorted(pqc_publications, key=lambda x: x.get('release_date_raw', ''), reverse=True)
        pqc_presentations = sorted(pqc_presentations, key=lambda x: x.get('release_date', ''), reverse=True)
        pqc_news = sorted(pqc_news, key=lambda x: x.get('publish_date_raw', ''), reverse=True)
        
        # Check for new PQC items and save data
        new_pqc_items = storage.get_new_pqc_items(pqc_data)
        new_pqc_publications = new_pqc_items.get('publications', [])
        new_pqc_presentations = new_pqc_items.get('presentations', [])
        new_pqc_news = new_pqc_items.get('news', [])
        
        # Add new PQC items to persistent notifications
        for pub in new_pqc_publications:
            storage.add_notification('pqc_publication', pub)
        for pres in new_pqc_presentations:
            storage.add_notification('pqc_presentation', pres)
        for article in new_pqc_news:
            storage.add_notification('pqc_news', article)
        
        # Get all PQC notifications (not just active ones)
        all_pqc_notifications = storage.load_notifications()
        
        # Filter PQC notifications to only show items from the past year
        filtered_pqc_notifications = []
        for n in all_pqc_notifications:
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
                filtered_pqc_notifications.append(n)
        
        all_pqc_notifications = filtered_pqc_notifications
        
        # Save current PQC data
        storage.save_pqc_data(pqc_data)
        
        # Display PQC notifications with two-tier system
        pqc_notification_count = len(all_pqc_notifications)
        
        if pqc_notification_count > 0:
            # Get categorized notifications using the new method
            categorized_notifications = storage.get_notifications_by_week()
            week_1_notifications = categorized_notifications.get('week_1', [])
            week_2_notifications = categorized_notifications.get('week_2', [])
            
            # Separate by type for each week
            week_1_pub = [n for n in week_1_notifications if n.get('type') == 'pqc_publication']
            week_1_pres = [n for n in week_1_notifications if n.get('type') == 'pqc_presentation']
            week_1_news = [n for n in week_1_notifications if n.get('type') == 'pqc_news']
            
            week_2_pub = [n for n in week_2_notifications if n.get('type') == 'pqc_publication']
            week_2_pres = [n for n in week_2_notifications if n.get('type') == 'pqc_presentation']
            week_2_news = [n for n in week_2_notifications if n.get('type') == 'pqc_news']
            
            # Week 1 section (0-7 days)
            st.sidebar.subheader("📅 Week 1 (0-7 days)")
            if week_1_notifications:
                if week_1_pub:
                    st.sidebar.write("**🔐 PQC Publications:**")
                    for notif in week_1_pub:
                        from html import escape
                        pub = notif.get('item', {})
                        title = escape(pub.get('document_name', 'Untitled')).replace('_','&#95;')
                        title = f"<span style=\"color:black\">{title}</span>"
                        st.sidebar.markdown(f"• {title}", unsafe_allow_html=True)
                
                if week_1_pres:
                    st.sidebar.write("**🔐 PQC Presentations:**")
                    for notif in week_1_pres:
                        pres = notif.get('item', {})
                        st.sidebar.write(f"• {pres.get('document_name', 'Untitled')}")
                
                if week_1_news:
                    st.sidebar.write("**🔐 PQC News:**")
                    for notif in week_1_news:
                        article = notif.get('item', {})
                        st.sidebar.write(f"• {article.get('title', 'Untitled')}")
                        if article.get('summary'):
                            st.sidebar.caption(f"   Summary: {article['summary'][:100]}...")
            else:
                st.sidebar.write("No new PQC items in Week 1.")
            
            # Week 2 section (8-14 days)
            st.sidebar.subheader("📅 Week 2 (8-14 days)")
            if week_2_notifications:
                if week_2_pub:
                    st.sidebar.write("**🔐 PQC Publications:**")
                    for notif in week_2_pub:
                        from html import escape
                        pub = notif.get('item', {})
                        title = escape(pub.get('document_name', 'Untitled')).replace('_','&#95;')
                        title = f"<span style=\"color:black\">{title}</span>"
                        st.sidebar.markdown(f"• {title}", unsafe_allow_html=True)
                
                if week_2_pres:
                    st.sidebar.write("**🔐 PQC Presentations:**")
                    for notif in week_2_pres:
                        pres = notif.get('item', {})
                        st.sidebar.write(f"• {pres.get('document_name', 'Untitled')}")
                
                if week_2_news:
                    st.sidebar.write("**🔐 PQC News:**")
                    for notif in week_2_news:
                        article = notif.get('item', {})
                        st.sidebar.write(f"• {article.get('title', 'Untitled')}")
                        if article.get('summary'):
                            st.sidebar.caption(f"   Summary: {article['summary'][:100]}...")
            else:
                st.sidebar.write("No new PQC items in Week 2.")
        else:
            st.sidebar.info("No new PQC items found since last check.")
        
        # Display last scrape information
        scrape_info = storage.get_last_scrape_info()
        st.sidebar.divider()
        st.sidebar.subheader("📊 Scrape Session Info")
        if scrape_info['last_scrape']:
            from datetime import datetime
            last_scrape_dt = datetime.fromisoformat(scrape_info['last_scrape'])
            st.sidebar.write(f"**Last Scrape:** {last_scrape_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            st.sidebar.write(f"**Total Notifications:** {scrape_info['scrape_count']}")
            st.sidebar.write(f"**New Items This Session:** {scrape_info['new_items_this_session']}")
        else:
            st.sidebar.write("**No scrape data available**")
    
    # keep only publications from the past year
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=365)
    
    # Only process data if we're on the Quantum Information Science page
    if page == "Quantum Information Science":
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

    # Only process Quantum Information Science data if we're on that page
    if page == "Quantum Information Science":
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
    else:
        # For PQC page, set empty values to avoid undefined variable errors
        publications = []
        presentations = []
        news = []
        new_publications = []
        new_presentations = []
        new_news = []
        all_notifications = []
    
    # Display notifications
    notification_count = len(all_notifications)
    
    if notification_count > 0:
        # Get categorized notifications using the new method
        categorized_notifications = storage.get_notifications_by_week()
        week_1_notifications = categorized_notifications.get('week_1', [])
        week_2_notifications = categorized_notifications.get('week_2', [])
        
        # Separate by type for each week
        week_1_pub = [n for n in week_1_notifications if n.get('type') == 'publication']
        week_1_pres = [n for n in week_1_notifications if n.get('type') == 'presentation']
        week_1_news = [n for n in week_1_notifications if n.get('type') == 'news']
        
        week_2_pub = [n for n in week_2_notifications if n.get('type') == 'publication']
        week_2_pres = [n for n in week_2_notifications if n.get('type') == 'presentation']
        week_2_news = [n for n in week_2_notifications if n.get('type') == 'news']
        
        # Week 1 section (0-7 days)
        st.sidebar.subheader("📅 Week 1 (0-7 days)")
        if week_1_notifications:
            if week_1_pub:
                st.sidebar.write("**📄 Publications:**")
                for notif in week_1_pub:
                    from html import escape
                    pub = notif.get('item', {})
                    title = escape(pub.get('document_name', 'Untitled')).replace('_','&#95;')
                    title = f"<span style=\"color:black\">{title}</span>"
                    st.sidebar.markdown(f"• {title}", unsafe_allow_html=True)
            
            if week_1_pres:
                st.sidebar.write("**🎤 Presentations:**")
                for notif in week_1_pres:
                    pres = notif.get('item', {})
                    st.sidebar.write(f"• {pres.get('document_name', 'Untitled')}")
            
            if week_1_news:
                st.sidebar.write("**📰 News:**")
                for notif in week_1_news:
                    article = notif.get('item', {})
                    st.sidebar.write(f"• {article.get('title', 'Untitled')}")
                    if article.get('summary'):
                        st.sidebar.caption(f"   Summary: {article['summary'][:100]}...")
        else:
            st.sidebar.write("No new items in Week 1.")
        
        # Week 2 section (8-14 days)
        st.sidebar.subheader("📅 Week 2 (8-14 days)")
        if week_2_notifications:
            if week_2_pub:
                st.sidebar.write("**📄 Publications:**")
                for notif in week_2_pub:
                    from html import escape
                    pub = notif.get('item', {})
                    title = escape(pub.get('document_name', 'Untitled')).replace('_','&#95;')
                    title = f"<span style=\"color:black\">{title}</span>"
                    st.sidebar.markdown(f"• {title}", unsafe_allow_html=True)
            
            if week_2_pres:
                st.sidebar.write("**🎤 Presentations:**")
                for notif in week_2_pres:
                    pres = notif.get('item', {})
                    st.sidebar.write(f"• {pres.get('document_name', 'Untitled')}")
            
            if week_2_news:
                st.sidebar.write("**📰 News:**")
                for notif in week_2_news:
                    article = notif.get('item', {})
                    st.sidebar.write(f"• {article.get('title', 'Untitled')}")
                    if article.get('summary'):
                        st.sidebar.caption(f"   Summary: {article['summary'][:100]}...")
        else:
            st.sidebar.write("No new items in Week 2.")
    else:
        st.sidebar.info("No new items found since last check.")
    
    # Display data sections
    if page == "Post-Quantum Cryptography":
        # Display PQC data sections
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.header("📄 Publications")
            st.write(f"Total: {len(pqc_publications)} items")
            if new_pqc_publications:
                st.success(f"🆕 {len(new_pqc_publications)} new publication(s)")
            
            from html import escape
            for pub in pqc_publications:
                # header includes category for context
                title = pub.get('document_name','PQC Publication')
                category = pub.get('category', '')
                if category:
                    header = f"{category}: {title}"
                else:
                    header = title
                
                # escape any HTML characters and replace underscores so markdown won't style
                safe_header = escape(header).replace('_','&#95;')
                with st.expander(safe_header):
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
                        sanitized_link = sanitize_link(pub['link'])
                        st.markdown(f"[📄 View Document]({sanitized_link})")
                    st.write("---")
        
        with col2:
            st.header("🎤 Presentations")
            st.write(f"Total: {len(pqc_presentations)} items")
            if new_pqc_presentations:
                st.success(f"🆕 {len(new_pqc_presentations)} new presentation(s)")
            
            for pres in pqc_presentations:
                header = f"{pres['series']}: {pres['document_name']}"
                with st.expander(header):
                    st.write(f"**Status:** {pres['status']}")
                    st.write(f"**Type:** {pres['resource_type']}")
                    if pres.get('release_date'):
                        st.write(f"**Published:** {pres['release_date']}")
                    if pres['link']:
                        sanitized_link = sanitize_link(pres['link'])
                        st.markdown(f"[🎤 View Presentation]({sanitized_link})")
                    st.write("---")
        
        with col3:
            st.header("📰 News")
            st.write(f"Total: {len(pqc_news)} items")
            if new_pqc_news:
                st.success(f"🆕 {len(new_pqc_news)} new news item(s)")
            
            for article in pqc_news:
                with st.expander(f"{article['title']}"):
                    if article['summary']:
                        st.info(f"**Summary:** {article['summary']}")
                        st.divider()
                    if article['publish_date']:
                        st.write(f"**Published:** {article['publish_date']}")
                    if article['link']:
                        sanitized_link = sanitize_link(article['link'])
                        st.markdown(f"[📰 Read Article]({sanitized_link})")
                    st.write("---")
        
        # PQC Last update info
        st.sidebar.divider()
        st.sidebar.caption(f"PQC Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    elif page == "Artificial Intelligence":
        st.title("🤖 NIST Artificial Intelligence Tracker")
        storage_dir = os.path.join(os.path.dirname(__file__), 'data_storage')
        storage = DataStorage(storage_dir=storage_dir)
        st.sidebar.header("Notifications")

        with st.spinner('Scraping Artificial Intelligence data...'):
            ai_data = scrape_all_ai_data()
            ai_publications = ai_data.get('publications', [])
            ai_presentations = ai_data.get('presentations', [])
            ai_news = ai_data.get('news', [])

        cutoff = datetime.now() - timedelta(days=365)
        def _keep_recent(items, date_key):
            output = []
            for item in items:
                raw = item.get(date_key, '')
                if not raw:
                    continue
                dt = None
                try:
                    dt = datetime.fromisoformat(raw)
                except Exception:
                    try:
                        dt = datetime.strptime(raw, '%B %d, %Y')
                    except Exception:
                        continue
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                if dt >= cutoff:
                    output.append(item)
            return output

        ai_publications = _keep_recent(ai_publications, 'release_date_raw')
        ai_presentations = _keep_recent(ai_presentations, 'release_date')
        ai_news = _keep_recent(ai_news, 'publish_date_raw')

        new_ai_pubs = storage.get_new_items('ai_publications', ai_publications)
        new_ai_pres = storage.get_new_items('ai_presentations', ai_presentations)
        new_ai_news = storage.get_new_items('ai_news', ai_news)

        for pub in new_ai_pubs:
            storage.add_notification('ai_publication', pub)
        for pres in new_ai_pres:
            storage.add_notification('ai_presentation', pres)
        for article in new_ai_news:
            storage.add_notification('ai_news', article)

        # Save current AI data
        storage.save_ai_data(ai_data)
        
        # Get all AI notifications and organize by week
        all_notifications = storage.load_notifications()
        ai_notifications = [n for n in all_notifications if n.get('type', '').startswith('ai_')]
        
        # Get categorized notifications using the new method
        categorized_notifications = storage.get_notifications_by_week()
        week_1_notifications = categorized_notifications.get('week_1', [])
        week_2_notifications = categorized_notifications.get('week_2', [])
        
        # Filter to only AI notifications
        week_1_ai = [n for n in week_1_notifications if n.get('type', '').startswith('ai_')]
        week_2_ai = [n for n in week_2_notifications if n.get('type', '').startswith('ai_')]
        
        # Separate by type for each week
        week_1_ai_pub = [n for n in week_1_ai if n.get('type') == 'ai_publication']
        week_1_ai_pres = [n for n in week_1_ai if n.get('type') == 'ai_presentation']
        week_1_ai_news = [n for n in week_1_ai if n.get('type') == 'ai_news']
        
        week_2_ai_pub = [n for n in week_2_ai if n.get('type') == 'ai_publication']
        week_2_ai_pres = [n for n in week_2_ai if n.get('type') == 'ai_presentation']
        week_2_ai_news = [n for n in week_2_ai if n.get('type') == 'ai_news']
        
        # Week 1 section (0-7 days)
        st.sidebar.subheader("📅 Week 1 (0-7 days)")
        if week_1_ai:
            if week_1_ai_pub:
                st.sidebar.write("**🤖 AI Publications:**")
                for notif in week_1_ai_pub:
                    from html import escape
                    pub = notif.get('item', {})
                    title = escape(pub.get('document_name', 'Untitled')).replace('_','&#95;')
                    title = f"<span style=\"color:black\">{title}</span>"
                    st.sidebar.markdown(f"• {title}", unsafe_allow_html=True)
            
            if week_1_ai_pres:
                st.sidebar.write("**🤖 AI Presentations:**")
                for notif in week_1_ai_pres:
                    pres = notif.get('item', {})
                    st.sidebar.write(f"• {pres.get('document_name', 'Untitled')}")
            
            if week_1_ai_news:
                st.sidebar.write("**🤖 AI News:**")
                for notif in week_1_ai_news:
                    article = notif.get('item', {})
                    st.sidebar.write(f"• {article.get('title', 'Untitled')}")
                    if article.get('summary'):
                        st.sidebar.caption(f"   Summary: {article['summary'][:100]}...")
        else:
            st.sidebar.write("No new AI items in Week 1.")
        
        # Week 2 section (8-14 days)
        st.sidebar.subheader("📅 Week 2 (8-14 days)")
        if week_2_ai:
            if week_2_ai_pub:
                st.sidebar.write("**🤖 AI Publications:**")
                for notif in week_2_ai_pub:
                    from html import escape
                    pub = notif.get('item', {})
                    title = escape(pub.get('document_name', 'Untitled')).replace('_','&#95;')
                    title = f"<span style=\"color:black\">{title}</span>"
                    st.sidebar.markdown(f"• {title}", unsafe_allow_html=True)
            
            if week_2_ai_pres:
                st.sidebar.write("**🤖 AI Presentations:**")
                for notif in week_2_ai_pres:
                    pres = notif.get('item', {})
                    st.sidebar.write(f"• {pres.get('document_name', 'Untitled')}")
            
            if week_2_ai_news:
                st.sidebar.write("**🤖 AI News:**")
                for notif in week_2_ai_news:
                    article = notif.get('item', {})
                    st.sidebar.write(f"• {article.get('title', 'Untitled')}")
                    if article.get('summary'):
                        st.sidebar.caption(f"   Summary: {article['summary'][:100]}...")
        else:
            st.sidebar.write("No new AI items in Week 2.")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.header("📄 AI Publications")
            st.write(f"Total: {len(ai_publications)}")
            if new_ai_pubs:
                st.success(f"🆕 {len(new_ai_pubs)} new publication(s)")
            for pub in ai_publications:
                title = pub.get('document_name', 'AI Publication')
                category = pub.get('category', '')
                header = f"{category}: {title}" if category else title
                with st.expander(header):
                    if pub.get('summary'):
                        st.info(f"**Summary:** {pub['summary']}")
                    if pub.get('release_date'):
                        st.write(f"**Published:** {pub['release_date']}")
                    if pub.get('link'):
                        sanitized_link = sanitize_link(pub['link'])
                        st.markdown(f"[📄 View Document]({sanitized_link})")

        with col2:
            st.header("🎤 AI Presentations")
            st.write(f"Total: {len(ai_presentations)}")
            if new_ai_pres:
                st.success(f"🆕 {len(new_ai_pres)} new presentation(s)")
            for pres in ai_presentations:
                label = pres.get('document_name', 'AI Presentation')
                with st.expander(label):
                    st.write(f"**Status:** {pres.get('status', '')}")
                    if pres.get('release_date'):
                        st.write(f"**Published:** {pres['release_date']}")
                    if pres.get('link'):
                        sanitized_link = sanitize_link(pres['link'])
                        st.markdown(f"[🎤 View Presentation]({sanitized_link})")

        with col3:
            st.header("📰 AI News")
            st.write(f"Total: {len(ai_news)}")
            if new_ai_news:
                st.success(f"🆕 {len(new_ai_news)} new news item(s)")
            for article in ai_news:
                title = article.get('title', 'AI News')
                with st.expander(title):
                    if article.get('summary'):
                        st.info(f"**Summary:** {article['summary']}")
                    if article.get('publish_date'):
                        st.write(f"**Published:** {article['publish_date']}")
                    if article.get('link'):
                        sanitized_link = sanitize_link(article['link'])
                        st.markdown(f"[📰 Read Article]({sanitized_link})")

        st.sidebar.divider()
        st.sidebar.caption(f"AI Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    else:
        # Display regular Quantum Information Science data sections
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
                        sanitized_link = sanitize_link(pub['link'])
                        st.markdown(f"[📄 View Document]({sanitized_link})")
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
                        sanitized_link = sanitize_link(pres['link'])
                        st.markdown(f"[🎤 View Presentation]({sanitized_link})")
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
                        sanitized_link = sanitize_link(article['link'])
                        st.markdown(f"[📰 Read Article]({sanitized_link})")
                    st.write("---")
    
    # Last update info
    st.sidebar.divider()
    st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()