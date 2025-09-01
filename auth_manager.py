"""
FIT Group - Authentication Manager
=================================
Handles Google OAuth2 authentication flow and session management
for multi-user Gmail Assistant access.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask import session, redirect, url_for, request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from user_manager import UserManager


class AuthManager:
    """Manages Google OAuth2 authentication and user sessions"""
    
    # Gmail API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
    ]
    
    def __init__(self, user_manager: UserManager, client_secret_path: str = None):
        """Initialize Authentication Manager"""
        self.user_manager = user_manager
        self.client_secret_path = client_secret_path or 'client_secret.json'
        self.logger = logging.getLogger(__name__)
        
        # Load OAuth client configuration
        self._load_oauth_config()
    
    def _load_oauth_config(self):
        """Load OAuth client configuration from file"""
        try:
            if os.path.exists(self.client_secret_path):
                with open(self.client_secret_path, 'r') as f:
                    self.oauth_config = json.load(f)
                self.logger.info("✅ OAuth client configuration loaded")
            else:
                # Try to load from environment variable
                client_secret_json = os.environ.get('GOOGLE_CLIENT_SECRET_JSON')
                if client_secret_json:
                    self.oauth_config = json.loads(client_secret_json)
                    self.logger.info("✅ OAuth client configuration loaded from environment")
                else:
                    raise Exception("No OAuth client configuration found")
        except Exception as e:
            self.logger.error(f"❌ Failed to load OAuth config: {str(e)}")
            raise
    
    def get_authorization_url(self, redirect_uri: str) -> str:
        """Generate Google OAuth2 authorization URL"""
        try:
            flow = Flow.from_client_config(
                self.oauth_config,
                scopes=self.SCOPES
            )
            flow.redirect_uri = redirect_uri

            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'  # Always prompt to get refresh token
            )
            # Store only state to validate the callback (avoid storing flow in session)
            session['oauth_state'] = state
            
            self.logger.info("✅ Generated OAuth authorization URL")
            return authorization_url
            
        except Exception as e:
            self.logger.error(f"❌ Failed to generate authorization URL: {str(e)}")
            raise
    
    def handle_oauth_callback(self, authorization_response: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """Handle OAuth callback and exchange authorization code for tokens"""
        try:
            # Validate state to protect against CSRF
            expected_state = session.get('oauth_state')
            returned_state = request.args.get('state')
            if not expected_state or expected_state != returned_state:
                raise Exception("Invalid OAuth state")
            # Clear state from session after validation
            session.pop('oauth_state', None)

            # Extract authorization code
            code = request.args.get('code')
            if not code:
                raise Exception("Authorization code not found")

            # Recreate flow and exchange code for tokens
            flow = Flow.from_client_config(
                self.oauth_config,
                scopes=self.SCOPES
            )
            flow.redirect_uri = redirect_uri
            flow.fetch_token(code=code)
            
            # Get user info from Google
            credentials = flow.credentials
            user_info = self._get_user_info(credentials)
            
            if not user_info:
                raise Exception("Failed to get user info from Google")
            
            email = user_info['email']
            
            # Prepare tokens for storage
            google_tokens = {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'expires_at': credentials.expiry.isoformat() if credentials.expiry else '',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'scopes': credentials.scopes
            }
            
            # Create or update user in Notion
            user_result = self.user_manager.create_user(email, google_tokens)
            
            # Store user info in session
            session['user_email'] = email
            session['user_id'] = user_result['user_id']
            session['authenticated'] = True
            session['login_time'] = datetime.utcnow().isoformat()
            
                        
            self.logger.info(f"✅ User authenticated successfully: {email}")
            
            return {
                'email': email,
                'user_id': user_result['user_id'],
                'status': user_result['status']
            }
            
        except Exception as e:
            self.logger.error(f"❌ OAuth callback failed: {str(e)}")
            # Clear session on failure
            session.clear()
            return None
    
    def _get_user_info(self, credentials: Credentials) -> Optional[Dict[str, Any]]:
        """Get user information from Google using Gmail API profile (no userinfo scope required)."""
        try:
            gmail = build('gmail', 'v1', credentials=credentials)
            profile = gmail.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress')
            if not email:
                raise Exception("Email address not found in Gmail profile")
            return {
                'email': email,
                'name': None,
                'picture': None
            }
        except Exception as e:
            self.logger.error(f"❌ Failed to get user info: {str(e)}")
            return None
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return session.get('authenticated', False)
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current authenticated user"""
        if not self.is_authenticated():
            return None
        
        email = session.get('user_email')
        if not email:
            return None
        
        return self.user_manager.get_user_by_email(email)
    
    def logout(self):
        """Logout current user"""
        session.clear()
        self.logger.info("✅ User logged out")
    
    def require_auth(self, f):
        """Decorator to require authentication for routes"""
        def decorated_function(*args, **kwargs):
            if not self.is_authenticated():
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    
    def refresh_user_session(self) -> bool:
        """Refresh user's session and tokens if needed"""
        try:
            if not self.is_authenticated():
                return False
            
            email = session.get('user_email')
            if not email:
                return False
            
            # Check if tokens need refresh
            if self.user_manager.is_token_expired(email):
                refreshed = self.user_manager.refresh_user_tokens(email)
                if not refreshed:
                    self.logger.warning(f"⚠️ Failed to refresh tokens for {email}")
                    return False
                
                self.logger.info(f"✅ Refreshed tokens for {email}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Session refresh failed: {str(e)}")
            return False
    
    def get_user_credentials(self, email: str = None) -> Optional[Credentials]:
        """Get valid Google credentials for a user"""
        if not email:
            email = session.get('user_email')
        
        if not email:
            return None
        
        return self.user_manager.get_valid_credentials(email)
    
    def validate_session(self) -> bool:
        """Validate current session and refresh if needed"""
        if not self.is_authenticated():
            return False
        
        # Check if session is still valid
        login_time = session.get('login_time')
        if login_time:
            try:
                login_dt = datetime.fromisoformat(login_time)
                # Session expires after 24 hours
                if datetime.utcnow() - login_dt > timedelta(hours=24):
                    self.logout()
                    return False
            except:
                pass
        
        # Refresh tokens if needed
        return self.refresh_user_session()
    
    def get_oauth_config_info(self) -> Dict[str, Any]:
        """Get OAuth configuration information for frontend"""
        try:
            provider = self.oauth_config.get('installed') or self.oauth_config.get('web') or {}
            return {
                'client_id': provider.get('client_id'),
                'auth_uri': provider.get('auth_uri'),
                'token_uri': provider.get('token_uri'),
                'scopes': self.SCOPES
            }
        except Exception as e:
            self.logger.error(f"❌ Failed to get OAuth config info: {str(e)}")
            return {}
