import click
import boto3
import json
import time
import sys
import subprocess
import os
from pathlib import Path
import requests
from botocore.exceptions import ClientError

from ..core.utils import (
    print_success, print_error, print_info, print_warning, print_step, print_header
)

# Monitoring configuration
MONITORING_INSTANCE_ID = "i-097272e2689b6c0eb"
AWS_REGION = "ap-south-1"
AWS_PROFILE = "Uzaif"
SSH_KEY_PATH = r"C:\Users\Minfy\Desktop\capstone-devops\minfy-uzaif-capstone-key-pair.pem"

@click.group()
def monitoring():
    """Monitoring server management commands"""
    pass

@monitoring.command()
def start():
    """Start monitoring server and containers"""
    try:
        print_step("MONITORING", "Starting monitoring server...")
        
        # Initialize AWS client with explicit profile
        session = boto3.Session(profile_name=AWS_PROFILE)
        ec2 = session.client('ec2', region_name=AWS_REGION)
        
        # Check current state
        response = ec2.describe_instances(InstanceIds=[MONITORING_INSTANCE_ID])
        instance = response['Reservations'][0]['Instances'][0]
        current_state = instance['State']['Name']
        
        print_info(f"Current instance state: {current_state}")
        
        if current_state == 'stopped':
            # Start instance
            print_info("Starting EC2 instance...")
            ec2.start_instances(InstanceIds=[MONITORING_INSTANCE_ID])
            
            # Wait for running state
            print_info("Waiting for instance to start...")
            waiter = ec2.get_waiter('instance_running')
            waiter.wait(InstanceIds=[MONITORING_INSTANCE_ID])
            print_success("Instance started successfully!")
            
            # Get updated instance info
            response = ec2.describe_instances(InstanceIds=[MONITORING_INSTANCE_ID])
            instance = response['Reservations'][0]['Instances'][0]
        elif current_state == 'running':
            print_info("Instance is already running")
        
        public_ip = instance.get('PublicIpAddress')
        if not public_ip:
            print_error("Instance is running but no public IP assigned")
            return
        
        print_success(f"Instance is running with IP: {public_ip}")
        
        # Wait for SSH to be available
        print_info("Waiting for SSH to be available...")
        time.sleep(30)
        
        # Start monitoring containers via SSH
        print_info("Starting monitoring containers...")
        ssh_success = start_containers_via_ssh(public_ip)
        
        if ssh_success:
            print_success("Monitoring server and containers started!")
            
            # Wait for services to be fully ready
            print_info("Waiting for services to initialize...")
            time.sleep(60)
            
            # Display service URLs
            print_header("MONITORING SERVICES")
            print_info(f"Server IP: {public_ip}")
            print_info(f"Grafana Dashboard: http://{public_ip}:3000")
            print_info(f"Prometheus: http://{public_ip}:9090")
            print_info(f"Node Exporter: http://{public_ip}:9100")
            print_info(f"Blackbox Exporter: http://{public_ip}:9115")
            print_info(f"Alertmanager: http://{public_ip}:9093")
            print_info(f"Discovery Service: http://{public_ip}:8082/metrics")
            
            print_header("LOGIN CREDENTIALS")
            print_info("Grafana: admin/admin123")
            
            # Save configuration
            save_monitoring_config({
                'public_ip': public_ip,
                'instance_id': MONITORING_INSTANCE_ID,
                'status': 'running',
                'started_at': time.time(),
                'grafana_url': f"http://{public_ip}:3000",
                'prometheus_url': f"http://{public_ip}:9090"
            })
            
                
        else:
            print_warning("Instance started but containers may still be starting")
            print_info("Wait a few minutes and check status with: deploy-tool monitoring status")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AuthFailure':
            print_error("AWS authentication failed")
            print_info("Please run: aws sso login --profile Uzaif")
        else:
            print_error(f"AWS Error: {e}")
    except Exception as e:
        print_error(f"Failed to start monitoring: {e}")

