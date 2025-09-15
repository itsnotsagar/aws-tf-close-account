module "offboarding_lambda" {
  source                                   = "../module"
  cloudwatch_log_group_retention           = "90"
  region                                   = "eu-west-1"
  aft_account_id                           = "123456789012"
  ct_account_id                            = "210987654321"
  ct_destination_ou                        = "ou-juup-d1e061ao"
  ct_root_ou_id                            = "r-juup"
  aft-request-audit-table-encrption-key-id = "arn:aws:kms:eu-west-1:123456789012:key/5c9e23e2-3e83-4fe6-98ec-b87f11c772fb"
  aft-request-audit-table-stream-arn       = "arn:aws:dynamodb:eu-west-1:123456789012:table/aft-request-audit/stream/2021-03-13T06:52:29.259"

  default_tags = {
    Environment = "AFT"
    Project     = "Offboarding Automation"
  }

  providers = {
    aws    = aws.aft
    aws.ct = aws.ct
  }
}
