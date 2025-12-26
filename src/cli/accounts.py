import click
from src.helpers import (
    load_accounts,
    save_accounts,
    verify_and_save_account,
    list_accounts_interactive,
    get_active_account,
    set_active_account,
    create_session_from_cookies,
    extract_org_id,
)
import src.claude as claude


@click.command()
def accounts():
    """List all Claude accounts"""
    accounts = load_accounts()
    
    if not accounts:
        click.echo("No accounts found. Use 'add-account' first.")
        return
    
    active = get_active_account()
    click.echo("Available accounts:\n")
    
    for i, name in enumerate(accounts.keys(), 1):
        indicator = "-> " if name == active else "   "
        click.echo(f"{indicator}{i}. {name}")
    
    if active:
        click.echo(f"\nActive account: {active}")
    else:
        click.echo("\nNo active account selected. Use 'switch-account' to select one.")


@click.command()
def add_account():
    """Add a new Claude account"""
    account_name = click.prompt("Account name")
    cookies = click.prompt("Paste your Claude cookies", hide_input=True).strip()
    
    verify_and_save_account(account_name, cookies, is_update=False)


@click.command()
@click.argument('account_name', required=False)
@click.argument('cookies', required=False)
def update_account(account_name, cookies):
    """Update an existing account's cookies"""
    accounts = load_accounts()
    
    if not accounts:
        click.echo("No accounts found. Use 'add-account' first.")
        return
    
    if not account_name:
        account_name = list_accounts_interactive(accounts)
        if not account_name:
            return
    
    if account_name not in accounts:
        click.echo(f"Account '{account_name}' not found.")
        return
    
    if not cookies:
        cookies = click.prompt("New cookies", hide_input=True).strip()
    
    verify_and_save_account(account_name, cookies, is_update=True)


@click.command()
@click.argument('account_name', required=False)
def switch_account(account_name):
    """Switch to a different Claude account"""
    accounts_list = load_accounts()
    
    if not accounts_list:
        click.echo("No accounts found. Use 'add-account' first.")
        return
    
    if not account_name:
        account_name = list_accounts_interactive(accounts_list)
        if not account_name:
            return
    
    if account_name not in accounts_list:
        click.echo(f"Account '{account_name}' not found.")
        return
    
    click.echo(f"Validating account '{account_name}'...")
    cookies = accounts_list[account_name]
    org_id = extract_org_id(cookies)
    
    if not org_id:
        click.echo("Could not find lastActiveOrg in cookies. Account may be corrupted.")
        return
    
    session = create_session_from_cookies(cookies)
    
    try:
        response = claude.get_conversation_count(session, org_id)
        
        if response.status_code == 200:
            click.echo("Account validated successfully!")
            set_active_account(account_name)
            click.echo(f"Switched to account '{account_name}'")
        elif response.status_code == 401 or response.status_code == 403:
            click.echo(f"Account cookies expired. Please run 'update-account {account_name}' to refresh.")
        else:
            click.echo(f"Validation failed (status code: {response.status_code})")
    except Exception as e:
        click.echo(f"Error validating account: {e}")


@click.command()
@click.argument('account_name', required=False)
def remove_account(account_name):
    """Remove a Claude account"""
    accounts = load_accounts()
    
    if not accounts:
        click.echo("No accounts found.")
        return
    
    if not account_name:
        account_name = list_accounts_interactive(accounts)
        if not account_name:
            return
    
    if account_name not in accounts:
        click.echo(f"Account '{account_name}' not found.")
        return
    
    if click.confirm(f"Are you sure you want to remove '{account_name}'?"):
        del accounts[account_name]
        save_accounts(accounts)
        click.echo(f"Account '{account_name}' removed successfully!")
    else:
        click.echo("Cancelled.")