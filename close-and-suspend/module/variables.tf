variable "cloudwatch_log_group_retention" {
  description = "Lambda CloudWatch log group retention period"
  type        = number
  default     = 90
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653, 0], var.cloudwatch_log_group_retention)
    error_message = "Valid values for var: cloudwatch_log_group_retention are (1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653, and 0)."
  }

}

variable "default_tags" {
  type        = map(string)
  description = "Default tags for the module"
  default = {
    Environment = "AFT"
    Project     = "Offboarding Automation"
  }
}

variable "region" {
  type        = string
  description = "Default Region"
  default     = "eu-west-1"
}

variable "ct_account_id" {
  type        = string
  description = "CT Account ID"
  default     = "210987654321"
}

variable "aft_account_id" {
  type        = string
  description = "AFT Account ID"
  default     = "123456789012"
}

variable "ct_destination_ou" {
  type        = string
  description = "Destination OU into which Account will be moved"
  default     = "ou-juup-d1e061ao"
}

variable "ct_root_ou_id" {
  type        = string
  description = "CT Account Root OU ID"
  default     = "r-juup"
}

variable "aft-request-audit-table-stream-arn" {
  type        = string
  description = "DynamoDB table aft-request-audit table stream ARN"
  default     = "arn:aws:dynamodb:eu-west-1:123456789012:table/aft-request-audit/stream/2025-03-13T06:52:29.259"
}

variable "aft-request-audit-table-encrption-key-id" {
  type        = string
  description = "DynamoDB table aft-request-audit table stream ARN"
  default     = "arn:aws:kms:eu-west-1:123456789012:key/5c9e23e2-3e83-4fe6-98ec-b77f00c772fb"
}