@monitoring.command()
def stop():
    """Stop monitoring containers and server"""
    try:
        print_step("MONITORING", "Stopping monitoring...")
        
        # Initialize AWS client
        session = boto3.Session(profile_name=AWS_PROFILE)
        ec2 = session.client('ec2', region_name=AWS_REGION)
        
        # Get current instance info
        response = ec2.describe_instances(InstanceIds=[MONITORING_INSTANCE_ID])
        instance = response['Reservations'][0]['Instances'][0]
        current_state = instance['State']['Name']
        
        print_info(f"Current instance state: {current_state}")
        
        if current_state == 'running':
            public_ip = instance.get('PublicIpAddress')
            
            if public_ip:
                print_info("Stopping monitoring containers...")
                stop_containers_via_ssh(public_ip)
            
            # Stop instance
            print_info("Stopping EC2 instance...")
            ec2.stop_instances(InstanceIds=[MONITORING_INSTANCE_ID])
            
            # Wait for stopped state
            print_info("Waiting for instance to stop...")
            waiter = ec2.get_waiter('instance_stopped')
            waiter.wait(InstanceIds=[MONITORING_INSTANCE_ID])
            print_success("Instance stopped successfully!")
        elif current_state == 'stopped':
            print_info("Instance is already stopped")
        
        print_success("Monitoring server stopped!")
        
        # Update config
        save_monitoring_config({'status': 'stopped', 'stopped_at': time.time()})
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'AuthFailure':
            print_error("AWS authentication failed")
            print_info("Please run: aws sso login --profile Uzaif")
        else:
            print_error(f"AWS Error: {e}")
    except Exception as e:
        print_error(f"Failed to stop monitoring: {e}")

@monitoring.command()
def status():
    """Check monitoring server status"""
    try:
        print_step("MONITORING", "Checking server status...")
        
        # Initialize AWS client
        session = boto3.Session(profile_name=AWS_PROFILE)
        ec2 = session.client('ec2', region_name=AWS_REGION)
        
        response = ec2.describe_instances(InstanceIds=[MONITORING_INSTANCE_ID])
        instance = response['Reservations'][0]['Instances'][0]
        
        state = instance['State']['Name']
        public_ip = instance.get('PublicIpAddress', 'None')
        
        print_header("MONITORING STATUS")
        print_info(f"Instance ID: {MONITORING_INSTANCE_ID}")
        print_info(f"State: {state.upper()}")
        print_info(f"Public IP: {public_ip}")
        
        if state == 'running' and public_ip != 'None':
            print_success(" Server is running!")
            
            print_header("ACCESS URLS")
            print_info(f"Grafana: http://{public_ip}:3000")
            print_info(f"Prometheus: http://{public_ip}:9090")
            print_info("Login: admin/admin123")
            
            # Save current IP
            save_monitoring_config({
                'public_ip': public_ip, 
                'instance_id': MONITORING_INSTANCE_ID,
                'status': 'running',
                'last_checked': time.time()
            })
        elif state == 'stopped':
            print_warning(" Server is stopped")
            print_info("Start with: deploy-tool monitoring start")
        elif state == 'pending':
            print_info(" Server is starting...")
        elif state == 'stopping':
            print_info(" Server is stopping...")
        else:
            print_warning(f"  Server is {state}")
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'AuthFailure':
            print_error("AWS authentication failed")
            print_info("Please run: aws sso login --profile Uzaif")
        else:
            print_error(f"AWS Error: {e}")
    except Exception as e:
        print_error(f"Failed to check status: {e}")

@monitoring.command()
def urls():
    """Get monitoring service URLs"""
    try:
        # Initialize AWS client
        session = boto3.Session(profile_name=AWS_PROFILE)
        ec2 = session.client('ec2', region_name=AWS_REGION)
        
        response = ec2.describe_instances(InstanceIds=[MONITORING_INSTANCE_ID])
        instance = response['Reservations'][0]['Instances'][0]
        
        state = instance['State']['Name']
        
        if state != 'running':
            print_warning(f"Server is {state}")
            print_info("Start server with: deploy-tool monitoring start")
            return
        
        public_ip = instance.get('PublicIpAddress')
        if not public_ip:
            print_error("No public IP available")
            return
        
        print_header("MONITORING SERVICE URLS")
        print_info(f" Grafana Dashboard: http://{public_ip}:3000")
        print_info(f" Prometheus: http://{public_ip}:9090")
        print_info(f" Node Exporter: http://{public_ip}:9100")
        print_info(f" Blackbox Exporter: http://{public_ip}:9115")
        print_info(f" Alertmanager: http://{public_ip}:9093")
        print_info(f" Discovery Service: http://{public_ip}:8082/metrics")
        
        print_header("LOGIN CREDENTIALS")
        print_info(" Grafana: admin / admin123")
        
        print_header("QUICK ACTIONS")
        print_info(" Open dashboard: deploy-tool monitoring dashboard")
        print_info(" Check discovered apps: deploy-tool monitoring discovered")
        print_info(" Check status: deploy-tool monitoring status")
        
        # Save current IP
        save_monitoring_config({
            'public_ip': public_ip, 
            'instance_id': MONITORING_INSTANCE_ID,
            'status': 'running',
            'urls_checked': time.time()
        })
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'AuthFailure':
            print_error("AWS authentication failed")
            print_info("Please run: aws sso login --profile Uzaif")
        else:
            print_error(f"AWS Error: {e}")
    except Exception as e:
        print_error(f"Failed to get URLs: {e}")

