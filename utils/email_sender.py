from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import re

def send_email(creds, recipient_email, subject, body):
    """Create a Gmail draft instead of sending directly"""
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # Create email message
        message = MIMEMultipart('alternative')
        message['to'] = recipient_email
        message['subject'] = subject
        
        body_html = body
        parts = re.split(r'(<table.*?</table>)', body_html, flags=re.DOTALL)
        processed_parts = []
        
        for part in parts:
            if '<table' in part:
                # This is a table, keep it as-is
                processed_parts.append(part)
            else:
                # This is regular text, process it
                part = part.replace('\n', '<br>')
                part = re.sub(r'\* ', '• ', part)
                processed_parts.append(part)
        
        body_html = ''.join(processed_parts)
        
        # Create clean HTML email WITHOUT overriding inline table styles
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body style="font-family: Calibri, Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #000000; margin: 0; padding: 20px;">
            <div style="max-width: 800px;">
{body_html}
            </div>
        </body>
        </html>
        """
        
        # Attach HTML content
        msg_html = MIMEText(html_body, 'html')
        message.attach(msg_html)
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # CREATE DRAFT instead of sending
        draft_body = {
            'message': {
                'raw': raw_message
            }
        }
        
        draft = service.users().drafts().create(
            userId='me',
            body=draft_body
        ).execute()
        
        return {
            'status': 'success',
            'draft_id': draft['id'],
            'message': f'Draft created successfully! Check your Gmail drafts.'
        }
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}