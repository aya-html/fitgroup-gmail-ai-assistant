# 🚀 FIT Group - Multilingual Gmail AI Assistant

A production-ready Flask web application that provides AI-powered email processing, analysis, and management system. The application supports multiple users with individual Gmail accounts and features a shared results database using Notion.

## 🌟 Key Features

- **Multi-User Support**: Secure authentication and user management with Google OAuth2
- **Gmail Integration**: Process and analyze emails from multiple Gmail accounts
- **AI-Powered Analysis**: GPT-4 integration for advanced email processing
- **Multilingual Support**: Handles emails in multiple languages including English, Spanish, French, German, Italian, Portuguese, Dutch, Chinese, and Arabic
- **Real-time Dashboard**: Web interface for monitoring and managing email processing
- **Notion Integration**: Store and organize processed results in Notion database
- **API-First Design**: RESTful API endpoints for all functionality
- **Advanced Email Classification**: 50+ business command categories for intelligent routing
- **Dual-Tone Reply Generation**: Professional and friendly response drafts
- **Confidence Scoring**: AI-powered quality assessment of generated responses

## 📋 Prerequisites

- Python 3.11+
- Google Cloud Project with Gmail API enabled
- OpenAI API key for GPT-4 access
- Notion API integration with two databases (Users and Results)
- Render.com account (for deployment)

## 🔧 Setup Instructions

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd fitgroup-gmail-ai-assistant
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file for local development:

```bash
# Required
OPENAI_API_KEY=sk-your-openai-key
GOOGLE_CLIENT_SECRET_JSON='{"web":{"client_id":"...","client_secret":"..."}}'

# Notion Integration
NOTION_TOKEN=secret_your-notion-token
NOTION_USERS_DB_ID=your-users-database-id
NOTION_RESULTS_DB_ID=your-results-database-id

# Application Settings
FLASK_ENV=development
DEBUG=true
PORT=5000
HOST=127.0.0.1
```

### 4. Run the Application

**Using the start script (recommended)**
```bash
./start.sh
```


## 🚀 Deployment to Render.com

### 1. Prepare Your Repository
- Push your code to GitHub
- Ensure all environment variables are ready

