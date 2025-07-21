import os
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
import subprocess
import shutil
import tempfile
import time
import threading
import re

from .utils import (
    print_info, print_error, print_warning, print_step, print_success,
    run_command, check_command_exists, load_json_file,
    format_file_size, get_directory_size, clean_directory
)

class BuildManager:
    """Robust build manager with automatic dependency resolution and path fixes"""
    
    def __init__(self):
        self.work_dir = Path(tempfile.gettempdir()) / "deploy-workspace"
        self.work_dir.mkdir(exist_ok=True)
    
    def build_and_prepare_for_deployment(self, repo_dir: Path) -> Tuple[Path, Dict]:
        """Complete build pipeline with automatic fixes"""
        try:
            # Find package.json and project directory
            project_dir, relative_path = self._find_package_json(repo_dir)
            
            print_step("ANALYZE", f"Found package.json in: {relative_path if relative_path != '.' else 'root'}")
            
            # Detect framework and build directory
            framework, build_dir_name = self._detect_framework_and_build_dir(project_dir)
            
            print_info(f"Framework: {framework}")
            print_info(f"Build directory: {build_dir_name}")
            
            # Build the project with automatic fixes
            print_step("BUILD", "Building project...")
            build_dir = self._build_project_robust(project_dir, framework, build_dir_name)
            
            # Verify and fix build
            if not self._verify_and_fix_build(build_dir):
                raise Exception("Build failed - no valid content generated")
            
            file_count = len(list(build_dir.rglob('*')))
            build_size = get_directory_size(build_dir)
            
            print_success(f"Build completed: {file_count} files, {format_file_size(build_size)}")
            
            # Schedule cleanup
            self._schedule_cleanup(repo_dir)
            
            build_info = {
                'framework': framework,
                'project_path': relative_path,
                'build_dir': str(build_dir),
                'total_files': file_count,
                'total_size_formatted': format_file_size(build_size)
            }
            
            return build_dir, build_info
            
        except Exception as e:
            self._cleanup_directory(repo_dir)
            raise Exception(f"Build failed: {str(e)}")
    
    def detect_project_directory(self, project_dir: Path) -> Tuple[str, Path]:
        """Detect project for init command"""
        try:
            actual_project_dir, _ = self._find_package_json(project_dir)
            framework, _ = self._detect_framework_and_build_dir(actual_project_dir)
            return framework, actual_project_dir
        except Exception:
            return "react", project_dir
    
    def _find_package_json(self, repo_dir: Path) -> Tuple[Path, str]:
        """Find package.json in repository"""
        # Check root first
        if (repo_dir / 'package.json').exists():
            return repo_dir, "."
        
        # Search subdirectories
        for package_file in repo_dir.rglob('package.json'):
            # Skip node_modules
            if 'node_modules' in str(package_file):
                continue
            
            project_dir = package_file.parent
            relative_path = project_dir.relative_to(repo_dir)
            
            print_info(f"Found package.json in: {relative_path}")
            return project_dir, str(relative_path).replace('\\', '/')
        
        raise Exception("No package.json found in repository")
    
    def _detect_framework_and_build_dir(self, project_dir: Path) -> Tuple[str, str]:
        """Detect framework and corresponding build directory"""
        try:
            package_json = load_json_file(project_dir / 'package.json')
            dependencies = {
                **package_json.get('dependencies', {}),
                **package_json.get('devDependencies', {})
            }
            
            # Detect framework and build directory
            if 'vite' in dependencies:
                return 'vite', 'dist'
            elif 'next' in dependencies:
                return 'next', '.next'
            elif '@angular/core' in dependencies:
                return 'angular', 'dist'
            elif 'vue' in dependencies:
                return 'vue', 'dist'
            elif 'react-scripts' in dependencies:
                return 'react', 'build'
            elif 'react' in dependencies:
                return 'react', 'build'
            else:
                return 'node', 'dist'
                
        except Exception:
            return 'react', 'build'
    
    def _build_project_robust(self, project_dir: Path, framework: str, build_dir_name: str) -> Path:
        """Robust build process with automatic dependency resolution"""
        build_dir = project_dir / build_dir_name
        
        # Clean existing build
        if build_dir.exists():
            shutil.rmtree(build_dir)
        
        # Fix dependencies and configuration BEFORE building
        if framework == 'vite':
            self._prepare_vite_project(project_dir)
        elif framework == 'react':
            self._prepare_react_project(project_dir)
        
        # Install dependencies with multiple strategies
        self._install_dependencies_robust(project_dir)
        
        # Build with multiple fallback strategies
        self._build_with_fallbacks(project_dir, framework)
        
        # Verify build directory exists
        if not build_dir.exists():
            raise Exception(f"Build directory '{build_dir_name}' not created")
        
        return build_dir
    
    def _prepare_vite_project(self, project_dir: Path):
        """Prepare Vite project with all necessary dependencies and config"""
        try:
            print_info("Preparing Vite project...")
            
            # Read existing package.json
            package_json_path = project_dir / 'package.json'
            package_json = load_json_file(package_json_path)
            
            dependencies = {**package_json.get('dependencies', {}), **package_json.get('devDependencies', {})}
            
            # Auto-install missing Vite dependencies
            missing_deps = []
            
            if 'vite' not in dependencies:
                missing_deps.append('vite@latest')
            
            if 'react' in dependencies and '@vitejs/plugin-react' not in dependencies:
                missing_deps.append('@vitejs/plugin-react@latest')
            
            if 'vue' in dependencies and '@vitejs/plugin-vue' not in dependencies:
                missing_deps.append('@vitejs/plugin-vue@latest')
            
            if 'typescript' in package_json.get('scripts', {}).get('build', '') and 'typescript' not in dependencies:
                missing_deps.extend(['typescript@latest', '@types/node@latest'])
            
            # Install missing dependencies
            if missing_deps:
                print_info(f"Installing missing dependencies: {', '.join(missing_deps)}")
                run_command(['npm', 'install', '--save-dev'] + missing_deps, cwd=str(project_dir), timeout=180)
                print_success("Missing dependencies installed")
            
            # Create optimized vite.config.js
            self._create_optimized_vite_config(project_dir, dependencies)
            
        except Exception as e:
            print_warning(f"Vite preparation failed: {e}")
    
    def _create_optimized_vite_config(self, project_dir: Path, dependencies: Dict):
        """Create optimized Vite configuration for S3 deployment"""
        try:
            vite_config_path = project_dir / 'vite.config.js'
            
            # Determine available plugins
            imports = ["import { defineConfig } from 'vite'"]
            plugins = []
            
            if 'react' in dependencies:
                if '@vitejs/plugin-react' in dependencies:
                    imports.append("import react from '@vitejs/plugin-react'")
                    plugins.append("react()")
                else:
                    print_warning("React detected but @vitejs/plugin-react not available")
            
            if 'vue' in dependencies:
                if '@vitejs/plugin-vue' in dependencies:
                    imports.append("import vue from '@vitejs/plugin-vue'")
                    plugins.append("vue()")
            
            plugins_array = f"[{', '.join(plugins)}]" if plugins else "[]"
            
            config_content = f"""{chr(10).join(imports)}

export default defineConfig({{
  base: './',
  plugins: {plugins_array},
  build: {{
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    rollupOptions: {{
      output: {{
        manualChunks: undefined
      }}
    }}
  }},
  server: {{
    fs: {{
      strict: false
    }}
  }}
}})
"""
            
            vite_config_path.write_text(config_content)
            print_success("Created optimized Vite configuration")
            
        except Exception as e:
            print_warning(f"Could not create Vite config: {e}")
            # Create minimal fallback
            self._create_minimal_vite_config(project_dir)
    
    def _create_minimal_vite_config(self, project_dir: Path):
        """Create minimal Vite config that always works"""
        try:
            vite_config_path = project_dir / 'vite.config.js'
            
            minimal_config = """import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false
  }
})
"""
            
            vite_config_path.write_text(minimal_config)
            print_info("Created minimal Vite configuration")
            
        except Exception as e:
            print_warning(f"Could not create minimal config: {e}")
    
    def _prepare_react_project(self, project_dir: Path):
        """Prepare React project for building"""
        try:
            print_info("Preparing React project...")
            
            package_json_path = project_dir / 'package.json'
            package_json = load_json_file(package_json_path)
            
            dependencies = {**package_json.get('dependencies', {}), **package_json.get('devDependencies', {})}
            
            # Auto-install missing React dependencies
            missing_deps = []
            
            if 'react' not in dependencies:
                missing_deps.extend(['react@latest', 'react-dom@latest'])
            
            if 'react-scripts' not in dependencies and 'vite' not in dependencies:
                missing_deps.append('react-scripts@latest')
            
            # Install missing dependencies
            if missing_deps:
                print_info(f"Installing missing React dependencies: {', '.join(missing_deps)}")
                run_command(['npm', 'install'] + missing_deps, cwd=str(project_dir), timeout=180)
                print_success("Missing React dependencies installed")
            
        except Exception as e:
            print_warning(f"React preparation failed: {e}")
    
    def _install_dependencies_robust(self, project_dir: Path):
        """Robust dependency installation with multiple strategies"""
        try:
            # Clear npm cache first
            try:
                run_command(['npm', 'cache', 'clean', '--force'], cwd=str(project_dir), timeout=60)
            except:
                pass
            
            # Strategy 1: npm ci
            try:
                print_info("Installing dependencies with npm ci...")
                run_command(['npm', 'ci'], cwd=str(project_dir), timeout=300)
                print_success("Dependencies installed with npm ci")
                return
            except Exception as e:
                print_warning(f"npm ci failed: {e}")
            
            # Strategy 2: npm install
            try:
                print_info("Installing dependencies with npm install...")
                run_command(['npm', 'install'], cwd=str(project_dir), timeout=300)
                print_success("Dependencies installed with npm install")
                return
            except Exception as e:
                print_warning(f"npm install failed: {e}")
            
            # Strategy 3: npm install --legacy-peer-deps
            try:
                print_info("Installing dependencies with legacy peer deps...")
                run_command(['npm', 'install', '--legacy-peer-deps'], cwd=str(project_dir), timeout=300)
                print_success("Dependencies installed with legacy peer deps")
                return
            except Exception as e:
                print_warning(f"npm install --legacy-peer-deps failed: {e}")
            
            # Strategy 4: yarn (if available)
            if check_command_exists('yarn'):
                try:
                    print_info("Installing dependencies with yarn...")
                    run_command(['yarn', 'install'], cwd=str(project_dir), timeout=300)
                    print_success("Dependencies installed with yarn")
                    return
                except Exception as e:
                    print_warning(f"yarn install failed: {e}")
            
            raise Exception("All dependency installation methods failed")
            
        except Exception as e:
            raise Exception(f"Failed to install dependencies: {e}")
    
    def _build_with_fallbacks(self, project_dir: Path, framework: str):
        """Build project with multiple fallback strategies"""
        build_successful = False
        
        # Strategy 1: Standard build command
        if not build_successful:
            try:
                print_info("Attempting standard build...")
                run_command(['npm', 'run', 'build'], cwd=str(project_dir), timeout=600)
                build_successful = True
                print_success("Standard build completed")
            except Exception as e:
                print_warning(f"Standard build failed: {e}")
        
        # Strategy 2: Framework-specific commands
        if not build_successful:
            try:
                print_info("Attempting framework-specific build...")
                if framework == 'vite':
                    run_command(['npx', 'vite', 'build'], cwd=str(project_dir), timeout=600)
                elif framework == 'react':
                    run_command(['npx', 'react-scripts', 'build'], cwd=str(project_dir), timeout=600)
                elif framework == 'next':
                    run_command(['npx', 'next', 'build'], cwd=str(project_dir), timeout=600)
                elif framework == 'angular':
                    run_command(['npx', 'ng', 'build', '--base-href', './'], cwd=str(project_dir), timeout=600)
                else:
                    run_command(['npm', 'run', 'build'], cwd=str(project_dir), timeout=600)
                
                build_successful = True
                print_success("Framework-specific build completed")
            except Exception as e:
                print_warning(f"Framework-specific build failed: {e}")
        
        # Strategy 3: Force build with base path
        if not build_successful and framework == 'vite':
            try:
                print_info("Attempting Vite build with forced base path...")
                run_command(['npx', 'vite', 'build', '--base', './'], cwd=str(project_dir), timeout=600)
                build_successful = True
                print_success("Forced base path build completed")
            except Exception as e:
                print_warning(f"Forced build failed: {e}")
        
        # Strategy 4: Build without config
        if not build_successful and framework == 'vite':
            try:
                print_info("Attempting build without configuration...")
                vite_config = project_dir / 'vite.config.js'
                backup_config = None
                
                if vite_config.exists():
                    backup_config = project_dir / 'vite.config.js.backup'
                    vite_config.rename(backup_config)
                    print_info("Temporarily removed Vite config")
                
                run_command(['npx', 'vite', 'build', '--base', './'], cwd=str(project_dir), timeout=600)
                build_successful = True
                print_success("Build without config completed")
                
                # Restore config
                if backup_config and backup_config.exists():
                    backup_config.rename(vite_config)
                
            except Exception as e:
                print_warning(f"Build without config failed: {e}")
                # Restore config if it exists
                backup_config = project_dir / 'vite.config.js.backup'
                if backup_config.exists():
                    backup_config.rename(project_dir / 'vite.config.js')
        
        if not build_successful:
            raise Exception("All build strategies failed")
    
    def _verify_and_fix_build(self, build_dir: Path) -> bool:
        """Verify build has content and fix asset paths"""
        if not build_dir.exists():
            return False
        
        # Check for any files
        files = list(build_dir.rglob('*'))
        files = [f for f in files if f.is_file()]
        
        if len(files) == 0:
            return False
        
        # Fix asset paths in HTML files
        self._fix_all_asset_paths(build_dir)
        
        # Verify we have essential web files
        web_files = [f for f in files if f.suffix.lower() in ['.html', '.js', '.css']]
        return len(web_files) > 0
    
    def _fix_all_asset_paths(self, build_dir: Path):
        """Fix asset paths in all HTML files for S3 compatibility"""
        try:
            # Find all HTML files
            html_files = list(build_dir.rglob('*.html'))
            
            for html_file in html_files:
                self._fix_single_html_file(html_file)
            
            if html_files:
                print_success(f"Fixed asset paths in {len(html_files)} HTML files")
            
        except Exception as e:
            print_warning(f"Could not fix asset paths: {e}")
    
    def _fix_single_html_file(self, html_file: Path):
        """Fix asset paths in a single HTML file"""
        try:
            content = html_file.read_text(encoding='utf-8')
            original_content = content
            
            # Fix script src paths (absolute to relative)
            content = re.sub(r'<script([^>]*)\ssrc="(/[^"]*)"', r'<script\1 src=".\2"', content)
            
            # Fix link href paths (CSS and other resources)
            content = re.sub(r'<link([^>]*)\shref="(/[^"]*)"', r'<link\1 href=".\2"', content)
            
            # Fix img src paths
            content = re.sub(r'<img([^>]*)\ssrc="(/[^"]*)"', r'<img\1 src=".\2"', content)
            
            # Fix any other absolute paths in common attributes
            content = re.sub(r'(src|href|action)="(/[^"]*)"', r'\1=".\2"', content)
            
            # Remove problematic base tags that can break S3 hosting
            content = re.sub(r'<base[^>]*/?>', '', content)
            
            # Fix any absolute paths in CSS imports or JS
            content = re.sub(r'url\(/([^)]*)\)', r'url(./\1)', content)
            
            # Write back if changed
            if content != original_content:
                html_file.write_text(content, encoding='utf-8')
                print_info(f"Fixed paths in {html_file.name}")
            
        except Exception as e:
            print_warning(f"Could not fix {html_file.name}: {e}")
    
    def _schedule_cleanup(self, directory: Path):
        """Schedule cleanup after deployment"""
        def cleanup_after_delay():
            time.sleep(30)  # Wait for deployment to complete
            self._cleanup_directory(directory)
        
        threading.Thread(target=cleanup_after_delay, daemon=True).start()
    
    def _cleanup_directory(self, directory: Path):
        """Clean up directory"""
        try:
            if directory.exists():
                clean_directory(directory)
        except:
            # Move to temp if deletion fails
            try:
                import uuid
                temp_path = Path(tempfile.gettempdir()) / f"cleanup-{uuid.uuid4().hex[:8]}"
                directory.rename(temp_path)
            except:
                pass  








