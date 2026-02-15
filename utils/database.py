import sqlite3
import json
import base64
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Generate or load encryption key
def get_encryption_key():
    """Get or create encryption key for sensitive data"""
    # First, try to get from environment variable
    env_key = os.getenv('SECRET_KEY')
    
    if env_key:
        # Use key from environment
        return env_key.encode() if isinstance(env_key, str) else env_key
    
    # Fallback: check for secret.key file
    key_file = 'secret.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    
    # Generate new key if neither exists
    key = Fernet.generate_key()
    
    # Save to file as backup
    with open(key_file, 'wb') as f:
        f.write(key)
    
    print("⚠️ WARNING: New secret key generated and saved to secret.key")
    print("⚠️ Please add this to your .env file as SECRET_KEY and delete secret.key")
    print(f"⚠️ SECRET_KEY={key.decode()}")
    
    return key

ENCRYPTION_KEY = get_encryption_key()
cipher = Fernet(ENCRYPTION_KEY)

class UserDatabase:
    def __init__(self, db_path='users.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                gemini_api_key_encrypted TEXT NOT NULL,
                google_credentials_encrypted TEXT,
                creds_fingerprint TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Draft history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS draft_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                draft_id TEXT NOT NULL,
                subject TEXT,
                recipient TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def encrypt_data(self, data):
        """Encrypt sensitive data"""
        if isinstance(data, dict):
            data = json.dumps(data)
        return cipher.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data):
        """Decrypt sensitive data"""
        try:
            decrypted = cipher.decrypt(encrypted_data.encode()).decode()
            try:
                return json.loads(decrypted)
            except:
                return decrypted
        except:
            return None
    
    def save_user(self, email, gemini_api_key, google_creds=None):
        """Save or update user credentials"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        encrypted_gemini = self.encrypt_data(gemini_api_key)
        encrypted_google = self.encrypt_data(google_creds) if google_creds else None
        
        try:
            cursor.execute('''
                INSERT INTO users (email, gemini_api_key_encrypted, google_credentials_encrypted)
                VALUES (?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    gemini_api_key_encrypted = excluded.gemini_api_key_encrypted,
                    google_credentials_encrypted = excluded.google_credentials_encrypted,
                    last_login = CURRENT_TIMESTAMP
            ''', (email, encrypted_gemini, encrypted_google))
            
            conn.commit()
            user_id = cursor.lastrowid if cursor.lastrowid else cursor.execute(
                'SELECT id FROM users WHERE email = ?', (email,)
            ).fetchone()[0]
            
            conn.close()
            return {'status': 'success', 'user_id': user_id}
        except Exception as e:
            conn.close()
            return {'status': 'error', 'message': str(e)}
    
    def get_user(self, email):
        """Retrieve user credentials"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, gemini_api_key_encrypted, google_credentials_encrypted
            FROM users WHERE email = ?
        ''', (email,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            user_id, email, encrypted_gemini, encrypted_google = result
            return {
                'status': 'success',
                'user_id': user_id,
                'email': email,
                'gemini_api_key': self.decrypt_data(encrypted_gemini),
                'google_creds': self.decrypt_data(encrypted_google) if encrypted_google else None
            }
        else:
            return {'status': 'error', 'message': 'User not found'}
    
    def list_all_users(self):
        """List all registered users (emails only)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT email FROM users ORDER BY last_login DESC')
        users = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return users
    
    def save_draft_history(self, user_id, draft_id, subject, recipient):
        """Save draft creation to history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO draft_history (user_id, draft_id, subject, recipient)
            VALUES (?, ?, ?, ?)
        ''', (user_id, draft_id, subject, recipient))
        
        conn.commit()
        conn.close()
    
    def get_draft_history(self, user_id, limit=10):
        """Get draft history for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT draft_id, subject, recipient, created_at
            FROM draft_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        drafts = []
        for row in cursor.fetchall():
            drafts.append({
                'draft_id': row[0],
                'subject': row[1],
                'recipient': row[2],
                'created_at': row[3]
            })
        
        conn.close()
        return drafts
    
    def delete_user(self, email):
        """Delete a user and all their data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get user_id first
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return {'status': 'error', 'message': 'User not found'}
            
            user_id = result[0]
            
            # Delete draft history
            cursor.execute('DELETE FROM draft_history WHERE user_id = ?', (user_id,))
            
            # Delete user
            cursor.execute('DELETE FROM users WHERE email = ?', (email,))
            
            conn.commit()
            conn.close()
            
            return {'status': 'success', 'message': 'User deleted successfully'}
            
        except Exception as e:
            conn.close()
            return {'status': 'error', 'message': str(e)}
    
    def check_fingerprint_exists(self, fingerprint):
        """Check if credentials fingerprint already exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email FROM users WHERE creds_fingerprint = ?
        ''', (fingerprint,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def save_fingerprint(self, email, fingerprint):
        """Save credentials fingerprint for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET creds_fingerprint = ? WHERE email = ?
        ''', (fingerprint, email))
        
        conn.commit()
        conn.close()