import streamlit as st
import sys
import os
import re
import json
from datetime import datetime, timedelta
from urllib.parse import urlsplit

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

def dedupe_notifications_for_sidebar(notifications):
    """Deduplicate notifications by what users see in the sidebar."""
    selected = {}

    def _score_notification_link(notification):
        item = notification.get('item', {})
        link = item.get('link') or ''
        if not link:
            return 0

        sanitized = sanitize_link(link)
        try:
            parsed = urlsplit(sanitized)
        except Exception:
            return 0

        score = 0
        path = parsed.path.rstrip('/')
        hostname = parsed.netloc.lower()
        notification_type = notification.get('type', '')

        # Prefer real document pages over section homepages.
        if path and path != '':
            score += 10
        if path.count('/') > 1:
            score += 10

        # AI/general items are typically canonical on www.nist.gov.
        if hostname == 'www.nist.gov' and (notification_type.startswith('ai_') or notification_type in {'publication', 'presentation', 'news'}):
            score += 20

        # PQC items usually live on CSRC.
        if hostname == 'csrc.nist.gov' and notification_type.startswith('pqc_'):
            score += 20

        # Prefer links that look like direct content pages.
        if any(segment in path for segment in ('/publications/', '/news-events/news/', '/presentations/')):
            score += 10

        # Avoid bare homepages.
        if path in {'', '/'}:
            score -= 50

        return score

    for notif in notifications:
        item = notif.get('item', {})
        label = (item.get('document_name') or item.get('title') or '').strip().lower()
        if not label:
            label = (item.get('link') or '').strip().lower()
        key = f"{notif.get('type', '')}::{label}"

        current = selected.get(key)
        if current is None or _score_notification_link(notif) > _score_notification_link(current):
            selected[key] = notif

    return list(selected.values())

def render_sidebar_notification_item(label, link):
    """Render a sidebar notification as a clickable bullet when a link exists."""
    safe_label = (label or 'Untitled')
    safe_label = safe_label.replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('_', '\\_')
    if link:
        st.sidebar.markdown(f"• [{safe_label}]({sanitize_link(link)})")
    else:
        st.sidebar.markdown(f"• {safe_label}")

def group_notifications_for_sidebar(notifications, section_specs):
    """Group and deduplicate notifications for sidebar rendering."""
    grouped = {}
    for notification_type, _, _, _ in section_specs:
        grouped[notification_type] = dedupe_notifications_for_sidebar(
            [n for n in notifications if n.get('type') == notification_type]
        )
    return grouped

def render_weekly_notifications(grouped_notifications, empty_message=None):
    """Render a weekly notifications block in the sidebar."""
    has_items = False
    for heading, notifications, label_key, summary_key in grouped_notifications:
        if not notifications:
            continue
        has_items = True
        st.sidebar.write(f"**{heading}:**")
        for notif in notifications:
            item = notif.get('item', {})
            render_sidebar_notification_item(item.get(label_key, 'Untitled'), item.get('link'))
            if summary_key and item.get(summary_key):
                st.sidebar.caption(f"   Summary: {item[summary_key][:100]}...")

    if not has_items and empty_message:
        st.sidebar.write(empty_message)

def render_two_week_notification_sidebar(week_1_notifications, week_2_notifications, section_specs, empty_week_1_message=None, empty_week_2_message=None):
    """Render Past 1 Week and Past 2 Weeks notification sections."""
    week_1_grouped = group_notifications_for_sidebar(week_1_notifications, section_specs)
    week_2_grouped = group_notifications_for_sidebar(week_2_notifications, section_specs)

    st.sidebar.subheader("📅 Past 1 Week (0-7 days)")
    render_weekly_notifications(
        [(heading, week_1_grouped[notification_type], label_key, summary_key) for notification_type, heading, label_key, summary_key in section_specs],
        empty_week_1_message,
    )

    st.sidebar.subheader("📅 Past 2 Weeks (8-14 days)")
    render_weekly_notifications(
        [(heading, week_2_grouped[notification_type], label_key, summary_key) for notification_type, heading, label_key, summary_key in section_specs],
        empty_week_2_message,
    )

def parse_dashboard_date(raw_value):
    """Parse supported dashboard date formats into a naive datetime."""
    if not raw_value:
        return None

    for parser in (datetime.fromisoformat, lambda value: datetime.strptime(value, '%B %d, %Y')):
        try:
            parsed = parser(raw_value)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except Exception:
            continue

    return None

def get_item_date(item, date_keys):
    """Return the first parseable date found on an item."""
    for key in date_keys:
        parsed = parse_dashboard_date(item.get(key))
        if parsed:
            return parsed
    return None

def filter_items_since(items, cutoff, date_keys):
    """Keep only items whose configured date fields are on or after cutoff."""
    output = []
    for item in items:
        item_date = get_item_date(item, date_keys)
        if item_date and item_date >= cutoff:
            output.append(item)
    return output

def filter_notifications_since(notifications, cutoff):
    """Keep only notifications whose underlying item date is on or after cutoff."""
    output = []
    for notification in notifications:
        item_date = get_item_date(notification.get('item', {}), ('release_date_raw', 'publish_date_raw', 'release_date', 'publish_date'))
        if item_date and item_date >= cutoff:
            output.append(notification)
    return output

