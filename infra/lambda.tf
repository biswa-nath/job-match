resource "aws_security_group" "lambda" {
  name   = "job-matcher-lambda"
  vpc_id = data.aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lambda_function" "job_matcher" {
  function_name = "job-matcher"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = var.ecr_image_uri

  # Playwright + LLM calls can take several minutes; 14 min leaves headroom
  timeout     = 840
  memory_size = 1024

  vpc_config {
    subnet_ids         = data.aws_subnets.private.ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  file_system_config {
    arn              = aws_efs_access_point.data.arn
    local_mount_path = "/mnt/efs"
  }

  depends_on = [aws_efs_mount_target.data]

  environment {
    variables = {
      LAMBDA_MODE       = "1"
      SESSION_DIR       = "/mnt/efs"
      DATABASE_URL      = var.database_url
      SHEET_ID          = var.sheet_id
      LLM_MODEL         = var.llm_model
      ANTHROPIC_API_KEY = var.anthropic_api_key
      SNS_TOPIC_ARN     = aws_sns_topic.alerts.arn
    }
  }
}
