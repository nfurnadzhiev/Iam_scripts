from msal import PublicClientApplication
import requests
import pandas as pd
from datetime import datetime, timedelta
import argparse
import os

TENANT_ID = "<your tenant id>"
SCOPES = ['https://graph.microsoft.com/.default']

STATUS_CODES = {
    '0': 'Success',
    '50034': 'User not found',
    '50126': 'Invalid username or password',
    '50076': 'MFA required',
    '50074': 'MFA required (strong authentication)',
    '50058': 'IP address is not trusted',
    '50053': 'Account locked',
    '50057': 'Account disabled',
    '50055': 'Password expired'
}

def get_token():
    """Authenticate and retrieve an access token using MSAL."""
    app = PublicClientApplication(
        client_id="<your client id>",
        authority=f"https://login.microsoftonline.com/{TENANT_ID}"
    )
    accounts = app.get_accounts()
    if accounts:
        return app.acquire_token_silent(SCOPES, account=accounts[0])
    return app.acquire_token_interactive(SCOPES)

def fetch_all_signin_logs(headers, filter_query):
    """Fetch all pages of sign-in logs."""
    url = f'https://graph.microsoft.com/v1.0/auditLogs/signIns?$filter=createdDateTime ge {filter_query}&$orderby=createdDateTime desc'
    all_signins = []

    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            all_signins.extend(data.get('value', []))
            url = data.get('@odata.nextLink')
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return []

    return all_signins

def print_statistics(df):
    """Print summary statistics of the sign-in logs."""
    total_signins = len(df)
    status_counts = df['status'].value_counts()

    print("\nStatistics:")
    print(f"Total Sign-ins: {total_signins}")
    print("\nStatus Breakdown:")
    for status, count in status_counts.items():
        print(f"{status}: {count} ({(count/total_signins*100):.1f}%)")

def get_signin_logs(time_filter='1h', output_format='both', unique_users=False):
    """Fetch and process sign-in logs."""
    result = get_token()
    
    if 'access_token' in result:
        headers = {'Authorization': f'Bearer {result["access_token"]}'}
        
        if 'h' in time_filter:
            delta = timedelta(hours=int(time_filter.replace('h', '')))
        else:
            delta = timedelta(minutes=int(time_filter.replace('m', '')))
            
        start_time = datetime.utcnow() - delta
        filter_query = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        signins = fetch_all_signin_logs(headers, filter_query)
        
        if signins:
            processed_signins = []
            for s in signins:
                status_code = str(s.get('status', {}).get('errorCode', ''))
                signin_data = {
                    'timestamp': s['createdDateTime'],
                    'user': s['userPrincipalName'],
                    'app': s.get('appDisplayName', 'N/A'),
                    'ip_address': s.get('ipAddress', 'N/A'),
                    'status_code': status_code,
                    'status': STATUS_CODES.get(status_code, 'Unknown'),
                    'client_app': s.get('clientAppUsed', 'N/A')
                }
                
                location = s.get('location', {})
                if location:
                    location_string = f"{location.get('city', 'N/A')}, {location.get('countryOrRegion', 'N/A')}"
                    signin_data['location'] = location_string
                    signin_data['country'] = location_string.split(', ')[-1] 
                else:
                    signin_data['location'] = 'N/A'
                    signin_data['country'] = 'N/A'
                    
                processed_signins.append(signin_data)
            
            df = pd.DataFrame(processed_signins)
            
            print_statistics(df)
            
            if unique_users:
                df = df.sort_values('timestamp').groupby('user').last().reset_index()
            
            if output_format in ['csv', 'both']:
                filename = f"signins_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                df.to_csv(filename, index=False)
                print(f"\nCSV saved as: {filename}")
            
            if output_format in ['console', 'both']:
                if len(df) > 0:
                    print(f"\nSign-ins from the last {time_filter}:")
                    print(df.to_string())
                    print("\nStatus Code Reference:")
                    for code, meaning in STATUS_CODES.items():
                        print(f"{code}: {meaning}")
                else:
                    print(f"No sign-ins found in the last {time_filter}")
            
            return df
        else:
            print(f"No sign-ins found in the past {time_filter}.")
    else:
        print(f"Authentication failed: {result.get('error_description')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch Entra sign-in logs')
    parser.add_argument('-t', '--time', default='1h', help='Time filter (e.g., 10m, 1h)')
    parser.add_argument('-o', '--output', default='both', choices=['csv', 'console', 'both'], 
                      help='Output format')
    parser.add_argument('-u', '--unique', action='store_true', help='Show only most recent sign-in per user')
    args = parser.parse_args()
    get_signin_logs(args.time, args.output, args.unique)
