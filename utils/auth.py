from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/gmail.compose', 
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

def authenticate_google(credentials_path='credentials.json'):
    """Authenticate with Google Services"""
    creds = None
    
    # Check if we have saved credentials
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}")
                creds = None
        
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, 
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            return {'status': 'needs_auth', 'url': auth_url, 'flow': flow}
    
    # Save credentials for next time
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    
    return {'status': 'authenticated', 'credentials': creds}

def complete_auth(flow, code):
    """Complete authentication with authorization code"""
    flow.fetch_token(code=code)
    creds = flow.credentials
    
    # Save credentials
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    
    return creds

def get_user_email(creds):
    """Get authenticated user's email"""
    from googleapiclient.discovery import build
    
    try:
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        return user_info.get('email')
    except:
        return None