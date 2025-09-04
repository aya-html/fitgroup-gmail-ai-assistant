"""
FIT Group - Multi-User Gmail Assistant Web API
==============================================
Production-ready Flask application for the Unified Multilingual Gmail Assistant.
Provides REST API endpoints for email processing, monitoring, and management.
Supports multiple users with individual Gmail accounts and shared results database.
"""
from dotenv import load_dotenv
load_dotenv()
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any


from flask import Flask, request, jsonify, render_template_string, render_template, redirect, url_for
from flask_cors import CORS
import traceback

# Import our core modules
from gmail_assistant import GmailAssistant, EmailProcessingError
from user_manager import UserManager
from auth_manager import AuthManager
from notion_manager import NotionManager
from werkzeug.middleware.proxy_fix import ProxyFix


# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'b6f91a2f93d64d5f9c56a02b2a6e6b8b9c7e8c9c1a3d9f7c2b5e8a7f5c1b2a9d')
CORS(app)  # Enable CORS for frontend integration

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_REFRESH_EACH_REQUEST=True
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
user_manager = None
auth_manager = None
notion_manager = None

# Ensure services are initialized on first request if import-time init failed
def ensure_services_initialized():
    """Ensure all services are initialized before first request"""
    global user_manager, auth_manager, notion_manager
    if user_manager is None:
        try:
            initialize_services()
            logger.info("✅ Services initialized on first request")
        except Exception as e:
            logger.error(f"❌ Service initialization failed on first request: {str(e)}")
            raise



def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    return {
        # OpenAI Configuration
        'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
        
        # Google APIs Configuration
        'GOOGLE_CLIENT_SECRET_JSON': os.environ.get('GOOGLE_CLIENT_SECRET_JSON'),
                        'GMAIL_USER_EMAIL': os.environ.get('GMAIL_USER_EMAIL', 'admin@fitgroup.com'),
        
        # Notion Configuration
        'NOTION_TOKEN': os.environ.get('NOTION_TOKEN'),
        'NOTION_USERS_DB_ID': os.environ.get('NOTION_USERS_DB_ID'),
        'NOTION_RESULTS_DB_ID': os.environ.get('NOTION_RESULTS_DB_ID'),
        'NOTION_DATABASE_ID': os.environ.get('NOTION_RESULTS_DB_ID'),  # Legacy support - now points to results DB
        
        # Application Configuration
        'FLASK_ENV': os.environ.get('FLASK_ENV', 'production'),
        'DEBUG': os.environ.get('DEBUG', 'False').lower() == 'true',
        'PORT': int(os.environ.get('PORT', 10000)),
        'HOST': os.environ.get('HOST', '0.0.0.0')
    }


def initialize_services():
    """Initialize all services with configuration"""
    global user_manager, auth_manager, notion_manager
    
    try:
        config = load_config()
        
        # Validate required configuration
        required_vars = ['OPENAI_API_KEY', 'NOTION_TOKEN', 'NOTION_USERS_DB_ID', 'NOTION_RESULTS_DB_ID', 'GOOGLE_CLIENT_SECRET_JSON']
        missing_vars = [var for var in required_vars if not config.get(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables for multi-user mode: {', '.join(missing_vars)}")
        
        # Initialize Notion Manager (required for multi-user)
        notion_manager = NotionManager(
            config['NOTION_TOKEN'],
            config['NOTION_USERS_DB_ID'],
            config['NOTION_RESULTS_DB_ID']
        )
        logger.info("✅ Notion Manager initialized successfully")
        
        # Initialize User Manager
        user_manager = UserManager(
            config['NOTION_TOKEN'],
            config['NOTION_USERS_DB_ID']
        )
        logger.info("✅ User Manager initialized successfully")
        
        # Initialize Auth Manager
        auth_manager = AuthManager(user_manager, config.get('GOOGLE_CLIENT_SECRET_JSON'))
        logger.info("✅ Auth Manager initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {str(e)}")
        raise

# Ensure services are ready when imported by Gunicorn/Render
try:
    if user_manager is None:
        initialize_services()
        logger.info("✅ Services initialized during import")
except Exception as e:
    logger.warning(f"⚠️ Import-time initialization failed: {str(e)}")
    logger.info("Services will be initialized on first request")

# Use Flask 2.3+ compatible approach
with app.app_context():
    try:
        if user_manager is None:
            ensure_services_initialized()
    except Exception as e:
        logger.warning(f"⚠️ App context initialization failed: {str(e)}")

# Error handlers
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/auth/google"):
        return "Invalid OAuth callback URL", 400
    if auth_manager and auth_manager.is_authenticated():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred while processing your request.',
        'support': 'Please contact FIT Group support if this issue persists.'
    }), 500


