import streamlit as st
from datetime import datetime
import os
from utils.auth import authenticate_google, complete_auth, get_user_email
from utils.sheets import read_google_sheet
from utils.analyzer import analyze_with_gemini
from utils.email_sender import send_email
from utils.database import UserDatabase
from utils.gmail_drafts import get_gmail_drafts, get_draft_content
import google.genai as genai

# Helper function for week calculation
def get_week_of_month(date):
    """Calculate which week of the month it is (starting from 1)"""
    first_day = date.replace(day=1)
    day_of_month = date.day
    first_weekday = first_day.weekday()
    week_number = ((day_of_month + first_weekday - 1) // 7) + 1
    return week_number

def get_email_subject():
    """Generate email subject in format: [MM/DD/YYYY]: Week N Daily Status Report"""
    today = datetime.now()
    date_str = today.strftime('%m/%d/%Y')
    week_num = get_week_of_month(today)
    return f"[{date_str}]: Week {week_num} Daily Status Report"

# Page config
st.set_page_config(
    page_title="ETI Email Automation",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #373f6b;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        color: #155724;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 5px;
        color: #0c5460;
    }
    .warning-box {
        padding: 1rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        color: #856404;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Initialize database
db = UserDatabase()

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'credentials' not in st.session_state:
    st.session_state.credentials = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'preview_content' not in st.session_state:
    st.session_state.preview_content = None
if 'gemini_key' not in st.session_state:
    st.session_state.gemini_key = None
if 'gemini_validated' not in st.session_state:
    st.session_state.gemini_validated = False

# App header
st.markdown('<h1 class="main-header">📧 ETI | Automated Email</h1>', unsafe_allow_html=True)

# ============================================================================
# LOGIN SYSTEM - Upload credentials.json = Login
# ============================================================================

if not st.session_state.logged_in:
    st.markdown("---")
    st.header("🔐 Login")
    
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        # Check for existing users
        existing_users = db.list_all_users()
        
        if existing_users:
            st.info("👋 Select your account or create new")
            
            selected_user = st.selectbox(
                "Your Account:",
                [""] + existing_users + ["➕ New Account"],
                key="user_selector"
            )
            
            # Show delete option if an account is selected
            if selected_user and selected_user != "➕ New Account" and selected_user != "":
                col_login, col_delete = st.columns([3, 1])
                
                with col_login:
                    if st.button("🚀 Login", type="primary", use_container_width=True):
                        user_data = db.get_user(selected_user)
                        
                        if user_data['status'] == 'success':
                            st.session_state.user_email = user_data['email']
                            st.session_state.gemini_key = user_data['gemini_api_key']
                            st.session_state.gemini_validated = True
                            st.session_state.user_id = user_data['user_id']
                            
                            # Load Google credentials
                            if user_data['google_creds']:
                                try:
                                    creds_data = user_data['google_creds']
                                    from google.oauth2.credentials import Credentials
                                    creds = Credentials(
                                        token=creds_data.get('token'),
                                        refresh_token=creds_data.get('refresh_token'),
                                        token_uri=creds_data.get('token_uri'),
                                        client_id=creds_data.get('client_id'),
                                        client_secret=creds_data.get('client_secret'),
                                        scopes=creds_data.get('scopes')
                                    )
                                    st.session_state.credentials = creds
                                except:
                                    pass
                            
                            st.session_state.logged_in = True
                            st.success(f"✅ Welcome back, {selected_user}!")
                            st.rerun()
                
                with col_delete:
                    if st.button("❌", use_container_width=True, help="Delete this account"):
                        st.session_state.confirm_delete = selected_user
                        st.rerun()
                
                # Confirmation dialog
                if 'confirm_delete' in st.session_state and st.session_state.confirm_delete == selected_user:
                    st.warning(f"⚠️ **Delete account: {selected_user}?**")
                    st.markdown("This will permanently delete all data for this account.")
                    
                    col_yes, col_no = st.columns(2)
                    
                    with col_yes:
                        if st.button("✅ Yes, Delete", type="primary", use_container_width=True):
                            # Delete from database
                            result = db.delete_user(selected_user)
                            
                            if result['status'] == 'success':
                                if 'confirm_delete' in st.session_state:
                                    del st.session_state.confirm_delete
                                st.success(f"✅ Account deleted: {selected_user}")
                                st.rerun()
                            else:
                                st.error(f"❌ {result['message']}")
                    
                    with col_no:
                        if st.button("❌ Cancel", use_container_width=True):
                            del st.session_state.confirm_delete
                            st.rerun()
            
            elif selected_user == "" and st.button("🚀 Login", type="primary", use_container_width=True):
                st.warning("⚠️ Please select an account first")
            
            # Show new account section when selected
            if selected_user == "➕ New Account":
                st.markdown("---")
                st.markdown("### 📝 New Account Setup")
                
                # Upload credentials.json = instant login
                st.info("📤 Upload your credentials.json to create account")
                
                uploaded_creds = st.file_uploader(
                    "credentials.json",
                    type=['json'],
                    help="This file will be your login credential",
                    key="creds_uploader_new"
                )
                
                if uploaded_creds is not None:
                    # Save credentials file
                    with open("credentials.json", "wb") as f:
                        f.write(uploaded_creds.getvalue())
                    
                    st.success("✅ credentials.json loaded!")
                    
                    # Check if auth flow is in progress
                    if 'auth_flow' in st.session_state and st.session_state.auth_flow:
                        st.markdown("### 🔗 Authorization Required")
                        st.markdown(f"**Click this link:** [{st.session_state.auth_url}]({st.session_state.auth_url})")
                        st.markdown("---")
                        
                        auth_code = st.text_input(
                            "📋 Paste the authorization code here:",
                            help="Copy the code from the browser",
                            key="auth_code_new"
                        )
                        
                        if st.button("✅ Complete Authentication", use_container_width=True, key="complete_auth_new"):
                            if not auth_code:
                                st.error("❌ Please enter the authorization code")
                            else:
                                with st.spinner("Completing authentication..."):
                                    try:
                                        creds = complete_auth(st.session_state.auth_flow, auth_code)
                                        st.session_state.credentials = creds
                                        st.session_state.user_email = get_user_email(creds)
                                        st.session_state.logged_in = True
                                        st.session_state.auth_flow = None
                                        st.session_state.auth_url = None
                                        st.success("🎉 Authentication successful!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Authentication failed: {e}")
                    else:
                        # Authenticate button
                        create_btn = st.button("🚀 Create Account & Login", type="primary", use_container_width=True, key="create_new_account")
                        
                        if create_btn:
                            with st.spinner("Setting up your account..."):
                                try:
                                    auth_result = authenticate_google()
                                    
                                    if auth_result['status'] == 'authenticated':
                                        st.session_state.credentials = auth_result['credentials']
                                        st.session_state.user_email = get_user_email(auth_result['credentials'])
                                        st.session_state.logged_in = True
                                        st.success("🎉 Account created! Now set up Gemini API...")
                                        st.rerun()
                                    elif auth_result['status'] == 'needs_auth':
                                        st.session_state.auth_flow = auth_result['flow']
                                        st.session_state.auth_url = auth_result['url']
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Unexpected status: {auth_result.get('status')}")
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
        
        # If no existing users, show new account setup directly
        else:
            st.markdown("### 📝 New Account Setup")
            
            # Upload credentials.json = instant login
            st.info("📤 Upload your credentials.json to create account")
            
            uploaded_creds = st.file_uploader(
                "credentials.json",
                type=['json'],
                help="This file will be your login credential",
                key="creds_uploader_first"
            )
            
            if uploaded_creds is not None:
                # Save credentials file
                with open("credentials.json", "wb") as f:
                    f.write(uploaded_creds.getvalue())
                
                st.success("✅ credentials.json loaded!")
                
                # Check if auth flow is in progress
                if 'auth_flow' in st.session_state and st.session_state.auth_flow:
                    st.markdown("### 🔗 Authorization Required")
                    st.markdown(f"**Click this link:** [{st.session_state.auth_url}]({st.session_state.auth_url})")
                    st.markdown("---")
                    
                    auth_code = st.text_input(
                        "📋 Paste the authorization code here:",
                        help="Copy the code from the browser",
                        key="auth_code_first"
                    )
                    
                    if st.button("✅ Complete Authentication", use_container_width=True, key="complete_auth_first"):
                        if not auth_code:
                            st.error("❌ Please enter the authorization code")
                        else:
                            with st.spinner("Completing authentication..."):
                                try:
                                    creds = complete_auth(st.session_state.auth_flow, auth_code)
                                    st.session_state.credentials = creds
                                    st.session_state.user_email = get_user_email(creds)
                                    st.session_state.logged_in = True
                                    st.session_state.auth_flow = None
                                    st.session_state.auth_url = None
                                    st.success("🎉 Authentication successful!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Authentication failed: {e}")
                else:
                    # Authenticate button
                    create_btn = st.button("🚀 Create Account & Login", type="primary", use_container_width=True, key="create_first_account")
                    
                    if create_btn:
                        with st.spinner("Setting up your account..."):
                            try:
                                auth_result = authenticate_google()
                                
                                if auth_result['status'] == 'authenticated':
                                    st.session_state.credentials = auth_result['credentials']
                                    st.session_state.user_email = get_user_email(auth_result['credentials'])
                                    st.session_state.logged_in = True
                                    st.success("🎉 Account created! Now set up Gemini API...")
                                    st.rerun()
                                elif auth_result['status'] == 'needs_auth':
                                    st.session_state.auth_flow = auth_result['flow']
                                    st.session_state.auth_url = auth_result['url']
                                    st.rerun()
                                else:
                                    st.error(f"❌ Unexpected status: {auth_result.get('status')}")
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")

# ============================================================================
# STEP 1: GEMINI API SETUP (After Login)
# ============================================================================

elif st.session_state.logged_in and not st.session_state.gemini_validated:
    st.markdown("---")
    st.header("🔑 Step 1: Configure Gemini API")
    
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        st.info("📝 Enter your Gemini API key")
        st.markdown("Get your free API key: https://aistudio.google.com/app/apikey")
        
        gemini_input = st.text_input(
            "Gemini API Key",
            type="password",
            value=st.session_state.gemini_key or "",
            placeholder="AIzaSy...",
            key="gemini_input"
        )
        
        if st.button("✅ Save & Continue", type="primary", use_container_width=True):
            if not gemini_input:
                st.error("❌ Please enter an API key")
            else:
                st.session_state.gemini_key = gemini_input
                st.session_state.gemini_validated = True
                
                # Save to database
                creds = st.session_state.credentials
                creds_dict = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes
                }
                
                result = db.save_user(
                    st.session_state.user_email,
                    st.session_state.gemini_key,
                    creds_dict
                )
                
                if result['status'] == 'success':
                    st.session_state.user_id = result['user_id']
                
                st.success("✅ Setup complete!")
                st.rerun()

# ============================================================================
# MAIN WORKSPACE
# ============================================================================

else:
    # Sidebar
    with st.sidebar:
        st.header("👤 Account")
        st.success(f"**{st.session_state.user_email}**")
        
        # Gemini API Key Management
        st.markdown("---")
        st.markdown("### 🔑 Gemini API Key")
        
        with st.expander("Change API Key"):
            new_api_key = st.text_input(
                "New Gemini API Key",
                type="password",
                placeholder="AIzaSy...",
                key="new_gemini_key"
            )
            
            if st.button("💾 Update API Key", use_container_width=True):
                if not new_api_key:
                    st.error("❌ Please enter a new API key")
                else:
                    # Update in database
                    creds = st.session_state.credentials
                    creds_dict = {
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    }
                    
                    result = db.save_user(
                        st.session_state.user_email,
                        new_api_key,
                        creds_dict
                    )
                    
                    if result['status'] == 'success':
                        st.session_state.gemini_key = new_api_key
                        st.success("✅ API key updated!")
                        st.rerun()
                    else:
                        st.error(f"❌ {result['message']}")
        
        # Gmail Drafts
        st.markdown("---")
        st.markdown("### 📬 Gmail Drafts")
        
        if st.button("🔄 Fetch Drafts", use_container_width=True):
            with st.spinner("Fetching..."):
                drafts_result = get_gmail_drafts(st.session_state.credentials, max_results=5)
                
                if drafts_result['status'] == 'success':
                    st.session_state.gmail_drafts = drafts_result['drafts']
                    st.rerun()
                else:
                    st.error(f"Error: {drafts_result['message']}")
        
        if 'gmail_drafts' in st.session_state and st.session_state.gmail_drafts:
            for draft in st.session_state.gmail_drafts:
                with st.expander(f"✉️ {draft['subject'][:25]}..."):
                    st.write(f"**To:** {draft['to']}")
                    st.write(f"**Date:** {draft['date']}")
                    
                    # Button to view full content
                    if st.button(f"📄 View Content", key=f"view_{draft['id']}", use_container_width=True):
                        with st.spinner("Loading draft..."):
                            content_result = get_draft_content(st.session_state.credentials, draft['id'])
                            
                            if content_result['status'] == 'success':
                                st.session_state.viewing_draft = content_result
                                st.rerun()
                            else:
                                st.error(f"Error: {content_result['message']}")
        
        st.markdown("---")
        if st.button("🚪 Sign Out", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            if os.path.exists('token.pickle'):
                os.remove('token.pickle')
            st.rerun()
    
    # Main content
    st.header("📝 Generate Task Email")
    
    # Check if viewing a draft
    if 'viewing_draft' in st.session_state and st.session_state.viewing_draft:
        st.markdown("---")
        st.markdown("### 📧 Viewing Draft")
        
        draft_data = st.session_state.viewing_draft
        
        st.markdown(f"**Subject:** {draft_data['subject']}")
        st.markdown(f"**To:** {draft_data['to']}")
        st.markdown("---")
        
        # Display content in scrollable container
        st.markdown(draft_data['body'], unsafe_allow_html=True)
        
        st.markdown("---")
        if st.button("✖️ Close", use_container_width=True):
            del st.session_state.viewing_draft
            st.rerun()
        
        st.markdown("---")
    
    # Status
    col_status1, col_status2 = st.columns(2)
    with col_status1:
        st.markdown('<div class="success-box">✅ <strong>Gemini API:</strong> Ready</div>', unsafe_allow_html=True)
    with col_status2:
        st.markdown('<div class="success-box">✅ <strong>Google:</strong> Connected</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Input section
    col1, col2 = st.columns([3, 2])
    
    with col1:
        sheet_id = st.text_input(
            "📊 Google Sheets ID",
            placeholder="1mRPSNmWk86wEc6R9xaPNq9eRuycMQYKcgR6ioHoWDIg",
            help="Copy from your Google Sheets URL"
        )
        
        sheet_name = st.text_input(
            "📄 Sheet Name",
            value="Sheet1"
        )
    
    with col2:
        email_option = st.radio(
            "📧 Send to:",
            ["My account", "Custom email"]
        )
        
        if email_option == "Custom email":
            recipient_email = st.text_input(
                "Recipient Email",
                placeholder="manager@example.com"
            )
        else:
            recipient_email = st.session_state.user_email
        
        st.markdown(f'<div class="info-box">📬 <strong>{recipient_email}</strong></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        preview_btn = st.button("👁️ Preview", type="secondary", use_container_width=True)
    
    with col2:
        send_btn = st.button("📝 Create Draft", type="primary", use_container_width=True)
    
    with col3:
        clear_btn = st.button("🗑️ Clear", use_container_width=True)
    
    if clear_btn:
        st.session_state.preview_content = None
        st.rerun()
    
    # Preview
    if preview_btn:
        if not sheet_id:
            st.error("❌ Enter Google Sheets ID")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("🔄 Reading Sheets... (1/2)")
            progress_bar.progress(25)
            
            sheet_result = read_google_sheet(
                st.session_state.credentials,
                sheet_id,
                sheet_name
            )
            
            if sheet_result['status'] == 'error':
                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ {sheet_result['message']}")
            else:
                progress_bar.progress(50)
                status_text.text(f"✅ {len(sheet_result['data'])} rows read")
                
                status_text.text("🤖 Analyzing... (2/2)")
                progress_bar.progress(75)
                
                analysis_result = analyze_with_gemini(
                    sheet_result['data'],
                    st.session_state.gemini_key
                )
                
                if analysis_result['status'] == 'error':
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"❌ {analysis_result['message']}")
                else:
                    progress_bar.progress(100)
                    st.session_state.preview_content = analysis_result['content']
                    
                    import time
                    time.sleep(0.3)
                    progress_bar.empty()
                    status_text.empty()
                    st.success("✅ Generated!")
    
    # Display preview
    if st.session_state.preview_content:
        st.markdown("---")
        st.markdown("### 📧 Email Preview")
        
        st.markdown(f"**Subject:** {get_email_subject()}")
        st.markdown(f"**To:** {recipient_email}")
        st.markdown("---")
        
        # Show rendered email with proper table formatting
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Calibri, Arial, sans-serif;
                    font-size: 14px;
                    line-height: 1.6;
                    padding: 20px;
                    margin: 0;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 10px 0;
                }}
                th, td {{
                    border: 1px solid #d0d0d0;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #4a5f8c;
                    color: white;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            {st.session_state.preview_content}
        </body>
        </html>
        """
        
        # Display in component with scrolling
        st.components.v1.html(html_content, height=600, scrolling=True)
    
    # Create draft
    if send_btn:
        if not st.session_state.preview_content:
            st.warning("⚠️ Preview first")
        elif not recipient_email:
            st.error("❌ Enter recipient email")
        else:
            with st.spinner("📝 Creating draft..."):
                subject = get_email_subject()
                
                send_result = send_email(
                    st.session_state.credentials,
                    recipient_email,
                    subject,
                    st.session_state.preview_content
                )
                
                if send_result['status'] == 'error':
                    st.error(f"❌ {send_result['message']}")
                else:
                    st.success("✅ Draft created!")
                    st.balloons()
                    
                    st.markdown(f'<div class="success-box">📬 Draft for <strong>{recipient_email}</strong><br>Check Gmail to send!</div>', unsafe_allow_html=True)
                    
                    st.session_state.preview_content = None