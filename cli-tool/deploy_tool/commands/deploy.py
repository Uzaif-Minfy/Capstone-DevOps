import click
import sys
from datetime import datetime

from ..core.utils import (
    print_success, print_error, print_info, print_warning, print_step
)
from ..core.config_manager import ConfigManager
from ..core.git_manager import GitManager
from ..core.build_manager import BuildManager
from ..core.aws_manager import AWSManager

@click.command()
@click.option('--version', help='Version tag (auto-generated if not provided)')
@click.option('--build-only', is_flag=True, help='Only build, do not deploy')
@click.pass_context
def deploy(ctx, version, build_only):
    """
    Deploy project to S3 (one-button deployment)
    Automatic cleanup - no user maintenance required
    
    Example: deploy-tool deploy
    Example: deploy-tool deploy --version v1.2.0
    """
    try:
        print_step("DEPLOY", "Starting deployment process...")
        
        # Load configuration
        config_manager = ConfigManager()
        if not config_manager.config_exists():
            print_error("No project configuration found")
            print_info("Please run 'deploy-tool init' first")
            sys.exit(1)
        
        config = config_manager.load_config()
        
        # Initialize managers
        git_manager = GitManager()
        build_manager = BuildManager()
        aws_manager = AWSManager(
            profile=config['aws']['profile'],
            region=config['aws']['region']
        )
        
        # Validate AWS credentials
        print_step("AUTH", "Validating AWS credentials...")
        if not aws_manager.validate_credentials():
            print_error("AWS SSO session expired")
            print_info(f"Please run: aws sso login --profile {config['aws']['profile']}")
            sys.exit(1)
        
        # Generate version if not provided
        if not version:
            version = f"v{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        print_info(f"Deploying version: {version}")
        
        # Step 1: Get repository
        print_step("1/4", "Preparing repository...")
        repo_dir = git_manager.clone_for_deployment(
            config['project']['github_url'],
            config['project']['name']
        )
        
        # Step 2: Build project (automatic cleanup scheduled)
        print_step("2/4", "Building project...")
        build_output, build_info = build_manager.build_and_prepare_for_deployment(repo_dir)
        
        if build_only:
            print_success("Build completed successfully")
            print_info(f"Framework: {build_info['framework']}")
            print_info(f"Files: {build_info['total_files']}")
            print_info(f"Size: {build_info['total_size_formatted']}")
            return
        
        # Step 3: Deploy to S3 (S3 configuration happens automatically in deploy_version)
        print_step("3/4", "Deploying to S3...")
        deployment_info = aws_manager.deploy_version(
            config['project']['name'],
            version,
            build_output
        )
        
        # Step 4: Activate version
        print_step("4/4", "Activating new version...")
        activation_info = aws_manager.activate_version(config['project']['name'], version)
        
        # Update configuration
        config['project']['current_version'] = version
        config['project']['last_deployed'] = datetime.now().isoformat()
        config_manager.save_config(config)
        
        # Success! (Cleanup happens automatically in background)
        print_success("Deployment completed successfully!")
        print_info(f"Version: {version}")
        print_info(f"Live URL: {activation_info['website_url']}")
        print_info(f"Deployed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except KeyboardInterrupt:
        print_warning("Deployment interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        print_error(f"Deployment failed: {str(e)}")
        sys.exit(1)











# trying to work with .env file


# import click
# import sys
# from pathlib import Path
# from datetime import datetime

# from ..core.utils import (
#     print_success, print_error, print_info, print_warning, print_step, print_header
# )
# from ..core.config_manager import ConfigManager
# from ..core.git_manager import GitManager
# from ..core.build_manager import BuildManager
# from ..core.aws_manager import AWSManager

# @click.command()
# @click.option('--env', '--environment', 
#               default='production',
#               help='Target environment (display only)')
# @click.option('--version', help='Version tag (auto-generated if not provided)')
# @click.option('--env-file', help='Path to .env file for build')
# @click.option('--build-only', is_flag=True, help='Only build, do not deploy')
# @click.option('--skip-build', is_flag=True, help='Skip build step')
# @click.pass_context
# def deploy(ctx, env, version, env_file, build_only, skip_build):
#     """Deploy project with optional environment file support"""
#     try:
#         print_header("DEPLOYMENT")
#         print_step("DEPLOY", f"Starting deployment to {env} environment...")
        
#         # Load configuration
#         config_manager = ConfigManager()
#         if not config_manager.config_exists():
#             print_error("No project configuration found")
#             print_info("Please run 'deploy-tool init' first")
#             sys.exit(1)
        
#         config = config_manager.load_config()
#         project_name = config['project']['name']
        
#         # Generate version if not provided
#         if not version:
#             version = f"v{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
#         print_info(f"Project: {project_name}")
#         print_info(f"Environment: {env}")
#         print_info(f"Version: {version}")
        
#         # Show environment file info
#         if env_file:
#             env_file_path = Path(env_file)
#             if not env_file_path.exists():
#                 print_error(f"Environment file not found: {env_file}")
#                 sys.exit(1)
#             print_info(f"Environment file: {env_file}")
#         else:
#             print_info("No environment file specified")
        
#         # Initialize managers
#         build_manager = BuildManager()
#         git_manager = GitManager()
#         aws_manager = AWSManager(
#             profile=config['aws']['profile'],
#             region=config['aws']['region']
#         )
        
#         # Validate AWS credentials
#         print_step("AUTH", "Validating AWS credentials...")
#         if not aws_manager.validate_credentials():
#             print_error("AWS SSO session expired")
#             print_info(f"Please run: aws sso login --profile {config['aws']['profile']}")
#             sys.exit(1)
        
#         # Step 1: Get repository
#         print_step("1/4", "Preparing repository...")
#         repo_dir = git_manager.clone_for_deployment(
#             config['project']['github_url'],
#             project_name
#         )
        
#         build_dir = None
#         build_info = {}
        
#         # Step 2: Build project (if not skipped)
#         if not skip_build:
#             print_step("2/4", f"Building project...")
#             build_dir, build_info = build_manager.build_and_prepare_for_deployment(
#                 repo_dir,
#                 env_file_path=env_file
#             )
#         else:
#             print_info("Skipping build step as requested")
#             # Look for existing build directory
#             possible_build_dirs = ['build', 'dist', '.next']
#             for build_dir_name in possible_build_dirs:
#                 potential_build_dir = repo_dir / build_dir_name
#                 if potential_build_dir.exists():
#                     build_dir = potential_build_dir
#                     build_info = {'framework': config['project']['framework']}
#                     break
            
#             if not build_dir:
#                 print_error("No existing build found and build skipped")
#                 sys.exit(1)
        
#         if build_only:
#             print_success("Build completed successfully")
#             print_info(f"Build output: {build_dir}")
#             if env_file:
#                 print_info(f"Environment file used: {env_file}")
            
#             # Debug environment variables in build
#             print_header("BUILD DEBUG INFO")
#             if (build_dir / 'index.html').exists():
#                 try:
#                     html_content = (build_dir / 'index.html').read_text()
#                     if 'import.meta.env' in html_content or 'process.env' in html_content:
#                         print_info("✅ Environment variables detected in build")
#                     else:
#                         print_warning("⚠️  No environment variables detected in build")
                        
#                     # Check for main JavaScript file
#                     js_files = list(build_dir.glob('assets/*.js'))
#                     if js_files:
#                         try:
#                             js_content = js_files[0].read_text()
#                             if 'VITE_FIREBASE' in js_content:
#                                 print_info("✅ Firebase environment variables found in JavaScript")
#                             else:
#                                 print_warning("⚠️  Firebase environment variables not found in JavaScript")
#                         except:
#                             pass
#                 except Exception as e:
#                     print_warning(f"Could not analyze build: {e}")
#             return
        
#         # Step 3: Deploy to S3
#         print_step("3/4", f"Deploying to S3...")
#         deployment_info = aws_manager.deploy_version(
#             project_name,
#             version,
#             build_dir
#         )
        
#         # Step 4: Activate version
#         print_step("4/4", "Activating new version...")
#         activation_info = aws_manager.activate_version(project_name, version)
        
#         # Update configuration
#         config['project']['current_version'] = version
#         config['project']['last_deployed'] = datetime.now().isoformat()
#         config['project']['environment'] = env
        
#         # Store deployment metadata
#         if 'deployment_history' not in config:
#             config['deployment_history'] = []
        
#         config['deployment_history'].append({
#             'version': version,
#             'environment': env,
#             'deployed_at': datetime.now().isoformat(),
#             'build_info': build_info,
#             'deployment_info': deployment_info,
#             'env_file_used': bool(env_file)
#         })
        
#         # Keep only last 10 deployments
#         config['deployment_history'] = config['deployment_history'][-10:]
        
#         config_manager.save_config(config)
        
#         # Success!
#         print_success(f"Deployment to {env} completed successfully!")
        
#         print_header("DEPLOYMENT SUMMARY")
#         print_info(f"🌍 Environment: {env}")
#         print_info(f"📦 Version: {version}")
#         print_info(f"🌐 Live URL: {activation_info['website_url']}")
#         print_info(f"☁️ S3 Bucket: {config['aws']['bucket']}")
#         if env_file:
#             print_info(f"📁 Environment File: {env_file}")
        
#         print_header("BUILD INFORMATION")
#         if build_info:
#             print_info(f"Framework: {build_info.get('framework', 'Unknown')}")
#             print_info(f"Files: {build_info.get('total_files', 'Unknown')}")
#             print_info(f"Size: {build_info.get('total_size_formatted', 'Unknown')}")
#             print_info(f"Environment File Used: {'Yes' if build_info.get('env_file_used') else 'No'}")
        
#         print_header("DEBUGGING STEPS")
#         print_info("🐛 If you see a blank page:")
#         print_info("1. Open your website in a browser")
#         print_info("2. Press F12 to open developer console") 
#         print_info("3. Check Console tab for JavaScript errors")
#         print_info("4. Check Network tab for failed resource loads")
#         print_info("5. Type: window.envDebug to see environment variables")
        
#         if env_file:
#             print_header("ENVIRONMENT VARIABLES DEBUG")
#             print_info("To verify environment variables are loaded:")
#             print_info("- In browser console, type: console.log(import.meta.env)")
#             print_info("- Or type: window.envDebug.firebaseVars")
#             print_info("- Look for your VITE_ prefixed variables")
        
#         print_header("NEXT STEPS")
#         print_info("🔍 Monitor: deploy-tool monitoring start")
#         print_info("📊 Status: deploy-tool status")
#         print_info("↩️  Rollback: deploy-tool rollback")
        
#     except Exception as e:
#         print_error(f"Deployment failed: {str(e)}")
#         sys.exit(1)