@app.errorhandler(EmailProcessingError)
def handle_processing_error(error):
    logger.error(f"Email processing error: {str(error)}")
    return jsonify({
        'error': 'Email processing failed',
        'message': str(error),
        'type': 'EmailProcessingError'
    }), 400


# Authentication Routes
@app.route('/login', methods=['GET'])
def login_page():
    """Login page for multi-user authentication"""
    if auth_manager and auth_manager.is_authenticated():
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/auth/google', methods=['GET'])
def google_auth():
    """Initiate Google OAuth2 flow"""
    if not auth_manager:
        return jsonify({'error': 'Authentication not configured'}), 503
    
    try:
        redirect_uri = url_for('google_callback', _external=True)
        auth_url = auth_manager.get_authorization_url(redirect_uri)
        return redirect(auth_url)
    except Exception as e:
        logger.error(f"❌ Google auth failed: {str(e)}")
        return jsonify({'error': 'Authentication failed'}), 500

@app.route('/auth/google/callback')
def google_callback():
    if not auth_manager:
        return jsonify({'error': 'Authentication not configured'}), 503
    
    try:
        authorization_response = request.url
        redirect_uri = url_for('google_callback', _external=True)

        # Add error logging
        logger.info(f"Processing OAuth callback with redirect_uri: {redirect_uri}")
        print(f"========\n\n\n\n\n\n\n\n{redirect_uri}\n\n\n\n\n\n\n==========")
        
        result = auth_manager.handle_oauth_callback(authorization_response, redirect_uri)
        
        if not result:
            logger.error("OAuth callback returned False")
            return redirect(url_for('login_page'))

        # Verify tokens were saved
        current_user = auth_manager.get_current_user()
        if not current_user:
            logger.error("User not found after OAuth callback")
            return redirect(url_for('login_page'))

        user_creds = auth_manager.get_user_credentials()
        if not user_creds or not user_creds.refresh_token:
            logger.error("Missing refresh token after OAuth callback")
            # Force new OAuth flow with prompt
            return redirect(url_for('google_auth', prompt='consent'))

        return redirect(url_for('dashboard'))

    except Exception as e:
        logger.error(f"❌ OAuth callback failed: {str(e)}")
        return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    """Logout current user"""
    if auth_manager:
        auth_manager.logout()
    return redirect(url_for('login_page'))

@app.route('/dashboard')
def dashboard():
    """User dashboard (requires authentication)"""
    if not auth_manager or not auth_manager.is_authenticated():
        return redirect(url_for('login_page'))
    
    # Validate and refresh session
    if not auth_manager.validate_session():
        return redirect(url_for('login_page'))
    
    return render_template('dashboard.html')

@app.route('/', methods=['GET'])
def home():
    """Root redirect based on authentication state"""
    if auth_manager and auth_manager.is_authenticated():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))


def build_health_data():
    """Build health status dict (shared by endpoints)"""
    services = {
        'auth': bool(auth_manager),
        'user_manager': bool(user_manager),
        'notion_api': bool(notion_manager)
    }

    if not all(services.values()):
        return {
            'status': 'unhealthy',
            'message': 'Core services not initialized',
            'timestamp': datetime.utcnow().isoformat(),
            'services': services,
            'mode': 'multi-user'
        }, 503

    connectivity = {
        'notion': False,
        'openai_key': bool(os.environ.get('OPENAI_API_KEY')),
        'google_oauth': bool(os.environ.get('GOOGLE_CLIENT_SECRET_JSON'))
    }

    try:
        if notion_manager:
            notion_manager._ensure_databases()
            connectivity['notion'] = True
    except Exception as e:
        logger.warning(f"Notion connectivity check failed: {str(e)}")

    overall_healthy = all(services.values()) and connectivity['openai_key'] and connectivity['google_oauth']

    return {
        'status': 'healthy' if overall_healthy else 'degraded',
        'message': 'Core services operational' if overall_healthy else 'Some services degraded',
        'timestamp': datetime.utcnow().isoformat(),
        'services': services,
        'connectivity': connectivity,
        'version': '2.0.0',
        'mode': 'multi-user',
        'uptime': 'Running'
    }, 200 if overall_healthy else 200  # degraded still 200
        
