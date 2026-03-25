import json
import os
from datetime import datetime
from typing import List, Dict, Any

class DataStorage:
    def __init__(self, storage_dir="data_storage"):
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
    
    def save_data(self, data_type: str, data: List[Dict[str, Any]]):
        """Save scraped data to JSON file"""
        filename = f"{self.storage_dir}/{data_type}.json"
        with open(filename, 'w') as f:
            json.dump({
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'count': len(data)
            }, f, indent=2)
    
    def load_data(self, data_type: str) -> Dict[str, Any]:
        """Load previously saved data"""
        filename = f"{self.storage_dir}/{data_type}.json"
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return {'data': [], 'timestamp': None, 'count': 0}
    
    def get_previous_data(self, data_type: str) -> List[Dict[str, Any]]:
        """Get previously saved data"""
        saved_data = self.load_data(data_type)
        return saved_data.get('data', [])
    
    def save_pqc_data(self, data: Dict[str, List[Dict[str, Any]]]):
        """Save Post-Quantum Cryptography data to JSON file"""
        filename = f"{self.storage_dir}/pqc_data.json"
        with open(filename, 'w') as f:
            json.dump({
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'counts': {
                    'publications': len(data.get('publications', [])),
                    'presentations': len(data.get('presentations', [])),
                    'news': len(data.get('news', []))
                }
            }, f, indent=2)
    
    def save_ai_data(self, data: Dict[str, List[Dict[str, Any]]]):
        """Save Artificial Intelligence data to JSON file"""
        filename = f"{self.storage_dir}/ai_data.json"
        with open(filename, 'w') as f:
            json.dump({
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'counts': {
                    'publications': len(data.get('publications', [])),
                    'presentations': len(data.get('presentations', [])),
                    'news': len(data.get('news', []))
                }
            }, f, indent=2)
    
    def save_pqc_data_to_dashboard(self, data: Dict[str, List[Dict[str, Any]]]):
        """Save Post-Quantum Cryptography data to dashboard data storage"""
        dashboard_dir = f"{self.storage_dir}/dashboard/data_storage"
        if not os.path.exists(dashboard_dir):
            os.makedirs(dashboard_dir)
        
        print(f"DEBUG: save_pqc_data_to_dashboard called with {len(data.get('publications', []))} publications")
        print(f"DEBUG: Dashboard directory: {dashboard_dir}")
        
        # Save publications (only the filtered ones from the past year)
        if 'publications' in data:
            filename = f"{dashboard_dir}/publications.json"
            print(f"DEBUG: Saving {len(data['publications'])} publications to {filename}")
            with open(filename, 'w') as f:
                json.dump({
                    'data': data['publications'],
                    'timestamp': datetime.now().isoformat(),
                    'count': len(data['publications'])
                }, f, indent=2)
            print(f"DEBUG: Publications saved successfully")
        
        # Save presentations
        if 'presentations' in data:
            filename = f"{dashboard_dir}/presentations.json"
            print(f"DEBUG: Saving {len(data['presentations'])} presentations to {filename}")
            with open(filename, 'w') as f:
                json.dump({
                    'data': data['presentations'],
                    'timestamp': datetime.now().isoformat(),
                    'count': len(data['presentations'])
                }, f, indent=2)
            print(f"DEBUG: Presentations saved successfully")
        
        # Save news
        if 'news' in data:
            filename = f"{dashboard_dir}/news.json"
            print(f"DEBUG: Saving {len(data['news'])} news items to {filename}")
            with open(filename, 'w') as f:
                json.dump({
                    'data': data['news'],
                    'timestamp': datetime.now().isoformat(),
                    'count': len(data['news'])
                }, f, indent=2)
            print(f"DEBUG: News saved successfully")
    
    def load_pqc_data(self) -> Dict[str, Any]:
        """Load previously saved PQC data"""
        filename = f"{self.storage_dir}/pqc_data.json"
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return {'data': {'publications': [], 'presentations': [], 'news': []}, 'timestamp': None, 'counts': {'publications': 0, 'presentations': 0, 'news': 0}}
    
    def get_previous_pqc_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get previously saved PQC data"""
        saved_data = self.load_pqc_data()
        return saved_data.get('data', {'publications': [], 'presentations': [], 'news': []})
    
    def get_new_pqc_items(self, current_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """Get only the new PQC items since last save"""
        previous_data = self.get_previous_pqc_data()
        
        new_items = {'publications': [], 'presentations': [], 'news': []}
        
        # Check publications
        previous_pubs = {(item.get('document_name', '') + item.get('link', '')).lower() 
                        for item in previous_data.get('publications', [])}
        for item in current_data.get('publications', []):
            item_key = (item.get('document_name', '') + item.get('link', '')).lower()
            if item_key not in previous_pubs:
                new_items['publications'].append(item)
        
        # Check presentations
        previous_pres = {(item.get('document_name', '') + item.get('link', '')).lower() 
                        for item in previous_data.get('presentations', [])}
        for item in current_data.get('presentations', []):
            item_key = (item.get('document_name', '') + item.get('link', '')).lower()
            if item_key not in previous_pres:
                new_items['presentations'].append(item)
        
        # Check news
        previous_news = {(item.get('title', '') + item.get('link', '')).lower() 
                        for item in previous_data.get('news', [])}
        for item in current_data.get('news', []):
            item_key = (item.get('title', '') + item.get('link', '')).lower()
            if item_key not in previous_news:
                new_items['news'].append(item)
        
        return new_items
    
    def load_ai_data(self) -> Dict[str, Any]:
        """Load previously saved AI data"""
        filename = f"{self.storage_dir}/ai_data.json"
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return {'data': {'publications': [], 'presentations': [], 'news': []}, 'timestamp': None, 'counts': {'publications': 0, 'presentations': 0, 'news': 0}}
    
    def get_previous_ai_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get previously saved AI data"""
        saved_data = self.load_ai_data()
        return saved_data.get('data', {'publications': [], 'presentations': [], 'news': []})
    
    def get_new_ai_items(self, current_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """Get only the new AI items since last save"""
        previous_data = self.get_previous_ai_data()
        
        new_items = {'publications': [], 'presentations': [], 'news': []}
        
        # Check publications
        previous_pubs = {(item.get('document_name', '') + item.get('link', '')).lower() 
                        for item in previous_data.get('publications', [])}
        for item in current_data.get('publications', []):
            item_key = (item.get('document_name', '') + item.get('link', '')).lower()
            if item_key not in previous_pubs:
                new_items['publications'].append(item)
        
        # Check presentations
        previous_pres = {(item.get('document_name', '') + item.get('link', '')).lower() 
                        for item in previous_data.get('presentations', [])}
        for item in current_data.get('presentations', []):
            item_key = (item.get('document_name', '') + item.get('link', '')).lower()
            if item_key not in previous_pres:
                new_items['presentations'].append(item)
        
        # Check news
        previous_news = {(item.get('title', '') + item.get('link', '')).lower() 
                        for item in previous_data.get('news', [])}
        for item in current_data.get('news', []):
            item_key = (item.get('title', '') + item.get('link', '')).lower()
            if item_key not in previous_news:
                new_items['news'].append(item)
        
        return new_items
    
    def has_data_changed(self, data_type: str, current_data: List[Dict[str, Any]]) -> bool:
        """Check if data has changed since last save"""
        previous_data = self.get_previous_data(data_type)
        
        if len(previous_data) != len(current_data):
            return True
        
        # Compare based on unique identifiers (title + link)
        current_items = {(item.get('document_name', '') + item.get('link', '')).lower() 
                         for item in current_data}
        previous_items = {(item.get('document_name', '') + item.get('link', '')).lower() 
                          for item in previous_data}
        
        return current_items != previous_items
    
    def get_new_items(self, data_type: str, current_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get only the new items since last save"""
        previous_data = self.get_previous_data(data_type)
        previous_items = {(item.get('document_name', '') + item.get('link', '')).lower() 
                          for item in previous_data}
        
        new_items = []
        for item in current_data:
            item_key = (item.get('document_name', '') + item.get('link', '')).lower()
            if item_key not in previous_items:
                new_items.append(item)
        
        return new_items
    
    def add_notification(self, item_type: str, item: Dict[str, Any]):
        """Add a new item to the persistent notifications"""
        notifications = self.load_notifications()
        
        # Create notification entry with enhanced metadata
        notification = {
            'type': item_type,
            'timestamp': datetime.now().isoformat(),
            'item': item,
            'scrape_date': datetime.now().isoformat()
        }
        
        notifications.append(notification)
        self.save_notifications(notifications)
    
    def get_notifications_by_week(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get notifications categorized by week (Week 1: 0-7 days, Week 2: 8-14 days)"""
        notifications = self.load_notifications()
        now = datetime.now()
        categorized = {
            'week_1': [],  # 0-7 days
            'week_2': [],  # 8-14 days
            'archived': []  # older than 14 days
        }
        
        for n in notifications:
            item = n.get('item', {})
            item_date_str = None
            
            # Try to get the item's release/publish date
            if item.get('release_date_raw'):
                item_date_str = item['release_date_raw']  # ISO format date
            elif item.get('publish_date_raw'):
                item_date_str = item['publish_date_raw']  # ISO format date
            
            if item_date_str:
                try:
                    # Parse the ISO date
                    item_date = datetime.fromisoformat(item_date_str)
                    age_days = (now - item_date).days
                    
                    # Categorize based on age
                    if 0 <= age_days <= 7:
                        categorized['week_1'].append(n)
                    elif 8 <= age_days <= 14:
                        categorized['week_2'].append(n)
                    else:
                        categorized['archived'].append(n)
                        
                except Exception:
                    # If parsing fails, skip this notification
                    pass
        
        return categorized
    
    def get_last_scrape_info(self) -> Dict[str, Any]:
        """Get information about the last scrape session"""
        notifications = self.load_notifications()
        if not notifications:
            return {
                'last_scrape': None,
                'scrape_count': 0,
                'new_items_this_session': 0
            }
        
        # Get the most recent scrape date from notifications
        scrape_dates = []
        for n in notifications:
            if n.get('scrape_date'):
                try:
                    scrape_dates.append(datetime.fromisoformat(n['scrape_date']))
                except Exception:
                    pass
        
        if not scrape_dates:
            return {
                'last_scrape': None,
                'scrape_count': 0,
                'new_items_this_session': 0
            }
        
        last_scrape = max(scrape_dates)
        scrape_count = len(notifications)
        
        # Count items from the last scrape session (same day)
        today_start = last_scrape.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        new_items_this_session = 0
        for n in notifications:
            if n.get('scrape_date'):
                try:
                    scrape_date = datetime.fromisoformat(n['scrape_date'])
                    if today_start <= scrape_date <= today_end:
                        new_items_this_session += 1
                except Exception:
                    pass
        
        return {
            'last_scrape': last_scrape.isoformat(),
            'scrape_count': scrape_count,
            'new_items_this_session': new_items_this_session
        }
    
    def get_active_notifications(self) -> List[Dict[str, Any]]:
        """Get notifications where items were released within the last 48 hours"""
        notifications = self.load_notifications()
        now = datetime.now()
        active = []
        
        for n in notifications:
            item = n.get('item', {})
            item_date_str = None
            
            # Try to get the item's release/publish date
            if item.get('release_date_raw'):
                item_date_str = item['release_date_raw']  # ISO format date
            elif item.get('publish_date_raw'):
                item_date_str = item['publish_date_raw']  # ISO format date
            
            if item_date_str:
                try:
                    # Parse the ISO date
                    item_date = datetime.fromisoformat(item_date_str)
                    # Keep only items from the last 48 hours
                    if (now - item_date).total_seconds() < 48 * 3600:
                        active.append(n)
                except Exception:
                    # If parsing fails, skip this notification
                    pass
        
        return active
    
    def save_notifications(self, notifications: List[Dict[str, Any]]):
        filename = f"{self.storage_dir}/notifications.json"
        with open(filename, 'w') as f:
            json.dump(notifications, f, indent=2, default=str)
    
    def load_notifications(self) -> List[Dict[str, Any]]:
        filename = f"{self.storage_dir}/notifications.json"
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                for n in data:
                    n['timestamp'] = datetime.fromisoformat(n['timestamp'])
                return data
        return []