# import os
# import json
# from pathlib import Path
# from typing import Dict, Optional, Tuple
# import subprocess
# import shutil
# import tempfile
# import time
# import threading
# import re

# from .utils import (
#     print_info, print_error, print_warning, print_step, print_success,
#     run_command, check_command_exists, load_json_file,
#     format_file_size, get_directory_size, clean_directory
# )

# class BuildManager:
#     """Robust build manager with automatic dependency resolution and optional .env file support"""
    
#     def __init__(self):
#         self.work_dir = Path(tempfile.gettempdir()) / "deploy-workspace"
#         self.work_dir.mkdir(exist_ok=True)
    
#     def build_and_prepare_for_deployment(self, repo_dir: Path, env_file_path: Optional[str] = None) -> Tuple[Path, Dict]:
#         """Complete build pipeline with optional .env file support"""
#         try:
#             # Find package.json and project directory
#             project_dir, relative_path = self._find_package_json(repo_dir)
            
#             print_step("ANALYZE", f"Found package.json in: {relative_path if relative_path != '.' else 'root'}")
            
#             # Detect framework and build directory
#             framework, build_dir_name = self._detect_framework_and_build_dir(project_dir)
            
#             print_info(f"Framework: {framework}")
#             print_info(f"Build directory: {build_dir_name}")
            