@monitoring.command()
def dashboard():
    """Open Grafana dashboard in browser"""
    try:
        # Initialize AWS client
        session = boto3.Session(profile_name=AWS_PROFILE)
        ec2 = session.client('ec2', region_name=AWS_REGION)
        
        response = ec2.describe_instances(InstanceIds=[MONITORING_INSTANCE_ID])
        instance = response['Reservations'][0]['Instances'][0]
        
        if instance['State']['Name'] != 'running':
            print_error("Monitoring server is not running")
            print_info("Start with: deploy-tool monitoring start")
            return
        
        public_ip = instance.get('PublicIpAddress')
        if not public_ip:
            print_error("No public IP found")
            return
        
        url = f"http://{public_ip}:3000"
        print_info(f" Opening Grafana: {url}")
        print_info(" Login: admin / admin123")
        
        # Check if Grafana is accessible before opening browser
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print_success(" Grafana is accessible")
            else:
                print_warning("  Grafana may not be fully ready yet")
        except:
            print_warning("  Grafana is not responding - it may still be starting")
        
        import webbrowser
        webbrowser.open(url)
        
    except Exception as e:
        print_error(f"Failed to open dashboard: {e}")

@monitoring.command()
def discovered():
    """List auto-discovered applications"""
    try:
        # Get monitoring config
        session = boto3.Session(profile_name=AWS_PROFILE)
        ec2 = session.client('ec2', region_name=AWS_REGION)
        
        response = ec2.describe_instances(InstanceIds=[MONITORING_INSTANCE_ID])
        instance = response['Reservations'][0]['Instances'][0]
        
        if instance['State']['Name'] != 'running':
            print_error("Monitoring server is not running")
            print_info("Start with: deploy-tool monitoring start")
            return
        
        public_ip = instance.get('PublicIpAddress')
        if not public_ip:
            print_error("No public IP found")
            return
        
        print_step("DISCOVERY", "Checking auto-discovered applications...")
        
        # Get discovered apps from discovery service
        try:
            response = requests.get(f"http://{public_ip}:8082/metrics", timeout=10)
            if response.status_code == 200:
                metrics_text = response.text
                
                # Parse discovered deployments count
                discovered_count = 0
                for line in metrics_text.split('\n'):
                    if line.startswith('discovered_deployments_total'):
                        discovered_count = int(float(line.split()[-1]))
                        break
                
                print_success(f"🔍 Discovery service found {discovered_count} applications")
                
                # Get detailed info from targets file
                ssh_key = get_ssh_key()
                if ssh_key:
                    ssh_cmd = [
                        'ssh', '-i', ssh_key,
                        '-o', 'StrictHostKeyChecking=no',
                        '-o', 'ConnectTimeout=10',
                        f'ec2-user@{public_ip}',
                        'cat /home/ec2-user/monitoring/targets/auto_discovered_websites.json 2>/dev/null || echo "[]"'
                    ]
                    
                    result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        try:
                            targets = json.loads(result.stdout)
                            if targets:
                                print_header("DISCOVERED APPLICATIONS")
                                for i, target in enumerate(targets, 1):
                                    labels = target.get('labels', {})
                                    project = labels.get('project', 'Unknown')
                                    framework = labels.get('framework', 'Unknown')
                                    url = target.get('targets', ['Unknown'])[0]
                                    last_modified = labels.get('last_modified', 'Unknown')
                                    
                                    print_info(f" {i}. {project} ({framework})")
                                    print_info(f"    URL: {url}")
                                    print_info(f"    Last Modified: {last_modified}")
                                    print_info("")
                            else:
                                print_info(" No applications discovered yet")
                                print_info(" Deploy an application to see it appear automatically!")
                        except json.JSONDecodeError:
                            print_warning("  Could not parse discovery data")
                            
            else:
                print_warning("  Discovery service not responding")
                print_info("Check service status with: deploy-tool monitoring status")
                
        except requests.RequestException:
            print_error(" Cannot reach discovery service")
            print_info("Ensure monitoring services are running")
            
    except Exception as e:
        print_error(f"Failed to get discovered apps: {e}")

