output "vpc_id" {
  value = data.aws_vpc.main.id
}

output "subnet_ids" {
  value = data.aws_subnets.private.ids
}

output "lambda_function_name" {
  value = aws_lambda_function.job_matcher.function_name
}

output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "efs_file_system_id" {
  value = aws_efs_file_system.data.id
}

output "efs_access_point_id" {
  value = aws_efs_access_point.data.id
}
