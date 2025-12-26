import click
from src.helpers import (
    get_active_session,
    get_active_conversation,
    set_active_conversation,
    get_parent_message_uuid,
)
import src.claude as claude


@click.command()
@click.option('--web-search', type=click.Choice(['on', 'off']), help='Toggle web search')
@click.option('--thinking', type=click.Choice(['on', 'off']), help='Toggle extended thinking')
@click.option('--artifacts', type=click.Choice(['on', 'off']), help='Toggle artifacts')
def settings(web_search, thinking, artifacts):
    """View or change conversation settings"""
    session, org_id = get_active_session()
    conversation_uuid = get_active_conversation()
    
    if not session or not org_id:
        click.echo("No active account. Use 'switch-account' to select one.")
        return
    
    if not conversation_uuid:
        click.echo("No active conversation. Use 'conversations' or 'new' to select/create one.")
        return
    
    try:
        response = claude.get_conversation_details(session, org_id, conversation_uuid)
        
        if response.status_code == 404:
            click.echo("Conversation not found. Use 'conversations' to select a valid conversation.")
            return
        elif response.status_code == 401 or response.status_code == 403:
            click.echo("Authentication failed. Your cookies may have expired.")
            return
        elif response.status_code != 200:
            click.echo(f"Failed to fetch settings (status: {response.status_code})")
            return
        
        convo_data = response.json()
        current_settings = convo_data.get('settings', {})
        
        ws_enabled = current_settings.get('enabled_web_search', False)
        thinking_enabled = current_settings.get('paprika_mode') == "extended"
        artifacts_enabled = current_settings.get('preview_feature_uses_artifacts', False)
        
        if any([web_search, thinking, artifacts]):
            updates = {}
            
            if web_search:
                updates['enabled_web_search'] = (web_search == 'on')
                click.echo(f"{'Enabling' if web_search == 'on' else 'Disabling'} web search...")
            
            if thinking:
                updates['paprika_mode'] = "extended" if thinking == 'on' else None
                click.echo(f"{'Enabling' if thinking == 'on' else 'Disabling'} extended thinking...")
            
            if artifacts:
                updates['preview_feature_uses_artifacts'] = (artifacts == 'on')
                click.echo(f"{'Enabling' if artifacts == 'on' else 'Disabling'} artifacts...")
            
            update_response = claude.update_conversation_settings(session, org_id, conversation_uuid, updates)
            
            if update_response.status_code == 200 or update_response.status_code == 202:
                click.echo("Settings updated successfully!")
                
                refresh_response = claude.get_conversation_details(session, org_id, conversation_uuid)
                if refresh_response.status_code == 200:
                    new_settings = refresh_response.json().get('settings', {})
                    parent = get_parent_message_uuid()
                    set_active_conversation(conversation_uuid, parent, new_settings)
            else:
                click.echo(f"Failed to update settings (status: {update_response.status_code})")
            return
        
        settings_info = [
            {
                'key': 'web_search',
                'name': 'Web Search',
                'description': 'Allow Claude to search the web for current information',
                'current': ws_enabled,
            },
            {
                'key': 'thinking',
                'name': 'Extended Thinking',
                'description': 'Enable Claude to think longer for complex problems',
                'current': thinking_enabled,
            },
            {
                'key': 'artifacts',
                'name': 'Artifacts',
                'description': 'Create files, documents, and code in a separate panel',
                'current': artifacts_enabled,
            }
        ]
        
        for i, setting in enumerate(settings_info, 1):
            status = "ON " if setting['current'] else "OFF"
            click.echo(f"{i}) {setting['name']} [{status}] - {setting['description']}")
        
        click.echo()
        
        while True:
            user_input = click.prompt(
                "Change setting (index on/off)",
                default="",
                show_default=False
            ).strip()
            
            if not user_input:
                click.echo("Saved.")
                return
            
            parts = user_input.split()
            if len(parts) != 2:
                click.echo("Invalid format. Use: <index> <on/off>")
                continue
            
            index_str, action = parts
            
            if not index_str.isdigit():
                click.echo("Invalid index. Use 1, 2, or 3.")
                continue
            
            index = int(index_str)
            if index < 1 or index > 3:
                click.echo("Invalid index. Use 1, 2, or 3.")
                continue
            
            action = action.lower()
            if action not in ['on', 'off']:
                click.echo("Invalid action. Use 'on' or 'off'.")
                continue
            
            selected = settings_info[index - 1]
            new_state = (action == 'on')
            
            if selected['current'] == new_state:
                status = "enabled" if new_state else "disabled"
                click.echo(f"{selected['name']} is already {status}.")
                continue
            
            updates = {}
            
            if selected['key'] == 'web_search':
                updates['enabled_web_search'] = new_state
            elif selected['key'] == 'thinking':
                updates['paprika_mode'] = "extended" if new_state else None
            elif selected['key'] == 'artifacts':
                updates['preview_feature_uses_artifacts'] = new_state
            
            update_response = claude.update_conversation_settings(
                session, org_id, conversation_uuid, updates
            )
            
            if update_response.status_code == 200 or update_response.status_code == 202:
                status = "enabled" if new_state else "disabled"
                click.echo(f"{selected['name']} {status}.")
                
                selected['current'] = new_state
                
                refresh_response = claude.get_conversation_details(session, org_id, conversation_uuid)
                if refresh_response.status_code == 200:
                    new_settings = refresh_response.json().get('settings', {})
                    parent = get_parent_message_uuid()
                    set_active_conversation(conversation_uuid, parent, new_settings)
            else:
                click.echo(f"Failed to update (status: {update_response.status_code})")
            
    except Exception as e:
        click.echo(f"Error: {e}")