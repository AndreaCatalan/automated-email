from googleapiclient.discovery import build
from datetime import datetime
import base64
import re

def clean_html_content(html_content):
    """Remove wrapper divs and clean HTML for display"""
    if not html_content:
        return html_content
    
    # Remove DOCTYPE and html tags
    html_content = re.sub(r'<!DOCTYPE[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<html[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</html>', '', html_content, flags=re.IGNORECASE)
    
    # Remove head section
    html_content = re.sub(r'<head[^>]*>.*?</head>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove body tags but keep content
    html_content = re.sub(r'<body[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</body>', '', html_content, flags=re.IGNORECASE)
    
    # Remove outer wrapper divs (the style wrappers)
    html_content = re.sub(r'<div style="font-family:[^"]*"[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<div style="max-width:[^"]*"[^>]*>', '', html_content, flags=re.IGNORECASE)
    
    # Remove closing divs at the end (last 2-3 closing divs)
    # Count opening divs vs closing divs and remove excess closing ones
    opening_divs = len(re.findall(r'<div', html_content, flags=re.IGNORECASE))
    closing_divs = len(re.findall(r'</div>', html_content, flags=re.IGNORECASE))
    
    # Remove extra closing divs from the end
    extra_closing = closing_divs - opening_divs
    if extra_closing > 0:
        for _ in range(extra_closing):
            # Remove last occurrence of </div>
            html_content = html_content[::-1].replace('>vid/<', '', 1)[::-1]
    
    return html_content.strip()

def get_gmail_drafts(creds, max_results=10):
    """Fetch recent Gmail drafts"""
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # Get list of drafts
        results = service.users().drafts().list(userId='me', maxResults=max_results).execute()
        drafts = results.get('drafts', [])
        
        draft_list = []
        
        for draft in drafts:
            # Get full draft details
            draft_detail = service.users().drafts().get(userId='me', id=draft['id']).execute()
            
            message = draft_detail['message']
            payload = message.get('payload', {})
            headers = payload.get('headers', [])
            
            # Extract subject and recipient
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            to = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown')
            
            # Get internal date (timestamp)
            internal_date = message.get('internalDate')
            if internal_date:
                date = datetime.fromtimestamp(int(internal_date) / 1000).strftime('%Y-%m-%d %H:%M')
            else:
                date = 'Unknown'
            
            draft_list.append({
                'id': draft['id'],
                'subject': subject,
                'to': to,
                'date': date
            })
        
        return {'status': 'success', 'drafts': draft_list}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def get_draft_content(creds, draft_id):
    """Get the full body content of a specific draft"""
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # Get draft details
        draft = service.users().drafts().get(userId='me', id=draft_id).execute()
        
        message = draft['message']
        payload = message.get('payload', {})
        
        # Function to decode body
        def get_body(payload):
            body = ''
            
            if 'parts' in payload:
                # Multi-part message
                for part in payload['parts']:
                    if part['mimeType'] == 'text/html':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            break
                    elif part['mimeType'] == 'text/plain' and not body:
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            else:
                # Single part message
                if 'body' in payload and 'data' in payload['body']:
                    body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            
            return body
        
        body_content = get_body(payload)
        
        # Clean the HTML content
        body_content = clean_html_content(body_content)
        
        # Get headers
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        to = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown')
        
        return {
            'status': 'success',
            'subject': subject,
            'to': to,
            'body': body_content
        }
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}