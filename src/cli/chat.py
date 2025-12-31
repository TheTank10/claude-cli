import click
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
import json as json_lib
import re
import sys
from src.helpers import (
    get_active_session,
    get_active_conversation,
    set_active_conversation,
    get_parent_message_uuid,
    get_conversation_settings,
)
import src.claude as claude

console = Console()

SEPARATOR = "-" * 80
DEFAULT_PARENT_UUID = "00000000-0000-4000-8000-000000000000"
DEFAULT_SETTINGS = {
    "enabled_web_search": True,
    "preview_feature_uses_artifacts": True,
    "enabled_turmeric": True
}


def get_auth_context():
    session, org_id = get_active_session()
    conversation_uuid = get_active_conversation()
    
    if not session or not org_id:
        console.print("No active account. Use 'switch-account' to select one.", style="red")
        return None
    
    if not conversation_uuid:
        console.print("No active conversation. Use 'conversations' or 'new' to select/create one.", style="red")
        return None
    
    return session, org_id, conversation_uuid


def build_tools(settings):
    tools = []
    if settings.get('enabled_web_search'):
        tools.append({"type": "web_search_v0", "name": "web_search"})
    if settings.get('preview_feature_uses_artifacts'):
        tools.append({"type": "artifacts_v0", "name": "artifacts"})
    if settings.get('enabled_turmeric'):
        tools.append({"type": "repl_v0", "name": "repl"})
    return tools


def unescape_json_string(s):
    s = s.replace('\\n', '\n')
    s = s.replace('\\t', '\t')
    s = s.replace('\\r', '\r')
    s = s.replace('\\"', '"')
    s = s.replace('\\\\', '\\')
    return s


def extract_file_content(partial_json):
    match = re.search(r'"file_text"\s*:\s*"(.*)', partial_json, re.DOTALL)
    if match:
        content = match.group(1)
        if content.endswith('"}') or content.endswith('"'):
            content = content.rstrip('"}')
        return unescape_json_string(content)
    return None


def extract_file_path(partial_json):
    match = re.search(r'"path"\s*:\s*"([^"]*)"', partial_json)
    return match.group(1) if match else None


def parse_artifact(artifact_json):
    try:
        data = json_lib.loads(artifact_json)
        title = data.get('title', 'Untitled')
        content = data.get('content', '')
        lang = data.get('language', '')
        
        result = f"\n\n### {title}\n\n"
        if content:
            result += f"```{lang}\n{content}\n```\n\n"
        return result
    except json_lib.JSONDecodeError:
        return "\nCould not parse artifact JSON\n"


def format_tool_use(tool_name, tool_input):
    try:
        data = json_lib.loads(tool_input) if isinstance(tool_input, str) else tool_input
        
        if tool_name == "create_file":
            path = data.get('path', 'unknown')
            description = data.get('description', '')
            file_text = data.get('file_text', '')
            
            result = f"\n\n### Created File: `{path}`\n"
            if description:
                result += f"\n{description}\n"
            
            if file_text:
                ext = path.split('.')[-1] if '.' in path else ''
                result += f"\n```{ext}\n{file_text}\n```\n"
            
            return result + "\n"
        
        elif tool_name == "artifacts":
            title = data.get('title', 'Untitled')
            content = data.get('content', '')
            lang = data.get('language', '')
            
            result = f"\n\n### {title}\n\n"
            if content:
                result += f"```{lang}\n{content}\n```\n\n"
            return result
        
        elif tool_name == "present_files":
            filepaths = data.get('filepaths', [])
            if filepaths:
                result = "\n\n### Files:\n"
                for fp in filepaths:
                    result += f"- `{fp}`\n"
                return result + "\n"
        
        return ""
    
    except (json_lib.JSONDecodeError, Exception):
        return ""


