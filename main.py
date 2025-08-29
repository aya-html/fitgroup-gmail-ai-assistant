"""
FIT Group - Gmail Assistant Web API
===================================
Production-ready Flask application for the Unified Multilingual Gmail Assistant.
Provides REST API endpoints for email processing, monitoring, and management.
"""
from dotenv import load_dotenv
load_dotenv()
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from flask import Flask, request, jsonify, render_template_string, render_template
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
import traceback

# Import our core Gmail Assistant
from gmail_assistant import create_gmail_assistant, EmailProcessingError


# Initialize Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend integration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global assistant instance
gmail_assistant = None


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    return {
        # OpenAI Configuration
        'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
        
        # Google APIs Configuration
        'GOOGLE_SERVICE_ACCOUNT_JSON': os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON'),
        'GOOGLE_OAUTH_TOKEN': os.environ.get('GOOGLE_OAUTH_TOKEN'),
        'GMAIL_USER_EMAIL': os.environ.get('GMAIL_USER_EMAIL', 'admin@fitgroup.com'),
        
        # Notion Configuration
        'NOTION_TOKEN': os.environ.get('NOTION_TOKEN'),
        'NOTION_DATABASE_ID': os.environ.get('NOTION_DATABASE_ID'),
        
        # Application Configuration
        'FLASK_ENV': os.environ.get('FLASK_ENV', 'production'),
        'DEBUG': os.environ.get('DEBUG', 'False').lower() == 'true',
        'PORT': int(os.environ.get('PORT', 10000)),
        'HOST': os.environ.get('HOST', '0.0.0.0')
    }


def initialize_assistant():
    """Initialize the Gmail Assistant with configuration"""
    global gmail_assistant
    try:
        config = load_config()
        
        # Validate required configuration
        required_vars = ['OPENAI_API_KEY']
        missing_vars = [var for var in required_vars if not config.get(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        if not config.get('GOOGLE_SERVICE_ACCOUNT_JSON') and not config.get('GOOGLE_OAUTH_TOKEN'):
            raise ValueError("Either GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_OAUTH_TOKEN must be provided")
        
        gmail_assistant = create_gmail_assistant(config)
        logger.info("✅ Gmail Assistant initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gmail Assistant: {str(e)}")
        raise

# Ensure the assistant is ready when imported by Gunicorn/Render
try:
    if gmail_assistant is None:
        initialize_assistant()
except Exception as e:
    logger.exception(f"Startup init failed: {e}")

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'message': 'The requested URL was not found on this server.',
        'available_endpoints': [
            '/api/health',
            '/api/process-emails',
            '/api/stats',
            '/api/process-batch'
        ]
    }), 404


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


# API Routes
@app.route('/admin', methods=['GET'])
def admin_page():
    return render_template('admin.html')

