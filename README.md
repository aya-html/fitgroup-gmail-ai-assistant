# 🚀 FIT Group - Multilingual Gmail Assistant

Advanced AI-powered email processing system with GPT-4 integration for automated email analysis, classification, and response generation.

## 🌟 Key Features

- **Multilingual Processing**: Supports 7+ languages with automatic detection
- **Advanced AI Classification**: 50+ business command categories
- **Dual Reply Generation**: Professional & Friendly tone variations
- **Smart Confidence Scoring**: Automated quality assessment
- **Team Routing**: Automatic assignment to Sales, Support, HR, Legal, etc.
- **Notion Integration**: Seamless workflow logging
- **Real-time Analytics**: Processing statistics and performance metrics

## 📋 Prerequisites

### Required Services
1. **OpenAI API Account** - GPT-4 access required
2. **Google Cloud Console** - Gmail API access
3. **Notion Workspace** (Optional) - For workflow integration
4. **Render Account** - For deployment

### API Keys Needed
- OpenAI API Key
- Google Service Account JSON or OAuth Token
- Notion Integration Token (optional)

## 🔧 Setup Instructions

### 1. Google Cloud Setup

#### Option A: Service Account (Recommended for Production)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Gmail API
4. Create a Service Account:
   - Go to IAM & Admin > Service Accounts
   - Click "Create Service Account"
   - Grant necessary permissions
   - Generate JSON key
5. Enable Domain-Wide Delegation (for G Suite/Workspace):
   - Admin Console > Security > API Controls
   - Add service account client ID with Gmail scope

#### Option B: OAuth Token (Development)
1. Create OAuth 2.0 credentials
2. Download credentials.json
3. Run OAuth flow to get token.json

### 2. Notion Setup (Optional)
1. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Create a database with these properties:
   - Email Subject (Title)
   - Sender (Email)
   - Received Date (Date)
   - Language (Select)
   - Summary (Rich Text)
   - Commands (Multi-select)
   - Tone (Select: positive, neutral, negative, urgent, confused)
   - Team Tags (Multi-select)
   - Confidence Score (Number)
   - Action Status (Select)
   - Reply Draft 1 (Rich Text)
   - Reply Draft 2 (Rich Text)
   - Processing Status (Select)
   - Processed At (Date)

3. Share database with your integration

### 3. Render Deployment