#             # Handle environment file if provided
#             if env_file_path:
#                 self._handle_env_file(project_dir, env_file_path)
#             else:
#                 print_info("No environment file provided - using project defaults")
            
#             # Build the project with automatic fixes
#             print_step("BUILD", "Building project...")
#             build_dir = self._build_project_robust(project_dir, framework, build_dir_name)
            
#             # Verify and fix build
#             if not self._verify_and_fix_build(build_dir):
#                 raise Exception("Build failed - no valid content generated")
            
#             file_count = len(list(build_dir.rglob('*')))
#             build_size = get_directory_size(build_dir)
            
#             print_success(f"Build completed: {file_count} files, {format_file_size(build_size)}")
            
#             # Schedule cleanup
#             self._schedule_cleanup(repo_dir)
            
#             build_info = {
#                 'framework': framework,
#                 'project_path': relative_path,
#                 'build_dir': str(build_dir),
#                 'total_files': file_count,
#                 'total_size_formatted': format_file_size(build_size),
#                 'env_file_used': bool(env_file_path)
#             }
            
#             return build_dir, build_info
            
#         except Exception as e:
#             self._cleanup_directory(repo_dir)
#             raise Exception(f"Build failed: {str(e)}")
    
#     def detect_project_directory(self, project_dir: Path) -> Tuple[str, Path]:
#         """Detect project for init command"""
#         try:
#             actual_project_dir, _ = self._find_package_json(project_dir)
#             framework, _ = self._detect_framework_and_build_dir(actual_project_dir)
#             return framework, actual_project_dir
#         except Exception:
#             return "react", project_dir
    
