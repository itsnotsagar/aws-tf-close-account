# IAM Role in CT Account for Account Closure Operations
resource "aws_iam_role" "aft-account-closure-role" {
  provider = aws.ct
  name     = "aft-account-closure-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.aft_account_id}:role/aft-close-account-lambda-role"
        }
      }
    ]
  })

  tags = var.default_tags
}

# Inline policy for the CT role with all required permissions
resource "aws_iam_role_policy" "aft-account-closure-policy" {
  provider = aws.ct
  name     = "aft-account-closure-policy"
  role     = aws_iam_role.aft-account-closure-role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ServiceCatalogOperations"
        Effect = "Allow"
        Action = [
          "servicecatalog:TerminateProvisionedProduct"
        ]
        Resource = "*"
      },
      {
        Sid    = "OrganizationsOperations"
        Effect = "Allow"
        Action = [
          "organizations:ListParents",
          "organizations:MoveAccount",
          "organizations:CloseAccount",
          "organizations:DescribeAccount",
          "organizations:ListAccounts"
        ]
        Resource = "*"
      }
    ]
  })
}
