import click
import json
from pathlib import Path
from typing import Dict

from ..core.utils import (
    print_success, print_error, print_info, print_warning, print_step, print_header
)
from ..core.config_manager import ConfigManager

@click.group()
def config():
    """ Configuration management commands """
    pass

@config.command()
@click.option('--show-all', is_flag=True, help='Show all configuration')
def show(show_all):
    """ Display current configuration """
    try:
        config_manager = ConfigManager()
        
        if not config_manager.config_exists():
            print_warning("No configuration found")
            print_info("Run 'deploy-tool init' to create initial configuration")
            return
        
        config = config_manager.load_config()
        
        print_header("PROJECT CONFIGURATION")
        print_info(f"Project Name: {config['project']['name']}")
        print_info(f"GitHub URL: {config['project']['github_url']}")
        print_info(f"Framework: {config['project']['framework']}")
        print_info(f"Environment: {config['project'].get('environment', 'production')}")
        print_info(f"Project Path: {config['project'].get('project_path', 'root')}")
        print_info(f"Current Version: {config['project'].get('current_version', 'None')}")
        print_info(f"Last Deployed: {config['project'].get('last_deployed', 'Never')}")
        
        print_header("AWS CONFIGURATION")
        print_info(f"Profile: {config['aws']['profile']}")
        print_info(f"Region: {config['aws']['region']}")
        # Handle both bucket and s3_bucket keys
        bucket_name = config['aws'].get('bucket') or config['aws'].get('s3_bucket', 'Not configured')
        print_info(f"S3 Bucket: {bucket_name}")
        
        if 'build' in config:
            print_header("BUILD CONFIGURATION")
            print_info(f"Install Command: {config['build'].get('install_command', 'npm ci')}")
            print_info(f"Build Command: {config['build'].get('build_command', 'npm run build')}")
            print_info(f"Output Directory: {config['build'].get('output_dir', 'dist')}")
        
        if 'deployment' in config:
            print_header("DEPLOYMENT CONFIGURATION")
            print_info(f"Auto Cleanup: {config['deployment'].get('auto_cleanup', False)}")
            print_info(f"Versions to Keep: {config['deployment'].get('versions_to_keep', 10)}")
            
        if show_all:
            print_header("FULL CONFIGURATION")
            print_info(json.dumps(config, indent=2))
        
    except Exception as e:
        print_error(f"Failed to show configuration: {e}")


@config.command()
@click.confirmation_option(prompt='This will reset all configuration. Continue?')
def reset():
    """Reset all configuration"""
    try:
        config_manager = ConfigManager()
        
        if config_manager.config_exists():
            config_manager.config_file.unlink()
            print_success("Configuration reset successfully")
            print_info("Run 'deploy-tool init' to create a new configuration")
        else:
            print_info("No configuration found to reset")
            
    except Exception as e:
        print_error(f"Failed to reset configuration: {e}")


@config.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """Set a configuration value"""
    try:
        config_manager = ConfigManager()

        if not config_manager.config_exists():
            print_error("No configuration found. Run 'deploy-tool init' first.")
            return

        config = config_manager.load_config()

        keys = key.split('.')
        if len(keys) < 2:
            print_error("You must specify a section and a key, like 'aws.bucket'")
            return

        # The section must exist and must be one of the allowed sections
        section = keys[0]
        if section not in config or section not in {"aws", "build", "deployment", "project"}:
            print_error(f"Invalid top-level section: '{section}'")
            return

        current = config[section]

        for k in keys[1:-1]:
            if k not in current:
                print_error(f"Invalid key path: '{key}' — '{k}' does not exist.")
                return
            current = current[k]
            if not isinstance(current, dict):
                print_error(f"Invalid key path: '{key}' — '{k}' is not a section.")
                return

        if keys[-1] not in current:
            print_error(f"Invalid key: '{keys[-1]}' does not exist under '{'.'.join(keys[:-1])}'.")
            return

        current[keys[-1]] = _parse_value(value)
        config_manager.save_config(config)
        print_success(f"Set {key} = {value}")

    except Exception as e:
        print_error(f"Failed to set configuration: {e}")


@config.command()
@click.argument('key')
def get(key):
    """Get a configuration value"""
    try:
        config_manager = ConfigManager()

        if not config_manager.config_exists():
            print_error("No configuration found.")
            return

        config = config_manager.load_config()

        keys = key.split('.')
        if len(keys) < 2:
            print_error("You must specify a section and a key, like 'aws.bucket', 'project.name'")
            return

        section = keys[0]
        if section not in config or section not in {"aws", "build", "deployment", "project"}:
            print_error(f"Invalid top-level section: '{section}'")
            return

        current = config[section]

        for k in keys[1:]:
            if k not in current:
                print_warning(f"Key '{key}' not found.")
                return
            current = current[k]

        print_info(f"{key} = {current}")

    except Exception as e:
        print_error(f"Failed to get configuration: {e}")


def _parse_value(value):
    if value.lower() == "true":
        return True
    elif value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