#     def _handle_env_file(self, project_dir: Path, env_file_path: str):
#         """Handle user-provided .env file with better Vite integration"""
#         try:
#             env_file = Path(env_file_path).expanduser().resolve()
            
#             if not env_file.exists():
#                 print_error(f"Environment file not found: {env_file_path}")
#                 raise Exception(f"Environment file not found: {env_file_path}")
            
#             print_step("ENV", f"Using environment file: {env_file}")
            
#             # Read environment variables
#             env_vars = {}
#             with open(env_file, 'r') as f:
#                 for line in f:
#                     line = line.strip()
#                     if line and not line.startswith('#') and '=' in line:
#                         key, value = line.split('=', 1)
#                         key = key.strip()
#                         value = value.strip().strip('"').strip("'")
#                         env_vars[key] = value
            
#             # Copy .env file to project directory
#             target_env_file = project_dir / '.env'
#             shutil.copy2(env_file, target_env_file)
            
#             # Also create .env.production for Vite
#             prod_env_file = project_dir / '.env.production'
#             shutil.copy2(env_file, prod_env_file)
            
#             # Set environment variables for the build process
#             for key, value in env_vars.items():
#                 os.environ[key] = value
            
#             print_success(f"Environment file applied with {len(env_vars)} variables")
            
#             # Show loaded variables (keys only for security)
#             self._show_loaded_env_vars(target_env_file)
            