def sort_items_by_date(items, date_keys):
    """Sort items newest-first using the first available parseable date."""
    return sorted(items, key=lambda item: get_item_date(item, date_keys) or datetime.min, reverse=True)

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

        cutoff = datetime.now() - timedelta(days=365)
        pqc_presentations = filter_items_since(pqc_presentations, cutoff, ('release_date',))
        recent_pqc_news = filter_items_since(pqc_news, cutoff, ('publish_date_raw', 'publish_date'))
        
        # If nothing is found in strict 1-year window, fall back to 2 years to provide a populated view
        if not recent_pqc_news:
            fallback_cutoff = datetime.now() - timedelta(days=730)
            recent_pqc_news = filter_items_since(pqc_news, fallback_cutoff, ('publish_date_raw', 'publish_date'))

        pqc_news = recent_pqc_news

        # Sort by date - newest first
        pqc_publications = sort_items_by_date(pqc_publications, ('release_date_raw', 'release_date'))
        pqc_presentations = sort_items_by_date(pqc_presentations, ('release_date',))
        pqc_news = sort_items_by_date(pqc_news, ('publish_date_raw', 'publish_date'))
        
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
        all_pqc_notifications = filter_notifications_since(all_pqc_notifications, cutoff)
        
        # Save current PQC data
        storage.save_pqc_data(pqc_data)
        
        # Display PQC notifications with two-tier system
        pqc_notification_count = len(all_pqc_notifications)
        
        if pqc_notification_count > 0:
            # Get categorized notifications using the new method
            categorized_notifications = storage.get_notifications_by_week()
            week_1_notifications = categorized_notifications.get('week_1', [])
            week_2_notifications = categorized_notifications.get('week_2', [])

            render_two_week_notification_sidebar(
                week_1_notifications,
                week_2_notifications,
                [
                    ('pqc_publication', '🔐 PQC Publications', 'document_name', None),
                    ('pqc_presentation', '🔐 PQC Presentations', 'document_name', None),
                    ('pqc_news', '🔐 PQC News', 'title', 'summary'),
                ],
                empty_week_1_message="No new PQC items in Week 1.",
                empty_week_2_message="No new PQC items in Week 2.",
            )
        else:
            st.sidebar.info("No new PQC items found since last check.")
        
    
    cutoff = datetime.now() - timedelta(days=365)
    
    # Only process data if we're on the Quantum Information Science page
    if page == "Quantum Information Science":
        publications = filter_items_since(publications, cutoff, ('release_date_raw', 'release_date'))
        presentations = filter_items_since(presentations, cutoff, ('release_date',))
        news = filter_items_since(news, cutoff, ('publish_date_raw', 'publish_date'))

    # Only process Quantum Information Science data if we're on that page
    if page == "Quantum Information Science":
        # Sort by date - newest first
        publications = sort_items_by_date(publications, ('release_date_raw', 'release_date'))
        presentations = sort_items_by_date(presentations, ('release_date',))
        news = sort_items_by_date(news, ('publish_date_raw', 'publish_date'))
        
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
        all_notifications = filter_notifications_since(all_notifications, cutoff)
        
        # Save current data
        storage.save_data('publications', publications)
        storage.save_data('presentations', presentations)
        storage.save_data('news', news)
        
        # Save general publications to dashboard data storage
        dashboard_dir = os.path.join(os.path.dirname(__file__), 'data_storage')
        if not os.path.exists(dashboard_dir):
            os.makedirs(dashboard_dir)
        
        # Save publications to dashboard data storage
        filename = f"{dashboard_dir}/publications.json"
        with open(filename, 'w') as f:
            json.dump({
                'data': publications,
                'timestamp': datetime.now().isoformat(),
                'count': len(publications)
            }, f, indent=2)
        
        # Save presentations to dashboard data storage
        filename = f"{dashboard_dir}/presentations.json"
        with open(filename, 'w') as f:
            json.dump({
                'data': presentations,
                'timestamp': datetime.now().isoformat(),
                'count': len(presentations)
            }, f, indent=2)
        
        # Save news to dashboard data storage
        filename = f"{dashboard_dir}/news.json"
        with open(filename, 'w') as f:
            json.dump({
                'data': news,
                'timestamp': datetime.now().isoformat(),
                'count': len(news)
            }, f, indent=2)
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

        render_two_week_notification_sidebar(
            week_1_notifications,
            week_2_notifications,
            [
                ('publication', '📄 Publications', 'document_name', None),
                ('presentation', '🎤 Presentations', 'document_name', None),
                ('news', '📰 News', 'title', 'summary'),
            ],
            empty_week_1_message="No new items in Week 1.",
            empty_week_2_message="No new items in Week 2.",
        )
    else:
        pass
    
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
                    header = title
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
                header = pres['document_name']
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

        cutoff = datetime.now() - timedelta(days=60)
        ai_publications = filter_items_since(ai_publications, cutoff, ('release_date_raw', 'release_date'))
        ai_presentations = filter_items_since(ai_presentations, cutoff, ('release_date',))
        ai_news = filter_items_since(ai_news, cutoff, ('publish_date_raw', 'publish_date'))
        
        # Sort by date - newest first
        ai_publications = sort_items_by_date(ai_publications, ('release_date_raw', 'release_date'))
        ai_presentations = sort_items_by_date(ai_presentations, ('release_date',))
        ai_news = sort_items_by_date(ai_news, ('publish_date_raw', 'publish_date'))

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

        render_two_week_notification_sidebar(
            week_1_ai,
            week_2_ai,
            [
                ('ai_publication', '🤖 AI Publications', 'document_name', None),
                ('ai_presentation', '🤖 AI Presentations', 'document_name', None),
                ('ai_news', '🤖 AI News', 'title', 'summary'),
            ],
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.header("📄 AI Publications")
            st.write(f"Total: {len(ai_publications)}")
            for pub in ai_publications:
                title = pub.get('document_name', 'AI Publication')
                category = pub.get('category', '')
                header = title if category else title
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
                header = pres['document_name']
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