@app.route('/', methods=['GET'])
def home():
    """Home page with API documentation"""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FIT Group - Gmail Assistant API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            .header { background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }
            .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .method { display: inline-block; padding: 4px 8px; border-radius: 3px; font-weight: bold; }
            .get { background: #28a745; color: white; }
            .post { background: #007bff; color: white; }
            code { background: #e9ecef; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 FIT Group - Multilingual Gmail Assistant API</h1>
            <p>Advanced AI-powered email processing system with GPT-4 integration</p>
            <p><strong>Status:</strong> {{ status }} | <strong>Version:</strong> 2.0.0 | <strong>Time:</strong> {{ timestamp }}</p>
        </div>
        
        <h2>📡 Available Endpoints</h2>
        
        <div class="endpoint">
            <span class="method get">GET</span> <code>/api/health</code>
            <p>System health check and service status</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span> <code>/api/stats</code>
            <p>Processing statistics and system information</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span> <code>/api/process-emails</code>
            <p>Process recent emails with AI analysis</p>
            <p><strong>Parameters:</strong> <code>days</code> (optional, default: 7), <code>max_results</code> (optional, default: 50)</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span> <code>/api/process-batch</code>
            <p>Advanced batch processing with detailed analytics</p>
            <p><strong>Parameters:</strong> <code>days</code>, <code>max_results</code>, <code>sync_notion</code></p>
        </div>
        
        <h2>🔧 Features</h2>
        <ul>
            <li>✅ Multilingual email processing (English, Spanish, French, German, etc.)</li>
            <li>✅ Advanced GPT-4 powered analysis and classification</li>
            <li>✅ 50+ business command categories</li>
            <li>✅ Dual-tone reply generation (Professional & Friendly)</li>
            <li>✅ Confidence scoring and tone analysis</li>
            <li>✅ Notion database integration</li>
            <li>✅ Team routing and priority detection</li>
            <li>✅ Real-time processing analytics</li>
        </ul>
        
        <h2>📊 Team Departments</h2>
        <p><strong>Supported:</strong> Sales, Support, HR, Finance, Legal, Operations, Marketing, General</p>
        
        <p><em>Powered by OpenAI GPT-4 & Google Cloud • Built for FIT Group</em></p>
    </body>
    </html>
    """
    
    return render_template_string(html_template, 
                                 status="🟢 Online" if gmail_assistant else "🔴 Offline",
                                 timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'))


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        if not gmail_assistant:
            return jsonify({
                'status': 'unhealthy',
                'message': 'Gmail Assistant not initialized',
                'timestamp': datetime.utcnow().isoformat(),
                'services': {
                    'gmail_api': False,
                    'openai_api': False,
                    'notion_api': False
                }
            }), 503
        
        stats = gmail_assistant.get_processing_stats()
        return jsonify({
            'status': 'healthy',
            'message': 'All systems operational',
            'timestamp': datetime.utcnow().isoformat(),
            'services': stats.get('services', {}),
            'version': '2.0.0',
            'uptime': 'Running'
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics and capabilities"""
    try:
        if not gmail_assistant:
            return jsonify({'error': 'Gmail Assistant not initialized'}), 503
        
        stats = gmail_assistant.get_processing_stats()
        return jsonify(stats)
        
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
        if not gmail_assistant:
            return jsonify({'error': 'Gmail Assistant not initialized'}), 503
        
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
        
        logger.info(f"📧 Processing emails request: {days} days, max {max_results} emails")
        
        # Process emails
        result = gmail_assistant.process_emails_batch(
            days=days, 
            max_results=max_results
        )
        
        # Remove full email content from API response for performance
        if 'emails' in result:
            for email in result['emails']:
                # Keep only essential fields for API response
                email.pop('body', None)  # Remove full body content
                email.pop('raw_headers', None)  # Remove raw headers
        
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
        if not gmail_assistant:
            return jsonify({'error': 'Gmail Assistant not initialized'}), 503
        
        # Parse request parameters
        data = request.get_json() or {}
        days = data.get('days', 7)
        max_results = data.get('max_results', 50)
        include_full_data = data.get('include_full_data', False)
        
        logger.info(f"🔄 Batch processing request: {days} days, max {max_results} emails")
        
        # Process emails with full pipeline
        result = gmail_assistant.process_emails_batch(
            days=days,
            max_results=max_results
        )
        
        # Optionally remove full content for performance
        if not include_full_data and 'emails' in result:
            for email in result['emails']:
                # Summarize email data
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
    """Test API connections without processing emails"""
    try:
        if not gmail_assistant:
            return jsonify({'error': 'Gmail Assistant not initialized'}), 503
        
        # Test individual services
        test_results = {
            'gmail_api': False,
            'openai_api': False,
            'notion_api': False,
            'overall_status': False
        }
        
        # Test Gmail API
        try:
            profile = gmail_assistant.gmail_service.users().getProfile(userId='me').execute()
            test_results['gmail_api'] = True
            test_results['gmail_email'] = profile.get('emailAddress', 'Unknown')
        except Exception as e:
            test_results['gmail_error'] = str(e)
        
        # Test OpenAI API
        try:
            response = gmail_assistant.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Test connection - reply with 'OK'"}],
                max_tokens=10,
                temperature=0
            )
            if response.choices[0].message.content.strip().upper() == 'OK':
                test_results['openai_api'] = True
        except Exception as e:
            test_results['openai_error'] = str(e)
        
        # Test Notion API
        if gmail_assistant.notion_client:
            try:
                # Test by listing databases (limited access)
                gmail_assistant.notion_client.search(
                    filter={"property": "object", "value": "database"}
                )
                test_results['notion_api'] = True
            except Exception as e:
                test_results['notion_error'] = str(e)
        else:
            test_results['notion_error'] = 'Notion not configured'
        
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


@app.route("/api/test-refresh-token", methods=['GET'])
def test_gmail_refresh():
    try:
        # 1) Read GOOGLE_OAUTH_TOKEN JSON from env
        token_json = json.loads(os.getenv("GOOGLE_OAUTH_TOKEN"))

        # 2) Build credentials with refresh_token
        creds = Credentials(
            token=None,  # force refresh
            refresh_token=token_json["refresh_token"],
            token_uri=token_json["token_uri"],
            client_id=token_json["client_id"],
            client_secret=token_json["client_secret"],
            scopes=token_json["scopes"]
        )

        # 3) Refresh token (get new access token)
        creds.refresh(Request())

        # 4) Call Gmail API to verify
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()

        return jsonify({
            "status": "success",
            "email": profile["emailAddress"],
            "new_access_token": creds.token
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    try:
        # Initialize the Gmail Assistant
        initialize_assistant()
        
        # Load configuration
        config = load_config()
        
        # Run the Flask application
        logger.info(f"🚀 Starting FIT Group Gmail Assistant API on {config['HOST']}:{config['PORT']}")
        logger.info(f"📧 Environment: {config['FLASK_ENV']}")
        logger.info(f"🔧 Debug mode: {config['DEBUG']}")
        
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
        