#         except Exception as e:
#             print_error(f"Failed to handle environment file: {e}")
#             raise e
    
#     def _show_loaded_env_vars(self, env_file: Path):
#         """Show loaded environment variables (keys only, not values)"""
#         try:
#             content = env_file.read_text()
#             lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
            
#             env_vars = []
#             for line in lines:
#                 if '=' in line:
#                     key = line.split('=')[0].strip()
#                     env_vars.append(key)
            
#             if env_vars:
#                 print_info(f"📋 Loaded {len(env_vars)} environment variables:")
#                 for var in env_vars[:5]:  # Show first 5 to avoid cluttering
#                     print_info(f"  • {var}")
#                 if len(env_vars) > 5:
#                     print_info(f"  ... and {len(env_vars) - 5} more")
            
#         except Exception as e:
#             print_warning(f"Could not read environment variables: {e}")
    
#     def _find_package_json(self, repo_dir: Path) -> Tuple[Path, str]:
#         """Find package.json in repository"""
#         # Check root first
#         if (repo_dir / 'package.json').exists():
#             return repo_dir, "."
        
#         # Search subdirectories
#         for package_file in repo_dir.rglob('package.json'):
#             # Skip node_modules
#             if 'node_modules' in str(package_file):
#                 continue
            
#             project_dir = package_file.parent
#             relative_path = project_dir.relative_to(repo_dir)
            
#             print_info(f"Found package.json in: {relative_path}")
#             return project_dir, str(relative_path).replace('\\', '/')
        
#         raise Exception("No package.json found in repository")
    
#     def _detect_framework_and_build_dir(self, project_dir: Path) -> Tuple[str, str]:
#         """Detect framework and corresponding build directory"""
#         try:
#             package_json = load_json_file(project_dir / 'package.json')
#             dependencies = {
#                 **package_json.get('dependencies', {}),
#                 **package_json.get('devDependencies', {})
#             }
            
#             # Detect framework and build directory
#             if 'vite' in dependencies:
#                 return 'vite', 'dist'
#             elif 'next' in dependencies:
#                 return 'next', '.next'
#             elif '@angular/core' in dependencies:
#                 return 'angular', 'dist'
#             elif 'vue' in dependencies:
#                 return 'vue', 'dist'
#             elif 'react-scripts' in dependencies:
#                 return 'react', 'build'
#             elif 'react' in dependencies:
#                 return 'react', 'build'
#             else:
#                 return 'node', 'dist'
                
#         except Exception:
#             return 'react', 'build'
    
#     def _build_project_robust(self, project_dir: Path, framework: str, build_dir_name: str) -> Path:
#         """Robust build process with automatic dependency resolution"""
#         build_dir = project_dir / build_dir_name
        
#         # Clean existing build
#         if build_dir.exists():
#             shutil.rmtree(build_dir)
        
#         # Fix dependencies and configuration BEFORE building
#         if framework == 'vite':
#             self._prepare_vite_project(project_dir)
#         elif framework == 'react':
#             self._prepare_react_project(project_dir)
        
#         # Install dependencies with multiple strategies
#         self._install_dependencies_robust(project_dir)
        
#         # Build with multiple fallback strategies
#         self._build_with_fallbacks(project_dir, framework)
        
#         # Verify build directory exists
#         if not build_dir.exists():
#             raise Exception(f"Build directory '{build_dir_name}' not created")
        
#         return build_dir
    
