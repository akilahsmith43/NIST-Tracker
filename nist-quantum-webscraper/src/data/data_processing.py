def process_data(publications, presentations, news):
    # Combine all data into a single structure for easier management
    combined_data = {
        "publications": publications,
        "presentations": presentations,
        "news": news
    }
    return combined_data

def remove_duplicates(data_list):
    seen = set()
    unique_data = []
    for item in data_list:
        identifier = item.get('document_name')  # or any unique identifier
        if identifier not in seen:
            seen.add(identifier)
            unique_data.append(item)
    return unique_data

def update_data(existing_data, new_data):
    # Update existing data with new data, avoiding duplicates
    updated_data = existing_data.copy()
    for item in new_data:
        identifier = item.get('document_name')
        if identifier not in [d.get('document_name') for d in updated_data]:
            updated_data.append(item)
    return updated_data

def save_data_to_file(data, filename):
    import json
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)