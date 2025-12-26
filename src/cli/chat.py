import click
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
import json as json_lib
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


@click.command()
@click.argument('text', nargs=-1, required=True)
@click.option('--output', '-o', type=click.Path(), help='Save output to file')
@click.option('--raw', is_flag=True, help='Output raw markdown without formatting')
def chat(text, output, raw):
    """Send a message to Claude in the active conversation"""
    session, org_id = get_active_session()
    conversation_uuid = get_active_conversation()
    parent_message_uuid = get_parent_message_uuid()
    
    if not session or not org_id:
        console.print("No active account. Use 'switch-account' to select one.", style="red")
        return
    
    if not conversation_uuid:
        console.print("No active conversation. Use 'conversations' or 'new' to select/create one.", style="red")
        return
    
    prompt = " ".join(text)
    markdown_buffer = ""
    
    is_redirected = not sys.stdout.isatty()
    
    use_raw_mode = raw or output or is_redirected
    
    try:
        convo_settings = get_conversation_settings()
        
        if convo_settings is None:
            settings_response = claude.get_conversation_details(session, org_id, conversation_uuid)
            if settings_response.status_code == 200:
                convo_settings = settings_response.json().get('settings', {})
                set_active_conversation(conversation_uuid, parent_message_uuid, convo_settings)
            else:
                convo_settings = {
                    "enabled_web_search": True,
                    "preview_feature_uses_artifacts": True,
                    "enabled_turmeric": True
                }
        
        tools = []
        
        if convo_settings.get('enabled_web_search'):
            tools.append({"type": "web_search_v0", "name": "web_search"})
        if convo_settings.get('preview_feature_uses_artifacts'):
            tools.append({"type": "artifacts_v0", "name": "artifacts"})
        if convo_settings.get('enabled_turmeric'):
            tools.append({"type": "repl_v0", "name": "repl"})
        
        response = claude.send_completion(session, org_id, conversation_uuid, prompt, parent_message_uuid, tools=tools)
        
        if response.status_code == 200:
            new_message_uuid = None
            artifact_json = ""
            in_artifact = False
            current_index = None
            
            if not use_raw_mode:
                with Live("", console=console, refresh_per_second=4) as live:
                    for line in response.iter_lines():
                        if line:
                            line = line.decode('utf-8')
                            
                            if line.startswith('data: '):
                                data = line[6:]
                                
                                try:
                                    event_data = json_lib.loads(data)
                                    event_type = event_data.get('type')
                                    
                                    if event_type == 'message_start':
                                        new_message_uuid = event_data.get('message', {}).get('uuid')
                                    
                                    elif event_type == 'content_block_start':
                                        content_block = event_data.get('content_block', {})
                                        current_index = event_data.get('index')
                                        if content_block.get('type') == 'tool_use' and content_block.get('name') == 'artifacts':
                                            in_artifact = True
                                            artifact_json = ""
                                    
                                    elif event_type == 'content_block_delta':
                                        delta = event_data.get('delta', {})
                                        delta_type = delta.get('type')
                                        
                                        if delta_type == 'text_delta':
                                            text_chunk = delta['text']
                                            markdown_buffer += text_chunk
                                            live.update(Markdown(markdown_buffer))
                                        
                                        elif delta_type == 'input_json_delta' and in_artifact:
                                            json_chunk = delta['partial_json']
                                            artifact_json += json_chunk
                                    
                                    elif event_type == 'content_block_stop':
                                        index = event_data.get('index')
                                        if in_artifact and index == current_index:
                                            try:
                                                artifact_data = json_lib.loads(artifact_json)
                                                
                                                artifact_title = artifact_data.get('title', 'Untitled')
                                                content = artifact_data.get('content', '')
                                                
                                                markdown_buffer += f"\n\n### {artifact_title}\n\n"
                                                if content:
                                                    lang = artifact_data.get('language', '')
                                                    markdown_buffer += f"```{lang}\n{content}\n```\n\n"
                                                live.update(Markdown(markdown_buffer))
                                            
                                            except json_lib.JSONDecodeError:
                                                markdown_buffer += "\nCould not parse artifact JSON\n"
                                                live.update(Markdown(markdown_buffer))
                                            
                                            in_artifact = False
                                            artifact_json = ""
                                            current_index = None
                                
                                except json_lib.JSONDecodeError:
                                    pass
            
            else:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        
                        if line.startswith('data: '):
                            data = line[6:]
                            
                            try:
                                event_data = json_lib.loads(data)
                                event_type = event_data.get('type')
                                
                                if event_type == 'message_start':
                                    new_message_uuid = event_data.get('message', {}).get('uuid')
                                
                                elif event_type == 'content_block_start':
                                    content_block = event_data.get('content_block', {})
                                    current_index = event_data.get('index')
                                    if content_block.get('type') == 'tool_use' and content_block.get('name') == 'artifacts':
                                        in_artifact = True
                                        artifact_json = ""
                                
                                elif event_type == 'content_block_delta':
                                    delta = event_data.get('delta', {})
                                    delta_type = delta.get('type')
                                    
                                    if delta_type == 'text_delta':
                                        text_chunk = delta['text']
                                        markdown_buffer += text_chunk
                                        click.echo(text_chunk, nl=False)
                                    
                                    elif delta_type == 'input_json_delta' and in_artifact:
                                        json_chunk = delta['partial_json']
                                        artifact_json += json_chunk
                                
                                elif event_type == 'content_block_stop':
                                    index = event_data.get('index')
                                    if in_artifact and index == current_index:
                                        try:
                                            artifact_data = json_lib.loads(artifact_json)
                                            
                                            artifact_title = artifact_data.get('title', 'Untitled')
                                            content = artifact_data.get('content', '')
                                            
                                            artifact_text = f"\n\n### {artifact_title}\n\n"
                                            markdown_buffer += artifact_text
                                            click.echo(artifact_text, nl=False)
                                            
                                            if content:
                                                lang = artifact_data.get('language', '')
                                                code_block = f"```{lang}\n{content}\n```\n\n"
                                                markdown_buffer += code_block
                                                click.echo(code_block, nl=False)
                                        
                                        except json_lib.JSONDecodeError:
                                            error_text = "\nCould not parse artifact JSON\n"
                                            markdown_buffer += error_text
                                            click.echo(error_text, nl=False)
                                        
                                        in_artifact = False
                                        artifact_json = ""
                                        current_index = None
                            
                            except json_lib.JSONDecodeError:
                                pass
                
                click.echo()
                
                if output:
                    with open(output, 'w', encoding='utf-8') as f:
                        f.write(markdown_buffer)
                    click.echo(f"Output saved to {output}", err=True)
            
            if new_message_uuid:
                set_active_conversation(conversation_uuid, new_message_uuid)
                
        else:
            console.print(f"Failed to send message (status code: {response.status_code})", style="red")
    except Exception as e:
        console.print(f"Error: {e}", style="red")