#     def _prepare_vite_project(self, project_dir: Path):
#         """Prepare Vite project with all necessary dependencies and config"""
#         try:
#             print_info("Preparing Vite project...")
            
#             # Read existing package.json
#             package_json_path = project_dir / 'package.json'
#             package_json = load_json_file(package_json_path)
            
#             dependencies = {**package_json.get('dependencies', {}), **package_json.get('devDependencies', {})}
            
#             # Auto-install missing Vite dependencies
#             missing_deps = []
            
#             if 'vite' not in dependencies:
#                 missing_deps.append('vite@latest')
            
#             if 'react' in dependencies and '@vitejs/plugin-react' not in dependencies:
#                 missing_deps.append('@vitejs/plugin-react@latest')
            
#             if 'vue' in dependencies and '@vitejs/plugin-vue' not in dependencies:
#                 missing_deps.append('@vitejs/plugin-vue@latest')
            
#             if 'typescript' in package_json.get('scripts', {}).get('build', '') and 'typescript' not in dependencies:
#                 missing_deps.extend(['typescript@latest', '@types/node@latest'])
            
#             # Install missing dependencies
#             if missing_deps:
#                 print_info(f"Installing missing dependencies: {', '.join(missing_deps)}")
#                 run_command(['npm', 'install', '--save-dev'] + missing_deps, cwd=str(project_dir), timeout=180)
#                 print_success("Missing dependencies installed")
            
#             # Create optimized vite.config.js
#             self._create_optimized_vite_config(project_dir, dependencies)
            
#         except Exception as e:
#             print_warning(f"Vite preparation failed: {e}")
    
#     def _create_optimized_vite_config(self, project_dir: Path, dependencies: Dict):
#         """Create optimized Vite configuration for S3 deployment with .env support"""
#         try:
#             vite_config_path = project_dir / 'vite.config.js'
            
#             # Check if .env files exist
#             has_env_files = any([
#                 (project_dir / '.env').exists(),
#                 (project_dir / '.env.local').exists(),
#                 (project_dir / '.env.production').exists()
#             ])
            
#             # Determine available plugins
#             imports = ["import { defineConfig } from 'vite'"]
#             if has_env_files:
#                 imports = ["import { defineConfig, loadEnv } from 'vite'"]
            
#             plugins = []
            
#             if 'react' in dependencies:
#                 if '@vitejs/plugin-react' in dependencies:
#                     imports.append("import react from '@vitejs/plugin-react'")
#                     plugins.append("react()")
#                 else:
#                     print_warning("React detected but @vitejs/plugin-react not available")
            
#             if 'vue' in dependencies:
#                 if '@vitejs/plugin-vue' in dependencies:
#                     imports.append("import vue from '@vitejs/plugin-vue'")
#                     plugins.append("vue()")
            
#             plugins_array = f"[{', '.join(plugins)}]" if plugins else "[]"
            
#             if has_env_files:
#                 config_content = f"""{chr(10).join(imports)}

# export default defineConfig(({{ mode }}) => {{
#   const env = loadEnv(mode, process.cwd(), '')
  
#   return {{
#     base: './',
#     plugins: {plugins_array},
#     build: {{
#       outDir: 'dist',
#       assetsDir: 'assets',
#       sourcemap: false,
#       rollupOptions: {{
#         output: {{
#           manualChunks: undefined
#         }}
#       }}
#     }},
#     define: {{
#       'process.env': JSON.stringify(env)
#     }},
#     server: {{
#       fs: {{
#         strict: false
#       }}
#     }}
#   }}
# }})
# """
#             else:
#                 config_content = f"""{chr(10).join(imports)}

# export default defineConfig({{
#   base: './',
#   plugins: {plugins_array},
#   build: {{
#     outDir: 'dist',
#     assetsDir: 'assets',
#     sourcemap: false,
#     rollupOptions: {{
#       output: {{
#         manualChunks: undefined
#       }}
#     }}
#   }},
#   server: {{
#     fs: {{
#       strict: false
#     }}
#   }}
# }})
# """
            
#             vite_config_path.write_text(config_content)
#             print_success("Created optimized Vite configuration")
            
#         except Exception as e:
#             print_warning(f"Could not create Vite config: {e}")
#             # Create minimal fallback
#             self._create_minimal_vite_config(project_dir)
    
#     def _create_minimal_vite_config(self, project_dir: Path):
#         """Create minimal Vite config that always works"""
#         try:
#             vite_config_path = project_dir / 'vite.config.js'
            
#             minimal_config = """import { defineConfig } from 'vite'

# export default defineConfig({
#   base: './',
#   build: {
#     outDir: 'dist',
#     assetsDir: 'assets',
#     sourcemap: false
#   }
# })
# """
            
#             vite_config_path.write_text(minimal_config)
#             print_info("Created minimal Vite configuration")
            
#         except Exception as e:
#             print_warning(f"Could not create minimal config: {e}")
    
#     def _prepare_react_project(self, project_dir: Path):
#         """Prepare React project for building"""
#         try:
#             print_info("Preparing React project...")
            