#### Method 1: GitHub Integration (Recommended)
1. Fork/clone this repository
2. Push to your GitHub account
3. Connect to Render:
   - Go to [render.com](https://render.com)
   - New > Web Service
   - Connect your GitHub repo
   - Configure environment variables (see below)

#### Method 2: Direct Deploy
1. Create new Web Service on Render
2. Upload project files
3. Set build/start commands

### 4. Environment Variables

Set these in Render Dashboard > Environment:

```bash
# Required
OPENAI_API_KEY=sk-your-openai-key
GMAIL_USER_EMAIL=admin@yourcompany.com

# Google Auth (choose one)
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
# OR
GOOGLE_OAUTH_TOKEN={"access_token":"...","refresh_token":"..."}

# Optional - Notion Integration
NOTION_TOKEN=secret_your-notion-token
NOTION_DATABASE_ID=your-database-id

# Application Settings
FLASK_ENV=production
DEBUG=false
```

### 5. Build Configuration

Render will use these settings:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn --bind 0.0.0.0:$PORT main:app --workers 2 --timeout 120`
- **Python Version**: 3.11.6

## 📡 API Endpoints

### Health Check
```http
GET /api/health
```
Returns system status and service connectivity.

### Process Recent Emails
```http
POST /api/process-emails
Content-Type: application/json

{
    "days": 7,
    "max_results": 50
}
```

### Advanced Batch Processing
```http
POST /api/process-batch
Content-Type: application/json

{
    "days": 7,
    "max_results": 50,
    "include_full_data": false
}
```

### System Statistics
```http
GET /api/stats
```

### Test Connections
```http
GET /api/test-connection
```

## 🏗️ Project Structure

```
fit-gmail-assistant/
├── main.py                 # Flask web application
├── gmail_assistant.py      # Core AI processing logic
├── requirements.txt        # Python dependencies
├── render.yaml            # Render deployment config
├── README.md              # This file
└── logs/                  # Application logs (auto-created)
```

## 🔒 Security Best Practices

1. **API Keys**: Never commit API keys to version control
2. **Environment Variables**: Use Render's secure environment variable storage
3. **Service Accounts**: Prefer service accounts over OAuth for production
4. **Access Control**: Implement proper authentication for production use
5. **Rate Limiting**: Monitor API usage to avoid rate limits


## 🚀 Deployment Guide – Gmail → GPT → Notion Project

This guide explains how to run and deploy the Gmail AI Assistant project:

- **Production deployment** → Gunicorn on Render.com
- **Email data → GPT → Notion** integration
---

### ⚠️ Before You Start

1. **Notion DB Setup**
    - Create a Notion database with properties (columns) matching all fields the app saves (e.g. `Email Subject`, `Sender`, `Received Date`, `Language`, `Summary`, etc.).
    - Make sure the **property types match** (e.g. `title`, `email`, `date`, `select`, `rich_text`).
    - Share the database with your Notion integration (invite via “Share → Invite → your integration”).
        
2. **Google OAuth2 Setup**
    - Create a project in **Google Cloud Console** → Enable **Gmail API**.
    - Generate **OAuth2 credentials** (Client ID & Secret).
    - Run local OAuth flow to obtain **refresh token** (needed so you don’t re-consent every 7 days).
        
3. **Secrets Management**
    - Do **not** commit secrets to GitHub.
    - Use **Render.com Environment Variables** instead.
---

### 📦 Deployment to Render (Gunicorn)

1. Push your repo to GitHub.

2. On [Render.com](https://render.com?utm_source=chatgpt.com):
    - Create a **New Web Service**
    - Connect your GitHub repo
        
3. Add **Environment Variables** in Render dashboard:
    `OPENAI_API_KEY, NOTION_TOKEN, NOTION_DB_ID, GOOGLE_OAUTH_TOKEN, FLASK_ENV, DEBUG`

4. In Render service settings:
    - **Build Command**:
        `pip install -r requirements.txt`
    - **Start Command**:
        `gunicorn main:app --workers=2 --threads=8 --timeout=300`
        
5. Configure a health check endpoint (`/api/health`). Render will restart automatically if unhealthy.
---

### ✅ Verification

- Visit your Render service URL:
    `https://your-app.onrender.com/api/health`
    Expected:
    `{"status": "healthy", "uptime": "Running", ...}`
- Send a test email → check Notion database for a new entry with fields filled.
---

### 🔒 Security Checklist

-  Never commit `.env` or credential files.
-  Only store secrets in Render Environment Variables.
-  Always invite the Notion integration to your database.
-  Validate Gmail OAuth2 tokens (refresh if expired).
-  Use HTTPS-only for API keys & communication.
---

### 🧩 Common Issues

- **Notion integration can’t write** → You forgot to invite it to the database or the database schema doesn't match.
- **Email body empty** → Gmail sent only `text/html`, check parsing logic.
- **Invalid refresh token** → Re-run OAuth2 flow, update `refresh_token` in `GOOGLE_AUTH_TOKEN`. Visit your Render service URL: `https://your-app.onrender.com/api/test-refresh-token` for testing
- **Render restarts often** → Adjust Gunicorn workers/threads + health checks.
---

## 🚀 Production Deployment Checklist

- [ ] OpenAI API key configured
- [ ] Google Cloud project setup with Gmail API enabled
- [ ] Service account created with proper permissions
- [ ] Environment variables set in Render
- [ ] Health check endpoint responding
- [ ] Test connection endpoint validates all APIs
- [ ] Notion database configured (if using)
- [ ] Email processing tested with sample data
- [ ] Monitoring and logging configured
- [ ] Domain/subdomain pointed to Render (if needed)

## 📊 Monitoring & Analytics

### Key Metrics to Track
- **Processing Success Rate**: Percentage of emails processed successfully
- **Confidence Score Distribution**: Quality of AI-generated responses
- **Language Detection Accuracy**: Multilingual processing effectiveness
- **Team Routing Accuracy**: Correct department assignment
- **API Response Times**: Performance monitoring
- **Error Rates**: System reliability tracking

### Logging
- Application logs stored in `/logs/gmail_assistant.log`
- Structured logging for easy parsing
- Error tracking with stack traces
- Performance metrics logging

## 🛠️ Troubleshooting

### Common Issues

#### 1. Gmail API Authentication Errors
```
Error: [Errno 2] No such file or directory: 'token.json'
```
**Solution**: Ensure `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_OAUTH_TOKEN` is properly set.

#### 2. OpenAI API Rate Limits
```
Error: Rate limit exceeded
```
**Solution**: Implement request queuing or upgrade OpenAI plan.

#### 3. Notion Sync Failures
```
Error: Notion sync failed
```
**Solution**: 
- Verify `NOTION_TOKEN` and `NOTION_DATABASE_ID`
- Check database permissions
- Validate database schema matches expected properties

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

## 🧪 Testing

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=your-key
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'

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

*Last Updated: August 2025*