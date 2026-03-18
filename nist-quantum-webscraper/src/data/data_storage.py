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
        
        # Create notification entry
        notification = {
            'type': item_type,
            'timestamp': datetime.now().isoformat(),
            'item': item
        }
        
        notifications.append(notification)
        self.save_notifications(notifications)
    
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