@click.command()
@click.argument('text', nargs=-1, required=True)
@click.option('--output', '-o', type=click.Path(), help='Save output to file')
@click.option('--raw', is_flag=True, help='Output raw markdown without formatting')
def chat(text, output, raw):
    """Send a message to the active conversation."""
    auth = get_auth_context()
    if not auth:
        return
    
    session, org_id, conversation_uuid = auth
    parent_message_uuid = get_parent_message_uuid()
    prompt = " ".join(text)
    use_raw = raw or output or not sys.stdout.isatty()
    
    settings = get_conversation_settings()
    if settings is None:
        response = claude.get_conversation_details(session, org_id, conversation_uuid)
        settings = response.json().get('settings', DEFAULT_SETTINGS) if response.status_code == 200 else DEFAULT_SETTINGS
        set_active_conversation(conversation_uuid, parent_message_uuid, settings)
    
    tools = build_tools(settings)
    
    try:
        response = claude.send_completion(session, org_id, conversation_uuid, prompt, parent_message_uuid, tools=tools)
        
        if response.status_code != 200:
            console.print(f"Failed to send message (status code: {response.status_code})", style="red")
            return
        
        markdown_buffer = ""
        new_message_uuid = None
        
        tool_use_buffer = {}
        current_tool_id = None
        
        live = None if use_raw else Live("", console=console, refresh_per_second=4)
        
        if live:
            live.start()
        
        try:
            for line in response.iter_lines():
                if not line:
                    continue
                
                line = line.decode('utf-8')
                if not line.startswith('data: '):
                    continue
                
                try:
                    event = json_lib.loads(line[6:])
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
                                'input_json': '',
                                'complete': False,
                                'last_streamed_content': '',
                                'header_shown': False
                            }
                    
                    elif event_type == 'content_block_delta':
                        delta = event.get('delta', {})
                        delta_type = delta.get('type')
                        
                        if delta_type == 'text_delta':
                            text_chunk = delta['text']
                            markdown_buffer += text_chunk
                            
                            if use_raw:
                                click.echo(text_chunk, nl=False)
                            else:
                                live.update(Markdown(markdown_buffer))
                        
                        elif delta_type == 'input_json_delta' and current_tool_id:
                            json_chunk = delta['partial_json']
                            tool_data = tool_use_buffer[current_tool_id]
                            tool_data['input_json'] += json_chunk
                            
                            if tool_data['name'] == 'create_file':
                                file_path = extract_file_path(tool_data['input_json'])
                                file_content = extract_file_content(tool_data['input_json'])
                                
                                if file_content is not None:
                                    if use_raw:
                                        if not tool_data['header_shown']:
                                            file_path_display = file_path or "..."
                                            ext = file_path.split('.')[-1] if file_path and '.' in file_path else ''
                                            header = f"\n\n### Created File: `{file_path_display}`\n\n```{ext}\n"
                                            click.echo(header, nl=False)
                                            tool_data['header_shown'] = True
                                        
                                        new_content = file_content[len(tool_data['last_streamed_content']):]
                                        if new_content:
                                            click.echo(new_content, nl=False)
                                        tool_data['last_streamed_content'] = file_content
                                    else:
                                        ext = file_path.split('.')[-1] if file_path and '.' in file_path else ''
                                        file_path_display = file_path or "..."
                                        stream_content = f"\n\n### Creating: `{file_path_display}`\n\n```{ext}\n{file_content}\n```\n"
                                        temp_buffer = markdown_buffer + stream_content
                                        live.update(Markdown(temp_buffer))
                            
                            elif tool_data['name'] == 'artifacts':
                                try:
                                    artifact_data = json_lib.loads(tool_data['input_json'])
                                    content = artifact_data.get('content', '')
                                    
                                    if content:
                                        if use_raw:
                                            if not tool_data['header_shown']:
                                                title = artifact_data.get('title', 'Artifact')
                                                lang = artifact_data.get('language', '')
                                                header = f"\n\n### {title}\n\n```{lang}\n"
                                                click.echo(header, nl=False)
                                                tool_data['header_shown'] = True
                                            
                                            new_content = content[len(tool_data['last_streamed_content']):]
                                            if new_content:
                                                click.echo(new_content, nl=False)
                                            tool_data['last_streamed_content'] = content
                                        else:
                                            title = artifact_data.get('title', 'Artifact')
                                            lang = artifact_data.get('language', '')
                                            stream_content = f"\n\n### {title}\n\n```{lang}\n{content}\n```\n"
                                            temp_buffer = markdown_buffer + stream_content
                                            live.update(Markdown(temp_buffer))
                                except json_lib.JSONDecodeError:
                                    pass
                    
                    elif event_type == 'content_block_stop':
                        if current_tool_id and current_tool_id in tool_use_buffer:
                            tool_data = tool_use_buffer[current_tool_id]
                            tool_data['complete'] = True
                            
                            if tool_data['name'] in ('create_file', 'artifacts'):
                                if use_raw and tool_data['header_shown']:
                                    click.echo("\n```\n", nl=False)
                            
                            tool_output = format_tool_use(tool_data['name'], tool_data['input_json'])
                            if tool_output:
                                markdown_buffer += tool_output
                                
                                if use_raw:
                                    if not tool_data.get('header_shown'):
                                        click.echo(tool_output, nl=False)
                                else:
                                    live.update(Markdown(markdown_buffer))
                            
                            current_tool_id = None
                
                except json_lib.JSONDecodeError:
                    pass
        
        finally:
            if live:
                live.stop()
        
        if use_raw:
            click.echo()
        
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                f.write(markdown_buffer)
            click.echo(f"Output saved to {output}", err=True)
        
        if new_message_uuid:
            set_active_conversation(conversation_uuid, new_message_uuid)
    
    except Exception as e:
        console.print(f"Error: {e}", style="red")


