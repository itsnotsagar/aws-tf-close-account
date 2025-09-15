terraform {
  required_version = ">= 0.15.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 3.15"
    }
  }
  backend "s3" {
    bucket = "aft-management-gitlab-runner-tfstate"
    key    = "offboarding-module.tfstate"
    region = "eu-west-1"
    use_lockfile         = true # S3 native locking
    encrypt              = true
    workspace_key_prefix = "offboarding-module"
  }
}

provider "aws" {
  region = var.region
}

# AFT account
provider "aws" {
  alias  = "aft"
  region = var.region
  assume_role {
    role_arn    = "arn:aws:iam::123456789012:role/AWSAFTExecution"
    external_id = "ASSUME_ROLE_ON_TARGET_ACC"
  }
}

# CT account
provider "aws" {
  alias  = "ct"
  region = var.region
  assume_role {
    role_arn    = "arn:aws:iam::210987654321:role/AWSAFTExecution"
    external_id = "ASSUME_ROLE_ON_TARGET_ACC"
  }
}