#             package_json_path = project_dir / 'package.json'
#             package_json = load_json_file(package_json_path)
            
#             dependencies = {**package_json.get('dependencies', {}), **package_json.get('devDependencies', {})}
            
#             # Auto-install missing React dependencies
#             missing_deps = []
            
#             if 'react' not in dependencies:
#                 missing_deps.extend(['react@latest', 'react-dom@latest'])
            
#             if 'react-scripts' not in dependencies and 'vite' not in dependencies:
#                 missing_deps.append('react-scripts@latest')
            
#             # Install missing dependencies
#             if missing_deps:
#                 print_info(f"Installing missing React dependencies: {', '.join(missing_deps)}")
#                 run_command(['npm', 'install'] + missing_deps, cwd=str(project_dir), timeout=180)
#                 print_success("Missing React dependencies installed")
            
#         except Exception as e:
#             print_warning(f"React preparation failed: {e}")
    
#     def _install_dependencies_robust(self, project_dir: Path):
#         """Robust dependency installation with multiple strategies"""
#         try:
#             # Clear npm cache first
#             try:
#                 run_command(['npm', 'cache', 'clean', '--force'], cwd=str(project_dir), timeout=60)
#             except:
#                 pass
            
#             # Strategy 1: npm ci
#             try:
#                 print_info("Installing dependencies with npm ci...")
#                 run_command(['npm', 'ci'], cwd=str(project_dir), timeout=300)
#                 print_success("Dependencies installed with npm ci")
#                 return
#             except Exception as e:
#                 print_warning(f"npm ci failed: {e}")
            
#             # Strategy 2: npm install
#             try:
#                 print_info("Installing dependencies with npm install...")
#                 run_command(['npm', 'install'], cwd=str(project_dir), timeout=300)
#                 print_success("Dependencies installed with npm install")
#                 return
#             except Exception as e:
#                 print_warning(f"npm install failed: {e}")
            
#             # Strategy 3: npm install --legacy-peer-deps
#             try:
#                 print_info("Installing dependencies with legacy peer deps...")
#                 run_command(['npm', 'install', '--legacy-peer-deps'], cwd=str(project_dir), timeout=300)
#                 print_success("Dependencies installed with legacy peer deps")
#                 return
#             except Exception as e:
#                 print_warning(f"npm install --legacy-peer-deps failed: {e}")
            
#             # Strategy 4: yarn (if available)
#             if check_command_exists('yarn'):
#                 try:
#                     print_info("Installing dependencies with yarn...")
#                     run_command(['yarn', 'install'], cwd=str(project_dir), timeout=300)
#                     print_success("Dependencies installed with yarn")
#                     return
#                 except Exception as e:
#                     print_warning(f"yarn install failed: {e}")
            
#             raise Exception("All dependency installation methods failed")
            
#         except Exception as e:
#             raise Exception(f"Failed to install dependencies: {e}")
    
#     def _build_with_fallbacks(self, project_dir: Path, framework: str):
#         """Build project with enhanced environment variable support"""
#         build_successful = False
        
#         # Set NODE_ENV for production build
#         os.environ['NODE_ENV'] = 'production'
        
#         # Strategy 1: Standard build command with environment variables
#         if not build_successful:
#             try:
#                 print_info("Attempting standard build with environment variables...")
#                 run_command(['npm', 'run', 'build'], cwd=str(project_dir), timeout=600)
#                 build_successful = True
#                 print_success("Standard build completed")
#             except Exception as e:
#                 print_warning(f"Standard build failed: {e}")
        
#         # Strategy 2: Framework-specific commands with env
#         if not build_successful:
#             try:
#                 print_info("Attempting framework-specific build with environment...")
                
#                 if framework == 'vite':
#                     run_command(['npx', 'vite', 'build', '--mode', 'production'], cwd=str(project_dir), timeout=600)
#                 elif framework == 'react':
#                     run_command(['npx', 'react-scripts', 'build'], cwd=str(project_dir), timeout=600)
#                 elif framework == 'next':
#                     run_command(['npx', 'next', 'build'], cwd=str(project_dir), timeout=600)
#                 elif framework == 'angular':
#                     run_command(['npx', 'ng', 'build', '--base-href', './'], cwd=str(project_dir), timeout=600)
#                 else:
#                     run_command(['npm', 'run', 'build'], cwd=str(project_dir), timeout=600)
                
#                 build_successful = True
#                 print_success("Framework-specific build completed")
#             except Exception as e:
#                 print_warning(f"Framework-specific build failed: {e}")
        
#         # Strategy 3: Force build with base path
#         if not build_successful and framework == 'vite':
#             try:
#                 print_info("Attempting Vite build with forced base path...")
#                 run_command(['npx', 'vite', 'build', '--base', './', '--mode', 'production'], cwd=str(project_dir), timeout=600)
#                 build_successful = True
#                 print_success("Forced base path build completed")
#             except Exception as e:
#                 print_warning(f"Forced build failed: {e}")
        