### 2. Create Render Service
1. Go to [Render.com](https://render.com)
2. Create a **New Web Service**
3. Connect your GitHub repository
4. Select **Python** as the environment

### 3. Configure Environment Variables

Set these in Render Dashboard > Environment:

```bash
OPENAI_API_KEY=sk-your-openai-key
NOTION_TOKEN=secret_your-notion-token
NOTION_USERS_DB_ID=your-users-database-id
NOTION_RESULTS_DB_ID=your-results-database-id
GOOGLE_CLIENT_SECRET_JSON={"web":{"client_id":"...","client_secret":"..."}}
FLASK_ENV=production
DEBUG=false
```

### 4. Configure Build and Start Commands

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn main:app --workers=2 --threads=8 --timeout=300 --bind 0.0.0.0:$PORT
```

### 5. Health Check Configuration
- **Health Check Path**: `/api/health`
- **Auto-deploy**: Enable for main branch

## 📡 API Endpoints

### Authentication
- `GET /login` - Login page
- `GET /auth/google` - Initiate Google OAuth2 flow
- `GET /auth/google/callback` - OAuth2 callback handler
- `GET /logout` - Logout current user

### Core Features
- `POST /api/process-emails` - Process recent emails
- `POST /api/process-batch` - Advanced batch processing with analytics
- `GET /api/test-connection` - Test API connections
- `GET /api/health` - System health check
- `GET /api/stats` - System statistics and capabilities

### User Management
- `GET /api/user/profile` - Get current user profile
- `GET /api/user/results` - Get email processing results
- `GET /api/user/labels` - Get unique Gmail labels
- `POST /api/user/results/search` - Search processed results

### Admin Features
- `GET /api/admin/users` - Get all users list

## 🏗️ Project Structure

```
fitgroup-gmail-ai-assistant/
├── main.py                 # Flask application & API endpoints
├── auth_manager.py        # Google OAuth2 authentication
├── gmail_assistant.py     # Email processing & AI integration
├── notion_manager.py      # Notion database integration
├── user_manager.py        # User management & storage
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment config
├── start.sh             # Application startup script
├── static/              # Static assets
│   └── css/            # Stylesheets
├── templates/           # HTML templates
│   ├── login.html      # Login page
│   └── dashboard.html  # Main dashboard
└── README.md           # This file
```

## 🔒 Security Features

- Google OAuth2 authentication with refresh token management
- Session management and validation
- Secure credential storage with optional encryption
- Rate limiting and error handling
- CORS support for cross-origin requests
- Environment variable configuration
- Multi-user isolation

## 🛠️ Notion Database Setup

### Users Database Schema
Create a Notion database with these properties:
- **Name** (Title) - User email address
- **Email** (Email) - User email address
- **Google Access Token** (Rich Text) - Encrypted access token
- **Google Refresh Token** (Rich Text) - Encrypted refresh token
- **Token Expiry** (Date) - Token expiration date
- **Token URI** (Rich Text) - OAuth token URI
- **Scopes** (Rich Text) - JSON array of OAuth scopes
- **Status** (Select) - Active/Inactive
- **Created At** (Date) - User creation date
- **Last Login** (Date) - Last login timestamp

### Results Database Schema
Create a Notion database with these properties:
- **Email Subject** (Title) - Email subject line
- **User Email** (Email) - Processing user email
- **Sender** (Email) - Email sender address
- **Received Date** (Date) - Email received date
- **Language** (Select) - Detected language
- **Summary** (Rich Text) - AI-generated summary
- **Commands** (Multi-select) - Detected business commands
- **Labels** (Multi-select) - Gmail labels
- **Tone** (Select) - Email tone analysis
- **Team Tags** (Multi-select) - Assigned team tags
- **Confidence Score** (Number) - AI confidence (0-100)
- **Action Status** (Select) - Processing status
- **Reply Draft 1** (Rich Text) - Professional reply
- **Reply Draft 2** (Rich Text) - Friendly reply
- **Processing Status** (Select) - Processing state
- **Processed At** (Date) - Processing timestamp

## 🧪 Testing

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=your-key
export GOOGLE_CLIENT_SECRET_JSON='{"web":{"client_id":"...","client_secret":"..."}}'
export NOTION_TOKEN=your-notion-token
export NOTION_USERS_DB_ID=your-users-db-id
export NOTION_RESULTS_DB_ID=your-results-db-id

# Run application
python main.py
```

### API Testing
```bash
# Health check
curl https://your-app.onrender.com/api/health

# Process test emails
curl -X POST https://your-app.onrender.com/api/process-emails \
  -H "Content-Type: application/json" \
  -d '{"days": 1, "max_results": 5}'
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Gmail API Authentication Errors
```
Error: No valid Google credentials provided
```
**Solution**: Ensure `GOOGLE_CLIENT_SECRET_JSON` is properly set and contains valid OAuth2 credentials.

#### 2. Notion Sync Failures
```
Error: Notion sync failed
```
**Solution**: 
- Verify `NOTION_TOKEN` and database IDs
- Check database permissions
- Ensure database schema matches expected properties
- Invite your Notion integration to both databases

#### 3. OpenAI API Rate Limits
```
Error: Rate limit exceeded
```
**Solution**: Implement request queuing or upgrade OpenAI plan.

#### 4. Memory Issues on Render
```
Error: Application exceeded memory limit
```
**Solution**: 
- Reduce `max_results` parameter
- Upgrade to higher Render plan
- Optimize email content processing

### Debug Mode
Enable debug mode for development:
```bash
DEBUG=true
FLASK_ENV=development
```

## 📊 Monitoring & Analytics

### Key Metrics to Track
- **Processing Success Rate**: Percentage of emails processed successfully
- **Confidence Score Distribution**: Quality of AI-generated responses
- **Language Detection Accuracy**: Multilingual processing effectiveness
- **Team Routing Accuracy**: Correct department assignment
- **API Response Times**: Performance monitoring
- **Error Rates**: System reliability tracking

### Logging
- Application logs stored in `gmail_assistant.log`
- Structured logging for easy parsing
- Error tracking with stack traces
- Performance metrics logging

## 🔧 Configuration Options

### Email Processing Parameters
- `days`: Number of days to look back (1-30)
- `max_results`: Maximum emails to process (1-100)
- `include_full_data`: Include full email content in API responses

### AI Model Configuration
- Default model: GPT-4
- Temperature settings optimized for business communications
- Token limits configured for efficient processing

### Team Routing Configuration
Teams are automatically assigned based on command detection:
- **Sales**: demos, proposals, partnerships
- **Support**: technical issues, bugs, access requests
- **HR**: applications, interviews, employee queries
- **Finance**: billing, invoices, pricing
- **Legal**: contracts, compliance, privacy
- **Operations**: shipping, inventory, logistics
- **Marketing**: events, content, collaborations

## 📈 Scaling Considerations

### Performance Optimization
1. **Batch Processing**: Process multiple emails efficiently
2. **Caching**: Implement Redis for repeated queries
3. **Queue System**: Use Celery for background processing
4. **Database Optimization**: Index Notion database properly

### High-Volume Processing
For processing >1000 emails/day:
1. Upgrade to Render Pro plan
2. Implement worker processes
3. Add database connection pooling
4. Consider microservices architecture

## 🚀 Production Deployment Checklist

- [ ] OpenAI API key configured
- [ ] Google Cloud project setup with Gmail API enabled
- [ ] Notion databases created with proper schema
- [ ] Environment variables set in Render
- [ ] Health check endpoint responding
- [ ] Test connection endpoint validates all APIs
- [ ] Email processing tested with sample data
- [ ] Monitoring and logging configured
- [ ] Domain/subdomain pointed to Render

## 📞 Support & Maintenance

### Regular Maintenance Tasks
- [ ] Monitor API key usage and limits
- [ ] Review processing accuracy and adjust prompts
- [ ] Update command taxonomy based on business needs
- [ ] Backup Notion database configurations
- [ ] Monitor application logs for errors

### Performance Monitoring
- Set up Render metrics monitoring
- Configure email alerts for critical failures
- Track processing time trends
- Monitor memory and CPU usage

### Updates and Improvements
- Keep dependencies updated for security
- Regularly review and optimize AI prompts
- Expand language support as needed
- Add new business command categories

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch
3. Implement changes with tests
4. Submit pull request
5. Review and merge

### Code Standards
- Follow PEP 8 for Python code
- Add docstrings for all functions
- Include error handling
- Write unit tests for new features

## 📄 License

This project is proprietary to FIT Group. All rights reserved.

## 🆘 Emergency Contacts

- **Technical Issues**: aya@fitgroup.cc
- **API Problems**: aya@fitgroup.cc
- **Business Questions**: yang@fitgroup.cc

---

**Built for FIT Group by the AI Engineering Team**

*Last Updated: Sep.8 2025*