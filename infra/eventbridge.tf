resource "aws_cloudwatch_event_rule" "daily" {
  name                = "job-matcher-daily"
  description         = "Trigger job-matcher daily"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.daily.name
  target_id = "job-matcher"
  arn       = aws_lambda_function.job_matcher.arn
  input     = jsonencode({ source = "all" })
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.job_matcher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily.arn
}
