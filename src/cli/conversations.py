import click
import uuid
import sys, os
from datetime import datetime
from src.helpers import (
    get_active_session,
    get_active_conversation,
    set_active_conversation,
)
from src.config import extension_languages as ext_lang
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


@click.command()
@click.argument('scope', type=click.Choice(['all', 'this', 'choose']), required=False)
@click.argument('format', type=click.Choice(['json', 'js', 'markdown', 'md']), required=False)
@click.argument('directory', required=False)
def export(scope, format, directory):
    """Export conversations to JSON or Markdown format"""
    session, org_id = get_active_session()
    
    if not session or not org_id:
        click.echo("No active account. Use 'switch-account' to select one.")
        return
    
    # Interactive mode if no arguments
    if not scope:
        click.echo("Export options:\n")
        click.echo("1) all conversations")
        click.echo("2) this conversation")
        click.echo("3) choose conversations")
        
        scope_choice = click.prompt("\nEnter option", type=int)
        
        if scope_choice not in [1, 2, 3]:
            click.echo("Invalid option")
            return
        
        scope = ['all', 'this', 'choose'][scope_choice - 1]
    
    if not format:
        click.echo("\n1) json")
        click.echo("2) markdown")
        
        format_choice = click.prompt("\nEnter option", type=int)
        
        if format_choice not in [1, 2]:
            click.echo("Invalid option")
            return
        
        format = 'json' if format_choice == 1 else 'md'
    
    # Normalize format
    if format in ['js', 'json']:
        format = 'json'
        file_ext = 'json'
    else:
        format = 'md'
        file_ext = 'md'
    
    # Get directory for all/choose modes
    if scope in ['all', 'choose'] and not directory:
        directory = click.prompt("Directory name", default="conversations")
    
    def sanitize_filename(name):
        name = name.lower().strip()
        name = ''.join(c if c.isalnum() or c in ' -_' else '' for c in name)
        name = '-'.join(name.split())
        return name[:100] or 'untitled'
    
    def format_as_markdown(convo_data):
        lines = []
        name = convo_data.get('name', 'Untitled')
        uuid = convo_data.get('uuid', '')
        created = convo_data.get('created_at', '')
        messages = convo_data.get('chat_messages', [])

        def format_timestamp(ts):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone()
                return dt.strftime('%B %d, %Y at %I:%M %p')
            except:
                return ts
        
        lines.append(f"# {name}\n")
        lines.append(f"> **Conversation ID:** `{uuid}`  ")
        lines.append(f"> **Created:** {format_timestamp(created)}  ")
        lines.append(f"> **Messages:** {len(messages)}\n")
        lines.append("---\n")
        
        for idx, msg in enumerate(messages, 1):
            sender = msg.get('sender', 'unknown')
            timestamp = msg.get('created_at', '')
            
            lines.append(f"## {sender.title()} · Message {idx}")
            lines.append(f"<sub>{format_timestamp(timestamp)}</sub>\n")
            
            has_content = False
            
            for content in msg.get('content', []):
                ctype = content.get('type')
                
                if ctype == 'text':
                    text = content.get('text', '').strip()
                    if text:
                        lines.append(text + '\n')
                        has_content = True
                
                elif ctype == 'tool_use':
                    tool = content.get('name', '')
                    cdata = content.get('input', {})
                    
                    if tool == 'artifacts':
                        art_content = cdata.get('content', '').strip()
                        
                        if not art_content:
                            continue
                        
                        title = cdata.get('title', 'Artifact')
                        art_type = cdata.get('type', '')
                        command = cdata.get('command', '')
                        
                        if command == 'update':
                            lines.append(f"\n### Artifact Update: {title}\n")
                        else:
                            lines.append(f"\n### Artifact: {title}\n")
                        
                        lang_map = {
                            'application/vnd.ant.code': cdata.get('language', ''),
                            'text/html': 'html',
                            'application/vnd.ant.react': 'jsx',
                            'text/markdown': 'markdown',
                            'image/svg+xml': 'svg',
                            'application/vnd.ant.mermaid': 'mermaid'
                        }
                        lang = lang_map.get(art_type, '')
                        
                        if art_type:
                            lines.append(f"> **Type:** `{art_type}`\n")
                        
                        lines.append(f"```{lang}\n{art_content}\n```\n")
                        has_content = True
                    
                    elif tool == 'create_file':
                        file_text = cdata.get('file_text', '').strip()
                        
                        if not file_text:
                            continue
                        
                        path = cdata.get('path', 'unknown')
                        lang = next((l for ext, l in ext_lang.items() if path.lower().endswith(ext)), '')
                        
                        if not lang:
                            basename = path.split('/')[-1].lower()
                            if basename in ['dockerfile', 'makefile', 'rakefile']:
                                lang = basename
                        
                        lines.append(f"\n### Created File: `{path}`\n")
                        lines.append(f"```{lang}\n{file_text}\n```\n")
                        has_content = True
                    
                    elif tool == 'str_replace':
                        old = cdata.get('old_str', '')
                        new = cdata.get('new_str', '')
                        path = cdata.get('path', '')
                        
                        if old or new:
                            lines.append(f"\n### Edit: `{path}`\n")
                            lines.append(f"```diff\n- {old}\n+ {new}\n```\n")
                            has_content = True
                
                elif ctype == 'tool_result':
                    tool = content.get('name', '')
                    
                    if tool == 'bash_tool':
                        for rc in content.get('content', []):
                            if isinstance(rc, dict) and rc.get('type') == 'text':
                                result_text = rc.get('text', '').strip()
                                if result_text:
                                    lines.append(f"\n### Terminal Output\n")
                                    lines.append(f"```bash\n{result_text}\n```\n")
                                    has_content = True
                    
                    elif tool == 'view':
                        for rc in content.get('content', []):
                            if isinstance(rc, dict) and rc.get('type') == 'text':
                                result_text = rc.get('text', '').strip()
                                if result_text:
                                    lines.append(f"\n### File View\n")
                                    lines.append(f"```\n{result_text}\n```\n")
                                    has_content = True
                    
                    elif tool == 'present_files':
                        for rc in content.get('content', []):
                            if isinstance(rc, dict) and (fp := rc.get('file_path')):
                                try:
                                    with open(fp, 'r', encoding='utf-8') as f:
                                        file_data = f.read().strip()
                                        if file_data:
                                            lang = next((l for ext, l in ext_lang.items() if fp.lower().endswith(ext)), '')
                                            lines.append(f"\n### Presented File: `{fp}`\n")
                                            lines.append(f"```{lang}\n{file_data}\n```\n")
                                            has_content = True
                                except:
                                    pass
            
            if not has_content:
                lines.append("*[No content]*\n")
            
            lines.append("\n---\n")
        
        return '\n'.join(lines)

    def export_conversation(conv_uuid, conv_name, directory=None):
        try:
            response = claude.get_conversation_details(session, org_id, conv_uuid)
            
            if response.status_code != 200:
                click.echo(f"Failed to fetch conversation {conv_uuid[:8]}...")
                return False
            
            convo_data = response.json()
            filename = sanitize_filename(conv_name or convo_data.get('name', 'untitled'))
            
            if directory:
                filepath = os.path.join(directory, f"{filename}.{file_ext}")
            else:
                filepath = f"{filename}.{file_ext}"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                if format == 'json':
                    import json
                    json.dump(convo_data, f, indent=2, ensure_ascii=False)
                else:
                    f.write(format_as_markdown(convo_data))
            
            return True
        except Exception as e:
            click.echo(f"Error exporting {conv_uuid[:8]}: {e}")
            return False
    
    # Handle different scopes
    if scope == 'this':
        conversation_uuid = get_active_conversation()
        
        if not conversation_uuid:
            click.echo("No active conversation. Use 'conversations' to select one.")
            return
        
        click.echo("Exporting conversation...")
        
        if export_conversation(conversation_uuid, None):
            click.echo("Export complete!")
    
    elif scope == 'all':
        os.makedirs(directory, exist_ok=True)
        
        click.echo("Fetching conversations...")
        
        try:
            response_regular = claude.get_conversations(session, org_id, 1000, starred=False)
            response_starred = claude.get_conversations(session, org_id, 1000, starred=True)
            
            if response_regular.status_code != 200 or response_starred.status_code != 200:
                click.echo("Failed to fetch conversations")
                return
            
            all_convos = response_regular.json() + response_starred.json()
            
            if not all_convos:
                click.echo("No conversations found.")
                return
            
            click.echo(f"Exporting {len(all_convos)} conversations...\n")
            
            success_count = 0
            with click.progressbar(all_convos, 
                                label='Exporting',
                                show_eta=True,
                                show_percent=True,
                                item_show_func=lambda c: c.get('name', 'Untitled')[:40] if c else '') as bar:
                for convo in bar:
                    conv_uuid = convo.get('uuid', '')
                    conv_name = convo.get('name', 'Untitled')
                    
                    if export_conversation(conv_uuid, conv_name, directory):
                        success_count += 1
            
            click.echo(f"\nExport complete! {success_count}/{len(all_convos)} conversations exported to {directory}/")
        
        except Exception as e:
            click.echo(f"Error: {e}")
    
    elif scope == 'choose':
        click.echo("Fetching conversations...")
        
        try:
            response_regular = claude.get_conversations(session, org_id, 200, starred=False)
            response_starred = claude.get_conversations(session, org_id, 200, starred=True)
            
            if response_regular.status_code != 200 or response_starred.status_code != 200:
                click.echo("Failed to fetch conversations")
                return
            
            regular_convos = response_regular.json()
            starred_convos = response_starred.json()
            
            if not regular_convos and not starred_convos:
                click.echo("No conversations found.")
                return
            
            convo_map = {}
            
            for i, convo in enumerate(reversed(regular_convos)):
                index = len(regular_convos) + len(starred_convos) - i
                name = convo.get('name', 'Untitled')
                uuid = convo.get('uuid', '')
                click.echo(f"   {index}) {name} ({uuid[:8]}...)")
                convo_map[index] = (uuid, name)
            
            for i, convo in enumerate(reversed(starred_convos)):
                index = len(starred_convos) - i
                name = convo.get('name', 'Untitled')
                uuid = convo.get('uuid', '')
                click.echo(f"   {index}) [*] {name} ({uuid[:8]}...)")
                convo_map[index] = (uuid, name)
            
            total = len(regular_convos) + len(starred_convos)
            click.echo(f"\nTotal: {total} conversations ({len(starred_convos)} starred)")
            
            selection_input = click.prompt("\nSelect conversations (comma-separated numbers)", default="")
            
            if not selection_input:
                click.echo("No conversations selected.")
                return
            
            # Parse selection
            selected_indices = []
            for part in selection_input.split(','):
                part = part.strip()
                if part.isdigit():
                    selected_indices.append(int(part))
            
            if not selected_indices:
                click.echo("No valid selections.")
                return
            
            # Only create directory after user confirms selection
            os.makedirs(directory, exist_ok=True)
            
            click.echo(f"Exporting {len(selected_indices)} conversations...")
            
            success_count = 0
            for index in selected_indices:
                if index in convo_map:
                    conv_uuid, conv_name = convo_map[index]
                    if export_conversation(conv_uuid, conv_name, directory):
                        success_count += 1
            
            click.echo(f"Export complete! {success_count}/{len(selected_indices)} conversations exported to {directory}/")
        
        except Exception as e:
            click.echo(f"Error: {e}")