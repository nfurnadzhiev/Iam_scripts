import requests
import time
from datetime import datetime

OKTA_DOMAIN = "<your domain>"
API_KEY = "<your api key>"

EXCLUDED_USERS = [
    "admin@example.com",
    "serviceaccount@example.com",
]

class OktaDeactivator:
    def __init__(self):
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'SSWS {API_KEY}'
        }
        self.log_file = f"okta_deactivation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self.progress = {'current': 0, 'total': 0, 'success': 0, 'failed': 0}

    def log_action(self, message, print_progress=False):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        
        if print_progress:
            progress_str = f"Progress: {self.progress['current']}/{self.progress['total']} " \
                          f"(Success: {self.progress['success']}, Failed: {self.progress['failed']})"
            log_entry = f"{log_entry}\n{progress_str}"
        
        print(log_entry)
        with open(self.log_file, 'a') as f:
            f.write(log_entry + '\n')

    def get_group_users(self, group_id):
        """Get all users from a specific group"""
        users = []
        url = f"https://{OKTA_DOMAIN}/api/v1/groups/{group_id}/users"
        
        self.log_action("Fetching users from group...")
        while url:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                batch = response.json()
                users.extend(batch)
                self.log_action(f"Fetched batch of {len(batch)} users...")
                
                url = None
                if "next" in response.links:
                    url = response.links["next"]["url"]
                if url:
                    time.sleep(0.5)
            else:
                self.log_action(f"Failed to fetch users for group {group_id}: {response.status_code} - {response.text}")
                return []
        
        self.log_action(f"Total users fetched from group: {len(users)}")
        return users

    def revoke_user_sessions(self, user_id, email):
        """Revoke all sessions for a user"""
        url = f"https://{OKTA_DOMAIN}/api/v1/users/{user_id}/sessions"
        params = {"oauthTokens": "false"}
        
        response = requests.delete(url, headers=self.headers, params=params)
        if response.status_code == 204:
            self.log_action(f"Successfully revoked sessions for {email}")
            return True
        else:
            self.log_action(f"Failed to revoke sessions for {email}: {response.status_code} - {response.text}")
            return False

    def deactivate_user(self, user_id, email):
        """Deactivate a single user"""
        url = f"https://{OKTA_DOMAIN}/api/v1/users/{user_id}/lifecycle/deactivate"
        response = requests.post(url, headers=self.headers)
        
        self.progress['current'] += 1
        
        if response.status_code == 200:
            self.progress['success'] += 1
            self.log_action(f"Successfully deactivated user: {email}", print_progress=True)
            return True
        else:
            self.progress['failed'] += 1
            self.log_action(f"Failed to deactivate user {email}: {response.status_code} - {response.text}", 
                          print_progress=True)
            return False

    def filter_excluded_users(self, users):
        """Remove excluded users from the list"""
        filtered_users = []
        excluded_count = 0
        
        for user in users:
            email = user.get('profile', {}).get('email', '').lower()
            if email not in [excluded.lower() for excluded in EXCLUDED_USERS]:
                filtered_users.append(user)
            else:
                excluded_count += 1
                self.log_action(f"Excluding user from deactivation: {email}")
        
        self.log_action(f"Total users excluded: {excluded_count}")
        return filtered_users

    def run_deactivation(self, group_id=None, dry_run=True):
        """Main deactivation process"""
        self.progress = {'current': 0, 'total': 0, 'success': 0, 'failed': 0}
        
        self.log_action(f"{'DRY RUN - ' if dry_run else ''}Starting user deactivation process")
        self.log_action(f"Number of users in exclusion list: {len(EXCLUDED_USERS)}")
        
        if group_id:
            self.log_action(f"Fetching users from group: {group_id}")
            users = self.get_group_users(group_id)
            self.log_action(f"Found {len(users)} users in group")
        else:
            self.log_action("No group specified - fetching all active users")
            users = self.get_group_users(group_id)
            self.log_action(f"Found {len(users)} total active users")
        
        # Filter out excluded users
        users = self.filter_excluded_users(users)
        total_users = len(users)
        self.progress['total'] = total_users
        
        self.log_action(f"""
Deactivation Summary:
- Total users found: {len(users)}
- Users excluded: {len(EXCLUDED_USERS)}
- Users to be processed: {total_users}
        """)
        
        if dry_run:
            self.log_action("DRY RUN - No users will be deactivated")
            self.log_action("Users that would be deactivated:")
            for i, user in enumerate(users, 1):
                email = user.get('profile', {}).get('email', 'No email')
                self.log_action(f"{i}/{total_users}: {email}")
            return
        
        confirm = input(f"Are you sure you want to deactivate {total_users} users? This will:\n"
                       f"1. Revoke all active sessions\n"
                       f"2. Deactivate all user accounts\n"
                       f"Type 'DEACTIVATE' to confirm: ")
        
        if confirm != "DEACTIVATE":
            self.log_action("Deactivation cancelled by user")
            return
        
        self.log_action(f"\nStarting deactivation of {total_users} users...")
        
        for user in users:
            email = user.get('profile', {}).get('email', 'No email')
            user_id = user['id']
            
            self.revoke_user_sessions(user_id, email)
            
            self.deactivate_user(user_id, email)
            time.sleep(0.5)  
        
        self.log_action(f"""
Deactivation process completed:
- Total users processed: {self.progress['total']}
- Successfully deactivated: {self.progress['success']}
- Failed to deactivate: {self.progress['failed']}
Log file: {self.log_file}
        """)

if __name__ == "__main__":
    group_id = input("Enter group ID to target specific group (or press Enter for all users): ").strip()
    
    print("\nCurrent exclusion list:", EXCLUDED_USERS)
    add_exclusions = input("Would you like to add more emails to exclude? (yes/no): ")
    
    if add_exclusions.lower() == 'yes':
        while True:
            email = input("Enter email to exclude (or press Enter to finish): ").strip()
            if not email:
                break
            if email not in EXCLUDED_USERS:
                EXCLUDED_USERS.append(email)
    
    deactivator = OktaDeactivator()
    
    print("\nPerforming dry run first...")
    deactivator.run_deactivation(group_id=group_id if group_id else None, dry_run=True)
    
    proceed = input("\nWould you like to proceed with actual deactivation? (yes/no): ")
    if proceed.lower() == 'yes':
        deactivator.run_deactivation(group_id=group_id if group_id else None, dry_run=False)
    else:
        print("Deactivation cancelled")