@click.command()
def sync():
    """Sync the active conversation with claude."""
    session, org_id = get_active_session()
    conversation_uuid = get_active_conversation()
    
    if not session or not org_id:
        click.echo("No active account. Use 'switch-account' to select one.")
        return
    
    if not conversation_uuid:
        click.echo("No active conversation. Use 'conversations' to select one.")
        return
    
    click.echo("Syncing conversation...")
    
    try:
        response = claude.get_conversation_details(session, org_id, conversation_uuid)
        
        if response.status_code == 200:
            data = response.json()
            messages = data.get('chat_messages', [])
            settings = data.get('settings', {})
            
            if messages:
                last_uuid = messages[-1]['uuid']
                current_uuid = get_parent_message_uuid()
                set_active_conversation(conversation_uuid, last_uuid, settings)
                
                if current_uuid != last_uuid:
                    click.echo(f"Synced! Updated parent UUID:")
                    click.echo(f"  Old: {current_uuid[:16]}...")
                    click.echo(f"  New: {last_uuid[:16]}...")
                    click.echo(f"  Total messages: {len(messages)}")
                else:
                    click.echo("Already synced! No new messages.")
            else:
                set_active_conversation(conversation_uuid, DEFAULT_PARENT_UUID, settings)
                click.echo("Synced! (Conversation is empty)")
        
        elif response.status_code in (401, 403):
            click.echo("Authentication failed. Your cookies may have expired.")
            click.echo("Run 'update-account' to refresh your cookies.")
        else:
            click.echo(f"Failed to sync (status code: {response.status_code})")
    
    except Exception as e:
        click.echo(f"Error syncing: {e}")


@click.command()
@click.argument('limit', default=30, type=int)
@click.option('--output', '-o', type=click.Path(), help='Save output to file')
@click.option('--raw', is_flag=True, help='Output raw markdown without formatting')
def history(limit, output, raw):
    """View chat history of the active conversation."""
    auth = get_auth_context()
    if not auth:
        return
    
    session, org_id, conversation_uuid = auth
    use_raw = raw or output or not sys.stdout.isatty()
    markdown_buffer = ""
    
    try:
        response = claude.get_conversation_details(session, org_id, conversation_uuid)
        
        if response.status_code == 200:
            messages = response.json().get('chat_messages', [])
            
            if not messages:
                msg = "No messages in this conversation yet."
                console.print(msg, style="yellow") if not use_raw else click.echo(msg)
                return
            
            messages_to_show = messages[-limit:] if len(messages) > limit else messages
            
            if len(messages) > limit:
                omitted = len(messages) - limit
                info = f"\n[Showing last {limit} of {len(messages)} messages - {omitted} older messages hidden]\n"
                
                if use_raw:
                    markdown_buffer += info + "\n"
                    click.echo(info)
                else:
                    console.print(info, style="dim italic")
            
            for msg in messages_to_show:
                sender = msg.get('sender')
                label = "You" if sender == "human" else "Claude"
                
                text_parts = []
                for content in msg.get('content', []):
                    if content.get('type') == 'text':
                        text_parts.append(content.get('text', ''))
                    elif content.get('type') == 'tool_use':
                        tool_name = content.get('name', '')
                        tool_input = content.get('input', {})
                        tool_output = format_tool_use(tool_name, tool_input)
                        if tool_output:
                            text_parts.append(tool_output)
                
                if not text_parts:
                    continue
                
                text = ''.join(text_parts)
                
                if use_raw:
                    header = f"\n{label}:\n"
                    markdown_buffer += header + text + "\n" + SEPARATOR + "\n"
                    click.echo(header, nl=False)
                    click.echo(text)
                    click.echo(SEPARATOR)
                else:
                    style = "bold cyan" if sender == "human" else "bold green"
                    console.print(f"\n{label}:", style=style)
                    console.print(Markdown(text))
                    console.print(SEPARATOR, style="dim")
            
            if output:
                with open(output, 'w', encoding='utf-8') as f:
                    f.write(markdown_buffer)
                click.echo(f"\nOutput saved to {output}", err=True)
        
        elif response.status_code in (401, 403):
            console.print("Authentication failed. Your cookies may have expired.", style="red")
            console.print("Run 'update-account' to refresh your cookies.", style="red")
        else:
            console.print(f"Failed to fetch history (status code: {response.status_code})", style="red")
    
    except Exception as e:
        console.print(f"Error: {e}", style="red")