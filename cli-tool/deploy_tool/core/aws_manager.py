import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path
from typing import Dict, List
import mimetypes
import json

from .utils import (
    print_info, print_error, print_warning, print_success, print_step,
    format_file_size, get_directory_size
)
from ..config.constants import INFRASTRUCTURE_BUCKET

class AWSManager:
    """Enhanced S3 manager with proper website hosting configuration"""
    
    def __init__(self, profile: str, region: str):
        self.profile = profile
        self.region = region
        self.bucket_name = INFRASTRUCTURE_BUCKET
        self.session = None
        self.s3_client = None
        self._initialize_session()
        self._setup_website_hosting()
    
    def _initialize_session(self) -> None:
        """Initialize AWS session"""
        try:
            self.session = boto3.Session(profile_name=self.profile)
            self.s3_client = self.session.client('s3', region_name=self.region)
        except Exception as e:
            raise Exception(f"Failed to initialize AWS session: {str(e)}")
    
    def validate_credentials(self) -> bool:
        """Validate AWS credentials"""
        try:
            sts = self.session.client('sts')
            identity = sts.get_caller_identity()
            print_info(f"Authenticated as: {identity.get('Arn', 'Unknown')}")
            return True
        except (ClientError, NoCredentialsError):
            return False
        except Exception:
            return False
    
    def _setup_website_hosting(self) -> None:
        """Setup S3 bucket for static website hosting"""
        try:
            # Configure static website hosting
            self.s3_client.put_bucket_website(
                Bucket=self.bucket_name,
                WebsiteConfiguration={
                    'IndexDocument': {'Suffix': 'index.html'},
                    'ErrorDocument': {'Key': 'index.html'}
                }
            )
            
            # Set public read policy
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicReadGetObject",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{self.bucket_name}/*"
                    }
                ]
            }
            
            self.s3_client.put_bucket_policy(
                Bucket=self.bucket_name,
                Policy=json.dumps(policy)
            )
            
            # Ensure public access block is disabled for website hosting
            try:
                self.s3_client.delete_public_access_block(Bucket=self.bucket_name)
            except:
                pass  # May not exist
            
        except Exception:
            pass  # Silent setup
    
    def deploy_version(self, project_name: str, version: str, build_dir: Path) -> Dict:
        """Upload build files to S3 with proper content types"""
        try:
            version_prefix = f"{project_name}/builds/{version}/"
            
            print_step("UPLOAD", "Uploading files to S3...")
            
            # Get all files from build directory
            files_to_upload = list(build_dir.rglob('*'))
            files_to_upload = [f for f in files_to_upload if f.is_file()]
            
            if not files_to_upload:
                raise Exception("No files found in build directory")
            
            uploaded_files = 0
            total_size = 0
            
            # Upload each file with proper content type and caching
            for file_path in files_to_upload:
                relative_path = file_path.relative_to(build_dir)
                s3_key = f"{version_prefix}{relative_path}".replace('\\', '/')
                
                # Get enhanced content type
                content_type = self._get_enhanced_content_type(file_path)
                cache_control = self._get_cache_control(file_path)
                
                # Upload file
                self.s3_client.upload_file(
                    str(file_path),
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={
                        'ContentType': content_type,
                        'CacheControl': cache_control
                    }
                )
                
                uploaded_files += 1
                total_size += file_path.stat().st_size
                
                # Show progress
                if uploaded_files % 5 == 0:
                    print_info(f"Uploaded {uploaded_files}/{len(files_to_upload)} files...")
            
            print_success(f"Uploaded {uploaded_files} files ({format_file_size(total_size)})")
            
            return {
                'version': version,
                'uploaded_files': uploaded_files,
                'total_size': total_size,
                'website_url': f"http://{self.bucket_name}.s3-website.{self.region}.amazonaws.com/{project_name}/current/"
            }
            
        except Exception as e:
            raise Exception(f"Failed to upload files: {str(e)}")
    
    def _get_enhanced_content_type(self, file_path: Path) -> str:
        """Get proper content type for web files"""
        # Try mimetypes first
        content_type, _ = mimetypes.guess_type(str(file_path))
        if content_type:
            return content_type
        
        # Enhanced content type mapping
        suffix = file_path.suffix.lower()
        content_types = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.mjs': 'application/javascript; charset=utf-8',
            '.jsx': 'application/javascript; charset=utf-8',
            '.ts': 'application/javascript; charset=utf-8',
            '.tsx': 'application/javascript; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
            '.xml': 'application/xml; charset=utf-8',
            '.txt': 'text/plain; charset=utf-8',
            '.md': 'text/markdown; charset=utf-8',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.webp': 'image/webp',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
            '.eot': 'application/vnd.ms-fontobject'
        }
        
        return content_types.get(suffix, 'binary/octet-stream')
    
    def _get_cache_control(self, file_path: Path) -> str:
        """Get appropriate cache control headers"""
        suffix = file_path.suffix.lower()
        
        # Static assets - long cache
        if suffix in ['.js', '.css', '.png', '.jpg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf']:
            return 'public, max-age=31536000, immutable'
        # HTML files - no cache
        elif suffix == '.html':
            return 'public, max-age=0, must-revalidate'
        # JSON and other data files - short cache
        elif suffix in ['.json', '.xml', '.txt']:
            return 'public, max-age=3600'
        # Default
        else:
            return 'public, max-age=86400'
    
    def activate_version(self, project_name: str, version: str) -> Dict:
        """Make version live by copying to current/"""
        try:
            source_prefix = f"{project_name}/builds/{version}/"
            current_prefix = f"{project_name}/current/"
            
            print_step("ACTIVATE", "Making version live...")
            
            # Delete current files
            self._clear_prefix(current_prefix)
            
            # Copy new version to current
            copied_files = self._copy_s3_prefix(source_prefix, current_prefix)
            
            print_success(f"Website is now live ({copied_files} files)")
            
            return {
                'version': version,
                'copied_files': copied_files,
                'website_url': f"http://{self.bucket_name}.s3-website.{self.region}.amazonaws.com/{project_name}/current/"
            }
            
        except Exception as e:
            raise Exception(f"Failed to activate version: {str(e)}")
    
    def _clear_prefix(self, prefix: str) -> None:
        """Delete all objects with given prefix"""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            
            objects_to_delete = []
            for page in pages:
                for obj in page.get('Contents', []):
                    objects_to_delete.append({'Key': obj['Key']})
            
            if objects_to_delete:
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i:i+1000]
                    self.s3_client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': batch, 'Quiet': True}
                    )
        except Exception:
            pass
    
    def _copy_s3_prefix(self, source_prefix: str, dest_prefix: str) -> int:
        """Copy all objects from source prefix to destination prefix"""
        copied_files = 0
        
        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=source_prefix)
        
        for page in pages:
            for obj in page.get('Contents', []):
                source_key = obj['Key']
                relative_key = source_key[len(source_prefix):]
                dest_key = f"{dest_prefix}{relative_key}"
                
                # Copy with metadata preservation
                self.s3_client.copy_object(
                    CopySource={'Bucket': self.bucket_name, 'Key': source_key},
                    Bucket=self.bucket_name,
                    Key=dest_key,
                    MetadataDirective='COPY'
                )
                copied_files += 1
        
        return copied_files
    
    def list_versions(self, project_name: str) -> List[str]:
        """List available versions"""
        try:
            builds_prefix = f"{project_name}/builds/"
            versions = []
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=builds_prefix,
                Delimiter='/'
            )
            
            for page in pages:
                for prefix_info in page.get('CommonPrefixes', []):
                    prefix = prefix_info['Prefix']
                    version = prefix[len(builds_prefix):].rstrip('/')
                    if version:
                        versions.append(version)
            
            return sorted(versions, reverse=True)
            
        except Exception as e:
            raise Exception(f"Failed to list versions: {str(e)}")
    
    def get_project_status(self, project_name: str) -> Dict:
        """Get project status"""
        try:
            current_prefix = f"{project_name}/current/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=current_prefix,
                MaxKeys=1
            )
            
            is_deployed = 'Contents' in response and len(response['Contents']) > 0
            website_url = f"http://{self.bucket_name}.s3-website.{self.region}.amazonaws.com/{project_name}/current/"
            
            return {
                'is_deployed': is_deployed,
                'website_url': website_url if is_deployed else None,
                'bucket': self.bucket_name,
                'region': self.region
            }
            
        except Exception as e:
            return {'is_deployed': False, 'error': str(e)}
    
    def cleanup_old_versions(self, project_name: str, keep_count: int) -> int:
        """Cleanup old versions"""
        try:
            versions = self.list_versions(project_name)
            
            if len(versions) <= keep_count:
                return 0
            
            versions_to_delete = versions[keep_count:]
            deleted_count = 0
            
            for version in versions_to_delete:
                self._clear_prefix(f"{project_name}/builds/{version}/")
                deleted_count += 1
            
            return deleted_count
            
        except Exception as e:
            raise Exception(f"Failed to cleanup versions: {str(e)}")
