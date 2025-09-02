#!/bin/bash

# FIT Group - Gmail Assistant Startup Script
# This script helps with local development and deployment preparation

set -e  # Exit on any error

# Load environment variables from .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "✅ Loaded environment variables from .env"
else
    echo "⚠️  No .env file found"
fi

echo "🚀 FIT Group - Gmail Assistant Startup"
echo "======================================"

# Check Python version
python_version=$(python3 --version 2>&1)
echo "📋 Python Version: $python_version"

# Check if required environment variables are set
check_env_var() {
    if [ -z "${!1}" ]; then
        echo "❌ Error: $1 environment variable is not set"
        echo "   Please set this variable before starting the application"
        return 1
    else
        echo "✅ $1 is configured"
        return 0
    fi
}

echo ""
echo "🔍 Checking Environment Configuration..."

# Check required variables
required_vars=("OPENAI_API_KEY" "GOOGLE_CLIENT_SECRET_JSON" "NOTION_TOKEN" "NOTION_USERS_DB_ID" "NOTION_RESULTS_DB_ID")
optional_vars=("FLASK_ENV" "DEBUG" "PORT" "HOST")

all_required_set=true
for var in "${required_vars[@]}"; do
    if ! check_env_var "$var"; then
        all_required_set=false
    fi
done


# Check optional variables
echo ""
echo "📋 Optional Configuration Status:"
for var in "${optional_vars[@]}"; do
    if [ -n "${!var}" ]; then
        echo "✅ $var is configured"
    else
        echo "⚠️  $var is not set (optional)"
    fi
done

if [ "$all_required_set" = false ]; then
    echo ""
    echo "❌ Missing required configuration. Please check the following:"
    echo "   1. Copy .env.example to .env and fill in your values"
    echo "   2. Source the environment: source .env"
    echo "   3. Or export variables manually"
    echo ""
    echo "📖 See README.md for detailed setup instructions"
    exit 1
fi

echo ""
echo "🔧 Installing Dependencies..."

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: requirements.txt not found"
    exit 1
fi

# Install/update dependencies
pip3 install -r requirements.txt --quiet

echo ""
echo "🧪 Running Pre-flight Checks..."

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found"
    exit 1
fi

if [ ! -f "gmail_assistant.py" ]; then
    echo "❌ Error: gmail_assistant.py not found"
    exit 1
fi

echo "✅ All application files present"

echo ""
echo "🌐 Application Configuration:"
echo "   Environment: ${FLASK_ENV:-development}"
echo "   Debug Mode: ${DEBUG:-false}"
echo "   Port: ${PORT:-5000}"
echo "   Host: ${HOST:-127.0.0.1}"

echo ""
echo "🎯 Starting FIT Group Gmail Assistant..."
echo "   Access the application at: http://${HOST:-127.0.0.1}:${PORT:-5000}"
echo "   Health check: http://${HOST:-127.0.0.1}:${PORT:-5000}/api/health"
echo "   API documentation: http://${HOST:-127.0.0.1}:${PORT:-5000}"

echo ""
echo "📊 Useful Commands:"
echo "   Test connection: curl http://${HOST:-127.0.0.1}:${PORT:-5000}/api/test-connection"
echo "   Process emails: curl -X POST http://${HOST:-127.0.0.1}:${PORT:-5000}/api/process-emails -H 'Content-Type: application/json' -d '{\"days\": 1}'"
echo ""

# Start the application
if [ "${FLASK_ENV:-production}" = "production" ]; then
    echo "🚀 Starting with Gunicorn (Production Mode)..."
    exec gunicorn --bind ${HOST:-0.0.0.0}:${PORT:-5000} main:app --workers 2 --timeout 120 --keep-alive 5 --access-logfile - --error-logfile -
else
    echo "🔧 Starting with Flask Dev Server (Development Mode)..."
    exec python3 main.py
fi
