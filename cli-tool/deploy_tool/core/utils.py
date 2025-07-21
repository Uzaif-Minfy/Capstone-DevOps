import click
from colorama import Fore, Style, init
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Dict
import tempfile
import json
import re

# Initialize colorama
init()

def print_success(message: str) -> None:
    """Print success message"""
    click.echo(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")

def print_error(message: str) -> None:
    """Print error message"""
    click.echo(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")

def print_info(message: str) -> None:
    """Print info message"""
    click.echo(f"{Fore.BLUE}[INFO]{Style.RESET_ALL} {message}")

def print_warning(message: str) -> None:
    """Print warning message"""
    click.echo(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}")

def print_step(step: str, message: str) -> None:
    """Print step message"""
    click.echo(f"{Fore.CYAN}[{step}]{Style.RESET_ALL} {message}")

def print_header(title: str) -> None:
    """Print section header"""
    click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}{title}{Style.RESET_ALL}")
    click.echo(f"{Fore.MAGENTA}{'=' * len(title)}{Style.RESET_ALL}")

def check_command_exists(command: str) -> bool:
    """Check if a command exists in system PATH with Windows compatibility"""
    # On Windows, try both the command and .cmd version
    if os.name == 'nt':
        cmd_variants = [command, f"{command}.cmd", f"{command}.exe"]
        for variant in cmd_variants:
            result = shutil.which(variant)
            if result:
                print_info(f"Found {command} at: {result}")
                return True
        print_warning(f"{command} not found in PATH")
        return False
    else:
        result = shutil.which(command)
        if result:
            print_info(f"Found {command} at: {result}")
            return True
        else:
            print_warning(f"{command} not found in PATH")
            return False

def validate_github_url(url: str) -> bool:
    """Validate GitHub URL format"""
    github_patterns = [
        r'https://github\.com/[\w\-\.]+/[\w\-\.]+/?$',
        r'git@github\.com:[\w\-\.]+/[\w\-\.]+\.git$'
    ]
    return any(re.match(pattern, url) for pattern in github_patterns)

def extract_repo_name(github_url: str) -> str:
    """Extract repository name from GitHub URL"""
    # Handle HTTPS URLs
    https_match = re.search(r'github\.com/[\w\-\.]+/([\w\-\.]+)/?$', github_url)
    if https_match:
        return https_match.group(1).replace('.git', '')
    
    # Handle SSH URLs
    ssh_match = re.search(r'github\.com:[\w\-\.]+/([\w\-\.]+)\.git$', github_url)
    if ssh_match:
        return ssh_match.group(1)
    
    return "unknown-project"

def run_command(
    command: List[str], 
    cwd: Optional[str] = None, 
    capture_output: bool = False,
    timeout: int = 300
) -> subprocess.CompletedProcess:
    """Run shell command with Windows compatibility"""
    try:
        print_info(f"Running command: {' '.join(command)}")
        if cwd:
            print_info(f"Working directory: {cwd}")
        
        # Windows-specific command resolution
        if os.name == 'nt':  # Windows
            if command[0] == 'npm':
                command[0] = 'npm.cmd'
            elif command[0] == 'yarn':
                command[0] = 'yarn.cmd'
            elif command[0] == 'node':
                command[0] = 'node.exe'
        
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=True,
            timeout=timeout,
            shell=True if os.name == 'nt' else False  # Use shell on Windows
        )
        return result
    except subprocess.TimeoutExpired:
        raise Exception(f"Command timed out after {timeout} seconds: {' '.join(command)}")
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed: {' '.join(command)}"
        if capture_output and e.stderr:
            error_msg += f"\nError output: {e.stderr}"
        if e.stdout:
            error_msg += f"\nStdout: {e.stdout}"
        raise Exception(error_msg)
    except FileNotFoundError as e:
        raise Exception(f"Command not found: {command[0]}. Please ensure it's installed and in PATH.")


def create_temp_directory(prefix: str = "deploy-tool-") -> Path:
    """Create temporary directory"""
    return Path(tempfile.mkdtemp(prefix=prefix))

def clean_directory(directory: Path) -> None:
    """Remove directory and all contents"""
    if directory.exists() and directory.is_dir():
        shutil.rmtree(directory)

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"

def get_directory_size(directory: Path) -> int:
    """Get total size of directory in bytes"""
    total_size = 0
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size
    return total_size

def ensure_directory(directory: Path) -> None:
    """Ensure directory exists, create if it doesn't"""
    directory.mkdir(parents=True, exist_ok=True)

def load_json_file(file_path: Path) -> Dict:
    """Load JSON file with error handling"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception(f"File not found: {file_path}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON in {file_path}: {str(e)}")

def save_json_file(file_path: Path, data: Dict) -> None:
    """Save data to JSON file"""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
    except Exception as e:
        raise Exception(f"Failed to save JSON to {file_path}: {str(e)}")

def copy_directory_contents(src: Path, dst: Path) -> None:
    """Copy all contents from source to destination directory"""
    ensure_directory(dst)
    
    for item in src.rglob('*'):
        if item.is_file():
            relative_path = item.relative_to(src)
            destination_file = dst / relative_path
            ensure_directory(destination_file.parent)
            shutil.copy2(item, destination_file)

def get_file_size_mb(file_path: Path) -> float:
    """Get file size in megabytes"""
    return file_path.stat().st_size / (1024 * 1024)
