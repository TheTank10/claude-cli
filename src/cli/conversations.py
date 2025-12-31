import click
import uuid
import sys, os
from datetime import datetime
from src.helpers import (
    get_active_session,
    get_active_conversation,
    set_active_conversation,
)
import src.claude as claude


@click.command()
@click.option('--limit', default=200, help='Number of conversations to fetch')
def conversations(limit):
    """List all conversations for the active account and select one to switch to"""
    session, org_id = get_active_session()
    
    if not session or not org_id:
        click.echo("No active account. Use 'switch-account' to select one.")
        return
    
    click.echo("Fetching conversations...")
    try:
        response_regular = claude.get_conversations(session, org_id, limit, starred=False)
        response_starred = claude.get_conversations(session, org_id, limit, starred=True)
        
        if response_regular.status_code == 200 and response_starred.status_code == 200:
            regular_convos = response_regular.json()
            starred_convos = response_starred.json()
            
            if not regular_convos and not starred_convos:
                click.echo("No conversations found.")
                return
            
            active_convo = get_active_conversation()
            
            convo_map = {}
            
            for i, convo in enumerate(reversed(regular_convos)):
                index = len(regular_convos) + len(starred_convos) - i
                name = convo.get('name', 'Untitled')
                uuid = convo.get('uuid', '')
                arrow = "-> " if uuid == active_convo else "   "
                click.echo(f"{arrow}{index}) {name} ({uuid[:8]}...)")
                convo_map[index] = uuid
            
            for i, convo in enumerate(reversed(starred_convos)):
                index = len(starred_convos) - i
                name = convo.get('name', 'Untitled')
                uuid = convo.get('uuid', '')
                arrow = "-> " if uuid == active_convo else "   "
                click.echo(f"{arrow}{index}) [*] {name} ({uuid[:8]}...)")
                convo_map[index] = uuid
            
            total = len(regular_convos) + len(starred_convos)
            click.echo(f"\nTotal: {total} conversations ({len(starred_convos)} starred)")
            
            selection = click.prompt("\nSelect conversation (number or press Enter to skip)", 
                                    default="", show_default=False)
            
            if selection and selection.isdigit():
                index = int(selection)
                if index in convo_map:
                    uuid = convo_map[index]
                    
                    click.echo("Loading conversation...")
                    response = claude.get_conversation_details(session, org_id, uuid)
                    
                    if response.status_code == 200:
                        convo_data = response.json()
                        messages = convo_data.get('chat_messages', [])
                        settings = convo_data.get('settings', {})

                        if messages:
                            last_message_uuid = messages[-1]['uuid']
                            set_active_conversation(uuid, last_message_uuid, settings)
                            click.echo(f"Switched to conversation #{index}")
                        else:
                            set_active_conversation(uuid, "00000000-0000-4000-8000-000000000000", settings)
                            click.echo(f"Switched to conversation #{index} (empty)")
                    else:
                        click.echo("Failed to load conversation details")
                else:
                    click.echo("Invalid conversation number")
                    
        elif response_regular.status_code == 401 or response_regular.status_code == 403:
            click.echo("Authentication failed. Your cookies may have expired.")
            click.echo("Run 'update-account' to refresh your cookies.")
        else:
            click.echo(f"Failed to fetch conversations")
    except Exception as e:
        click.echo(f"Error fetching conversations: {e}")


@click.command()
@click.option('--name', default="", help='Name for the new conversation')
def new(name):
    """Create a new conversation"""
    session, org_id = get_active_session()
    
    if not session or not org_id:
        click.echo("No active account. Use 'switch-account' to select one.")
        return
    
    conversation_uuid = str(uuid.uuid4())
    
    click.echo(f"Creating new conversation...")
    
    try:
        response = claude.create_conversation(session, org_id, conversation_uuid, name)
        
        if response.status_code == 201 or response.status_code == 200:
            data = response.json()
            click.echo(f"Conversation created: {data['uuid'][:8]}...")

            default_settings = {
                "enabled_web_search": True,
                "paprika_mode": None,
                "preview_feature_uses_artifacts": True,
                "enabled_turmeric": True
            }
            
            set_active_conversation(conversation_uuid, "00000000-0000-4000-8000-000000000000", default_settings)
            click.echo(f"Switched to new conversation")
        else:
            click.echo(f"Failed to create conversation (status: {response.status_code})")
    except Exception as e:
        click.echo(f"Error: {e}")


