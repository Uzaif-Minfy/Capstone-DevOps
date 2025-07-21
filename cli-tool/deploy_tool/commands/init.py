import click
import sys
from pathlib import Path
from datetime import datetime

from ..core.utils import (
    print_success, print_error, print_info, print_warning, print_step,
    validate_github_url, extract_repo_name
)
from ..core.config_manager import ConfigManager
from ..core.git_manager import GitManager
from ..core.aws_manager import AWSManager
from ..core.build_manager import BuildManager

@click.command()
@click.option('--github-url', required=True, help='GitHub repository URL')
@click.option('--project-name', help='Project name (auto-detected if not provided)')
@click.option('--framework', type=click.Choice(['react', 'vite', 'next', 'auto']), 
              default='auto', help='Project framework')
@click.option('--environment', type=click.Choice(['development', 'staging', 'production']), 
              default='production', help='Default environment for deployments')
@click.pass_context
def init(ctx, github_url, project_name, framework, environment):
    """
    Initialize a new project for deployment
    
    Example: deploy-tool init --github-url https://github.com/user/my-react-app
    """
    git_manager = None
    build_manager = None
    temp_dir = None
    
    try:
        print_step("INIT", "Initializing new deployment project...")
        
        # Initialize managers
        config_manager = ConfigManager()
        git_manager = GitManager()
        aws_manager = AWSManager(
            profile=ctx.obj['aws_profile'],
            region=ctx.obj['aws_region']
        )
        
        # Validate GitHub URL
        print_step("VALIDATE", "Validating GitHub URL...")
        if not validate_github_url(github_url):
            print_error("Invalid GitHub URL format")
            print_info("Expected format: https://github.com/username/repository")
            sys.exit(1)
        
        # Extract project name if not provided
        if not project_name:
            project_name = extract_repo_name(github_url)
            print_info(f"Auto-detected project name: {project_name}")
        
        # Validate AWS credentials
        print_step("AWS", "Validating AWS credentials...")
        if not aws_manager.validate_credentials():
            print_error("AWS SSO authentication failed")
            print_info(f"Please run: aws sso login --profile {ctx.obj['aws_profile']}")
            sys.exit(1)
        print_success("AWS credentials validated")
        
        # Clone repository temporarily to detect framework
        print_step("CLONE", "Cloning repository to detect project type...")
        temp_dir = git_manager.clone_repository(github_url)
        
        # Auto-detect framework and project directory if needed
        if framework == 'auto':
            build_manager = BuildManager()
            detected_framework, actual_project_dir = build_manager.detect_project_directory(temp_dir)
            print_info(f"Detected framework: {detected_framework}")
            framework = detected_framework
            
            # Calculate relative path from repo root to actual project
            try:
                if actual_project_dir != temp_dir:
                    relative_project_path = actual_project_dir.relative_to(temp_dir)
                    project_path_str = str(relative_project_path).replace('\\', '/')
                    print_info(f"Project location: {project_path_str}")
                else:
                    project_path_str = "."
            except ValueError:
                project_path_str = "."
        else:
            project_path_str = "."
        
        # Determine build output directory based on framework
        if framework == "react":
            output_dir = "build"
        elif framework == "vite":
            output_dir = "dist"
        elif framework == "next":
            output_dir = ".next"
        else:
            output_dir = "build"  # default
        
        # Create project configuration
        config = {
            "project": {
                "name": project_name,
                "framework": framework,
                "github_url": github_url,
                "created_at": datetime.now().isoformat(),
                "current_version": None,
                "project_path": project_path_str,
                "environment": environment
            },
            "aws": {
                "profile": ctx.obj['aws_profile'],
                "region": ctx.obj['aws_region'],
                "bucket": "minfy-uzaif-capstone-deployments"
            },
            "build": {
                "output_dir": output_dir,
                "build_command": "npm run build",
                "install_command": "npm ci"
            },
            "deployment": {
                "versions_to_keep": 10,
                "auto_cleanup": True
            }
        }
        
        # Save configuration
        print_step("CONFIG", "Saving project configuration...")
        config_manager.save_config(config)
        
        print_success("Project initialized successfully")
        print_info(f"Project name: {project_name}")
        print_info(f"Framework: {framework}")
        print_info(f"Environment: {environment}")
        print_info(f"GitHub URL: {github_url}")
        if project_path_str != ".":
            print_info(f"Project path: {project_path_str}")
        print_info(f"AWS Bucket: minfy-uzaif-capstone-deployments")
        print_info(f"Region: {ctx.obj['aws_region']}")
        
    except KeyboardInterrupt:
        print_warning("Initialization interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        print_error(f"Initialization failed: {str(e)}")
        sys.exit(1)
        
    finally:
        # Cleanup temporary directory
        if git_manager and temp_dir:
            try:
                git_manager.cleanup_temp_dir(temp_dir)
            except Exception as cleanup_error:
                print_warning(f"Failed to cleanup temp directory: {cleanup_error}")
