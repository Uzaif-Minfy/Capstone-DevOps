# Main deployment bucket for all projects
resource "aws_s3_bucket" "deployments" {
  bucket        = "${var.infrastructure_prefix}-deployments"
  force_destroy = false

  tags = {
    Name        = "${var.infrastructure_prefix}-deployments"
    Purpose     = "Multi-project deployment storage"
    Environment = var.environment
    Region      = "ap-south-1"
  }
}

# Bucket versioning configuration
resource "aws_s3_bucket_versioning" "deployments_versioning" {
  bucket = aws_s3_bucket.deployments.id
  
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

# Bucket public access block
resource "aws_s3_bucket_public_access_block" "deployments_pab" {
  bucket = aws_s3_bucket.deployments.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# Bucket policy for public read access to deployed websites
resource "aws_s3_bucket_policy" "deployments_policy" {
  bucket = aws_s3_bucket.deployments.id
  depends_on = [aws_s3_bucket_public_access_block.deployments_pab]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.deployments.arn}/*/current/*"
      }
    ]
  })
}

# Bucket website configuration
resource "aws_s3_bucket_website_configuration" "deployments_website" {
  bucket = aws_s3_bucket.deployments.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "404.html"
  }

  routing_rule {
    condition {
      key_prefix_equals = "/"
    }
    redirect {
      replace_key_prefix_with = "index.html"
    }
  }
}

# Terraform state bucket
resource "aws_s3_bucket" "terraform_state" {
  bucket        = "${var.infrastructure_prefix}-terraform-state"
  force_destroy = false

  tags = {
    Name    = "${var.infrastructure_prefix}-terraform-state"
    Purpose = "Terraform state storage"
    Region  = "ap-south-1"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state_versioning" {
  bucket = aws_s3_bucket.terraform_state.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle configuration for managing old versions - CORRECTED
resource "aws_s3_bucket_lifecycle_configuration" "deployments_lifecycle" {
  bucket = aws_s3_bucket.deployments.id

  rule {
    id     = "cleanup_old_versions"
    status = "Enabled"

    # Empty filter applies rule to all objects in bucket
    filter {
      prefix = ""
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    noncurrent_version_transition {
      noncurrent_days = 30  # Changed from 7 to 30 (AWS minimum)
      storage_class   = "STANDARD_IA"
    }
  }

  rule {
    id     = "cleanup_incomplete_uploads"
    status = "Enabled"

    # Empty filter applies rule to all objects in bucket
    filter {
      prefix = ""
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}
