#!/usr/bin/env python3
"""
Automatic S3 Deployment Discovery Service
Continuously monitors S3 bucket for new deployments and updates monitoring targets
"""

import time
import json
import logging
import boto3
from datetime import datetime
from pathlib import Path
from prometheus_client import Counter, Gauge, start_http_server
import requests

# Prometheus metrics for discovery service
discovered_deployments = Gauge('discovered_deployments_total', 'Number of discovered deployments')
discovery_errors = Counter('discovery_errors_total', 'Discovery service errors')
last_discovery_time = Gauge('last_discovery_timestamp', 'Timestamp of last discovery run')

class S3DeploymentDiscovery:
    def __init__(self, bucket_name, region, targets_dir='/opt/monitoring/targets'):
        self.bucket_name = bucket_name
        self.region = region
        self.targets_dir = Path(targets_dir)
        self.targets_dir.mkdir(exist_ok=True)

        # Initialize AWS client
        self.s3_client = boto3.client('s3', region_name=region)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # Track previous discoveries for change detection
        self.previous_deployments = set()

    def discover_and_update(self):
        """Main discovery and update cycle"""
        try:
            self.logger.info("Starting S3 deployment discovery...")

            # Discover active deployments
            deployments = self.discover_deployments()

            # Check for changes
            current_deployments = {dep['project'] for dep in deployments}

            if current_deployments != self.previous_deployments:
                self.logger.info(f"Deployment changes detected. New: {current_deployments - self.previous_deployments}, Removed: {self.previous_deployments - current_deployments}")

                # Update monitoring targets
                self.update_prometheus_targets(deployments)
                self.update_grafana_variables(deployments)

                # Trigger Prometheus reload
                self.reload_prometheus_config()

                self.previous_deployments = current_deployments

            # Update metrics
            discovered_deployments.set(len(deployments))
            last_discovery_time.set(time.time())

            self.logger.info(f"Discovery complete. Found {len(deployments)} active deployments")

        except Exception as e:
            discovery_errors.inc()
            self.logger.error(f"Discovery error: {e}")

    def discover_deployments(self):
        """Discover all current deployments in S3"""
        deployments = []

        try:
            # List all top-level prefixes (projects)
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix='',
                Delimiter='/'
            )

            for page in pages:
                for prefix in page.get('CommonPrefixes', []):
                    project_name = prefix['Prefix'].rstrip('/')

                    # Skip if empty project name
                    if not project_name:
                        continue

                    # Check if project has a current deployment
                    if self._has_current_deployment(project_name):
                        deployment_info = self._get_deployment_info(project_name)
                        deployments.append(deployment_info)
                        self.logger.debug(f"Discovered deployment: {project_name}")

        except Exception as e:
            self.logger.error(f"Error discovering deployments: {e}")

        return deployments

    def _has_current_deployment(self, project_name):
        """Check if project has a current deployment"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{project_name}/current/",
                MaxKeys=1
            )
            return 'Contents' in response and len(response['Contents']) > 0
        except Exception as e:
            self.logger.error(f"Error checking current deployment for {project_name}: {e}")
            return False

    def _get_deployment_info(self, project_name):
        """Get detailed deployment information"""
        deployment_url = f"http://{self.bucket_name}.s3-website.{self.region}.amazonaws.com/{project_name}/current/"

        # Get deployment metadata
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{project_name}/current/"
            )

            contents = response.get('Contents', [])
            file_count = len(contents)
            total_size = sum(obj['Size'] for obj in contents)
            last_modified = max(obj['LastModified'] for obj in contents) if contents else datetime.now()

            # Detect framework type from file extensions
            framework = self._detect_framework(contents)

        except Exception as e:
            self.logger.error(f"Error getting deployment info for {project_name}: {e}")
            file_count = 0
            total_size = 0
            last_modified = datetime.now()
            framework = 'unknown'

        return {
            'project': project_name,
            'url': deployment_url,
            'file_count': file_count,
            'total_size': total_size,
            'last_modified': last_modified.isoformat(),
            'framework': framework,
            'monitor_type': 'website'
        }

    def _detect_framework(self, contents):
        """Detect framework type from deployment files"""
        filenames = [obj['Key'].split('/')[-1] for obj in contents]

        # React/Vite detection
        if any('chunk' in f for f in filenames) and any(f.endswith('.js') for f in filenames):
            return 'react'
        # Next.js detection
        elif any('_next' in obj['Key'] for obj in contents):
            return 'nextjs'
        # Angular detection
        elif any(f.startswith('main.') and f.endswith('.js') for f in filenames):
            return 'angular'
        # Vue detection
        elif any(f.startswith('app.') and f.endswith('.js') for f in filenames):
            return 'vue'
        else:
            return 'static'

    def update_prometheus_targets(self, deployments):
        """Update Prometheus target configuration"""
        targets = []

        for deployment in deployments:
            targets.append({
                'targets': [deployment['url']],
                'labels': {
                    'project': deployment['project'],
                    'framework': deployment['framework'],
                    'environment': 'production',
                    'monitor_type': deployment['monitor_type'],
                    'auto_discovered': 'true',
                    'last_modified': deployment['last_modified']
                }
            })

        # Write targets file for Prometheus file service discovery
        target_file = self.targets_dir / 'auto_discovered_websites.json'
        with open(target_file, 'w') as f:
            json.dump(targets, f, indent=2)

        self.logger.info(f"Updated Prometheus targets: {len(targets)} websites")

        # Also create a backup with timestamp
        backup_file = self.targets_dir / f'targets_backup_{int(time.time())}.json'
        with open(backup_file, 'w') as f:
            json.dump(targets, f, indent=2)

    def update_grafana_variables(self, deployments):
        """Update Grafana dashboard variables"""
        projects = sorted([dep['project'] for dep in deployments])
        frameworks = sorted(list(set([dep['framework'] for dep in deployments])))

        # Create variable file for Grafana
        variables_data = {
            'projects': projects,
            'frameworks': frameworks,
            'total_deployments': len(deployments),
            'last_updated': datetime.now().isoformat(),
            'deployments': deployments
        }

        variables_file = self.targets_dir / 'grafana_variables.json'
        with open(variables_file, 'w') as f:
            json.dump(variables_data, f, indent=2)

        self.logger.info(f"Updated Grafana variables: {len(projects)} projects, {len(frameworks)} frameworks")

    def reload_prometheus_config(self):
        """Trigger Prometheus configuration reload"""
        try:
            # Send reload signal to Prometheus
            response = requests.post('http://prometheus:9090/-/reload', timeout=5)
            if response.status_code == 200:
                self.logger.info("Prometheus configuration reloaded successfully")
            else:
                self.logger.warning(f"Prometheus reload returned status: {response.status_code}")
        except Exception as e:
            self.logger.error(f"Failed to reload Prometheus config: {e}")

    def run_continuous_discovery(self, interval=60):
        """Run continuous discovery service"""
        self.logger.info(f"Starting S3 deployment discovery service")
        self.logger.info(f"Monitoring bucket: {self.bucket_name}")
        self.logger.info(f"Discovery interval: {interval} seconds")

        # Run initial discovery
        self.discover_and_update()

        while True:
            try:
                time.sleep(interval)
                self.discover_and_update()
            except KeyboardInterrupt:
                self.logger.info("Discovery service stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in discovery loop: {e}")
                time.sleep(interval)

def main():
    # Start Prometheus metrics server for discovery service
    start_http_server(8082)
    print("Discovery service metrics available on port 8082")

    # Initialize discovery service
    discovery = S3DeploymentDiscovery(
        bucket_name='minfy-uzaif-capstone-deployments',
        region='ap-south-1'
    )

    # Run continuous discovery
    discovery.run_continuous_discovery(interval=30)

if __name__ == '__main__':
    main()
