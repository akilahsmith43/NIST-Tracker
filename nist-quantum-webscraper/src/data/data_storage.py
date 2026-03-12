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
            'timestamp': datetime.now(),
            'item': item
        }
        
        notifications.append(notification)
        self.save_notifications(notifications)
    
    def get_active_notifications(self) -> List[Dict[str, Any]]:
        """Get notifications that are less than 24 hours old"""
        notifications = self.load_notifications()
        now = datetime.now()
        active = []
        
        for n in notifications:
            if (now - n['timestamp']).total_seconds() < 24 * 3600:
                active.append(n)
            else:
                # Remove expired notifications
                notifications.remove(n)
        
        # Save cleaned notifications
        self.save_notifications(notifications)
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