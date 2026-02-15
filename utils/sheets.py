from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def read_google_sheet(creds, spreadsheet_id, range_name='Sheet1'):
    """Read data from Google Sheets"""
    try:
        # Build service
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        # Get the data
        result = sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            return {'status': 'error', 'message': 'No data found in the sheet'}
        
        return {'status': 'success', 'data': values}
        
    except HttpError as e:
        error_msg = str(e)
        if '404' in error_msg:
            return {'status': 'error', 'message': 'Spreadsheet not found. Check the Sheet ID.'}
        elif '403' in error_msg:
            return {'status': 'error', 'message': 'Permission denied. Make sure the sheet is shared with your account.'}
        else:
            return {'status': 'error', 'message': f'Google Sheets API error: {error_msg}'}
    
    except Exception as e:
        return {'status': 'error', 'message': f'Error reading sheet: {str(e)}'}