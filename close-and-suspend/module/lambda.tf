resource "aws_lambda_code_signing_config" "this" {
  description = "Code signing config for AFT Lambda"

  allowed_publishers {
    signing_profile_version_arns = [
      aws_signer_signing_profile.this.arn,
    ]
  }

  policies {
    untrusted_artifact_on_deployment = "Warn"
  }
}

resource "aws_signer_signing_profile" "this" {
  name_prefix = "AwsLambdaCodeSigningAction"
  platform_id = "AWSLambda-SHA384-ECDSA"

  signature_validity_period {
    value = 5
    type  = "YEARS"
  }
  tags = var.default_tags
}

resource "aws_lambda_function" "aft-close-account-lambda" {
  filename                = data.archive_file.aft_suspend_account.output_path
  function_name           = "aft-close-account-lambda"
  description             = "AFT Offboarding - Close Account Lambda"
  role                    = aws_iam_role.aft-close-account-lambda.arn
  handler                 = "aft-close-account.lambda_handler"
  code_signing_config_arn = aws_lambda_code_signing_config.this.arn
  source_code_hash        = data.archive_file.aft_suspend_account.output_base64sha256
  runtime                 = "python3.11"
  tags = var.default_tags
  environment {
    variables = {
      REGION        = var.region
      CT_ACCOUNT    = var.ct_account_id
      DESTINATIONOU = var.ct_destination_ou
      ROOTOU_ID     = var.ct_root_ou_id
    }
  }
  timeout = 900
  tracing_config {
    mode = "Active"
  }
  reserved_concurrent_executions = 1
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
