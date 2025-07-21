import os
import shutil
from pathlib import Path
from typing import Optional
import subprocess
import tempfile
import uuid
import threading
import time

from .utils import (
    print_info, print_error, print_warning, print_step, print_success,
    run_command, clean_directory, create_temp_directory,
    validate_github_url, extract_repo_name
)

class GitManager:
    """Simple Git manager - clone repository and cleanup"""
    
    def __init__(self):
        self.work_dir = Path(tempfile.gettempdir()) / "deploy-workspace"
        self.work_dir.mkdir(exist_ok=True)
    
    def validate_github_url(self, url: str) -> bool:
        """Validate GitHub URL"""
        return validate_github_url(url)
    
    def extract_project_name(self, github_url: str) -> str:
        """Extract project name from URL"""
        return extract_repo_name(github_url)
    
    def clone_repository(self, github_url: str, target_dir: Optional[Path] = None) -> Path:
        """Clone repository for init command"""
        if target_dir is None:
            target_dir = create_temp_directory("deploy-git-")
        
        try:
            print_info("Cloning repository...")
            
            run_command([
                'git', 'clone', 
                '--depth', '1',
                '--single-branch',
                '--no-tags',
                github_url, 
                str(target_dir)
            ], timeout=300)
            
            print_success("Repository cloned")
            return target_dir
            
        except Exception as e:
            self._force_cleanup(target_dir)
            raise Exception(f"Failed to clone repository: {str(e)}")
    
    def clone_for_deployment(self, github_url: str, project_name: str) -> Path:
        """Clone repository for deployment"""
        unique_id = str(uuid.uuid4())[:8]
        repo_dir = self.work_dir / f"deploy-{project_name}-{unique_id}"
        
        try:
            print_info("Cloning repository...")
            
            run_command([
                'git', 'clone', 
                '--depth', '1',
                '--single-branch',
                '--no-tags',
                github_url, 
                str(repo_dir)
            ], timeout=300)
            
            print_success("Repository ready")
            return repo_dir
            
        except Exception as e:
            self._force_cleanup(repo_dir)
            raise Exception(f"Failed to clone repository: {str(e)}")
    
    def cleanup_temp_dir(self, temp_dir: Path) -> None:
        """Clean up temporary directory"""
        self._schedule_cleanup(temp_dir)
    
    def _schedule_cleanup(self, directory: Path):
        """Schedule background cleanup"""
        def cleanup_after_delay():
            time.sleep(5)  # Brief delay
            self._force_cleanup(directory)
        
        threading.Thread(target=cleanup_after_delay, daemon=True).start()
    
    def _force_cleanup(self, directory: Path):
        """Force cleanup with multiple strategies"""
        if not directory.exists():
            return
        
        try:
            # Strategy 1: Standard cleanup
            for root, dirs, files in os.walk(str(directory)):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        os.chmod(file_path, 0o777)
                    except:
                        pass
            
            clean_directory(directory)
            
        except Exception:
            try:
                # Strategy 2: Windows command
                subprocess.run([
                    'cmd', '/c', 'rmdir', '/s', '/q', str(directory)
                ], capture_output=True, check=False, timeout=10)
                
            except Exception:
                try:
                    # Strategy 3: Move to temp
                    temp_name = f"cleanup-{uuid.uuid4().hex[:8]}"
                    temp_path = Path(tempfile.gettempdir()) / temp_name
                    directory.rename(temp_path)
                    
                except Exception:
                    pass  # Silent failure
