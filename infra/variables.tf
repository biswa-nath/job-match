variable "aws_region" {
  default = "us-east-1"
}

variable "ecr_image_uri" {
  description = "Full ECR image URI for the Lambda container (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/job-matcher:latest)"
}

variable "database_url" {
  description = "PostgreSQL connection string"
  sensitive   = true
}

variable "sheet_id" {
  description = "Google Sheets document ID"
}

variable "llm_model" {
  default = "anthropic/claude-sonnet-4-6"
}

variable "anthropic_api_key" {
  sensitive = true
}

variable "notification_email" {
  description = "Email address for SNS job-matcher alerts"
}

variable "vpc_name" {
  description = "Name tag of the VPC that contains the database and EFS mount targets"
}


variable "schedule_expression" {
  default     = "cron(0 2 * * ? *)"
  description = "EventBridge cron schedule for the daily run (default: 02:00 UTC)"
}
