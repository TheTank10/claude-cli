import click
import json
import os
import re
import requests
from pathlib import Path
import src.claude as claude

AUTH_FILE = "auth.json"
CONFIG_FILE = "config.json"

def create_session_from_cookies(cookie_string):
    """Create a requests session with cookies"""
    session = requests.Session()
    for cookie in cookie_string.split('; '):
        if '=' in cookie:
            name, value = cookie.split('=', 1)
            session.cookies.set(name.strip(), value.strip())
    return session

def get_cookie_string_from_session(session):
    """Extract cookie string from session"""
    return "; ".join([f"{c.name}={c.value}" for c in session.cookies])

def extract_org_id(cookies):
    """Extract organization ID from cookies"""
    match = re.search(r'lastActiveOrg=([a-f0-9\-]+)', cookies)
    return match.group(1) if match else None

def load_accounts():
    """Load accounts from auth.json"""
    if not os.path.exists(AUTH_FILE):
        return {}
    with open(AUTH_FILE, "r") as f:
        return json.load(f)

def save_accounts(accounts):
    """Save accounts to auth.json"""
    with open(AUTH_FILE, "w") as f:
        json.dump(accounts, f, indent=2)

def verify_and_save_account(account_name, cookies, is_update=False):
    """Verify cookies and save/update account"""
    org_id = extract_org_id(cookies)
    if not org_id:
        click.echo("Could not find lastActiveOrg in cookies")
        return
    
    session = create_session_from_cookies(cookies)
    
    click.echo("Verifying cookies...")
    try:
        response = claude.get_conversation_count(session, org_id)
        
        if response.status_code == 200:
            click.echo("Cookies verified successfully!")
            updated_cookies = get_cookie_string_from_session(session)
            
            accounts = load_accounts()
            accounts[account_name] = updated_cookies
            save_accounts(accounts)
            
            # Set as active account when adding new account
            if not is_update:
                set_active_account(account_name)
                click.echo(f"Account '{account_name}' added and set as active!")
            else:
                click.echo(f"Account '{account_name}' updated successfully!")
        else:
            click.echo(f"Cookie verification failed (status code: {response.status_code})")
    except Exception as e:
        click.echo(f"Error verifying cookies: {e}")

def list_accounts_interactive(accounts):
    """Display accounts and prompt for selection"""
    click.echo("Available accounts:")
    account_list = list(accounts.keys())
    
    for i, name in enumerate(account_list, 1):
        cookie_str = accounts[name]
        preview = cookie_str[:20] + "..." if len(cookie_str) > 20 else cookie_str
        click.echo(f"{i}. {name}: \"{preview}\"")
    
    selection = click.prompt("\nAccount")
    
    if selection.isdigit():
        index = int(selection) - 1
        if 0 <= index < len(account_list):
            return account_list[index]
        else:
            click.echo("Invalid account number")
            return None
    
    return selection

def load_config():
    """Load config from config.json"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    """Save config to config.json"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_active_account():
    """Get the currently active account name"""
    config = load_config()
    return config.get("active_account")

def set_active_account(account_name):
    """Set the active account"""
    config = load_config()
    config["active_account"] = account_name
    save_config(config)

def get_active_session():
    """Get session for the active account"""
    active = get_active_account()
    if not active:
        return None, None
    
    accounts = load_accounts()
    if active not in accounts:
        return None, None
    
    cookies = accounts[active]
    session = create_session_from_cookies(cookies)
    org_id = extract_org_id(cookies)
    
    return session, org_id

def get_active_conversation():
    """Get the currently active conversation UUID"""
    config = load_config()
    return config.get("active_conversation")

def set_active_conversation(conversation_uuid, parent_message_uuid=None, settings=None):
    """Set the active conversation, parent message UUID, and optionally cache settings"""
    config = load_config()
    config['active_conversation'] = conversation_uuid
    
    if parent_message_uuid is not None:
        config['parent_message_uuid'] = parent_message_uuid
    
    # Cache settings if provided
    if settings is not None:
        config['conversation_settings'] = settings
    
    save_config(config)

def get_parent_message_uuid():
    """Get the stored parent message UUID for the active conversation"""
    config = load_config()
    return config.get('parent_message_uuid', "00000000-0000-4000-8000-000000000000")

def get_conversation_settings():
    """Get cached conversation settings"""
    config = load_config()
    return config.get('conversation_settings')