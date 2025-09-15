resource "aws_iam_role" "aft-close-account-lambda" {
  name               = "aft-close-account-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role_policy.json
}

resource "aws_iam_role_policy" "lambda-policy" {
  name   = "lambda-policy"
  role   = aws_iam_role.aft-close-account-lambda.id
  policy = data.aws_iam_policy_document.lambda_policy.json
}
