import click
import sys

from ..core.utils import print_success, print_error, print_info, print_step
from ..core.config_manager import ConfigManager
from ..core.aws_manager import AWSManager

@click.command()
@click.option('--version', required=True, help='Version to rollback to')
@click.pass_context
def rollback(ctx, version):
    """
    Rollback to a previous version (instant, no rebuild)
    
    Example: deploy-tool rollback --version v20250720-050300
    """
    try:
        print_step("ROLLBACK", f"Rolling back to version: {version}")
        
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Initialize AWS manager
        aws_manager = AWSManager(
            profile=config['aws']['profile'],
            region=config['aws']['region']
        )
        
        # Validate credentials
        print_step("AUTH", "Validating AWS credentials...")
        if not aws_manager.validate_credentials():
            print_error("AWS SSO session expired")
            print_info(f"Please run: aws sso login --profile {config['aws']['profile']}")
            sys.exit(1)
        
        # Check if version exists
        print_step("VALIDATE", "Checking version availability...")
        available_versions = aws_manager.list_versions(config['project']['name'])
        if version not in available_versions:
            print_error(f"Version '{version}' not found")
            print_info("Available versions:")
            for v in sorted(available_versions, reverse=True):
                print_info(f"  - {v}")
            sys.exit(1)
        
        # Perform rollback
        print_step("ACTIVATE", "Activating previous version...")
        rollback_info = aws_manager.activate_version(config['project']['name'], version)
        
        # Update configuration
        config['project']['current_version'] = version
        config_manager.save_config(config)
        
        print_success("Rollback completed successfully")
        print_info(f"Live URL: {rollback_info['website_url']}")
        print_info(f"Active version: {version}")
        
    except Exception as e:
        print_error(f"Rollback failed: {str(e)}")
        sys.exit(1)