@click.command()
@click.argument('new_name', nargs=-1, required=False)
def name(new_name):
    """View or rename the active conversation"""
    session, org_id = get_active_session()
    conversation_uuid = get_active_conversation()
    
    if not session or not org_id:
        click.echo("No active account. Use 'switch-account' to select one.")
        return
    
    if not conversation_uuid:
        click.echo("No active conversation. Use 'conversations' to select one.")
        return
    
    try:
        response = claude.get_conversation_details(session, org_id, conversation_uuid)
        
        if response.status_code == 200:
            convo_data = response.json()
            current_name = convo_data.get('name', 'Untitled')
            
            if not new_name:
                click.echo(f"Current conversation: {current_name}")
                return
            
            new_name_str = " ".join(new_name)
            click.echo(f"Renaming conversation from '{current_name}' to '{new_name_str}'...")
            
            rename_response = claude.rename_conversation(session, org_id, conversation_uuid, new_name_str)
            
            if rename_response.status_code == 200 or rename_response.status_code == 202:
                click.echo(f"Conversation renamed successfully!")
            else:
                click.echo(f"Failed to rename conversation (status code: {rename_response.status_code})")
                
        elif response.status_code == 401 or response.status_code == 403:
            click.echo("Authentication failed. Your cookies may have expired.")
            click.echo("Run 'update-account' to refresh your cookies.")
        else:
            click.echo(f"Failed to fetch conversation (status code: {response.status_code})")
            
    except Exception as e:
        click.echo(f"Error: {e}")


@click.command()
@click.argument('conversation_uuid', required=False)
def delete(conversation_uuid):
    """Delete a conversation"""
    session, org_id = get_active_session()
    
    if not session or not org_id:
        click.echo("No active account. Use 'switch-account' to select one.")
        return
    
    if not conversation_uuid:
        conversation_uuid = get_active_conversation()
        if not conversation_uuid:
            click.echo("No conversation specified and no active conversation.")
            return
    
    if not click.confirm(f"Delete conversation {conversation_uuid[:8]}...?"):
        click.echo("Cancelled.")
        return
    
    try:
        response = claude.delete_conversation(session, org_id, conversation_uuid)
        
        if response.status_code in [200, 204]:
            click.echo(f"Conversation deleted")
            
            if conversation_uuid == get_active_conversation():
                set_active_conversation(None, None)
                click.echo("Cleared active conversation")
        else:
            click.echo(f"Failed to delete (status: {response.status_code})")
    except Exception as e:
        click.echo(f"Error: {e}")


@click.command()
def link():
    """Get the link to the active conversation"""
    conversation_uuid = get_active_conversation()
    click.echo(f"https://claude.ai/chat/{conversation_uuid or '???'}")


