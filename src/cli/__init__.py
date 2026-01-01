import click
import sys
import os

if sys.platform == 'win32':
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')
    os.system('chcp 65001 >nul 2>&1')

@click.group()
def cli():
    pass

@cli.command()
def test():
    click.echo("Everything is working!")

def register_commands():
    from .accounts import accounts, add_account, update_account, switch_account, remove_account
    from .conversations import conversations, new, name, delete, link, search, export
    from .chat import chat, sync, history, repl
    from .settings import settings
    
    # Account commands
    cli.add_command(accounts)
    cli.add_command(add_account)
    cli.add_command(update_account)
    cli.add_command(switch_account)
    cli.add_command(remove_account)

    # Conversation commands
    cli.add_command(conversations)
    cli.add_command(new)
    cli.add_command(name)
    cli.add_command(delete)
    cli.add_command(link)
    cli.add_command(search)
    cli.add_command(export)

    # Chat commands
    cli.add_command(chat)
    cli.add_command(sync)
    cli.add_command(history)
    cli.add_command(repl)

    # Settings commands
    cli.add_command(settings)

register_commands()