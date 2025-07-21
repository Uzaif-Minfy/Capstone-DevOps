output "deployment_bucket_name" {
  description = "Name of the main deployment S3 bucket"
  value       = aws_s3_bucket.deployments.bucket
}

output "deployment_bucket_arn" {
  description = "ARN of the deployment bucket"
  value       = aws_s3_bucket.deployments.arn
}

output "website_endpoint" {
  description = "S3 website endpoint for ap-south-1"
  value       = aws_s3_bucket_website_configuration.deployments_website.website_endpoint
}

output "bucket_domain_name" {
  description = "Bucket domain name"
  value       = aws_s3_bucket.deployments.bucket_domain_name
}

output "website_domain" {
  description = "Complete S3 website URL"
  value       = "http://${aws_s3_bucket.deployments.bucket}.s3-website.ap-south-1.amazonaws.com"
}

output "aws_region" {
  description = "AWS region used"
  value       = data.aws_region.current.name
}

output "aws_account_id" {
  description = "AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "available_zones" {
  description = "Available zones in ap-south-1"
  value       = data.aws_availability_zones.available.names
}

output "infrastructure_prefix" {
  description = "Infrastructure prefix used for naming"
  value       = var.infrastructure_prefix
}
