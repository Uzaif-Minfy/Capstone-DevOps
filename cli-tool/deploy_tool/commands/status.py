import click
import sys
from colorama import Fore, Style

from ..core.utils import print_error, print_info, print_header
from ..core.config_manager import ConfigManager
from ..core.aws_manager import AWSManager

@click.command()
@click.pass_context
def status(ctx):
    """
    Show project deployment status and information
    """
    try:
        # Load configuration
        config_manager = ConfigManager()
        if not config_manager.config_exists():
            print_error("No project configuration found")
            print_info("Please run 'deploy-tool init' first")
            sys.exit(1)
        
        config = config_manager.load_config()
        
        # Initialize AWS manager
        aws_manager = AWSManager(
            profile=config['aws']['profile'],
            region=config['aws']['region']
        )
        
        # Get project status
        project_info = aws_manager.get_project_status(config['project']['name'])
        available_versions = aws_manager.list_versions(config['project']['name'])
        
        # Display status
        print_header("PROJECT STATUS")
        
        print_info(f"Project Name:     {config['project']['name']}")
        print_info(f"Framework:        {config['project']['framework']}")
        print_info(f"GitHub URL:       {config['project']['github_url']}")
        print_info(f"AWS Bucket:       {config['aws']['bucket']}")
        print_info(f"Region:           {config['aws']['region']}")
        print_info(f"Current Version:  {config['project'].get('current_version', 'None')}")
        print_info(f"Live URL:         {project_info.get('website_url', 'Not deployed')}")
        print_info(f"Created:          {config['project']['created_at']}")
        
        click.echo()
        print_header("AVAILABLE VERSIONS")
        
        if available_versions:
            current_version = config['project'].get('current_version')
            for v in sorted(available_versions, reverse=True)[:10]:
                if v == current_version:
                    click.echo(f"{Fore.GREEN}* {v} (current){Style.RESET_ALL}")
                else:
                    click.echo(f"  {v}")
        else:
            print_info("No versions deployed yet")
            
    except Exception as e:
        print_error(f"Status check failed: {str(e)}")
