resource "aws_lambda_function" "aft-close-account-lambda" {
  filename         = data.archive_file.aft_suspend_account.output_path
  function_name    = "aft-close-account-lambda"
  description      = "AFT Offboarding - Close Account Lambda"
  role             = aws_iam_role.aft-close-account-lambda.arn
  handler          = "aft-close-account.lambda_handler"
  source_code_hash = data.archive_file.aft_suspend_account.output_base64sha256
  runtime          = "python3.11"
  memory_size      = 256
  tags             = var.default_tags
  environment {
    variables = {
      REGION         = var.region
      CT_ACCOUNT     = var.ct_account_id
      DESTINATION_OU = var.ct_destination_ou
      ROOT_OU_ID     = var.ct_root_ou_id
      LOG_LEVEL      = "INFO"
    }
  }
  timeout = 900
  tracing_config {
    mode = "PassThrough"
  }
}

resource "aws_lambda_event_source_mapping" "lambda_dynamodb" {
  event_source_arn  = var.aft-request-audit-table-stream-arn
  function_name     = aws_lambda_function.aft-close-account-lambda.arn
  starting_position = "LATEST"
}

resource "aws_cloudwatch_log_group" "aft-close-account-lambda-log" {
  name              = "/aws/lambda/aft-close-account-lambda"
  retention_in_days = var.cloudwatch_log_group_retention
  tags              = var.default_tags
}
