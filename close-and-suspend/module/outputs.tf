output "aft-close-account-lambda_arn" {
  description = "Account Close Lambda ARN"
  value       = aws_lambda_function.aft-close-account-lambda.arn
}

output "aft-account-closure-role_arn" {
  description = "CT Account Closure Role ARN"
  value       = aws_iam_role.aft-account-closure-role.arn
}
