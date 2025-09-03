"""
FIT Group - Notion Database Manager
==================================
Manages shared Notion database operations for multi-user email processing.
Handles both user management and email results storage.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from notion_client import Client as NotionClient


class NotionManager:
    """Manages Notion database operations for multi-user system"""
    
    def __init__(self, notion_token: str, users_db_id: str, results_db_id: str):
        """Initialize Notion Manager"""
        self.notion_client = NotionClient(auth=notion_token)
        self.users_db_id = users_db_id
        self.results_db_id = results_db_id
        self.logger = logging.getLogger(__name__)

        # Cached schemas
        self._users_properties: Dict[str, Any] = {}
        self._results_properties: Dict[str, Any] = {}
        
        # Ensure databases exist and load schema
        self._ensure_databases()
        self._load_schemas()
    
    # -----------------
    # Schema management
    # -----------------
    def _ensure_databases(self):
        """Ensure both users and results databases exist"""
        try:
            users_db = self.notion_client.databases.retrieve(database_id=self.users_db_id)
            self.logger.info(
                f"✅ Users database found: {users_db.get('title', [{}])[0].get('plain_text', 'Unknown')}"
            )
            results_db = self.notion_client.databases.retrieve(database_id=self.results_db_id)
            self.logger.info(
                f"✅ Results database found: {results_db.get('title', [{}])[0].get('plain_text', 'Unknown')}"
            )
        except Exception as e:
            self.logger.error(f"❌ Database check failed: {str(e)}")
            raise Exception(
                "Database validation failed. Please check NOTION_USERS_DB_ID and NOTION_RESULTS_DB_ID."
            )

    def _load_schemas(self):
        """Load and cache DB properties for users and results DBs"""
        try:
            users_db = self.notion_client.databases.retrieve(database_id=self.users_db_id)
            self._users_properties = users_db.get('properties', {}) or {}
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to load users DB schema: {e}")
            self._users_properties = {}
        
        try:
            results_db = self.notion_client.databases.retrieve(database_id=self.results_db_id)
            self._results_properties = results_db.get('properties', {}) or {}
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to load results DB schema: {e}")
            self._results_properties = {}

    def _ensure_results_property(self, name: str, ptype: str) -> None:
        """Ensure a property exists on the results database with the desired type.
        Supports common types, primarily multi_select for 'Labels'."""
        try:
            current = self._prop_type('results', name)
            if current == ptype:
                return
            props_update: Dict[str, Any] = {}
            if ptype == 'multi_select':
                props_update[name] = {"multi_select": {}}
            elif ptype == 'select':
                props_update[name] = {"select": {}}
            elif ptype == 'rich_text':
                props_update[name] = {"rich_text": {}}
            elif ptype == 'title':
                props_update[name] = {"title": {}}
            elif ptype == 'date':
                props_update[name] = {"date": {}}
            elif ptype == 'email':
                props_update[name] = {"email": {}}
            elif ptype == 'number':
                props_update[name] = {"number": {}}
            elif ptype == 'checkbox':
                props_update[name] = {"checkbox": {}}
            else:
                return
            self.notion_client.databases.update(
                database_id=self.results_db_id,
                properties=props_update
            )
            self._load_schemas()
            self.logger.info(f"✅ Ensured results property '{name}' exists as type '{ptype}'")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to ensure results property '{name}' as {ptype}: {e}")

    def _prop_type(self, db: str, prop: str) -> Optional[str]:
        props = self._results_properties if db == 'results' else self._users_properties
        p = props.get(prop)
        return p.get('type') if isinstance(p, dict) else None

    def _build_prop(self, db: str, prop: str, value: Any) -> Optional[Dict[str, Any]]:
        ptype = self._prop_type(db, prop)
        if not ptype:
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
            items: List[str] = []
            if isinstance(value, list):
                items = [str(v) for v in value]
            elif isinstance(value, str):
                items = [v.strip() for v in value.split(',') if v.strip()]
            return {"multi_select": [{"name": v} for v in items]}
        if ptype == 'number':
            try:
                return {"number": float(value)}
            except Exception:
                return {"number": None}
        if ptype == 'checkbox':
            return {"checkbox": bool(value)}
        return None

    def _sanitize_email(self, value: Optional[str]) -> Optional[str]:
        try:
            if not value:
                return None
            v = value.strip()
            # Extract between angle brackets if present
            if '<' in v and '>' in v:
                start = v.find('<') + 1
                end = v.find('>', start)
                if end > start:
                    v = v[start:end].strip()
            m = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', v)
            return m.group(0).lower() if m else None
        except Exception:
            return None

    # -----------------
    # Public operations
    # -----------------
    def create_email_result(self, email_data: Dict[str, Any], user_email: str) -> Optional[str]:
        """Create a new email result entry in the shared results database (schema-aware)"""
        try:
            self._load_schemas()  # refresh in case schema changed
            # Ensure Labels property exists as multi_select for saving Gmail labels
            self._ensure_results_property('Labels', 'multi_select')

            props: Dict[str, Any] = {}

            # Common values
            subject = (email_data.get('subject') or 'No Subject')[:100]
            sender_raw = email_data.get('sender', '')
            safe_user_email = self._sanitize_email(user_email) or user_email
            safe_sender = self._sanitize_email(sender_raw) or sender_raw
            received_date = email_data.get('received_time', '')
            language = email_data.get('detected_language', 'English')
            priority = email_data.get('priority', 'MEDIUM')
            processed_at = datetime.utcnow().isoformat()
            summary = (email_data.get('summary') or '')[:1000]
            thread_id = email_data.get('thread_id')
            commands_list = email_data.get('detected_commands') or email_data.get('commands') or []
            team_tags = self._determine_team_tags(commands_list)
            tone = email_data.get('tone', 'neutral')
            confidence_score = email_data.get('confidence_score', 0)
            action_status = self._determine_action_status(email_data)
            reply1 = email_data.get('reply_draft_1')
            reply2 = email_data.get('reply_draft_2')
            processing_status = email_data.get('processing_status', 'Completed')

            # Title
            if 'Email Subject' in self._results_properties:
                p = self._build_prop('results', 'Email Subject', subject)
                if p is not None:
                    props['Email Subject'] = p

            # User Email
            if 'User Email' in self._results_properties:
                p = self._build_prop('results', 'User Email', safe_user_email)
                if p is not None:
                    props['User Email'] = p

            # Sender
            if 'Sender' in self._results_properties:
                p = self._build_prop('results', 'Sender', safe_sender)
                if p is not None:
                    props['Sender'] = p

            # Received Date
            if 'Received Date' in self._results_properties:
                p = self._build_prop('results', 'Received Date', received_date)
                if p is not None:
                    props['Received Date'] = p

            # Language
            if 'Language' in self._results_properties:
                p = self._build_prop('results', 'Language', language)
                if p is not None:
                    props['Language'] = p

            # Priority
            if 'Priority' in self._results_properties:
                p = self._build_prop('results', 'Priority', priority)
                if p is not None:
                    props['Priority'] = p

            # Status (default Processed)
            if 'Status' in self._results_properties:
                p = self._build_prop('results', 'Status', 'Processed')
                if p is not None:
                    props['Status'] = p

            # Processing Date / fallback to Processed At
            if 'Processing Date' in self._results_properties:
                p = self._build_prop('results', 'Processing Date', processed_at)
                if p is not None:
                    props['Processing Date'] = p
            elif 'Processed At' in self._results_properties:
                p = self._build_prop('results', 'Processed At', processed_at)
                if p is not None:
                    props['Processed At'] = p

            # Additional requested fields
            if 'Tone' in self._results_properties:
                p = self._build_prop('results', 'Tone', tone)
                if p is not None:
                    props['Tone'] = p
            if 'Team Tags' in self._results_properties:
                if self._prop_type('results', 'Team Tags') == 'multi_select':
                    p = self._build_prop('results', 'Team Tags', team_tags)
                else:
                    p = self._build_prop('results', 'Team Tags', ', '.join(team_tags))
                if p is not None:
                    props['Team Tags'] = p
            if 'Confidence Score' in self._results_properties:
                p = self._build_prop('results', 'Confidence Score', confidence_score)
                if p is not None:
                    props['Confidence Score'] = p
            if 'Action Status' in self._results_properties:
                p = self._build_prop('results', 'Action Status', action_status)
                if p is not None:
                    props['Action Status'] = p
            if 'Reply Draft 1' in self._results_properties and reply1:
                p = self._build_prop('results', 'Reply Draft 1', str(reply1)[:2000])
                if p is not None:
                    props['Reply Draft 1'] = p
            if 'Reply Draft 2' in self._results_properties and reply2:
                p = self._build_prop('results', 'Reply Draft 2', str(reply2)[:2000])
                if p is not None:
                    props['Reply Draft 2'] = p
            if 'Processing Status' in self._results_properties:
                p = self._build_prop('results', 'Processing Status', processing_status)
                if p is not None:
                    props['Processing Status'] = p

            # Commands
            if 'Commands' in self._results_properties:
                if self._prop_type('results', 'Commands') == 'multi_select':
                    p = self._build_prop('results', 'Commands', commands_list)
                else:
                    commands_text = ', '.join(commands_list[:10])
                    p = self._build_prop('results', 'Commands', commands_text)
                if p is not None:
                    props['Commands'] = p

            # Labels (Gmail) as multi-select
            if 'Labels' in self._results_properties:
                labels_list = email_data.get('labels') or []
                p = self._build_prop('results', 'Labels', labels_list)
                if p is not None:
                    props['Labels'] = p

            # Summary
            if 'Summary' in self._results_properties and summary:
                p = self._build_prop('results', 'Summary', summary)
                if p is not None:
                    props['Summary'] = p

            # Thread ID
            if 'Thread ID' in self._results_properties and thread_id:
                p = self._build_prop('results', 'Thread ID', thread_id)
                if p is not None:
                    props['Thread ID'] = p

            if not props:
                raise Exception("Results DB has no matching properties for the payload; please check schema.")

            response = self.notion_client.pages.create(
                parent={"database_id": self.results_db_id},
                properties=props
            )
            page_id = response['id']
            self.logger.info(
                f"✅ Created email result for {safe_user_email}: '{subject}' (page_id={page_id})"
            )
            return page_id
        
        except Exception as e:
            self.logger.error(
                "❌ Failed to create email result: %s",
                str(e)
            )
            return None

    def get_user_results(self, user_email: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get email results for a specific user (schema-aware filter)"""
        try:
            self._load_schemas()
            past_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            if 'User Email' not in self._results_properties:
                return []

            ptype = self._prop_type('results', 'User Email')
            if ptype == 'email':
                user_filter = {"property": "User Email", "email": {"equals": user_email}}
            else:
                user_filter = {"property": "User Email", "rich_text": {"equals": user_email}}

            date_prop = 'Processing Date' if 'Processing Date' in self._results_properties else (
                'Processed At' if 'Processed At' in self._results_properties else None
            )
            if not date_prop:
                return []

            response = self.notion_client.databases.query(
                database_id=self.results_db_id,
                filter={
                    "and": [
                        user_filter,
                        {"property": date_prop, "date": {"on_or_after": past_date}},
                    ]
                },
                sorts=[{"property": date_prop, "direction": "descending"}]
            )
            
            results: List[Dict[str, Any]] = []
            for page in response.get('results', []):
                result_data = self._parse_result_page(page)
                if result_data:
                    results.append(result_data)
            
            self.logger.info(f"✅ Retrieved {len(results)} results for {user_email}")
            return results
        except Exception as e:
            self.logger.error(f"❌ Failed to get user results: {str(e)}")
            return []

    def get_all_results(self, days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all email results from the shared database"""
        try:
            self._load_schemas()
            past_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            date_prop = 'Processing Date' if 'Processing Date' in self._results_properties else (
                'Processed At' if 'Processed At' in self._results_properties else None
            )
            if not date_prop:
                return []

            response = self.notion_client.databases.query(
                database_id=self.results_db_id,
                filter={"property": date_prop, "date": {"on_or_after": past_date}},
                sorts=[{"property": date_prop, "direction": "descending"}],
                page_size=limit
            )
            
            results: List[Dict[str, Any]] = []
            for page in response.get('results', []):
                result_data = self._parse_result_page(page)
                if result_data:
                    results.append(result_data)
            self.logger.info(f"✅ Retrieved {len(results)} total results")
            return results
        except Exception as e:
            self.logger.error(f"❌ Failed to get all results: {str(e)}")
            return []

    def search_results(
        self,
        user_email: str,
        labels: Optional[List[str]] = None,
        date_preset: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        text: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Query results DB by filters: user, labels, date range/preset, text. Returns matching rows.
        - labels: OR across provided labels (contains)
        - text: OR across Subject/Summary/Sender (contains)
        - date: if preset in {24h,7d,30d} use that; else use provided from/to
        """
        try:
            self._load_schemas()

            # Determine date property
            date_prop = 'Processing Date' if 'Processing Date' in self._results_properties else (
                'Processed At' if 'Processed At' in self._results_properties else None
            )
            if not date_prop:
                return []

            # Build user filter (only when a specific user is requested)
            filters_and: List[Dict[str, Any]] = []
            if user_email and 'User Email' in self._results_properties:
                ptype = self._prop_type('results', 'User Email')
                if ptype == 'email':
                    filters_and.append({"property": "User Email", "email": {"equals": user_email}})
                else:
                    filters_and.append({"property": "User Email", "rich_text": {"equals": user_email}})

            # Date filter (supports presets and custom range). For custom:
            # - from: inclusive at start of day
            # - to: inclusive end of day (implemented via before next-day 00:00)
            start_date: Optional[str] = None
            end_date: Optional[str] = None
            end_exclusive = False
            preset = (date_preset or '').lower()
            if preset in ('24h', '7d', '30d'):
                days = 1 if preset == '24h' else (7 if preset == '7d' else 30)
                start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            else:
                if date_from:
                    sd = str(date_from)
                    # normalize to start of day when only a date provided
                    start_date = sd if 'T' in sd else f"{sd}T00:00:00"
                if date_to:
                    try:
                        dt_to = datetime.fromisoformat(str(date_to))
                        end_date = (dt_to + timedelta(days=1)).isoformat()
                        end_exclusive = True
                    except Exception:
                        # fallback (keep as provided)
                        ed = str(date_to)
                        end_date = ed if 'T' in ed else f"{ed}T23:59:59"
                        end_exclusive = False
            # Apply date filters
            if start_date:
                filters_and.append({"property": date_prop, "date": {"on_or_after": start_date}})
            if end_date:
                if end_exclusive:
                    filters_and.append({"property": date_prop, "date": {"before": end_date}})
                else:
                    filters_and.append({"property": date_prop, "date": {"on_or_before": end_date}})
            if not start_date and not end_date:
                filters_and.append({"property": date_prop, "date": {"on_or_after": (datetime.utcnow() - timedelta(days=30)).isoformat()}})

            # Labels AND filter (must contain all selected labels)
            labels = labels or []
            if labels and 'Labels' in self._results_properties and self._prop_type('results', 'Labels') == 'multi_select':
                label_filters = [{"property": 'Labels', "multi_select": {"contains": l}} for l in labels]
                for lf in label_filters:
                    filters_and.append(lf)

            # Text OR filter across known textual fields
            text = (text or '').strip()
            if text:
                text_filters: List[Dict[str, Any]] = []
                if 'Email Subject' in self._results_properties:
                    text_filters.append({"property": 'Email Subject', "title": {"contains": text}})
                if 'Summary' in self._results_properties:
                    text_filters.append({"property": 'Summary', "rich_text": {"contains": text}})
                if 'Sender' in self._results_properties:
                    ptype_sender = self._prop_type('results', 'Sender')
                    if ptype_sender == 'email':
                        text_filters.append({"property": 'Sender', "email": {"contains": text}})
                    else:
                        text_filters.append({"property": 'Sender', "rich_text": {"contains": text}})
                if text_filters:
                    if len(text_filters) == 1:
                        filters_and.append(text_filters[0])
                    else:
                        filters_and.append({"or": text_filters})

            # Paginate and aggregate up to limit
            results: List[Dict[str, Any]] = []
            start_cursor: Optional[str] = None
            while True:
                page_size = 100 if limit > 100 else limit
                if page_size <= 0:
                    break
                query_args: Dict[str, Any] = {
                    'database_id': self.results_db_id,
                    'filter': {"and": filters_and},
                    'sorts': [{"property": date_prop, "direction": "descending"}],
                    'page_size': page_size
                }
                if start_cursor:
                    query_args['start_cursor'] = start_cursor
                response = self.notion_client.databases.query(**query_args)
                for page in response.get('results', []):
                    parsed = self._parse_result_page(page)
                    if parsed:
                        results.append(parsed)
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
                if response.get('has_more'):
                    start_cursor = response.get('next_cursor')
                else:
                    break

            return results
        except Exception as e:
            self.logger.error(f"❌ Failed to search results: {str(e)}")
            return []

    def update_result_status(self, result_id: str, status: str, notes: str = None) -> bool:
        """Update the status of an email result"""
        try:
            update_data = {}
            if 'Status' in self._results_properties:
                update_data['Status'] = {"select": {"name": status}}
            if notes and 'Notes' in self._results_properties:
                update_data['Notes'] = {"rich_text": [{"text": {"content": notes}}]}
            if not update_data:
                return False
            self.notion_client.pages.update(page_id=result_id, properties=update_data)
            self.logger.info(f"✅ Updated result {result_id} status to {status}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to update result status: {str(e)}")
            return False

    # -----------------
    # Business helpers
    # -----------------
    def _determine_team_tags(self, commands: List[str]) -> List[str]:
        mapping = {
            'Sales': ['schedule_demo', 'send_proposal', 'custom_plan_request', 'partnership_request', 'confirm_availability', 'renew_contract'],
            'Support': ['technical_issue', 'bug_report', 'access_request', 'reset_password', 'security_alert', 'system_down', 'general_question'],
            'HR': ['job_application', 'referral_submission', 'interview_schedule_request', 'cv_update_request', 'hr_query', 'employee_onboarding'],
            'Finance': ['billing_question', 'send_invoice', 'pricing_request', 'account_closure', 'budget_request'],
            'Legal': ['legal_inquiry', 'contract_request', 'privacy_policy_question', 'data_deletion_request', 'compliance_audit', 'gdpr_request'],
            'Operations': ['shipping_issue', 'delivery_update_request', 'return_request', 'inventory_request', 'resource_allocation'],
            'Marketing': ['unsubscribe', 'event_registration', 'press_inquiry', 'marketing_collaboration', 'content_request'],
        }
        assigned = set()
        for team, cmds in mapping.items():
            if any(c in (commands or []) for c in cmds):
                assigned.add(team)
        return list(assigned) if assigned else ['General']

    def _determine_action_status(self, email_data: Dict[str, Any]) -> str:
        reply = (email_data.get('reply_draft_1') or '') + (email_data.get('reply_draft_2') or '')
        commands = email_data.get('detected_commands') or []
        confidence = email_data.get('confidence_score', 0)
        text = reply.upper()
        if '[SKIPPED' in text or 'no_action' in commands:
            return 'Skipped'
        if 'ERROR' in text:
            return 'Error'
        if 'requires_human_review' in commands or confidence < 40:
            return 'Needs Review'
        if confidence >= 80:
            return 'Ready to Send'
        return 'Draft Generated'

    # --------------
    # Parse helpers
    # --------------
    def _parse_result_page(self, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            properties = page.get('properties', {})
            data: Dict[str, Any] = {
                'result_id': page['id'],
                'subject': self._extract_title(properties, 'Email Subject'),
                'user_email': self._extract_email_or_text(properties, 'User Email'),
                'sender': self._extract_email_or_text(properties, 'Sender'),
                'received_date': self._extract_date(properties, 'Received Date'),
                'language': self._extract_select(properties, 'Language'),
                'priority': self._extract_select(properties, 'Priority'),
                'status': self._extract_select(properties, 'Status'),
                'processing_date': self._extract_date(properties, 'Processing Date') or self._extract_date(properties, 'Processed At'),
                'summary': self._extract_rich_text(properties, 'Summary'),
                'thread_id': self._extract_rich_text(properties, 'Thread ID'),
                'notes': self._extract_rich_text(properties, 'Notes'),
            }
            # Commands: support rich_text or multi_select
            if 'Commands' in properties:
                p = properties['Commands']
                ptype = p.get('type')
                if ptype == 'multi_select':
                    data['detected_commands'] = [it.get('name', '') for it in p.get('multi_select', []) if it.get('name')]
                else:
                    data['detected_commands'] = self._extract_rich_text(properties, 'Commands')
            # Team Tags: support multi_select or rich_text
            if 'Team Tags' in properties:
                p = properties['Team Tags']
                ptype = p.get('type')
                if ptype == 'multi_select':
                    team_tags_list = [it.get('name', '') for it in p.get('multi_select', []) if it.get('name')]
                    data['team_tag'] = ', '.join(team_tags_list) if team_tags_list else ''
                else:
                    data['team_tag'] = self._extract_rich_text(properties, 'Team Tags')
            # Action Status: select or rich_text
            if 'Action Status' in properties:
                name = self._extract_select(properties, 'Action Status')
                data['action_status'] = name or self._extract_rich_text(properties, 'Action Status')
            # Extract Labels multi-select if present
            if 'Labels' in properties and properties['Labels'].get('type') == 'multi_select':
                data['labels'] = [it.get('name', '') for it in properties['Labels'].get('multi_select', []) if it.get('name')]
            return data
        except Exception as e:
            self.logger.error(f"❌ Failed to parse result page: {str(e)}")
            return None

    def _extract_title(self, properties: Dict[str, Any], prop: str) -> str:
        arr = properties.get(prop, {}).get('title', [])
        return arr[0].get('plain_text', '') if arr else ''

    def _extract_rich_text(self, properties: Dict[str, Any], prop: str) -> str:
        arr = properties.get(prop, {}).get('rich_text', [])
        return arr[0].get('plain_text', '') if arr else ''

    def _extract_date(self, properties: Dict[str, Any], prop: str) -> str:
        d = properties.get(prop, {}).get('date', {})
        return d.get('start', '') if d else ''

    def _extract_select(self, properties: Dict[str, Any], prop: str) -> str:
        s = properties.get(prop, {}).get('select', {})
        return s.get('name', '') if s else ''

    def _extract_email_or_text(self, properties: Dict[str, Any], prop: str) -> str:
        ptype = self._prop_type('results', prop)
        if ptype == 'email':
            return properties.get(prop, {}).get('email', '')
        if ptype == 'title':
            return self._extract_title(properties, prop)
        return self._extract_rich_text(properties, prop)

    def cleanup_old_results(self, days: int = 90) -> int:
        """Clean up old results (archived status)"""
        try:
            past = (datetime.utcnow() - timedelta(days=days)).isoformat()
            date_prop = 'Processing Date' if 'Processing Date' in self._results_properties else (
                'Processed At' if 'Processed At' in self._results_properties else None
            )
            if not date_prop:
                return 0
            response = self.notion_client.databases.query(
                database_id=self.results_db_id,
                filter={
                    "and": [
                        {"property": date_prop, "date": {"before": past}},
                        {"property": "Status", "select": {"equals": "Processed"}} if 'Status' in self._results_properties else {"property": date_prop, "date": {"before": past}}
                    ]
                }
            )
            old_results = response.get('results', [])
            archived_count = 0
            for result in old_results:
                try:
                    if 'Status' in self._results_properties:
                        self.notion_client.pages.update(
                            page_id=result['id'],
                            properties={"Status": {"select": {"name": "Archived"}}}
                        )
                        archived_count += 1
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to archive result {result['id']}: {str(e)}")
                    continue
            self.logger.info(f"✅ Archived {archived_count} old results")
            return archived_count
        except Exception as e:
            self.logger.error(f"❌ Cleanup failed: {str(e)}")
            return 0

    def get_unique_labels(self, user_email: Optional[str] = None, days: int = 30) -> List[str]:
        """Collect all unique labels from the Results DB 'Labels' multi_select.
        Optionally filters by user_email and a time window (days)."""
        try:
            self._load_schemas()
            # Ensure Labels property exists and is multi_select
            if 'Labels' not in self._results_properties or self._prop_type('results', 'Labels') != 'multi_select':
                return []

            past_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            date_prop = 'Processing Date' if 'Processing Date' in self._results_properties else (
                'Processed At' if 'Processed At' in self._results_properties else None
            )
            if not date_prop:
                return []

            # Build filter
            filters: List[Dict[str, Any]] = [
                {"property": date_prop, "date": {"on_or_after": past_date}}
            ]
            if user_email and 'User Email' in self._results_properties:
                ptype = self._prop_type('results', 'User Email')
                if ptype == 'email':
                    user_filter = {"property": "User Email", "email": {"equals": user_email}}
                else:
                    user_filter = {"property": "User Email", "rich_text": {"equals": user_email}}
                filters.insert(0, user_filter)

            # Query with pagination to gather all labels
            labels_set: set[str] = set()
            start_cursor: Optional[str] = None
            while True:
                query_args: Dict[str, Any] = {
                    'database_id': self.results_db_id,
                    'filter': {"and": filters},
                    'page_size': 100
                }
                if start_cursor:
                    query_args['start_cursor'] = start_cursor
                response = self.notion_client.databases.query(**query_args)
                for page in response.get('results', []):
                    props = page.get('properties', {})
                    if 'Labels' in props and props['Labels'].get('type') == 'multi_select':
                        for opt in props['Labels'].get('multi_select', []):
                            name = opt.get('name')
                            if name:
                                labels_set.add(name)
                if response.get('has_more'):
                    start_cursor = response.get('next_cursor')
                else:
                    break

            return sorted(labels_set)
        except Exception as e:
            self.logger.error(f"❌ Failed to get unique labels: {str(e)}")
            return []
