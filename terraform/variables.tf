variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "ap-south-1"
}

variable "aws_profile" {
  description = "AWS profile for SSO authentication"
  type        = string
  default     = "Uzaif"
}

variable "infrastructure_prefix" {
  description = "Prefix for all AWS infrastructure resources"
  type        = string
  default     = "minfy-uzaif-capstone"
  
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.infrastructure_prefix))
    error_message = "Infrastructure prefix must follow AWS naming conventions: lowercase letters, numbers, and hyphens only."
  }
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "enable_versioning" {
  description = "Enable S3 bucket versioning"
  type        = bool
  default     = true
}

variable "max_versions_to_keep" {
  description = "Maximum number of versions to keep per project"
  type        = number
  default     = 10
}

variable "availability_zones" {
  description = "Available AZs in ap-south-1 region"
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
}
