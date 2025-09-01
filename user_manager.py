"""
FIT Group - User Management System
==================================
Multi-user authentication and token management using Notion database.
Handles user registration, OAuth token storage, and session management.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from notion_client import Client as NotionClient

# Optional encryption support (recommended). If TOKEN_ENCRYPTION_KEY is set and
# the cryptography package is available, access/refresh tokens will be encrypted
# before storing in Notion and decrypted on read.
try:
    from cryptography.fernet import Fernet  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Fernet = None  # type: ignore


class UserManager:
    """Manages user authentication and token storage in Notion"""
    
    def __init__(self, notion_token: str, users_db_id: str):
        """Initialize User Manager with Notion client"""
        self.notion_client = NotionClient(auth=notion_token)
        self.users_db_id = users_db_id
        self.logger = logging.getLogger(__name__)

        # Will be populated from DB schema
        self.db_properties: Dict[str, Any] = {}
        self.title_prop_name: Optional[str] = None
        
        # Set up optional application-layer encryption
        self._setup_crypto()
        
        # Ensure users database exists and load schema
        self._ensure_users_database()
        self._load_db_schema()
        
        # Validate OAuth provider configuration early (fail fast with clear error)
        try:
            _ = self._get_oauth_provider()
        except Exception as e:
            # Log a clear message to help operators
            self.logger.error(f"OAuth client configuration invalid or missing (GOOGLE_CLIENT_SECRET_JSON). Details: {e}")
            # Do not raise here; refresh/build calls will raise with clear error if needed.

    # ---------------------------
    # Internal helpers (security)
    # ---------------------------
    def _setup_crypto(self):
        """Initialize Fernet encryption using TOKEN_ENCRYPTION_KEY if available."""
        self._fernet = None
        key = os.environ.get('TOKEN_ENCRYPTION_KEY')
        if key:
            if Fernet is None:
                self.logger.warning(
                    "TOKEN_ENCRYPTION_KEY set but 'cryptography' is not installed; storing tokens in plaintext."
                )
                return
            try:
                self._fernet = Fernet(key.encode())
                self.logger.info("Token encryption enabled for Notion-stored tokens")
            except Exception as e:
                self._fernet = None
                self.logger.warning(f"Failed to initialize token encryption, storing plaintext tokens. Reason: {e}")

    def _encrypt_value(self, value: str) -> str:
        if not value:
            return value
        if self._fernet is None:
            return value
        try:
            return self._fernet.encrypt(value.encode('utf-8')).decode('utf-8')
        except Exception as e:
            self.logger.warning(f"Token encryption failed, storing plaintext. Reason: {e}")
            return value

    def _decrypt_value(self, value: str) -> str:
        if not value:
            return value
        if self._fernet is None:
            return value
        try:
            return self._fernet.decrypt(value.encode('utf-8')).decode('utf-8')
        except Exception as e:
            # If value was not encrypted previously, return as-is
            self.logger.debug(f"Token decryption skipped/failed, assuming plaintext. Reason: {e}")
            return value

    def _secure_store(self, value: str) -> str:
        """Apply encryption if available before storing sensitive values."""
        return self._encrypt_value(value)

    def _secure_read(self, value: str) -> str:
        """Decrypt stored sensitive values if encryption is enabled."""
        return self._decrypt_value(value)

    # ------------------------------
    # Notion schema/connection guard
    # ------------------------------
    def _ensure_users_database(self):
        """Ensure the users database exists with proper schema"""
        try:
            # Check if database exists
            database = self.notion_client.databases.retrieve(database_id=self.users_db_id)
            self.logger.info(
                f"✅ Users database found: {database.get('title', [{}])[0].get('plain_text', 'Unknown')} (id={self.users_db_id})"
            )
        except Exception as e:
            self.logger.error(f"❌ Users database not found (id={self.users_db_id}): {str(e)}")
            raise Exception(f"Users database {self.users_db_id} not accessible. Please check NOTION_USERS_DB_ID.")

    def _load_db_schema(self):
        """Load and cache DB properties; identify the Title property name."""
        try:
            database = self.notion_client.databases.retrieve(database_id=self.users_db_id)
            self.db_properties = database.get('properties', {}) or {}
            # Find the title property name
            for prop_name, prop_def in self.db_properties.items():
                if prop_def.get('type') == 'title':
                    self.title_prop_name = prop_name
                    break
            if not self.title_prop_name:
                # Notion DB must have exactly one title property
                raise Exception("Users DB has no title property; please add a Title column (e.g., 'Name').")
            self.logger.info(f"Users DB title property: {self.title_prop_name}")
        except Exception as e:
            self.logger.error(f"❌ Failed to load users DB schema: {e}")
            raise

    def _get_property_type(self, property_name: str) -> Optional[str]:
        prop = self.db_properties.get(property_name)
        return prop.get('type') if isinstance(prop, dict) else None

    def _build_property_value(self, property_name: str, value: Any) -> Optional[Dict[str, Any]]:
        ptype = self._get_property_type(property_name)
        if not ptype:
            # Unknown property in DB; don't include
            self.logger.debug(f"Skipping unknown Notion property '{property_name}'")
            return None
        if ptype == 'title':
            return {"title": [{"text": {"content": str(value)}}]}
        if ptype == 'email':
            return {"email": str(value) if value else None}
        if ptype == 'rich_text':
            return {"rich_text": [{"text": {"content": str(value) if value is not None else ''}}]}
        if ptype == 'date':
            return {"date": {"start": str(value) if value else None}}
        if ptype == 'select':
            return {"select": {"name": str(value)} if value else None}
        if ptype == 'multi_select':
            return {"multi_select": [{"name": str(v)} for v in (value or [])]}
        if ptype == 'number':
            try:
                return {"number": float(value)}
            except Exception:
                return {"number": None}
        if ptype == 'checkbox':
            return {"checkbox": bool(value)}
        # Default: skip unsupported types
        self.logger.debug(f"Unsupported Notion property type '{ptype}' for '{property_name}'")
        return None

    # ----------------
    # Public interface
    # ----------------
    def create_user(self, email: str, google_tokens: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user in Notion Users database. Adapts to DB schema."""
        try:
            # Check if user already exists
            existing_user = self.get_user_by_email(email)
            if existing_user:
                return self.update_user_tokens(email, google_tokens)
            
            # Prepare sensitive tokens (optionally encrypted)
            access_token = self._secure_store(google_tokens.get('access_token', ''))
            refresh_token = self._secure_store(google_tokens.get('refresh_token', ''))
            token_uri = google_tokens.get('token_uri', 'https://oauth2.googleapis.com/token')
            scopes = google_tokens.get('scopes', [])

            # Build properties dynamically
            properties: Dict[str, Any] = {}
            # Always set the Title property to the email for human readability
            title_payload = self._build_property_value(self.title_prop_name, email)
            if title_payload:
                properties[self.title_prop_name] = title_payload
            
            # Set the 'Email' property according to its schema (email or title)
            if 'Email' in self.db_properties:
                email_payload = self._build_property_value('Email', email)
                if email_payload is not None:
                    properties['Email'] = email_payload
            
            # Common token properties (only if present in DB)
            for name, value in [
                ('Google Access Token', access_token),
                ('Google Refresh Token', refresh_token),
                ('Token Expiry', google_tokens.get('expires_at', '')),
                ('Token URI', token_uri),
                ('Scopes', json.dumps(scopes))
            ]:
                payload = self._build_property_value(name, value)
                if payload is not None:
                    properties[name] = payload
            
            # Status, Created At, Last Login if present in DB
            for name, value in [
                ('Status', 'Active'),
                ('Created At', datetime.utcnow().isoformat()),
                ('Last Login', datetime.utcnow().isoformat()),
            ]:
                payload = self._build_property_value(name, value)
                if payload is not None:
                    properties[name] = payload

            response = self.notion_client.pages.create(
                parent={"database_id": self.users_db_id},
                properties=properties
            )
            
            self.logger.info(f"✅ Created new user in Notion (email={email}, page_id={response.get('id')})")
            return {
                'user_id': response['id'],
                'email': email,
                'status': 'created',
                'created_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create user in Notion (email={email}, db={self.users_db_id}): {str(e)}")
            raise Exception(f"User creation failed: {str(e)}")
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieve user by email address. Adapts query to DB schema."""
        try:
            # Prefer querying by the 'Email' property if it exists
            if 'Email' in self.db_properties:
                ptype = self._get_property_type('Email')
                if ptype == 'email':
                    flt = {"property": "Email", "email": {"equals": email}}
                elif ptype == 'title':
                    flt = {"property": "Email", "title": {"equals": email}}
                else:
                    # Fallback to title property
                    flt = {"property": self.title_prop_name, "title": {"equals": email}}
            else:
                # Fallback: filter by title property (we store email in title)
                flt = {"property": self.title_prop_name, "title": {"equals": email}}

            response = self.notion_client.databases.query(
                database_id=self.users_db_id,
                filter=flt
            )
            
            if response['results']:
                user_page = response['results'][0]
                return self._parse_user_page(user_page)
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get user from Notion (email={email}, db={self.users_db_id}): {str(e)}")
            return None
    
    def update_user_tokens(self, email: str, google_tokens: Dict[str, Any]) -> Dict[str, Any]:
        """Update user's Google OAuth tokens"""
        try:
            user = self.get_user_by_email(email)
            if not user:
                raise Exception(f"User {email} not found")
            
            access_token = self._secure_store(google_tokens.get('access_token', ''))
            refresh_token = self._secure_store(google_tokens.get('refresh_token', ''))
            token_uri = google_tokens.get('token_uri', user.get('token_uri') or 'https://oauth2.googleapis.com/token')
            
            # Update token properties
            update_data: Dict[str, Any] = {}
            for name, value in [
                ('Google Access Token', access_token),
                ('Google Refresh Token', refresh_token),
                ('Token Expiry', google_tokens.get('expires_at', '')),
                ('Token URI', token_uri),
                ('Last Login', datetime.utcnow().isoformat()),
            ]:
                payload = self._build_property_value(name, value)
                if payload is not None:
                    update_data[name] = payload
            
            self.notion_client.pages.update(
                page_id=user['user_id'],
                properties=update_data
            )
            
            self.logger.info(f"✅ Updated tokens for user in Notion (email={email}, page_id={user['user_id']})")
            return {
                'user_id': user['user_id'],
                'email': email,
                'status': 'updated',
                'updated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to update user tokens in Notion (email={email}, db={self.users_db_id}): {str(e)}")
            raise Exception(f"Token update failed: {str(e)}")
    
    def refresh_user_tokens(self, email: str) -> Optional[Dict[str, Any]]:
        """Refresh user's Google OAuth tokens (handles refresh token rotation)"""
        try:
            user = self.get_user_by_email(email)
            if not user:
                return None
            
            # Build credentials for refresh
            provider = self._get_oauth_provider()
            token_uri = provider.get('token_uri', user.get('token_uri') or 'https://oauth2.googleapis.com/token')
            creds = Credentials(
                token=None,  # Force refresh
                refresh_token=self._secure_read(user['google_refresh_token']),
                token_uri=token_uri,
                client_id=provider.get('client_id'),
                client_secret=provider.get('client_secret'),
                scopes=user['scopes']
            )
            
            # Refresh tokens
            creds.refresh(Request())
            
            # Detect refresh token rotation (rare, but handle if provided)
            rotated_refresh = creds.refresh_token or self._secure_read(user['google_refresh_token'])
            
            # Update in Notion
            new_tokens = {
                'access_token': creds.token,
                'refresh_token': rotated_refresh,
                'expires_at': creds.expiry.isoformat() if creds.expiry else '',
                'token_uri': token_uri,
                'scopes': user['scopes']
            }
            
            return self.update_user_tokens(email, new_tokens)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to refresh tokens for user (email={email}): {str(e)}")
            return None
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from the database (with pagination)"""
        try:
            users = []
            start_cursor: Optional[str] = None
            while True:
                query_args: Dict[str, Any] = {
                    'database_id': self.users_db_id,
                    'sorts': [{"property": self.title_prop_name or "Created At", "direction": "descending"}]
                }
                if start_cursor:
                    query_args['start_cursor'] = start_cursor
                response = self.notion_client.databases.query(**query_args)
                
                for user_page in response.get('results', []):
                    user_data = self._parse_user_page(user_page)
                    if user_data:
                        users.append(user_data)
                
                if response.get('has_more'):
                    start_cursor = response.get('next_cursor')
                else:
                    break
            
            return users
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get all users from Notion (db={self.users_db_id}): {str(e)}")
            return []
    
    def _parse_user_page(self, user_page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Notion user page into user data dictionary (adapts to schema)."""
        try:
            properties = user_page.get('properties', {})
            
            # Determine email from Email property (email/title) or fallback to Title
            email_value = ''
            email_prop_type = self._get_property_type('Email') if 'Email' in self.db_properties else None
            if email_prop_type == 'email':
                email_value = properties.get('Email', {}).get('email', '')
            elif email_prop_type == 'title':
                email_value = self._join_rich_text(properties.get('Email', {}).get('title', []))
            if not email_value and self.title_prop_name:
                email_value = self._join_rich_text(properties.get(self.title_prop_name, {}).get('title', []))
            if not email_value:
                return None
            
            user_data = {
                'user_id': user_page['id'],
                'email': email_value,
                'google_access_token': self._secure_read(self._join_rich_text(properties.get('Google Access Token', {}).get('rich_text', []))),
                'google_refresh_token': self._secure_read(self._join_rich_text(properties.get('Google Refresh Token', {}).get('rich_text', []))),
                'token_expiry': self._extract_date(properties, 'Token Expiry'),
                'token_uri': self._join_rich_text(properties.get('Token URI', {}).get('rich_text', [])) or 'https://oauth2.googleapis.com/token',
                'scopes': self._extract_scopes(properties, 'Scopes'),
                'status': self._extract_select(properties, 'Status'),
                'created_at': self._extract_date(properties, 'Created At'),
                'last_login': self._extract_date(properties, 'Last Login')
            }
            
            return user_data
            
        except Exception as e:
            self.logger.error(f"❌ Failed to parse user page from Notion (page_id={user_page.get('id')}): {str(e)}")
            return None
    
    # ----------------
    # Notion utilities
    # ----------------
    def _join_rich_text(self, rich_segments: List[Dict[str, Any]]) -> str:
        return ''.join((seg.get('plain_text', '') for seg in rich_segments or []))

    def _extract_date(self, properties: Dict[str, Any], property_name: str) -> str:
        """Extract date from Notion property"""
        prop = properties.get(property_name, {}).get('date', {})
        return prop.get('start', '') if prop else ''
    
    def _extract_select(self, properties: Dict[str, Any], property_name: str) -> str:
        """Extract select value from Notion property"""
        prop = properties.get(property_name, {}).get('select', {})
        return prop.get('name', '') if prop else ''
    
    def _extract_scopes(self, properties: Dict[str, Any], property_name: str) -> List[str]:
        """Extract and parse scopes from Notion property"""
        scopes_text = self._join_rich_text(properties.get(property_name, {}).get('rich_text', []))
        try:
            return json.loads(scopes_text) if scopes_text else []
        except Exception as e:
            self.logger.warning(f"Failed to parse scopes JSON from Notion property '{property_name}': {e}")
            return []
    
    # ----------------------
    # Credential management
    # ----------------------
    def _get_oauth_provider(self) -> Dict[str, Any]:
        """Load and validate OAuth client provider (installed/web) from environment."""
        client_secret_json = os.environ.get('GOOGLE_CLIENT_SECRET_JSON')
        if not client_secret_json:
            raise Exception("GOOGLE_CLIENT_SECRET_JSON not configured")
        cfg = json.loads(client_secret_json)
        if not isinstance(cfg, dict):
            raise Exception("Invalid GOOGLE_CLIENT_SECRET_JSON format: expected JSON object")
        provider = cfg.get('installed') or cfg.get('web') or cfg
        # Validate required fields
        missing = []
        for k in ('client_id', 'client_secret', 'token_uri'):
            if not provider.get(k):
                missing.append(k)
        if missing:
            raise Exception(f"Missing required OAuth config fields: {', '.join(missing)}")
        return provider

    def is_token_expired(self, email: str) -> bool:
        """Check if user's token is expired"""
        try:
            user = self.get_user_by_email(email)
            if not user:
                self.logger.warning(f"Token expiry check: user not found (email={email})")
                return True
            if not user.get('token_expiry'):
                self.logger.info(f"Token expiry missing; will refresh proactively (email={email})")
                return True
            try:
                expiry = datetime.fromisoformat(user['token_expiry'].replace('Z', '+00:00'))
            except Exception as pe:
                self.logger.warning(f"Malformed token expiry for user (email={email}): {user['token_expiry']} ({pe})")
                return True
            now = datetime.now(expiry.tzinfo) if expiry.tzinfo else datetime.utcnow()
            return now >= expiry
        except Exception as e:
            self.logger.error(f"❌ Failed to check token expiry for {email}: {str(e)}")
            return True
    
    def get_valid_credentials(self, email: str) -> Optional[Credentials]:
        """Get valid Google credentials for a user"""
        try:
            user = self.get_user_by_email(email)
            if not user:
                self.logger.warning(f"Requested credentials for unknown user (email={email})")
                return None
            
            # Check if token is expired
            if self.is_token_expired(email):
                # Try to refresh
                refreshed = self.refresh_user_tokens(email)
                if not refreshed:
                    self.logger.warning(f"Failed to refresh tokens (email={email})")
                    return None
                user = self.get_user_by_email(email)  # Get updated data
                if not user:
                    self.logger.warning(f"User disappeared after refresh (email={email})")
                    return None
            
            # Build credentials with server-side client credentials
            provider = self._get_oauth_provider()
            token_uri = provider.get('token_uri', user.get('token_uri') or 'https://oauth2.googleapis.com/token')
            creds = Credentials(
                token=self._secure_read(user['google_access_token']),
                refresh_token=self._secure_read(user['google_refresh_token']),
                token_uri=token_uri,
                client_id=provider.get('client_id'),
                client_secret=provider.get('client_secret'),
                scopes=user['scopes']
            )
            
            return creds
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get credentials for {email}: {str(e)}")
            return None
