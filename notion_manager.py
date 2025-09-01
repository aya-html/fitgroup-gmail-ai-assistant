"""
FIT Group - Notion Database Manager
==================================
Manages shared Notion database operations for multi-user email processing.
Handles both user management and email results storage.
"""

import os
import json
import logging
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
        
        # Ensure databases exist
        self._ensure_databases()
    
    def _ensure_databases(self):
        """Ensure both users and results databases exist"""
        try:
            # Check users database
            users_db = self.notion_client.databases.retrieve(database_id=self.users_db_id)
            self.logger.info(f"✅ Users database found: {users_db.get('title', [{}])[0].get('plain_text', 'Unknown')}")
            
            # Check results database
            results_db = self.notion_client.databases.retrieve(database_id=self.results_db_id)
            self.logger.info(f"✅ Results database found: {results_db.get('title', [{}])[0].get('plain_text', 'Unknown')}")
            
        except Exception as e:
            self.logger.error(f"❌ Database check failed: {str(e)}")
            raise Exception(f"Database validation failed. Please check NOTION_USERS_DB_ID and NOTION_RESULTS_DB_ID.")
    
    def create_email_result(self, email_data: Dict[str, Any], user_email: str) -> Optional[str]:
        """Create a new email result entry in the shared results database"""
        try:
            # Prepare the result data for Notion - keeping existing structure + adding User Email
            result_properties = {
                "Email Subject": {
                    "title": [{"text": {"content": email_data.get('subject', 'No Subject')[:100]}}]
                },
                "User Email": {
                    "rich_text": [{"text": {"content": user_email}}]
                },
                "Sender": {
                    "rich_text": [{"text": {"content": email_data.get('sender', 'Unknown')}}]
                },
                "Received Date": {
                    "date": {"start": email_data.get('received_time', '')}
                },
                "Language": {
                    "select": {"name": email_data.get('detected_language', 'English')}
                },
                "Priority": {
                    "select": {"name": email_data.get('priority', 'MEDIUM')}
                },
                "Status": {
                    "select": {"name": "Processed"}
                },
                "Processing Date": {
                    "date": {"start": datetime.utcnow().isoformat()}
                }
            }
            
            # Add command classification if available
            if email_data.get('commands'):
                commands_text = ', '.join(email_data['commands'][:5])  # Limit to 5 commands
                result_properties["Commands"] = {
                    "rich_text": [{"text": {"content": commands_text}}]
                }
            
            # Add summary if available
            if email_data.get('summary'):
                result_properties["Summary"] = {
                    "rich_text": [{"text": {"content": email_data['summary'][:1000]}}]  # Limit to 1000 chars
                }
            
            # Add thread ID for reference
            if email_data.get('thread_id'):
                result_properties["Thread ID"] = {
                    "rich_text": [{"text": {"content": email_data['thread_id']}}]
                }
            
            # Create the page in results database
            response = self.notion_client.pages.create(
                parent={"database_id": self.results_db_id},
                properties=result_properties
            )
            
            result_id = response['id']
            self.logger.info(f"✅ Created email result: {email_data.get('subject', 'No Subject')} for {user_email}")
            
            return result_id
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create email result: {str(e)}")
            return None
    
    def get_user_results(self, user_email: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get email results for a specific user"""
        try:
            # Calculate date filter
            past_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            response = self.notion_client.databases.query(
                database_id=self.results_db_id,
                filter={
                    "and": [
                        {
                            "property": "User Email",
                            "rich_text": {"equals": user_email}
                        },
                        {
                            "property": "Processing Date",
                            "date": {"on_or_after": past_date}
                        }
                    ]
                },
                sorts=[{"property": "Processing Date", "direction": "descending"}]
            )
            
            results = []
            for page in response['results']:
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
            # Calculate date filter
            past_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            response = self.notion_client.databases.query(
                database_id=self.results_db_id,
                filter={
                    "property": "Processing Date",
                    "date": {"on_or_after": past_date}
                },
                sorts=[{"property": "Processing Date", "direction": "descending"}],
                page_size=limit
            )
            
            results = []
            for page in response['results']:
                result_data = self._parse_result_page(page)
                if result_data:
                    results.append(result_data)
            
            self.logger.info(f"✅ Retrieved {len(results)} total results")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get all results: {str(e)}")
            return []
    
    def update_result_status(self, result_id: str, status: str, notes: str = None) -> bool:
        """Update the status of an email result"""
        try:
            update_data = {
                "Status": {"select": {"name": status}}
            }
            
            if notes:
                update_data["Notes"] = {
                    "rich_text": [{"text": {"content": notes}}]
                }
            
            self.notion_client.pages.update(
                page_id=result_id,
                properties=update_data
            )
            
            self.logger.info(f"✅ Updated result {result_id} status to {status}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to update result status: {str(e)}")
            return False
    
    def get_results_statistics(self, user_email: str = None, days: int = 30) -> Dict[str, Any]:
        """Get statistics about email processing results"""
        try:
            # Calculate date filter
            past_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Base filter
            base_filter = {
                "property": "Processing Date",
                "date": {"on_or_after": past_date}
            }
            
            # Add user filter if specified
            if user_email:
                base_filter = {
                    "and": [
                        base_filter,
                        {
                            "property": "User Email",
                            "rich_text": {"equals": user_email}
                        }
                    ]
                }
            
            response = self.notion_client.databases.query(
                database_id=self.results_db_id,
                filter=base_filter
            )
            
            results = response['results']
            
            # Calculate statistics
            stats = {
                'total_processed': len(results),
                'languages': {},
                'priorities': {},
                'statuses': {},
                'commands': {},
                'users': {}
            }
            
            for page in results:
                properties = page.get('properties', {})
                
                # Language stats
                language = self._extract_select(properties, 'Language')
                if language:
                    stats['languages'][language] = stats['languages'].get(language, 0) + 1
                
                # Priority stats
                priority = self._extract_select(properties, 'Priority')
                if priority:
                    stats['priorities'][priority] = stats['priorities'].get(priority, 0) + 1
                
                # Status stats
                status = self._extract_select(properties, 'Status')
                if status:
                    stats['statuses'][status] = stats['statuses'].get(status, 0) + 1
                
                # User stats
                user = self._extract_rich_text(properties, 'User Email')
                if user:
                    stats['users'][user] = stats['users'].get(user, 0) + 1
                
                # Command stats
                commands_text = self._extract_rich_text(properties, 'Commands')
                if commands_text:
                    commands = [cmd.strip() for cmd in commands_text.split(',')]
                    for cmd in commands:
                        if cmd:
                            stats['commands'][cmd] = stats['commands'].get(cmd, 0) + 1
            
            self.logger.info(f"✅ Generated statistics for {stats['total_processed']} results")
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Failed to generate statistics: {str(e)}")
            return {}
    
    def search_results(self, query: str, user_email: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search email results by text query"""
        try:
            # Use Notion's search functionality
            search_filter = {
                "property": "object",
                "value": "page"
            }
            
            if user_email:
                search_filter = {
                    "and": [
                        search_filter,
                        {
                            "property": "User Email",
                            "rich_text": {"equals": user_email}
                        }
                    ]
                }
            
            response = self.notion_client.search(
                query=query,
                filter=search_filter,
                page_size=limit
            )
            
            results = []
            for page in response['results']:
                # Only include pages from our results database
                if page.get('parent', {}).get('database_id') == self.results_db_id:
                    result_data = self._parse_result_page(page)
                    if result_data:
                        results.append(result_data)
            
            self.logger.info(f"✅ Search returned {len(results)} results for query: {query}")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Search failed: {str(e)}")
            return []
    
    def _parse_result_page(self, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Notion result page into result data dictionary"""
        try:
            properties = page.get('properties', {})
            
            # Extract basic properties
            result_data = {
                'result_id': page['id'],
                'subject': self._extract_title(properties, 'Email Subject'),
                'user_email': self._extract_rich_text(properties, 'User Email'),
                'sender': self._extract_rich_text(properties, 'Sender'),
                'received_date': self._extract_date(properties, 'Received Date'),
                'language': self._extract_select(properties, 'Language'),
                'priority': self._extract_select(properties, 'Priority'),
                'status': self._extract_select(properties, 'Status'),
                'processing_date': self._extract_date(properties, 'Processing Date'),
                'commands': self._extract_rich_text(properties, 'Commands'),
                'summary': self._extract_rich_text(properties, 'Summary'),
                'thread_id': self._extract_rich_text(properties, 'Thread ID'),
                'notes': self._extract_rich_text(properties, 'Notes')
            }
            
            return result_data
            
        except Exception as e:
            self.logger.error(f"❌ Failed to parse result page: {str(e)}")
            return None
    
    def _extract_title(self, properties: Dict[str, Any], property_name: str) -> str:
        """Extract title content from Notion property"""
        prop = properties.get(property_name, {}).get('title', [])
        return prop[0].get('plain_text', '') if prop else ''
    
    def _extract_rich_text(self, properties: Dict[str, Any], property_name: str) -> str:
        """Extract rich text content from Notion property"""
        prop = properties.get(property_name, {}).get('rich_text', [])
        return prop[0].get('plain_text', '') if prop else ''
    
    def _extract_date(self, properties: Dict[str, Any], property_name: str) -> str:
        """Extract date from Notion property"""
        prop = properties.get(property_name, {}).get('date', {})
        return prop.get('start', '') if prop else ''
    
    def _extract_select(self, properties: Dict[str, Any], property_name: str) -> str:
        """Extract select value from Notion property"""
        prop = properties.get(property_name, {}).get('select', {})
        return prop.get('name', '') if prop else ''
    
    def cleanup_old_results(self, days: int = 90) -> int:
        """Clean up old results (archived status)"""
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Find old results
            response = self.notion_client.databases.query(
                database_id=self.results_db_id,
                filter={
                    "and": [
                        {
                            "property": "Processing Date",
                            "date": {"before": cutoff_date}
                        },
                        {
                            "property": "Status",
                            "select": {"equals": "Processed"}
                        }
                    ]
                }
            )
            
            old_results = response['results']
            archived_count = 0
            
            for result in old_results:
                try:
                    # Archive old results
                    self.notion_client.pages.update(
                        page_id=result['id'],
                        properties={
                            "Status": {"select": {"name": "Archived"}}
                        }
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
