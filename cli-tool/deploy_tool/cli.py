import click
import sys
from pathlib import Path
from colorama import init, Fore, Style

# Initialize colorama
init()

try:
    from .core.utils import print_header, print_info, print_error
except ImportError:
    # Fallback for basic functionality during development
    def print_header(title: str):
        click.echo(f"\n{title}")
        click.echo("=" * len(title))
    
    def print_info(message: str):
        click.echo(f"[INFO] {message}")
    
    def print_error(message: str):
        click.echo(f"[ERROR] {message}")

from .commands.init import init
from .commands.deploy import deploy
from .commands.rollback import rollback
from .commands.status import status
from .commands.versions import versions
from .commands.monitoring import monitoring  
from .commands.config import config

@click.group()
@click.version_option(version="1.0.0")
@click.option('--profile', default='Uzaif', help='AWS SSO profile name')
@click.option('--region', default='ap-south-1', help='AWS region')
@click.pass_context
def cli(ctx, profile, region):
    """
    Deploy Tool - Vercel-like deployment for AWS S3
    DevOps Capstone Project: One-button deployment from GitHub to S3
    
    Simple commands for effortless deployment:
    
    • init    - Set up a new project for deployment
    • deploy  - Deploy your application to AWS S3  
    • status  - Check deployment status and information
    • rollback - Instantly rollback to a previous version
    • versions - List available versions
    • monitoring - Manage monitoring infrastructure
    
    All caching, optimization, and cleanup happens automatically.
    """
    ctx.ensure_object(dict)
    ctx.obj['aws_profile'] = profile
    ctx.obj['aws_region'] = region
    
    # Display banner
    print_header("DEPLOY TOOL")
    print_info("Vercel-like AWS S3 Deployment CLI")
    print_info("DevOps Capstone Project")
    click.echo()

# Register commands
cli.add_command(init)
cli.add_command(deploy)
cli.add_command(rollback)
cli.add_command(status)
cli.add_command(versions)
cli.add_command(monitoring)
cli.add_command(config)



if __name__ == '__main__':
    cli()