#         # Strategy 4: Build without config but with inline env variables
#         if not build_successful and framework == 'vite':
#             try:
#                 print_info("Attempting build without config but with environment variables...")
                
#                 # Backup and remove vite config
#                 vite_config = project_dir / 'vite.config.js'
#                 backup_config = None
                
#                 if vite_config.exists():
#                     backup_config = project_dir / 'vite.config.js.backup'
#                     vite_config.rename(backup_config)
#                     print_info("Temporarily removed Vite config")
                
#                 # Build with environment variables passed via command line
#                 build_cmd = ['npx', 'vite', 'build', '--base', './', '--mode', 'production']
                
#                 # Add environment variables as defines
#                 for key, value in os.environ.items():
#                     if key.startswith('VITE_'):
#                         build_cmd.extend(['--define', f'import.meta.env.{key}="{value}"'])
                
#                 run_command(build_cmd, cwd=str(project_dir), timeout=600)
#                 build_successful = True
#                 print_success("Build without config completed")
                
#                 # Restore config
#                 if backup_config and backup_config.exists():
#                     backup_config.rename(vite_config)
                
#             except Exception as e:
#                 print_warning(f"Build without config failed: {e}")
#                 # Restore config if it exists
#                 backup_config = project_dir / 'vite.config.js.backup'
#                 if backup_config.exists():
#                     backup_config.rename(project_dir / 'vite.config.js')
        
#         if not build_successful:
#             raise Exception("All build strategies failed")
    
#     def _verify_and_fix_build(self, build_dir: Path) -> bool:
#         """Verify build has content and fix asset paths"""
#         if not build_dir.exists():
#             return False
        
#         # Check for any files
#         files = list(build_dir.rglob('*'))
#         files = [f for f in files if f.is_file()]
        
#         if len(files) == 0:
#             return False
        
#         # Fix asset paths in HTML files
#         self._fix_all_asset_paths(build_dir)
        
#         # Verify we have essential web files
#         web_files = [f for f in files if f.suffix.lower() in ['.html', '.js', '.css']]
#         return len(web_files) > 0
    
#     def _fix_all_asset_paths(self, build_dir: Path):
#         """Fix asset paths in all HTML files for S3 compatibility"""
#         try:
#             # Find all HTML files
#             html_files = list(build_dir.rglob('*.html'))
            
#             for html_file in html_files:
#                 self._fix_single_html_file(html_file)
            
#             if html_files:
#                 print_success(f"Fixed asset paths in {len(html_files)} HTML files")
            
#         except Exception as e:
#             print_warning(f"Could not fix asset paths: {e}")
    
#     def _fix_single_html_file(self, html_file: Path):
#         """Fix asset paths in a single HTML file"""
#         try:
#             content = html_file.read_text(encoding='utf-8')
#             original_content = content
            
#             # Fix script src paths (absolute to relative)
#             content = re.sub(r'<script([^>]*)\ssrc="(/[^"]*)"', r'<script\1 src=".\2"', content)
            
#             # Fix link href paths (CSS and other resources)
#             content = re.sub(r'<link([^>]*)\shref="(/[^"]*)"', r'<link\1 href=".\2"', content)
            
#             # Fix img src paths
#             content = re.sub(r'<img([^>]*)\ssrc="(/[^"]*)"', r'<img\1 src=".\2"', content)
            
#             # Fix any other absolute paths in common attributes
#             content = re.sub(r'(src|href|action)="(/[^"]*)"', r'\1=".\2"', content)
            
#             # Remove problematic base tags that can break S3 hosting
#             content = re.sub(r'<base[^>]*/?>', '', content)
            
#             # Fix any absolute paths in CSS imports or JS
#             content = re.sub(r'url\(/([^)]*)\)', r'url(./\1)', content)
            
#             # Write back if changed
#             if content != original_content:
#                 html_file.write_text(content, encoding='utf-8')
#                 print_info(f"Fixed paths in {html_file.name}")
            
#         except Exception as e:
#             print_warning(f"Could not fix {html_file.name}: {e}")
    
#     def _schedule_cleanup(self, directory: Path):
#         """Schedule cleanup after deployment"""
#         def cleanup_after_delay():
#             time.sleep(30)  # Wait for deployment to complete
#             self._cleanup_directory(directory)
        
#         threading.Thread(target=cleanup_after_delay, daemon=True).start()
    
#     def _cleanup_directory(self, directory: Path):
#         """Clean up directory"""
#         try:
#             if directory.exists():
#                 clean_directory(directory)
#         except:
#             # Move to temp if deletion fails
#             try:
#                 import uuid
#                 temp_path = Path(tempfile.gettempdir()) / f"cleanup-{uuid.uuid4().hex[:8]}"
#                 directory.rename(temp_path)
#             except:
#                 pass  # Silent failure
