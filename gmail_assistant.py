"""
FIT Group - Unified Multilingual Gmail Assistant
===============================================
Advanced email processing system with GPT-powered analysis, classification,
and automated response generation across multiple departments.

Core Features:
- Multilingual email processing and language detection
- Smart command classification for 50+ business scenarios
- Dual-tone reply generation (Professional & Friendly)
- Confidence scoring and tone analysis
- Notion database integration for team workflows
- Thread mapping and Gmail API integration
"""

import os
import json
import re
import time
import random
import logging
import traceback
from datetime import datetime, timedelta
from base64 import urlsafe_b64decode
from typing import List, Dict, Any, Tuple, Optional
from bs4 import BeautifulSoup
from email import message_from_bytes

# External dependencies
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openai import OpenAI
from notion_client import Client as NotionClient
import requests


class EmailProcessingError(Exception):
    """Custom exception for email processing errors"""
    pass


class GmailAssistant:
    """
    Unified Gmail Assistant for FIT Group
    Processes emails with advanced AI analysis and automated response generation
    """
    
    # Comprehensive business command taxonomy
    BUSINESS_COMMANDS = [
        # Customer Relations & Support
        "billing_question", "pricing_request", "general_question", "complaint", 
        "feature_request", "technical_issue", "bug_report", "access_request",
        "reset_password", "security_alert", "system_down", "customer_testimonial",
        
        # Sales & Business Development
        "schedule_demo", "send_proposal", "follow_up", "renew_contract",
        "custom_plan_request", "partnership_request", "confirm_availability",
        
        # Operations & Logistics
        "send_invoice", "shipping_issue", "delivery_update_request", 
        "return_request", "inventory_request", "account_closure",
        "update_contact", "change_account_details", "duplicate_request",
        
        # Human Resources & Recruitment
        "job_application", "referral_submission", "interview_schedule_request",
        "cv_update_request", "hr_query", "employee_onboarding",
        
        # Legal & Compliance
        "legal_inquiry", "contract_request", "privacy_policy_question",
        "data_deletion_request", "compliance_audit", "gdpr_request",
        
        # Marketing & Communications
        "unsubscribe", "feedback_positive", "event_registration",
        "press_inquiry", "marketing_collaboration", "content_request",
        
        # Document & Information Management
        "file_request", "request_report", "request_presentation",
        "send_agreement", "document_approval", "data_export_request",
        
        # Internal Operations
        "forward_to_support", "escalate_to_manager", "schedule_meeting",
        "project_update", "budget_request", "resource_allocation",
        
        # Meta Actions
        "no_action", "requires_human_review", "spam_detected"
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Gmail Assistant with configuration"""
        self.config = config
        self.logger = self._setup_logging()
        
        # Initialize API clients
        self.gmail_service = None
        self.openai_client = None
        self.notion_client = None
        self.max_email_length = 50000
        
        self._initialize_services()
    
    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the application"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('gmail_assistant.log')
            ]
        )
        return logging.getLogger(__name__)
    
    def _initialize_services(self):
        """Initialize external API services"""
        try:
            # Gmail API Setup
            self._setup_gmail_service()
            
            # OpenAI Setup
            self.openai_client = OpenAI(
                api_key=self.config.get('OPENAI_API_KEY')
            )
            
            # Notion Setup
            if self.config.get('NOTION_TOKEN'):
                self.notion_client = NotionClient(
                    auth=self.config.get('NOTION_TOKEN')
                )
            
            self.logger.info("✅ All services initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Service initialization failed: {str(e)}")
            raise EmailProcessingError(f"Failed to initialize services: {str(e)}")
    
    def _setup_gmail_service(self):
        """Setup Gmail API service with proper authentication"""
        try:
            scopes = ['https://www.googleapis.com/auth/gmail.readonly']
            
            # Priority 1: User credentials from AuthManager (multi-user mode)
            if self.config.get('user_credentials'):
                user_creds = self.config['user_credentials']
                
                # If it's already a Credentials object
                if isinstance(user_creds, Credentials):
                    credentials = user_creds
                # If it's a dict/token info
                elif isinstance(user_creds, dict):
                    if 'token' in user_creds:
                        credentials = Credentials.from_authorized_user_info(user_creds, scopes)
                    else:
                        credentials = Credentials.from_authorized_user_info(user_creds, scopes)
                # If it's a JSON string
                elif isinstance(user_creds, str):
                    token_info = json.loads(user_creds)
                    credentials = Credentials.from_authorized_user_info(token_info, scopes)
                else:
                    raise EmailProcessingError(f"Unsupported user_credentials type: {type(user_creds)}")
                
                self.logger.info("✅ Gmail API authenticated with user credentials")
            
            else:
                raise EmailProcessingError("No valid Google credentials provided")
            
            self.gmail_service = build('gmail', 'v1', credentials=credentials)
            self.logger.info("✅ Gmail API service built successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Gmail setup failed: {str(e)}")
            raise
    
    def fetch_recent_emails(self, days: int = 7, max_results: int = 50, batch_size: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch recent emails from Gmail inbox with full content extraction
        
        Args:
            days: Number of days to look back
            max_results: Maximum number of emails to fetch
            batch_size: Number of emails to process in each batch
            
        Returns:
            List of email dictionaries with processed content
        """
        try:
            # Calculate date range
            past_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y/%m/%d')
            query = f"after:{past_date} in:inbox"
            
            # Fetch email threads with pagination
            threads = []
            page_token = None
            
            while len(threads) < max_results:
                # Fetch next batch of threads
                threads_result = self.gmail_service.users().threads().list(
                    userId='me', q=query, maxResults=min(100, max_results - len(threads)),
                    pageToken=page_token
                ).execute()
                
                batch_threads = threads_result.get('threads', [])
                if not batch_threads:
                    break
                    
                threads.extend(batch_threads)
                page_token = threads_result.get('nextPageToken')
                if not page_token:
                    break
            
            self.logger.info(f"📬 Found {len(threads)} email threads")
            
            processed_emails = []
            retries = 3  # Number of retries for failed attempts
            
            # Process emails in batches
            for i in range(0, len(threads), batch_size):
                batch = threads[i:i + batch_size]
                retry_count = 0
                
                while retry_count < retries:
                    try:
                        for thread in batch:
                            try:
                                email_data = self._process_single_thread(thread['id'])
                                if email_data:
                                    processed_emails.append(email_data)
                                    self.logger.debug(f"✅ Processed: {email_data.get('subject', 'No Subject')}")
                            except Exception as e:
                                self.logger.warning(f"⚠️ Failed to process thread {thread['id']}: {str(e)}")
                                continue
                            
                            # Add small delay between requests to avoid rate limiting
                            time.sleep(0.1)
                        break  # Break retry loop if batch succeeds
                        
                    except HttpError as e:
                        if e.resp.status in [429, 500, 503]:  # Rate limit or server error
                            retry_count += 1
                            if retry_count < retries:
                                wait_time = (2 ** retry_count) + random.uniform(0, 1)  # Exponential backoff
                                self.logger.warning(f"⚠️ Rate limit hit, waiting {wait_time:.2f}s before retry {retry_count}")
                                time.sleep(wait_time)
                                continue
                        raise  # Re-raise if not a retriable error or out of retries
            
            self.logger.info(f"✅ Successfully processed {len(processed_emails)} emails")
            return processed_emails
            
        except HttpError as e:
            self.logger.error(f"❌ Gmail API error: {str(e)}")
            raise EmailProcessingError(f"Gmail API error: {str(e)}")
        except Exception as e:
            self.logger.error(f"❌ Email fetch error: {str(e)}")
            raise EmailProcessingError(f"Failed to fetch emails: {str(e)}")
    
    def _process_single_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Process a single Gmail thread by ID and extract relevant information.

        Note: `threads().list()` returns thread IDs. We must fetch via
        `threads().get(...)` and then read a message from the `messages` array.
        """
        try:
            # Fetch the full thread
            thread = self.gmail_service.users().threads().get(
                userId='me', id=thread_id
            ).execute()

            messages = thread.get('messages', [])
            if not messages:
                return None

            # Choose the latest message in the thread for processing
            message = messages[-1]

            payload = message.get('payload', {})
            headers = {h['name']: h['value'] for h in payload.get('headers', [])}

            # Extract basic information
            subject = headers.get('Subject', '(No Subject)')
            sender = headers.get('From', '')
            timestamp_ms = int(message.get('internalDate', 0))
            timestamp = timestamp_ms / 1000 if timestamp_ms else 0
            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp else ''

            # Extract email body
            body = self._extract_email_body(payload)

            # Skip if no meaningful content
            if not body or len(body.strip()) < 10:
                return None

            # Detect language
            detected_language = self._detect_language(body)

            email_data = {
                'thread_id': thread_id,
                'message_id': message.get('id', ''),
                'subject': subject,
                'sender': sender,
                'received_time': date_str,
                'timestamp': timestamp,
                'body': body,
                'detected_language': detected_language,
                'raw_headers': headers
            }

            return email_data

        except Exception as e:
            self.logger.warning(f"Failed to process thread {thread_id}: {str(e)}")
            return None
    
    def _extract_email_body(self, payload: Dict[str, Any]) -> str:
        """
        Robustly extract and clean plain-text from Gmail message payload.
        Handles HTML, signatures, quoted replies, and encodings.
        """
        try:
            def decode_and_clean(data: str) -> str:
                """Helper to decode base64 and clean HTML/text safely"""
                raw_bytes = urlsafe_b64decode(data)
                msg = message_from_bytes(raw_bytes)

                # Try plain text first
                if msg.get_content_type() == "text/plain":
                    text = msg.get_payload(decode=True).decode(
                        msg.get_content_charset() or "utf-8", errors="replace"
                    )
                else:
                    # fallback to HTML
                    html = msg.get_payload(decode=True).decode(
                        msg.get_content_charset() or "utf-8", errors="replace"
                    )
                    text = BeautifulSoup(html, "html.parser").get_text(" ")

                # Normalize whitespace
                text = re.sub(r"\s+", " ", text).strip()

                # Remove quoted replies ("On ... wrote:")
                text = re.split(r"\nOn .*wrote:\n", text)[0]

                # Remove signatures ("-- ", "Sent from my iPhone")
                text = re.split(r"(-- |Sent from my)", text)[0]

                # Truncate giant emails
                if len(text) > self.max_email_length:
                    text = text[:self.max_email_length] + "\n...[truncated]"

                return text

            # Case 1: Simple body
            data = payload.get("body", {}).get("data")
            if data:
                return decode_and_clean(data)

            # Case 2: Multipart email
            if "parts" in payload:
                for part in payload["parts"]:
                    data = part.get("body", {}).get("data")
                    if data:
                        text = decode_and_clean(data)
                        if text.strip():
                            return text

            return "[No text content extracted]"

        except Exception as e:
            self.logger.warning(f"Email body extraction failed: {str(e)}")
            return "[Body extraction error]"
    
    def _detect_language(self, text: str) -> str:
        """Detect the language of the email content using GPT"""
        if not text or len(text.strip()) < 20:
            return "English"
        
        prompt = f"""
        Detect the primary language of this email content. 
        Respond with only the language name in English (e.g., "English", "Spanish", "French", "German", "Chinese", "Arabic", etc.).
        
        Email content (first 500 characters):
        {text[:500]}
        
        Language:"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            language = response.choices[0].message.content.strip()
            return language if language else "English"
            
        except Exception as e:
            self.logger.warning(f"Language detection failed: {str(e)}")
            return "English"
    
    def generate_email_summary(self, email_data: Dict[str, Any]) -> str:
        """Generate a concise multilingual summary of the email"""
        body = email_data.get('body', '')
        language = email_data.get('detected_language', 'English')
        subject = email_data.get('subject', '')
        
        if not body or body == "[No text content extracted]":
            return f"[Summary unavailable - Subject: {subject}]"
        
        prompt = f"""
        You are an expert email analyst for FIT Group's business operations.
        Create a professional, concise summary of this email for management dashboard review.
        
        Requirements:
        - Write the summary in {language}
        - Keep it 2-4 sentences maximum
        - Focus on key action items, requests, or important information
        - Be clear and business-focused
        - Include sender context if relevant for business decisions
        
        Email Subject: {subject}
        Email Content:
        ---
        {body[:2000]}
        ---
        
        Professional Summary:"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=250
            )
            
            summary = response.choices[0].message.content.strip()
            return summary if summary else "[Summary generation failed]"
            
        except Exception as e:
            self.logger.warning(f"Summary generation failed: {str(e)}")
            return f"[Summary Error: {str(e)[:100]}]"
    
    def classify_email_commands(self, email_data: Dict[str, Any]) -> List[str]:
        """Classify email into business command categories using advanced GPT analysis"""
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        summary = email_data.get('summary', '')
        language = email_data.get('detected_language', 'English')
        
        commands_str = ', '.join(self.BUSINESS_COMMANDS)
        
        prompt = f"""
        You are FIT Group's advanced email classification AI. Analyze this business email and identify ALL applicable command categories.
        
        COMMAND TAXONOMY:
        {commands_str}
        
        CLASSIFICATION RULES:
        1. Return a Python list of strings: ["command1", "command2", ...]
        2. Only use commands from the provided taxonomy
        3. Include ALL relevant commands (multiple commands are common)
        4. For system notifications/newsletters: ["spam_detected"] or ["no_action"]
        5. For complex requests needing human review: include ["requires_human_review"]
        6. Prioritize the most specific applicable commands
        
        Email Language: {language}
        Subject: "{subject}"
        Summary: "{summary}"
        
        Body Preview:
        {body[:1500]}
        
        Classification Result:"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse the result safely
            try:
                commands = eval(result) if result.startswith('[') else []
                # Validate commands are in our taxonomy
                valid_commands = [cmd for cmd in commands if cmd in self.BUSINESS_COMMANDS]
                return valid_commands if valid_commands else ["no_action"]
                
            except (SyntaxError, ValueError):
                self.logger.warning(f"Failed to parse command classification: {result}")
                return ["requires_human_review"]
            
        except Exception as e:
            self.logger.warning(f"Command classification failed: {str(e)}")
            return ["requires_human_review"]
    
    def detect_email_tone(self, email_data: Dict[str, Any]) -> str:
        """Analyze the emotional tone of the email"""
        body = email_data.get('body', '')
        language = email_data.get('detected_language', 'English')
        
        if not body or body == "[No text content extracted]":
            return "neutral"
        
        prompt = f"""
        Analyze the emotional tone of this {language} business email.
        Choose exactly ONE tone from: positive, neutral, negative, urgent, confused
        
        Consider:
        - Overall sentiment and emotional indicators
        - Language formality and politeness
        - Urgency markers and escalation language
        - Customer satisfaction signals
        
        Email content:
        {body[:1000]}
        
        Tone (one word only):"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            tone = response.choices[0].message.content.strip().lower()
            valid_tones = ['positive', 'neutral', 'negative', 'urgent', 'confused']
            
            return tone if tone in valid_tones else "neutral"
            
        except Exception as e:
            self.logger.warning(f"Tone detection failed: {str(e)}")
            return "neutral"
    
    def generate_reply_drafts(self, email_data: Dict[str, Any]) -> Tuple[str, str]:
        """Generate two different reply drafts with different tones"""
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        commands = email_data.get('detected_commands', [])
        language = email_data.get('detected_language', 'English')
        sender = email_data.get('sender', '')
        
        # Skip non-actionable emails
        if not commands or 'no_action' in commands or 'spam_detected' in commands:
            skip_msg = f"[SKIPPED - {', '.join(commands)}]"
            return skip_msg, skip_msg
        
        base_prompt = f"""
        You are FIT Group's professional email response AI assistant.
        Generate a helpful, accurate, and contextually appropriate business reply.
        
        CONTEXT:
        - Sender: {sender}
        - Original Subject: {subject}
        - Detected Language: {language}
        - Business Commands: {', '.join(commands)}
        
        REPLY GUIDELINES:
        1. Write in {language}
        2. Address all key points from the original email
        3. Be professional yet personable
        4. Provide specific next steps when applicable
        5. Include appropriate contact information or escalation paths
        6. Keep response length appropriate (3-8 sentences typically)
        7. Use proper business email formatting
        
        Original Email:
        ---
        {body[:2000]}
        ---
        
        """
        
        # Generate two different toned responses
        prompts = [
            base_prompt + "\nTone: Professional and formal. Focus on clarity and efficiency.\n\nReply:",
            base_prompt + "\nTone: Warm and collaborative. Show empathy and partnership.\n\nReply:"
        ]
        
        drafts = []
        
        for i, prompt in enumerate(prompts, 1):
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.4 + (i * 0.1),  # Slightly different creativity levels
                    max_tokens=500
                )
                
                draft = response.choices[0].message.content.strip()
                drafts.append(draft)
                
            except Exception as e:
                error_msg = f"[Reply Generation Error: {str(e)[:100]}]"
                drafts.append(error_msg)
                self.logger.warning(f"Reply draft {i} generation failed: {str(e)}")
        
        return drafts[0], drafts[1]
    
    def calculate_confidence_score(self, email_data: Dict[str, Any]) -> int:
        """Calculate confidence score for the generated reply (0-100)"""
        reply_draft = email_data.get('reply_draft_1', '')
        commands = email_data.get('detected_commands', [])
        tone = email_data.get('tone', 'neutral')
        
        # Base scoring logic
        score = 50  # Start with neutral confidence
        
        # Penalize problematic cases
        if not reply_draft or '[SKIPPED' in reply_draft.upper():
            return 0
        
        if 'ERROR' in reply_draft.upper():
            return 15
        
        if 'no_action' in commands:
            return 25
        
        if 'requires_human_review' in commands:
            return 35
        
        # Boost confidence for well-structured replies
        quality_indicators = [
            'thank you', 'please find', 'attached', 'i\'ve forwarded',
            'let us know', 'happy to help', 'best regards', 'sincerely'
        ]
        
        quality_score = sum(1 for indicator in quality_indicators 
                          if indicator in reply_draft.lower())
        score += min(quality_score * 8, 30)
        
        # Length and structure bonus
        word_count = len(reply_draft.split())
        if 20 <= word_count <= 150:
            score += 15
        elif 150 < word_count <= 300:
            score += 10
        
        # Command specificity bonus
        specific_commands = [
            'send_invoice', 'schedule_demo', 'technical_issue',
            'job_application', 'contract_request'
        ]
        if any(cmd in commands for cmd in specific_commands):
            score += 10
        
        # Tone appropriateness
        if tone in ['positive', 'neutral']:
            score += 5
        elif tone == 'urgent':
            score += 8  # Urgent emails often need quick responses
        
        return min(max(score, 0), 100)
    
    def sync_to_notion(self, processed_emails: List[Dict[str, Any]]) -> bool:
        """Sync processed emails to Notion database"""
        if not self.notion_client or not self.config.get('NOTION_DATABASE_ID'):
            self.logger.warning("Notion sync skipped - no configuration provided")
            return False
        
        database_id = self.config.get('NOTION_DATABASE_ID')
        successful_syncs = 0

        # NOTION_TOKEN = os.getenv("NOTION_TOKEN")
        # DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

        # headers = {
        #     "Authorization": f"Bearer {NOTION_TOKEN}",
        #     "Notion-Version": "2022-06-28"
        # }

        # url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"
        # resp = requests.get(url, headers=headers)
        # print("==========resp.json()\n\n")
        # print(resp.json())
        # print("\n\n==========resp.json()\n\n")

        for email in processed_emails:
            try:
                # Determine team routing
                team_tags = self._determine_team_tags(
                    email.get('detected_commands', [])
                )
                
                # Determine action status
                action_status = self._determine_action_status(email)
                
                # Create Notion page
                properties = {
                    "Email Subject": {
                        "title": [{"text": {"content": email.get('subject', 'No Subject')[:100]}}]
                    },
                    "Sender": {
                        "email": email.get('sender', '')[:100] if '@' in email.get('sender', '') else None
                    },
                    "Received Date": {
                        "date": {"start": email.get('received_time', datetime.utcnow().isoformat())}
                    },
                    "Language": {
                        "select": {"name": email.get('detected_language', 'English')}
                    },
                    "Summary": {
                        "rich_text": [{"text": {"content": email.get('summary', '')[:2000]}}]
                    },
                    "Commands": {
                        "multi_select": [{"name": cmd} for cmd in email.get('detected_commands', [])]
                    },
                    "Tone": {
                        "select": {"name": email.get('tone', 'neutral')}
                    },
                    "Team Tags": {
                        "multi_select": [{"name": tag} for tag in team_tags]
                    },
                    "Confidence Score": {
                        "number": email.get('confidence_score', 0)
                    },
                    "Action Status": {
                        "select": {"name": action_status}
                    },
                    "Reply Draft 1": {
                        "rich_text": [{"text": {"content": email.get('reply_draft_1', '')[:2000]}}]
                    },
                    "Reply Draft 2": {
                        "rich_text": [{"text": {"content": email.get('reply_draft_2', '')[:2000]}}]
                    },
                    "Processing Status": {
                        "select": {"name": "Completed"}
                    },
                    "Processed At": {
                        "date": {"start": datetime.utcnow().isoformat()}
                    }
                }
                
                # Clean up None values and invalid emails
                properties = {k: v for k, v in properties.items() if v is not None}
                
                self.notion_client.pages.create(
                    parent={"database_id": database_id},
                    properties=properties
                )
                
                successful_syncs += 1
                self.logger.debug(f"✅ Synced to Notion: {email.get('subject', 'No Subject')}")
                
            except Exception as e:
                self.logger.warning(f"❌ Notion sync failed for email '{email.get('subject', '')}': {str(e)}")
                continue
        
        self.logger.info(f"✅ Successfully synced {successful_syncs}/{len(processed_emails)} emails to Notion")
        return successful_syncs == len(processed_emails)
    
    def _determine_team_tags(self, commands: List[str]) -> List[str]:
        """Determine appropriate team tags based on detected commands"""
        team_mapping = {
            'Sales': [
                'schedule_demo', 'send_proposal', 'custom_plan_request',
                'partnership_request', 'confirm_availability', 'renew_contract'
            ],
            'Support': [
                'technical_issue', 'bug_report', 'access_request', 'reset_password',
                'security_alert', 'system_down', 'general_question'
            ],
            'HR': [
                'job_application', 'referral_submission', 'interview_schedule_request',
                'cv_update_request', 'hr_query', 'employee_onboarding'
            ],
            'Finance': [
                'billing_question', 'send_invoice', 'pricing_request',
                'account_closure', 'budget_request'
            ],
            'Legal': [
                'legal_inquiry', 'contract_request', 'privacy_policy_question',
                'data_deletion_request', 'compliance_audit', 'gdpr_request'
            ],
            'Operations': [
                'shipping_issue', 'delivery_update_request', 'return_request',
                'inventory_request', 'resource_allocation'
            ],
            'Marketing': [
                'unsubscribe', 'event_registration', 'press_inquiry',
                'marketing_collaboration', 'content_request'
            ]
        }
        
        assigned_teams = set()
        for team, team_commands in team_mapping.items():
            if any(cmd in commands for cmd in team_commands):
                assigned_teams.add(team)
        
        return list(assigned_teams) if assigned_teams else ['General']
    
    def _determine_action_status(self, email_data: Dict[str, Any]) -> str:
        """Determine the action status for Notion tracking"""
        reply_draft = email_data.get('reply_draft_1', '')
        commands = email_data.get('detected_commands', [])
        confidence = email_data.get('confidence_score', 0)
        
        if '[SKIPPED' in reply_draft.upper() or 'no_action' in commands:
            return 'Skipped'
        elif 'ERROR' in reply_draft.upper():
            return 'Error'
        elif 'requires_human_review' in commands or confidence < 40:
            return 'Needs Review'
        elif confidence >= 80:
            return 'Ready to Send'
        else:
            return 'Draft Generated'
    
    def process_emails_batch(self, days: int = 7, max_results: int = 50) -> Dict[str, Any]:
        """
        Main processing pipeline - fetch, analyze, and sync emails
        
        Returns processing summary and results
        """
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"🚀 Starting email processing batch (last {days} days, max {max_results} emails)")
            
            # Step 1: Fetch emails
            emails = self.fetch_recent_emails(days=days, max_results=max_results)
            
            if not emails:
                return {
                    'success': True,
                    'processed_count': 0,
                    'message': 'No emails found to process',
                    'processing_time': (datetime.utcnow() - start_time).total_seconds()
                }
            
            # Step 2: Process each email through the AI pipeline
            for i, email in enumerate(emails, 1):
                self.logger.info(f"Processing email {i}/{len(emails)}: {email.get('subject', 'No Subject')}")
                
                try:
                    # Generate summary
                    email['summary'] = self.generate_email_summary(email)
                    
                    # Classify commands
                    email['detected_commands'] = self.classify_email_commands(email)
                    
                    # Detect tone
                    email['tone'] = self.detect_email_tone(email)
                    
                    # Generate reply drafts
                    draft1, draft2 = self.generate_reply_drafts(email)
                    email['reply_draft_1'] = draft1
                    email['reply_draft_2'] = draft2
                    
                    # Calculate confidence score
                    email['confidence_score'] = self.calculate_confidence_score(email)
                    
                    self.logger.debug(f"✅ Completed processing: {email.get('subject', 'No Subject')}")
                    
                except Exception as e:
                    self.logger.error(f"❌ Failed to process email {i}: {str(e)}")
                    # Add error information to email record
                    email['processing_error'] = str(e)
                    email['confidence_score'] = 0
                    continue
            
            # Step 3: Sync to Notion
            notion_success = self.sync_to_notion(emails)
            
            # Step 4: Generate processing summary
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            summary = {
                'success': True,
                'processed_count': len(emails),
                'notion_sync_success': notion_success,
                'processing_time': processing_time,
                'languages_detected': list(set(email.get('detected_language', 'English') for email in emails)),
                'commands_summary': self._generate_commands_summary(emails),
                'confidence_distribution': self._calculate_confidence_distribution(emails),
                'tone_distribution': self._calculate_tone_distribution(emails),
                'emails_by_team': self._group_emails_by_team(emails),
                'high_priority_count': len([e for e in emails if e.get('tone') == 'urgent' or e.get('confidence_score', 0) >= 80]),
                'needs_review_count': len([e for e in emails if 'requires_human_review' in e.get('detected_commands', [])]),
                'processed_at': datetime.utcnow().isoformat(),
                'emails': emails  # Include full email data for API responses
            }
            
            self.logger.info(f"✅ Batch processing completed successfully in {processing_time:.2f}s")
            return summary
            
        except Exception as e:
            error_msg = f"Batch processing failed: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'processed_count': 0,
                'processing_time': (datetime.utcnow() - start_time).total_seconds(),
                'traceback': traceback.format_exc()
            }
    
    def _generate_commands_summary(self, emails: List[Dict[str, Any]]) -> Dict[str, int]:
        """Generate summary of detected commands across all emails"""
        command_counts = {}
        for email in emails:
            for command in email.get('detected_commands', []):
                command_counts[command] = command_counts.get(command, 0) + 1
        return dict(sorted(command_counts.items(), key=lambda x: x[1], reverse=True))
    
    def _calculate_confidence_distribution(self, emails: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate distribution of confidence scores"""
        distribution = {'0-20': 0, '21-40': 0, '41-60': 0, '61-80': 0, '81-100': 0}
        for email in emails:
            score = email.get('confidence_score', 0)
            if score <= 20:
                distribution['0-20'] += 1
            elif score <= 40:
                distribution['21-40'] += 1
            elif score <= 60:
                distribution['41-60'] += 1
            elif score <= 80:
                distribution['61-80'] += 1
            else:
                distribution['81-100'] += 1
        return distribution
    
    def _calculate_tone_distribution(self, emails: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate distribution of email tones"""
        tone_counts = {}
        for email in emails:
            tone = email.get('tone', 'neutral')
            tone_counts[tone] = tone_counts.get(tone, 0) + 1
        return tone_counts
    
    def _group_emails_by_team(self, emails: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group emails by assigned team tags"""
        team_counts = {}
        for email in emails:
            teams = self._determine_team_tags(email.get('detected_commands', []))
            for team in teams:
                team_counts[team] = team_counts.get(team, 0) + 1
        return team_counts
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics and system health"""
        try:
            return {
                'system_status': 'healthy',
                'services': {
                    'gmail_api': bool(self.gmail_service),
                    'openai_api': bool(self.openai_client),
                    'notion_api': bool(self.notion_client)
                },
                'supported_languages': ['English', 'Spanish', 'French', 'German', 'Italian', 'Portuguese', 'Dutch', 'Chinese', 'Arabic'],
                'command_categories': len(self.BUSINESS_COMMANDS),
                'available_commands': self.BUSINESS_COMMANDS,
                'version': '2.0.0',
                'last_check': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'system_status': 'error',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }


def create_gmail_assistant(config: Dict[str, Any]) -> GmailAssistant:
    """Factory function to create and initialize Gmail Assistant"""
    return GmailAssistant(config)
