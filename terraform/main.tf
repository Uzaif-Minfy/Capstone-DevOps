terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket  = "minfy-uzaif-capstone-terraform-state"
    key     = "capstone/terraform.tfstate"
    region  = "ap-south-1"
    profile = "Uzaif"
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = "DevOps-Capstone"
      Environment = var.environment
      Owner       = "Uzaif"
      ManagedBy   = "Terraform"
      Region      = "ap-south-1"
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for AWS region
data "aws_region" "current" {}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}
