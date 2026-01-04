import uuid
import json
from ..helpers import (
    load_accounts,
    create_session_from_cookies,
    extract_org_id
)
from .. import claude


DEFAULT_SETTINGS = {
    "enabled_web_search": True,
    "preview_feature_uses_artifacts": True,
    "enabled_turmeric": True,
    "paprika_mode": None
}

DEFAULT_PARENT_UUID = "00000000-0000-4000-8000-000000000000"

class Response:

    def __init__(self, text="", artifacts=None, files=None, tool_uses=None):
        self.text = text
        self.artifacts = artifacts or []
        self.files = files or []
        self.tool_uses = tool_uses or []
    
    def __str__(self):
        """Return text when converted to string"""
        return self.text
    
    def __repr__(self):
        parts = [f"text_length={len(self.text)}"]
        if self.artifacts:
            parts.append(f"artifacts={len(self.artifacts)}")
        if self.files:
            parts.append(f"files={len(self.files)}")
        if self.tool_uses:
            parts.append(f"tool_uses={len(self.tool_uses)}")
        return f"<Response {', '.join(parts)}>"


class Conversation:
    def __init__(self, client, conversation_id):
        self.client = client
        self.uuid = conversation_id
        self.parent_message_uuid = DEFAULT_PARENT_UUID
        self.settings = None
        self._load_details()
    
    def _load_details(self):
        """Load conversation details to get latest message UUID and settings"""
        try:
            response = claude.get_conversation_details(
                self.client.session,
                self.client.org_id,
                self.uuid
            )
            
            if response.status_code == 200:
                data = response.json()
                messages = data.get('chat_messages', [])
                self.settings = data.get('settings', DEFAULT_SETTINGS)
                
                if messages:
                    self.parent_message_uuid = messages[-1]['uuid']
                else:
                    self.parent_message_uuid = DEFAULT_PARENT_UUID
        except Exception:
            # use defaults
            self.settings = DEFAULT_SETTINGS.copy()
            self.parent_message_uuid = DEFAULT_PARENT_UUID
    
    def send_message(self, prompt, stream=False):
        # Build tools from settings
        tools = self._build_tools(self.settings or DEFAULT_SETTINGS)
        
        # Send completion
        response = claude.send_completion(
            self.client.session,
            self.client.org_id,
            self.uuid,
            prompt,
            self.parent_message_uuid,
            tools=tools
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to send message: {response.status_code}")
        
        if stream:
            return self._stream_response(response)
        else:
            return self._parse_full_response(response)
    
    def _build_tools(self, settings):
        """Build tools list from settings"""
        tools = []
        if settings.get('enabled_web_search'):
            tools.append({"type": "web_search_v0", "name": "web_search"})
        if settings.get('preview_feature_uses_artifacts'):
            tools.append({"type": "artifacts_v0", "name": "artifacts"})
        if settings.get('enabled_turmeric'):
            tools.append({"type": "repl_v0", "name": "repl"})
        return tools
    
    def _parse_full_response(self, response):
        """Parse streaming response and return Response object with all content"""
        text_buffer = ""
        new_message_uuid = None
        artifacts = []
        files = []
        tool_uses = []
        
        # Track tool use blocks
        tool_use_buffer = {}
        current_tool_id = None
        
        for line in response.iter_lines():
            if not line:
                continue
            
            line = line.decode('utf-8')
            if not line.startswith('data: '):
                continue
            
            try:
                event = json.loads(line[6:])
                event_type = event.get('type')
                
                if event_type == 'message_start':
                    new_message_uuid = event.get('message', {}).get('uuid')
                
                elif event_type == 'content_block_start':
                    block = event.get('content_block', {})
                    block_type = block.get('type')
                    
                    if block_type == 'tool_use':
                        tool_id = block.get('id')
                        tool_name = block.get('name')
                        current_tool_id = tool_id
                        tool_use_buffer[tool_id] = {
                            'name': tool_name,
                            'input_json': ''
                        }
                
                elif event_type == 'content_block_delta':
                    delta = event.get('delta', {})
                    delta_type = delta.get('type')
                    
                    if delta_type == 'text_delta':
                        text_buffer += delta['text']
                    
                    elif delta_type == 'input_json_delta' and current_tool_id:
                        tool_data = tool_use_buffer[current_tool_id]
                        tool_data['input_json'] += delta['partial_json']
                
                elif event_type == 'content_block_stop':
                    if current_tool_id and current_tool_id in tool_use_buffer:
                        tool_data = tool_use_buffer[current_tool_id]
                        tool_name = tool_data['name']
                        
                        # Parse the complete JSON input
                        try:
                            input_data = json.loads(tool_data['input_json'])
                        except json.JSONDecodeError:
                            input_data = {}
                        
                        # Categorize by tool type
                        if tool_name == 'artifacts':
                            artifacts.append({
                                'title': input_data.get('title', 'Untitled'),
                                'content': input_data.get('content', ''),
                                'language': input_data.get('language', ''),
                                'type': input_data.get('type', ''),
                                'command': input_data.get('command', 'create')
                            })
                        
                        elif tool_name == 'create_file':
                            files.append({
                                'path': input_data.get('path', ''),
                                'content': input_data.get('file_text', ''),
                                'description': input_data.get('description', '')
                            })
                        
                        else:
                            # Other tool uses
                            tool_uses.append({
                                'name': tool_name,
                                'input': input_data
                            })
                        
                        current_tool_id = None
            
            except json.JSONDecodeError:
                pass
        
        # Update parent message UUID for next message
        if new_message_uuid:
            self.parent_message_uuid = new_message_uuid
        
        return Response(
            text=text_buffer,
            artifacts=artifacts,
            files=files,
            tool_uses=tool_uses
        )
    
    def _stream_response(self, response):
        """Generator that yields response chunks"""
        new_message_uuid = None
        
        for line in response.iter_lines():
            if not line:
                continue
            
            line = line.decode('utf-8')
            if not line.startswith('data: '):
                continue
            
            try:
                event = json.loads(line[6:])
                event_type = event.get('type')
                
                if event_type == 'message_start':
                    new_message_uuid = event.get('message', {}).get('uuid')
                
                elif event_type == 'content_block_delta':
                    delta = event.get('delta', {})
                    if delta.get('type') == 'text_delta':
                        yield delta['text']
            
            except json.JSONDecodeError:
                pass
        
        # Update parent message UUID after streaming completes
        if new_message_uuid:
            self.parent_message_uuid = new_message_uuid
    
    def history(self, limit=None):
        response = claude.get_conversation_details(
            self.client.session,
            self.client.org_id,
            self.uuid
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch history: {response.status_code}")
        
        messages = response.json().get('chat_messages', [])
        
        if limit:
            messages = messages[-limit:]
        
        # Simplify message format
        simplified = []
        for msg in messages:
            text_parts = []
            for content in msg.get('content', []):
                if content.get('type') == 'text':
                    text_parts.append(content.get('text', ''))
            
            simplified.append({
                'sender': msg.get('sender'),
                'text': '\n'.join(text_parts),
                'uuid': msg.get('uuid'),
                'created_at': msg.get('created_at'),
                'index': msg.get('index')
            })
        
        return simplified
    
    def update_settings(self, settings):
        response = claude.update_conversation_settings(
            self.client.session,
            self.client.org_id,
            self.uuid,
            settings
        )
        
        if response.status_code not in [200, 202]:
            raise Exception(f"Failed to update settings: {response.status_code}")

        if not self.settings:
            self.settings = {}
        self.settings.update(settings)
    
    def delete(self):
        response = claude.delete_conversation(
            self.client.session,
            self.client.org_id,
            self.uuid
        )
        
        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to delete conversation: {response.status_code}")
    
    def __repr__(self):
        return f"<Conversation uuid={self.uuid[:8]}...>"


class Client:
    def __init__(self, account_name):
        accounts = load_accounts()
        
        if account_name not in accounts:
            raise ValueError(f"Account '{account_name}' not found in auth.json")
        
        cookies = accounts[account_name]
        self.session = create_session_from_cookies(cookies)
        self.org_id = extract_org_id(cookies)
        
        if not self.org_id:
            raise ValueError(f"Could not extract org_id from account '{account_name}'")
        
        self.account_name = account_name
    
    def create_conversation(self, name=""):
        conversation_uuid = str(uuid.uuid4())
        
        response = claude.create_conversation(
            self.session, 
            self.org_id, 
            conversation_uuid, 
            name
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create conversation: {response.status_code}")
        
        return Conversation(self, conversation_uuid)
    
    def get_conversation(self, conversation_id):
        return Conversation(self, conversation_id)
    
    def list_conversations(self, limit=200, starred=False):
        response = claude.get_conversations(
            self.session, 
            self.org_id, 
            limit, 
            starred
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch conversations: {response.status_code}")
        
        return response.json()