@click.command()
def sync():
    """Sync active conversation with latest messages"""
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
            convo_data = response.json()
            messages = convo_data.get('chat_messages', [])
            
            if messages:
                last_message_uuid = messages[-1]['uuid']
                current_parent = get_parent_message_uuid()
                settings = convo_data.get('settings', {})

                set_active_conversation(conversation_uuid, last_message_uuid, settings)
                
                if current_parent != last_message_uuid:
                    click.echo(f"Synced! Updated parent UUID:")
                    click.echo(f"  Old: {current_parent[:16]}...")
                    click.echo(f"  New: {last_message_uuid[:16]}...")
                    click.echo(f"  Total messages in conversation: {len(messages)}")
                else:
                    click.echo("Already synced! No new messages on web.")
            else:
                settings = convo_data.get('settings', {})
                set_active_conversation(conversation_uuid, "00000000-0000-4000-8000-000000000000", settings)
                click.echo("Synced! (Conversation is empty)")
                
        elif response.status_code == 401 or response.status_code == 403:
            click.echo("Authentication failed. Your cookies may have expired.")
            click.echo("Run 'update-account' to refresh your cookies.")
        else:
            click.echo(f"Failed to sync (status code: {response.status_code})")
            
    except Exception as e:
        click.echo(f"Error syncing: {e}")