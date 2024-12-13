import requests
from datetime import datetime

OKTA_DOMAIN = "<your domain>"
API_KEY = "<your api key>"

def get_users_by_status(status):
    """Get users with specific status"""
    users = []
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'SSWS {API_KEY}'
    }
    
    url = f"https://{OKTA_DOMAIN}/api/v1/users?filter=status eq \"{status}\""
    
    while url:
        print(f"Fetching {status} users...")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            batch = response.json()
            users.extend(batch)
            
            # Handle pagination
            url = None
            if "next" in response.links:
                url = response.links["next"]["url"]
        else:
            print(f"Error fetching users: {response.status_code} - {response.text}")
            return []
    
    return users

def generate_report():
    """Generate a report of user counts by status"""
    active_users = get_users_by_status("ACTIVE")
    deactivated_users = get_users_by_status("DEPROVISIONED")
    
    print("\nOkta User Status Report")
    print("=" * 30)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 30)
    print(f"Active Users: {len(active_users)}")
    print(f"Deactivated Users: {len(deactivated_users)}")
    print(f"Total Users: {len(active_users) + len(deactivated_users)}")
    print("=" * 30)

if __name__ == "__main__":
    generate_report()