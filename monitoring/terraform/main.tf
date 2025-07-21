provider "aws" {
  region  = "ap-south-1"
  profile = "Uzaif"
}

# Data source for default VPC
data "aws_vpc" "default" {
  default = true
}

# IAM Role for Monitoring Server
resource "aws_iam_role" "minfy_capstone_monitoring_role" {
  name = "minfy-uzaif-capstone-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name    = "minfy-uzaif-capstone-monitoring-role"
    Project = "DevOps Capstone"
    Type    = "Monitoring"
  }
}

# IAM Policy for CloudWatch and EC2 monitoring
resource "aws_iam_role_policy" "minfy_capstone_monitoring_policy" {
  name = "minfy-uzaif-capstone-monitoring-policy"
  role = aws_iam_role.minfy_capstone_monitoring_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:GetMetricData",
          "cloudwatch:ListMetrics",
          "cloudwatch:PutMetricData",
          "cloudwatch:GetDashboard",
          "cloudwatch:ListDashboards",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeRegions",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeVolumes",
          "ec2:DescribeSnapshots",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketNotification",
          "s3:GetBucketWebsite",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:DescribeLogGroups",
          "logs:GetLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::minfy-uzaif-capstone-deployments",
          "arn:aws:s3:::minfy-uzaif-capstone-deployments/*"
        ]
      }
    ]
  })
}

# Attach CloudWatch Agent policy
resource "aws_iam_role_policy_attachment" "cloudwatch_agent_policy" {
  role       = aws_iam_role.minfy_capstone_monitoring_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# Attach SSM policy for systems manager
resource "aws_iam_role_policy_attachment" "ssm_managed_instance_core" {
  role       = aws_iam_role.minfy_capstone_monitoring_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "minfy_capstone_monitoring_profile" {
  name = "minfy-uzaif-capstone-monitoring-profile"
  role = aws_iam_role.minfy_capstone_monitoring_role.name

  tags = {
    Name    = "minfy-uzaif-capstone-monitoring-profile"
    Project = "DevOps Capstone"
    Type    = "Monitoring"
  }
}

# Security Group for Monitoring Server
resource "aws_security_group" "minfy_capstone_monitoring_sg" {
  name        = "minfy-uzaif-capstone-monitoring-sg"
  description = "Security group for monitoring server"
  vpc_id      = data.aws_vpc.default.id

  # SSH access
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Prometheus
  ingress {
    description = "Prometheus"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Grafana
  ingress {
    description = "Grafana"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Node Exporter
  ingress {
    description = "Node Exporter"
    from_port   = 9100
    to_port     = 9100
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Blackbox Exporter
  ingress {
    description = "Blackbox Exporter"
    from_port   = 9115
    to_port     = 9115
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Alertmanager
  ingress {
    description = "Alertmanager"
    from_port   = 9093
    to_port     = 9093
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Custom Metrics Server
  ingress {
    description = "Custom Metrics"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "minfy-uzaif-capstone-monitoring-sg"
    Project = "DevOps Capstone"
    Type    = "Monitoring"
  }
}

# Monitoring Server - Cost Optimized
resource "aws_instance" "minfy_capstone_monitoring" {
  ami                    = "ami-0a1235697f4afa8a4"
  instance_type          = "t3.small"
  key_name              = "minfy-uzaif-capstone-key-pair"
  iam_instance_profile  = aws_iam_instance_profile.minfy_capstone_monitoring_profile.name
  vpc_security_group_ids = [aws_security_group.minfy_capstone_monitoring_sg.id]

  user_data_base64 = base64encode(<<-EOF
              #!/bin/bash
              yum update -y
              yum install -y docker git python3 python3-pip
              systemctl start docker
              systemctl enable docker
              usermod -aG docker ec2-user
              
              # Install Docker Compose
              curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
              chmod +x /usr/local/bin/docker-compose
              
              # Create monitoring directory
              mkdir -p /home/ec2-user/monitoring
              chown ec2-user:ec2-user /home/ec2-user/monitoring
              
              # Configure AWS environment
              cat > /etc/environment << 'EOL'
              AWS_DEFAULT_REGION=ap-south-1
              AWS_REGION=ap-south-1
              EOL
              
              echo "Monitoring server setup completed" > /home/ec2-user/setup-complete.log
              EOF
  )

  tags = {
    Name    = "minfy-uzaif-capstone-monitoring"
    Project = "DevOps Capstone"
    Type    = "Monitoring"
    Size    = "t3.small"
  }
}

# Output the public IP for easy access
output "monitoring_server_public_ip" {
  description = "Public IP address of the monitoring server"
  value       = aws_instance.minfy_capstone_monitoring.public_ip
}

output "monitoring_server_id" {
  description = "Instance ID of the monitoring server"
  value       = aws_instance.minfy_capstone_monitoring.id
}

output "grafana_url" {
  description = "Grafana dashboard URL"
  value       = "http://${aws_instance.minfy_capstone_monitoring.public_ip}:3000"
}

output "prometheus_url" {
  description = "Prometheus URL"
  value       = "http://${aws_instance.minfy_capstone_monitoring.public_ip}:9090"
}