@monitoring.command()
def logs():
    """View monitoring service logs"""
    try:
        session = boto3.Session(profile_name=AWS_PROFILE)
        ec2 = session.client('ec2', region_name=AWS_REGION)
        
        response = ec2.describe_instances(InstanceIds=[MONITORING_INSTANCE_ID])
        instance = response['Reservations'][0]['Instances'][0]
        
        if instance['State']['Name'] != 'running':
            print_error("Monitoring server is not running")
            return
        
        public_ip = instance.get('PublicIpAddress')
        if not public_ip:
            print_error("No public IP found")
            return
        
        print_step("LOGS", "Fetching monitoring service logs...")
        
        ssh_key = get_ssh_key()
        if not ssh_key:
            return
        
        # Get Docker Compose logs
        ssh_cmd = [
            'ssh', '-i', ssh_key,
            '-o', 'StrictHostKeyChecking=no',
            f'ec2-user@{public_ip}',
            'cd /home/ec2-user/monitoring && docker-compose logs --tail=50'
        ]
        
        print_info(" Recent monitoring service logs:")
        print_info("=" * 60)
        subprocess.run(ssh_cmd)
        
    except Exception as e:
        print_error(f"Failed to fetch logs: {e}")

# Helper functions
def start_containers_via_ssh(public_ip):
    """Start monitoring containers via SSH"""
    try:
        ssh_key = get_ssh_key()
        if not ssh_key:
            return False
        
        print_info(f"Connecting to {public_ip} via SSH...")
        
        ssh_cmd = [
            'ssh', 
            '-i', ssh_key,
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=30',
            '-o', 'ServerAliveInterval=60',
            f'ec2-user@{public_ip}',
            'cd /home/ec2-user/monitoring && docker-compose up -d'
        ]
        
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print_success(" Containers started successfully")
            return True
        else:
            print_warning(f"  Container startup may have issues:")
            if result.stderr:
                print_info(result.stderr)
            return False
        
    except subprocess.TimeoutExpired:
        print_warning(" SSH command timed out - containers may still be starting")
        return False
    except Exception as e:
        print_error(f" SSH command failed: {e}")
        return False

def stop_containers_via_ssh(public_ip):
    """Stop monitoring containers via SSH"""
    try:
        ssh_key = get_ssh_key()
        if not ssh_key:
            return
        
        ssh_cmd = [
            'ssh', 
            '-i', ssh_key,
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=10',
            f'ec2-user@{public_ip}',
            'cd /home/ec2-user/monitoring && docker-compose down'
        ]
        
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print_success(" Containers stopped successfully")
        else:
            print_warning("  Some containers may still be running")
        
    except Exception as e:
        print_warning(f"  SSH stop command failed: {e}")

def check_container_status(public_ip):
    """Check status of monitoring containers"""
    services = {
        'Grafana': 3000,
        'Prometheus': 9090,
        'Node Exporter': 9100,
        'Blackbox Exporter': 9115,
        'Alertmanager': 9093,
        'Discovery Service': 8082
    }
    
    status = {}
    for service, port in services.items():
        try:
            response = requests.get(f'http://{public_ip}:{port}', timeout=5)
            status[service] = response.status_code == 200
        except:
            status[service] = False
    
    return status

def get_ssh_key():
    """Get SSH key path"""
    if os.path.exists(SSH_KEY_PATH):
        return SSH_KEY_PATH
    else:
        print_error(f" SSH key not found at: {SSH_KEY_PATH}")
        print_info("Please ensure the SSH key file exists at the specified location")
        return None

def save_monitoring_config(config):
    """Save monitoring configuration"""
    try:
        config_dir = Path.home() / '.deploy-tool'
        config_dir.mkdir(exist_ok=True)
        
        config_file = config_dir / 'monitoring.json'
        
        # Load existing config and update
        existing_config = {}
        if config_file.exists():
            with open(config_file, 'r') as f:
                existing_config = json.load(f)
        
        existing_config.update(config)
        existing_config['last_updated'] = time.time()
        
        with open(config_file, 'w') as f:
            json.dump(existing_config, f, indent=2)
            
    except Exception as e:
        print_warning(f"  Could not save config: {e}")

def load_monitoring_config():
    """Load monitoring configuration"""
    try:
        config_file = Path.home() / '.deploy-tool' / 'monitoring.json'
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print_warning(f"  Could not load config: {e}")
    return {}