@click.command()
@click.argument('query', nargs=-1, required=True)
@click.option('-o', '--output', default=None, help='Output file or folder path')
def search(query, output):
    """Search for a phrase in the active conversation"""
    session, org_id = get_active_session()
    conversation_uuid = get_active_conversation()
    
    if not session or not org_id:
        return click.echo("No active account. Use 'switch-account' to select one.")
    if not conversation_uuid:
        return click.echo("No active conversation. Use 'conversations' to select one.")
    
    query_str = " ".join(query)
    
    try:
        response = claude.get_conversation_details(session, org_id, conversation_uuid)
        
        if response.status_code != 200:
            msg = "Authentication failed. Your cookies may have expired.\nRun 'update-account' to refresh your cookies." if response.status_code in [401, 403] else "Failed to fetch conversation"
            return click.echo(msg)
        
        messages = response.json().get('chat_messages', [])
        matches = []
        
        for msg in messages:
            text_parts, file_contents = [], []
            
            for content in msg.get('content', []):
                ctype, cdata = content.get('type'), content.get('input', {})
                
                if ctype == 'text':
                    text_parts.append(content.get('text', ''))
                
                elif ctype == 'tool_use':
                    tool = content.get('name', '')
                    
                    # Artifacts tool 
                    if tool == 'artifacts':
                        if art_content := cdata.get('content'):
                            art_title = cdata.get('title', 'unknown')
                            file_contents.append(f"\n--- Artifact: {art_title} ---\n{art_content}\n")
                            text_parts.append(art_content)
                    
                    elif tool == 'create_file':
                        if file_text := cdata.get('file_text'):
                            file_contents.append(f"\n--- Created File: {cdata.get('path', 'unknown')} ---\n{file_text}\n")
                            text_parts.append(file_text)
                    
                    elif tool == 'str_replace':
                        old, new = cdata.get('old_str', ''), cdata.get('new_str', '')
                        if old or new:
                            text_parts.append(f"[Edit] Old: {old} -> New: {new}")
                
                elif ctype == 'tool_result':
                    tool = content.get('name', '')
                    
                    if tool == 'present_files':
                        for rc in content.get('content', []):
                            if isinstance(rc, dict) and (fp := rc.get('file_path')):
                                try:
                                    with open(fp, 'r', encoding='utf-8') as f:
                                        file_data = f.read()
                                        file_contents.append(f"\n--- Presented File: {fp} ---\n{file_data}\n")
                                        text_parts.append(file_data)
                                except: pass
                    
                    elif tool in ['bash_tool', 'view']:
                        for rc in content.get('content', []):
                            if isinstance(rc, dict) and rc.get('type') == 'text':
                                text_parts.append(rc.get('text', ''))
            
            full_text = ' '.join(text_parts)
            if query_str.lower() in full_text.lower():
                matches.append({
                    'msg_uuid': msg.get('uuid'),
                    'sender': msg.get('sender'),
                    'timestamp': msg.get('created_at', 'unknown'),
                    'text': ' '.join(text_parts[:1]) + ('\n' + ''.join(file_contents) if file_contents else ''),
                    'search_text': full_text,
                    'index': msg.get('index'),
                    'match_pos': full_text.lower().find(query_str.lower())
                })
        
        if not matches:
            return click.echo("No matches found.")
        
        # Output handling
        is_redirected = not sys.stdout.isatty()
        
        def format_ts(ts):
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
            except:
                return ts
        
        if output or is_redirected:
            if output and output.endswith('.txt'):
                with open(output, 'w', encoding='utf-8') as f:
                    for m in matches:
                        f.write(f"---\nrole: {m['sender']}\ntimestamp: {format_ts(m.get('timestamp', 'unknown'))}\nuuid: {m['msg_uuid']}\n---\n\n{m['text']}\n\n{'-'*50}\n\n")
                click.echo(f"Saved {len(matches)} messages to {output}", err=True)
            elif output:
                os.makedirs(output, exist_ok=True)
                for i, m in enumerate(matches):
                    idx = len(matches) - i  # 1 = most recent
                    ts = m.get('timestamp', 'unknown')
                    try:
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone()
                        time_str = dt.strftime('%Y-%m-%d_%H-%M-%S')
                        formatted_ts = dt.strftime('%Y-%m-%d %H:%M:%S %Z')
                    except:
                        time_str = 'unknown'
                        formatted_ts = ts
                    with open(os.path.join(output, f"{idx}_{m['sender']}_{time_str}.txt"), 'w', encoding='utf-8') as f:
                        f.write(f"---\nrole: {m['sender']}\ntimestamp: {formatted_ts}\nuuid: {m['msg_uuid']}\n---\n\n{m['text']}")
                click.echo(f"Saved {len(matches)} messages to {output}/", err=True)
            else:
                for m in matches:
                    click.echo(f"---\nrole: {m['sender']}\ntimestamp: {format_ts(m.get('timestamp', 'unknown'))}\nuuid: {m['msg_uuid']}\n---\n\n{m['text']}\n\n{'-'*50}\n")
        else:
            # Interactive mode
            while True:
                for i, m in enumerate(matches):
                    idx = len(matches) - i
                    pos = m['match_pos']
                    txt = m['search_text']
                    start, end = max(0, pos - 30), min(len(txt), pos + len(query_str) + 70)
                    preview = ('...' if start > 0 else '') + txt[start:end].replace('\n', ' ') + ('...' if end < len(txt) else '')
                    click.echo(f"{idx}) [{m['sender']}] {preview}")
                
                selection = click.prompt("\nLoad (enter index or press Enter to exit)", default="", show_default=False)
                
                if not selection:
                    break
                
                if selection.isdigit() and 1 <= int(selection) <= len(matches):
                    m = matches[int(selection) - 1]
                    click.echo(f"\n---\nrole: {m['sender']}\ntimestamp: {format_ts(m.get('timestamp', 'unknown'))}\nuuid: {m['msg_uuid']}\n---\n\n{m['text']}\n")
                else:
                    click.echo("Invalid index" if selection.isdigit() else "Please enter a number")
                    
    except Exception as e:
        click.echo(f"Error: {e}")