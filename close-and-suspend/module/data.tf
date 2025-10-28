# Update Alternate SSO
data "aws_region" "aft_management_region" {}

data "aws_caller_identity" "aft_management_id" {}

# Local values for Lambda configuration
locals {
  lambda_source_dir = "${path.module}/lambda/aft-close-account"
}

data "archive_file" "aft_suspend_account" {
  type        = "zip"
  source_dir  = local.lambda_source_dir
  output_path = "${path.module}/lambda/aft-close-account.zip"
}

data "aws_iam_policy_document" "assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    effect = "Allow"
    sid    = ""
  }
}

data "aws_iam_policy_document" "lambda_policy" {
  statement {
    sid       = "AllowLambdaFunctionToCreateLogs"
    actions   = ["logs:*"]
    effect    = "Allow"
    resources = ["arn:aws:logs:*:*:*"]
  }

  statement {
    sid       = "AllowLambdaFunctionSSMAccess"
    effect    = "Allow"
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = ["arn:aws:ssm:${data.aws_region.aft_management_region.region}:${data.aws_caller_identity.aft_management_id.account_id}:parameter/aft/resources/ddb/aft-request-metadata-table-name"]
  }

  statement {
    sid       = "AllowLambdaFunctionInvocation"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:aws:dynamodb:${data.aws_region.aft_management_region.region}:${data.aws_caller_identity.aft_management_id.account_id}:table/aft-request-audit/stream/*"]
  }

  statement {
    sid       = "AllowLambdaFunctionKMSAccess"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.aft-request-audit-table-encrption-key-id]
  }

  statement {
    sid       = "AllowLambdaFunctionDDBAccess"
    effect    = "Allow"
    actions   = ["dynamodb:DescribeTable", "dynamodb:Query", "dynamodb:Scan"]
    resources = ["arn:aws:dynamodb:${data.aws_region.aft_management_region.region}:${data.aws_caller_identity.aft_management_id.account_id}:table/aft-request-metadata/index/emailIndex"]
  }

  statement {
    sid       = "APIAccessForDynamoDBStreams"
    effect    = "Allow"
    actions   = ["dynamodb:GetRecords", "dynamodb:GetShardIterator", "dynamodb:DescribeStream", "dynamodb:ListStreams"]
    resources = ["arn:aws:dynamodb:${data.aws_region.aft_management_region.region}:${data.aws_caller_identity.aft_management_id.account_id}:table/aft-request-audit/stream/*"]
  }

  statement {
    sid       = "AllowAssumeRoleInCTAccount"
    effect    = "Allow"
    actions   = ["sts:AssumeRole"]
    resources = ["arn:aws:iam::${var.ct_account_id}:role/aft-account-closure-role"]
  }
}
