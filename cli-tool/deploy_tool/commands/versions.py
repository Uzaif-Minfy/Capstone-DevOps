import click
import sys
from colorama import Fore, Style

from ..core.utils import print_success, print_error, print_info, print_step, print_header
from ..core.config_manager import ConfigManager
from ..core.aws_manager import AWSManager

@click.command()
@click.option('--list', is_flag=True, help='List all available versions')
@click.option('--cleanup', is_flag=True, help='Clean up old versions')
@click.option('--keep', default=10, help='Number of versions to keep during cleanup')
@click.pass_context
def versions(ctx, list, cleanup, keep):
    """
    Manage project versions
    
    Example: deploy-tool versions --list
    Example: deploy-tool versions --cleanup --keep 5
    """
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Initialize AWS manager
        aws_manager = AWSManager(
            profile=config['aws']['profile'],
            region=config['aws']['region']
        )
        
        if list:
            # List all versions
            available_versions = aws_manager.list_versions(config['project']['name'])
            current_version = config['project'].get('current_version')
            
            print_header(f"VERSIONS FOR '{config['project']['name']}'")
            
            if available_versions:
                for version in sorted(available_versions, reverse=True):
                    if version == current_version:
                        click.echo(f"{Fore.GREEN}* {version} (current){Style.RESET_ALL}")
                    else:
                        click.echo(f"  {version}")
            else:
                print_info("No versions found")
        
        if cleanup:
            # Cleanup old versions
            print_step("CLEANUP", f"Cleaning up old versions (keeping {keep} most recent)...")
            cleaned_count = aws_manager.cleanup_old_versions(config['project']['name'], keep)
            print_success(f"Cleaned up {cleaned_count} old versions")
            
    except Exception as e:
        print_error(f"Version management failed: {str(e)}")