@app.route('/api/health', methods=['GET'])
def health_check():
    data, status = build_health_data()
    return jsonify(data), status


@app.route('/api/stats', methods=['GET'])
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics and capabilities"""
    try:
        data, status_code = build_health_data()
        services = data['services']

        # If core services not initialized
        if not all(services.values()):
            return jsonify({'error': 'Core services not initialized', 'services': services}), 503

        stats = {
            'mode': 'multi-user',
            'services': services,
            'system_status': data['status'],  # directly from build_health_data
            'version': data.get('version'),
            'command_categories': len(GmailAssistant.BUSINESS_COMMANDS),
            'supported_languages': ['English', 'Spanish', 'French', 'German', 'Italian', 'Portuguese', 'Dutch', 'Chinese', 'Arabic'],
            'timestamp': datetime.utcnow().isoformat()
        }

        # Add user count if available
        try:
            users = user_manager.get_all_users()
            stats['users_count'] = len(users)
        except Exception:
            stats['users_count'] = None

        return jsonify(stats), status_code

    except Exception as e:
        logger.error(f"Stats retrieval failed: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve statistics',
            'message': str(e)
        }), 500

@app.route('/api/process-emails', methods=['POST'])
def process_emails():
    """Process recent emails through the AI pipeline"""
    try:
        # Require authentication
        if not auth_manager or not auth_manager.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get current user
        current_user = auth_manager.get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Create Gmail assistant with user credentials
        user_creds = auth_manager.get_user_credentials()
        if not user_creds:
            return jsonify({'error': 'Invalid user credentials'}), 401
        
        user_config = {
            'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
            'user_credentials': user_creds
        }
        user_assistant = GmailAssistant(user_config)
        
        # Parse request parameters
        data = request.get_json() or {}
        days = data.get('days', 7)
        max_results = data.get('max_results', 50)
        
        # Validate parameters
        if not isinstance(days, int) or days < 1 or days > 30:
            return jsonify({
                'error': 'Invalid days parameter',
                'message': 'Days must be an integer between 1 and 30'
            }), 400
        
        if not isinstance(max_results, int) or max_results < 1 or max_results > 100:
            return jsonify({
                'error': 'Invalid max_results parameter',
                'message': 'max_results must be an integer between 1 and 100'
            }), 400
        
        logger.info(f"📧 Processing emails request: {days} days, max {max_results} emails for user: {current_user.get('email')}")
        
        # Process emails
        result = user_assistant.process_emails_batch(
            days=days, 
            max_results=max_results
        )
        logger.error(f"current_user: {current_user} user_creds: {user_creds} user_assistant: {user_assistant}")
        # Save results to shared Notion database
        if notion_manager:
            try:
                for email in result.get('emails', []):
                    notion_manager.create_email_result(email, current_user['email'])
                result['notion_sync_success'] = True
            except Exception as e:
                logger.error(f"❌ Notion sync failed: {str(e)}")
                result['notion_sync_success'] = False
        else:
            logger.error(f"❌ Notion sync failed: no notion_manager")
        
        # Remove full email content from API response for performance
        if 'emails' in result:
            for email in result['emails']:
                email.pop('body', None)
                email.pop('raw_headers', None)
        
        return jsonify(result)
        
    except EmailProcessingError as e:
        return jsonify({
            'error': 'Email processing failed',
            'message': str(e)
        }), 400
    
    except Exception as e:
        logger.error(f"Email processing request failed: {str(e)}")
        return jsonify({
            'error': 'Processing request failed',
            'message': str(e),
            'traceback': traceback.format_exc() if app.config.get('DEBUG') else None
        }), 500


@app.route('/api/process-batch', methods=['POST'])
def process_batch():
    """Advanced batch processing with full analytics"""
    try:
        if not auth_manager or not auth_manager.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        current_user = auth_manager.get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        user_creds = auth_manager.get_user_credentials()
        if not user_creds:
            return jsonify({'error': 'Invalid user credentials'}), 401
        
        user_config = {
            'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
            'user_credentials': user_creds
        }
        user_assistant = GmailAssistant(user_config)
        
        # Parse request parameters
        data = request.get_json() or {}
        days = data.get('days', 7)
        max_results = data.get('max_results', 50)
        include_full_data = data.get('include_full_data', False)
        
        logger.info(f"🔄 Batch processing request: {days} days, max {max_results} emails for user: {current_user.get('email')}")
        
        # Process emails with full pipeline
        result = user_assistant.process_emails_batch(
            days=days,
            max_results=max_results
        )
        
        # Optionally remove full content for performance
        if not include_full_data and 'emails' in result:
            for email in result['emails']:
                email.pop('body', None)
                email.pop('raw_headers', None)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        return jsonify({
            'error': 'Batch processing failed',
            'message': str(e)
        }), 500


@app.route('/api/test-connection', methods=['GET'])
def test_connection():
    """Test API connections without processing emails (multi-user only)"""
    try:
        if not auth_manager or not auth_manager.is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        
        current_user = auth_manager.get_current_user()
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        user_creds = auth_manager.get_user_credentials()
        if not user_creds:
            return jsonify({'error': 'Invalid user credentials'}), 401
        
        user_config = {
            'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
            'user_credentials': user_creds
        }
        user_assistant = GmailAssistant(user_config)
        
        # Test individual services
        test_results = {
            'gmail_api': False,
            'openai_api': False,
            'notion_api': bool(notion_manager),
            'overall_status': False
        }
        
        # Test Gmail API
        try:
            profile = user_assistant.gmail_service.users().getProfile(userId='me').execute()
            test_results['gmail_api'] = True
            test_results['gmail_email'] = profile.get('emailAddress', 'Unknown')
        except Exception as e:
            test_results['gmail_error'] = str(e)
        
        # Test OpenAI API
        try:
            response = user_assistant.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Test connection - reply with 'OK'"}],
                max_tokens=10,
                temperature=0
            )
            if response.choices[0].message.content.strip().upper() == 'OK':
                test_results['openai_api'] = True
        except Exception as e:
            test_results['openai_error'] = str(e)
        
        # Overall status
        test_results['overall_status'] = (
            test_results['gmail_api'] and test_results['openai_api']
        )
        
        test_results['timestamp'] = datetime.utcnow().isoformat()
        
        return jsonify(test_results)
        
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return jsonify({
            'error': 'Connection test failed',
            'message': str(e)
        }), 500


# Multi-user API endpoints
@app.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    """Get current user profile"""
    if not auth_manager or not auth_manager.is_authenticated():
        return jsonify({'error': 'Authentication required'}), 401
    
    current_user = auth_manager.get_current_user()
    if not current_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Return safe user data (no sensitive tokens)
    safe_user_data = {
        'email': current_user['email'],
        'status': current_user['status'],
        'created_at': current_user['created_at'],
        'last_login': current_user['last_login']
    }
    
    return jsonify(safe_user_data)

@app.route('/api/user/results', methods=['GET'])
def get_user_results():
    """Get email processing results for current user"""
    if not auth_manager or not auth_manager.is_authenticated():
        return jsonify({'error': 'Authentication required'}), 401
    
    if not notion_manager:
        return jsonify({'error': 'Results database not configured'}), 503
    
    current_user = auth_manager.get_current_user()
    if not current_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get query parameters
    days = request.args.get('days', 30, type=int)
    limit = request.args.get('limit', 100, type=int)
    
    try:
        results = notion_manager.get_user_results(current_user['email'], days)
        return jsonify({
            'results': results[:limit],
            'total_count': len(results),
            'user_email': current_user['email']
        })
    except Exception as e:
        logger.error(f"❌ Failed to get user results: {str(e)}")
        return jsonify({'error': 'Failed to retrieve results'}), 500

@app.route('/api/user/labels', methods=['GET'])
def get_user_labels():
    """Get unique Gmail labels from Notion results for current user"""
    if not auth_manager or not auth_manager.is_authenticated():
        return jsonify({'error': 'Authentication required'}), 401
    if not notion_manager:
        return jsonify({'error': 'Results database not configured'}), 503
    current_user = auth_manager.get_current_user()
    if not current_user:
        return jsonify({'error': 'User not found'}), 404

    days = request.args.get('days', 60, type=int)
    try:
        labels = notion_manager.get_unique_labels(current_user['email'], days)
        return jsonify({'labels': labels, 'total_count': len(labels)})
    except Exception as e:
        logger.error(f"❌ Failed to get user labels: {str(e)}")
        return jsonify({'error': 'Failed to retrieve labels'}), 500

@app.route('/api/user/results/search', methods=['POST'])
def search_user_results():
    """Search Notion results DB using panel filters"""
    if not auth_manager or not auth_manager.is_authenticated():
        return jsonify({'error': 'Authentication required'}), 401
    if not notion_manager:
        return jsonify({'error': 'Results database not configured'}), 503
    current_user = auth_manager.get_current_user()
    if not current_user:
        return jsonify({'error': 'User not found'}), 404

    try:
        data = request.get_json() or {}
        user = data.get('user') or 'current'
        labels = data.get('labels') or []
        date_preset = data.get('date_preset')
        date_from = data.get('from')
        date_to = data.get('to')
        text = data.get('search')
        limit = int(data.get('limit') or 500)

        # Resolve user scope: None means all users
        user_email = None if user == 'all' else (current_user['email'] if user == 'current' else user)

        results = notion_manager.search_results(
            user_email=user_email,
            labels=labels,
            date_preset=date_preset,
            date_from=date_from,
            date_to=date_to,
            text=text,
            limit=limit
        )
        return jsonify({ 'results': results, 'count': len(results) })
    except Exception as e:
        logger.error(f"❌ Search failed: {str(e)}")
        return jsonify({'error': 'Search failed'}), 500

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    """Get all users (admin only)"""
    if not auth_manager or not auth_manager.is_authenticated():
        return jsonify({'error': 'Authentication required'}), 401
    
    if not user_manager:
        return jsonify({'error': 'User management not configured'}), 503
    
    try:
        users = user_manager.get_all_users()
        # Return safe user data
        safe_users = []
        for user in users:
            safe_users.append({
                'email': user['email'],
                'status': user['status'],
                'created_at': user['created_at'],
                'last_login': user['last_login']
            })
        
        return jsonify({'users': safe_users, 'total_count': len(safe_users)})
    except Exception as e:
        logger.error(f"❌ Failed to get users: {str(e)}")
        return jsonify({'error': 'Failed to retrieve users'}), 500

@app.route('/api/admin/statistics', methods=['GET'])
def get_admin_statistics():
    """Get system-wide statistics (admin only)"""
    if not auth_manager or not auth_manager.is_authenticated():
        return jsonify({'error': 'Authentication required'}), 401
    
    if not notion_manager:
        return jsonify({'error': 'Results database not configured'}), 503
    
    try:
        days = request.args.get('days', 30, type=int)
        stats = notion_manager.get_results_statistics(days=days)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"❌ Failed to get statistics: {str(e)}")
        return jsonify({'error': 'Failed to retrieve statistics'}), 500


if __name__ == '__main__':
    try:
        # Initialize all services
        initialize_services()
        
        # Load configuration
        config = load_config()
        
        # Run the Flask application
        logger.info(f"🚀 Starting FIT Group Multi-User Gmail Assistant API on {config['HOST']}:{config['PORT']}")
        logger.info(f"📧 Environment: {config['FLASK_ENV']}")
        logger.info(f"🔧 Debug mode: {config['DEBUG']}")
        
        if user_manager and auth_manager:
            logger.info("✅ Multi-user mode enabled")
        else:
            logger.error("❌ Multi-user services not initialized")
        
        app.run(
            host=config['HOST'],
            port=config['PORT'],
            debug=config['DEBUG'],
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start application: {str(e)}")
        print(f"Application startup failed: {str(e)}")
        exit(1)

