from src.config import USER_AGENT

def get_conversation_count(session, org_id):
    response = session.get(
            f"https://claude.ai/api/organizations/{org_id}/chat_conversations/count_all",
            headers={
                "User-Agent": USER_AGENT,
                "referer": "https://claude.ai/",
                "accept": "*/*",
            },
            timeout=10
        )
    return response

def get_conversations(session, org_id, limit=200, starred=False):
    """Get conversations for an organization"""
    return session.get(
        f"https://claude.ai/api/organizations/{org_id}/chat_conversations?limit={limit}&starred={str(starred).lower()}&consistency=eventual",
        headers={
            "User-Agent": USER_AGENT,
            "referer": "https://claude.ai/new",
            "accept": "*/*",
        },
        timeout=10
    )

def send_completion(session, org_id, conversation_uuid, prompt, parent_message_uuid, tools=None):
    """Send a completion request and return streaming response"""
    
    # Default tools if not provided
    if tools is None:
        tools = [
            {"type": "web_search_v0", "name": "web_search"},
            {"type": "artifacts_v0", "name": "artifacts"},
            {"type": "repl_v0", "name": "repl"}
        ]
    
    body = {
        "prompt": prompt,
        "parent_message_uuid": parent_message_uuid,
        "timezone": "America/New_York",
        "personalized_styles": [{
            "type": "default",
            "key": "Default",
            "name": "Normal",
            "nameKey": "normal_style_name",
            "prompt": "Normal\n",
            "summary": "Default responses from Claude",
            "summaryKey": "normal_style_summary",
            "isDefault": True
        }],
        "locale": "en-US",
        "tools": tools,  # Now dynamic!
        "attachments": [],
        "files": [],
        "sync_sources": [],
        "rendering_mode": "messages"
    }
    
    return session.post(
        f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{conversation_uuid}/completion",
        headers={
            "User-Agent": USER_AGENT,
            "accept": "text/event-stream, text/event-stream",
            "referer": f"https://claude.ai/chat/{conversation_uuid}",
            "content-type": "application/json",
        },
        json=body,
        stream=True,
        timeout=60
    )

def get_conversation_details(session, org_id, conversation_uuid):
    """Get full conversation tree with message history"""
    return session.get(
        f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{conversation_uuid}?tree=True&rendering_mode=messages&render_all_tools=true&consistency=strong",
        headers={
            "User-Agent": USER_AGENT,
            "referer": f"https://claude.ai/chat/{conversation_uuid}",
            "accept": "*/*",
        },
        timeout=10
    )

def delete_conversation(session, org_id, conversation_uuid):
    """Delete a conversation"""
    return session.delete(
        f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{conversation_uuid}",
        headers={
            "User-Agent": USER_AGENT,
            "accept": "*/*",
            "referer": f"https://claude.ai/chat/{conversation_uuid}",
        },
        timeout=10
    )

def create_conversation(session, org_id, conversation_uuid, name="", is_temporary=False):
    """Create a new conversation"""
    url = f"https://claude.ai/api/organizations/{org_id}/chat_conversations"
    
    payload = {
        "uuid": conversation_uuid,
        "name": name,
        "include_conversation_preferences": True,
        "is_temporary": is_temporary
    }
    
    return session.post(
        url, 
        json=payload,
        headers={
            "User-Agent": USER_AGENT,
            "accept": "*/*",
            "referer": f"https://claude.ai/new",
            "content-type": "application/json",
        },)

def rename_conversation(session, org_id, conversation_uuid, new_name):
    """Rename a conversation"""
    url = f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{conversation_uuid}"
    headers = {
        "User-Agent": USER_AGENT,
        "accept": "*/*",
        "referer": f"https://claude.ai/new",
        "content-type": "application/json",
    }
    body = {"name": new_name}
    
    return session.put(url, headers=headers, json=body)

def update_conversation_settings(session, org_id, conversation_uuid, settings):
    """Update conversation settings (web_search, paprika_mode, artifacts)"""
    url = f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{conversation_uuid}"
    headers = {
        "User-Agent": USER_AGENT,
        "accept": "*/*",
        "referer": f"https://claude.ai/new",
        "content-type": "application/json",
    }
    body = {"settings": settings}
    return session.put(url, headers=headers, json=body, params={"rendering_mode": "raw"})