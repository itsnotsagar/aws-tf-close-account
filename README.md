# AWS Terraform Account Closure Automation

An automated solution for closing and suspending AWS accounts in AWS Control Tower environments using Terraform and Lambda functions. This project provides a secure, event-driven approach to account lifecycle management with proper governance controls.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [How It Works](#how-it-works)
- [Security](#security)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)
- [Contributing](#contributing)

## Overview

This solution automates the process of closing AWS accounts within an AWS Control Tower environment. When an account removal request is detected in the AFT (Account Factory for Terraform) audit trail, the system automatically:

1. Terminates the Service Catalog provisioned product
2. Moves the account to a SUSPENDED organizational unit
3. Closes the AWS account permanently

The automation ensures proper governance, audit trails, and secure cross-account operations.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   AFT Account   │    │  Control Tower   │    │   Target OU     │
│                 │    │    Account       │    │  (SUSPENDED)    │
├─────────────────┤    ├──────────────────┤    ├─────────────────┤
│ DynamoDB Stream │───▶│ Lambda Function  │───▶│ Closed Account  │
│ (Audit Trail)   │    │ (Account Closer) │    │                 │
│                 │    │                  │    │                 │
│ IAM Role        │    │ Service Catalog  │    │                 │
│ (Lambda Exec)   │    │ Organizations    │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Components

- **AFT Account**: Contains the Lambda function and DynamoDB stream trigger
- **Control Tower Account**: Provides cross-account role for account operations
- **Lambda Function**: Processes account closure requests
- **DynamoDB Stream**: Triggers automation on audit trail changes
- **IAM Roles**: Secure cross-account access with least privilege

## Features

- **Event-Driven**: Automatically triggered by AFT audit trail changes
- **Secure**: Cross-account role assumption with minimal permissions
- **Auditable**: Comprehensive logging and CloudWatch integration
- **Resilient**: Error handling and retry mechanisms
- **Configurable**: Customizable organizational units and timeouts
- **Code Signing**: Lambda functions are signed for security
- **Monitoring**: CloudWatch logs with configurable retention

## Prerequisites

Before deploying this solution, ensure you have:

### AWS Environment
- AWS Control Tower deployed and configured
- Account Factory for Terraform (AFT) set up
- Appropriate AWS Organizations structure with SUSPENDED OU
- Cross-account trust relationships configured

### Permissions
- Administrative access to AFT management account
- Administrative access to Control Tower management account
- Permissions to create IAM roles and policies
- Permissions to deploy Lambda functions

### Tools
- Terraform >= 1.0
- AWS CLI configured
- Python 3.11 (for Lambda runtime)

## Quick Start

### Prerequisites Setup

1. **GitLab Runner Configuration:**
   ```bash
   # Ensure runner has required tags
   tags: ["test-org"]
   
   # Install required tools on runner
   terraform --version  # >= 0.15.0
   aws --version        # Latest AWS CLI
   ```

2. **AWS Credentials:**
   ```bash
   # Configure runner with appropriate AWS credentials
   # Must have access to assume roles in both AFT and CT accounts
   export AWS_ACCESS_KEY_ID="your-access-key"
   export AWS_SECRET_ACCESS_KEY="your-secret-key"
   export AWS_DEFAULT_REGION="eu-west-1"
   ```

### Deployment via GitLab CI/CD

1. **Clone and configure:**
   ```bash
   git clone <repository-url>
   cd aws-tf-close-account
   ```

2. **Update configuration:**
   ```bash
   # Edit close-and-suspend/configuration/main.tf
   # Update account IDs, OUs, and other environment-specific values
   ```

3. **Deploy via pipeline:**
   ```bash
   git add .
   git commit -m "Configure account closure automation"
   git push origin main
   ```

4. **Monitor deployment:**
   - Navigate to GitLab → CI/CD → Pipelines
   - Review terraform-plan-close-and-suspend job output
   - Verify terraform-apply-close-and-suspend completes successfully

5. **Verify deployment:**
   - Check AWS Lambda console for `aft-close-account-lambda`
   - Verify IAM roles in both AFT and CT accounts
   - Review CloudWatch logs for any initialization issues

### Manual Deployment (Alternative)

If you prefer manual deployment or need to troubleshoot:

1. **Local setup:**
   ```bash
   cd close-and-suspend/configuration
   terraform init
   ```

2. **Plan and apply:**
   ```bash
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

3. **Cleanup (if needed):**
   ```bash
   terraform destroy
   ```

## Configuration

### Required Variables

Edit `close-and-suspend/configuration/main.tf` with your environment-specific values:

```hcl
module "offboarding_lambda" {
  source = "../module"
  
  # CloudWatch Configuration
  cloudwatch_log_group_retention = "90"  # Days to retain logs
  
  # AWS Configuration
  region         = "eu-west-1"           # Primary region
  aft_account_id = "123456789012"        # AFT management account ID
  ct_account_id  = "210987654321"        # Control Tower management account ID
  
  # Organizational Units
  ct_destination_ou = "ou-juup-d1e061ao" # SUSPENDED OU ID
  ct_root_ou_id     = "r-juup"           # Root OU ID
  
  # DynamoDB Configuration
  aft-request-audit-table-encrption-key-id = "arn:aws:kms:eu-west-1:123456789012:key/..."
  aft-request-audit-table-stream-arn       = "arn:aws:dynamodb:eu-west-1:123456789012:table/aft-request-audit/stream/..."
  
  # Tagging
  default_tags = {
    Environment = "AFT"
    Project     = "Offboarding Automation"
  }
}
```

### Environment Variables

The Lambda function uses these environment variables:

- `REGION`: AWS region for operations
- `CT_ACCOUNT`: Control Tower management account ID
- `DESTINATION_OU`: Target OU for suspended accounts
- `ROOT_OU_ID`: Root organizational unit ID

## GitLab CI/CD Pipeline

### Pipeline Overview

The GitLab CI/CD pipeline provides automated, secure deployment of the account closure infrastructure with proper state management and cross-account role assumptions.

### Pipeline Stages

#### 1. Terraform Plan (`terraform-plan-close-and-suspend`)

**Purpose**: Creates and validates Terraform execution plan

**Triggers**:
- Commits to `main` branch
- Changes in `close-and-suspend/configuration/**/*`
- Changes in `close-and-suspend/module/**/*`

**Process**:
```bash
cd close-and-suspend/configuration
terraform init
terraform plan -out=tfplan
```

**Artifacts**:
- `tfplan`: Terraform execution plan
- `aft-close-account.zip`: Lambda deployment package
- Expiration: 3 hours

#### 2. Terraform Apply (`terraform-apply-close-and-suspend`)

**Purpose**: Applies the validated Terraform plan

**Dependencies**: Requires successful plan stage

**Process**:
```bash
cd close-and-suspend/configuration
terraform init
terraform apply -auto-approve tfplan
```

**Safety Features**:
- Uses pre-validated plan from artifacts
- No interactive approval required
- Automatic rollback on failure

#### 3. Terraform Destroy (`terraform-destroy-close-and-suspend`)

**Purpose**: Removes all infrastructure (manual trigger only)

**Trigger**: Manual execution only

**Process**:
```bash
cd close-and-suspend/configuration
terraform init
terraform destroy -auto-approve
```

**Safety**: Manual trigger prevents accidental destruction

### Runner Configuration

#### Required Tags
```yaml
tags:
  - test-org
```

#### Required Software
- Terraform >= 0.15.0
- AWS CLI (latest version)
- Git
- Bash/Shell access

#### AWS Permissions
The runner must have permissions to:
- Assume `AWSAFTExecution` role in AFT account
- Assume `AWSAFTExecution` role in CT account
- Access S3 backend bucket
- DynamoDB state locking

### State Management

#### S3 Backend Configuration
```hcl
backend "s3" {
  bucket               = "aft-management-gitlab-runner-tfstate"
  key                  = "offboarding-module.tfstate"
  region               = "eu-west-1"
  use_lockfile         = true    # S3 native locking
  encrypt              = true    # State encryption
  workspace_key_prefix = "offboarding-module"
}
```

#### State Security Features
- **Encryption**: All state files encrypted at rest
- **Locking**: Prevents concurrent modifications
- **Versioning**: S3 versioning for state history
- **Access Control**: IAM-based access restrictions

### Pipeline Variables

#### GitLab CI Variables (Optional)
Set these in GitLab → Settings → CI/CD → Variables:

```bash
# AWS Credentials (if not using IAM roles)
AWS_ACCESS_KEY_ID: "your-access-key"
AWS_SECRET_ACCESS_KEY: "your-secret-key"
AWS_DEFAULT_REGION: "eu-west-1"

# Terraform Variables (if overriding defaults)
TF_VAR_region: "eu-west-1"
TF_VAR_aft_account_id: "123456789012"
TF_VAR_ct_account_id: "210987654321"
```

### Pipeline Monitoring

#### Success Indicators
- ✅ Plan stage completes without errors
- ✅ Apply stage creates all resources
- ✅ Lambda function is deployed and active
- ✅ IAM roles created in both accounts

#### Failure Scenarios
- ❌ Terraform validation errors
- ❌ AWS permission issues
- ❌ Cross-account role assumption failures
- ❌ Resource creation conflicts

#### Troubleshooting Pipeline Issues

**Plan Stage Failures**:
```bash
# Check Terraform syntax
terraform validate

# Verify AWS credentials
aws sts get-caller-identity

# Test role assumptions
aws sts assume-role --role-arn arn:aws:iam::123456789012:role/AWSAFTExecution --role-session-name test
```

**Apply Stage Failures**:
```bash
# Check resource conflicts
terraform state list

# Verify permissions
aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::123456789012:role/AWSAFTExecution --action-names lambda:CreateFunction

# Review CloudWatch logs
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/aft-close-account
```

### Pipeline Best Practices

#### Development Workflow
1. Create feature branch for changes
2. Test changes in development environment
3. Create merge request to main
4. Review pipeline output before merging
5. Monitor production deployment

#### Security Practices
- Use IAM roles instead of access keys when possible
- Regularly rotate access credentials
- Monitor pipeline execution logs
- Implement proper approval workflows for sensitive changes
- Use branch protection rules

#### Operational Practices
- Monitor pipeline execution times
- Set up notifications for pipeline failures
- Regularly review and update runner configurations
- Maintain backup of Terraform state
- Document any manual interventions

## Deployment

### GitLab CI/CD Pipeline

This project uses GitLab CI/CD for automated deployment with a three-stage pipeline:

```yaml
stages:
  - terraform-plan
  - terraform-apply
  - terraform-destroy
```

#### Pipeline Configuration

The pipeline is configured in `.gitlab-ci.yml` with the following jobs:

**Planning Stage:**
- `terraform-plan-close-and-suspend`: Creates Terraform execution plan
- Triggers on changes to `close-and-suspend/` directory
- Stores plan artifacts for apply stage

**Apply Stage:**
- `terraform-apply-close-and-suspend`: Applies the Terraform plan
- Requires successful planning stage
- Automatically applies on main branch

**Destroy Stage:**
- `terraform-destroy-close-and-suspend`: Destroys infrastructure
- Manual trigger only for safety

### Pipeline Execution Flow

1. **Trigger Conditions:**
   ```yaml
   rules:
     - if: $CI_COMMIT_BRANCH == "main"
       changes:
         - close-and-suspend/configuration/**/*
         - close-and-suspend/module/**/*
   ```

2. **Artifact Management:**
   - Terraform plans stored as artifacts
   - Lambda deployment packages included
   - 3-hour expiration for security

3. **Runner Requirements:**
   - Tagged with `test-org`
   - Must have AWS credentials configured
   - Terraform and AWS CLI installed

### Backend Configuration

The solution uses S3 backend for state management:

```hcl
backend "s3" {
  bucket               = "aft-management-gitlab-runner-tfstate"
  key                  = "offboarding-module.tfstate"
  region               = "eu-west-1"
  use_lockfile         = true
  encrypt              = true
  workspace_key_prefix = "offboarding-module"
}
```

### Multi-Provider Setup

The configuration uses multiple AWS providers for cross-account deployment:

```hcl
# Default provider
provider "aws" {
  region = var.region
}

# AFT Management Account
provider "aws" {
  alias  = "aft"
  region = var.region
  assume_role {
    role_arn    = "arn:aws:iam::123456789012:role/AWSAFTExecution"
    external_id = "ASSUME_ROLE_ON_TARGET_ACC"
  }
}

# Control Tower Management Account
provider "aws" {
  alias  = "ct"
  region = var.region
  assume_role {
    role_arn    = "arn:aws:iam::210987654321:role/AWSAFTExecution"
    external_id = "ASSUME_ROLE_ON_TARGET_ACC"
  }
}
```

### Deployment Methods

#### Option 1: GitLab CI/CD (Recommended)

1. **Push changes to repository:**
   ```bash
   git add .
   git commit -m "Update account closure configuration"
   git push origin main
   ```

2. **Monitor pipeline:**
   - Navigate to GitLab CI/CD → Pipelines
   - Review plan output in planning stage
   - Verify successful apply stage

3. **Manual destroy (if needed):**
   - Navigate to GitLab CI/CD → Pipelines
   - Click "Run pipeline" → Select "terraform-destroy-close-and-suspend"

#### Option 2: Manual Deployment

1. **Configure AWS credentials:**
   ```bash
   # Set up profiles for both accounts
   aws configure --profile aft-account
   aws configure --profile ct-account
   ```

2. **Initialize and deploy:**
   ```bash
   cd close-and-suspend/configuration
   terraform init
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

3. **Verify deployment:**
   ```bash
   # Check Lambda function
   aws lambda get-function --function-name aft-close-account-lambda --profile aft-account
   
   # Check CT role
   aws iam get-role --role-name aft-account-closure-role --profile ct-account
   ```

### Multi-Account Resource Distribution

**AFT Management Account (123456789012):**
- Lambda function (`aft-close-account-lambda`)
- Lambda execution role (`aft-close-account-lambda-role`)
- CloudWatch log group (`/aws/lambda/aft-close-account-lambda`)
- DynamoDB stream event source mapping
- Code signing configuration and profile

**Control Tower Management Account (210987654321):**
- Cross-account IAM role (`aft-account-closure-role`)
- Service Catalog and Organizations permissions
- Account closure execution permissions

### Pipeline Security

- **State Encryption**: Terraform state encrypted in S3
- **State Locking**: DynamoDB locking prevents concurrent runs
- **Role Assumption**: Cross-account access via IAM roles
- **Artifact Security**: Limited artifact expiration (3 hours)
- **Manual Destroy**: Destroy operations require manual approval

## How It Works

### Workflow Overview

1. **Trigger**: AFT audit trail DynamoDB stream detects account removal request
2. **Processing**: Lambda function processes the stream event
3. **Validation**: Verifies account details and permissions
4. **Service Catalog**: Terminates the provisioned product
5. **Organizations**: Moves account to SUSPENDED OU
6. **Closure**: Initiates AWS account closure
7. **Logging**: Records all operations in CloudWatch

### Event Processing

The Lambda function processes DynamoDB stream events:

```python
# Event structure
{
    "Records": [
        {
            "eventName": "INSERT",
            "dynamodb": {
                "NewImage": {
                    "control_tower_parameters": {
                        "M": {
                            "AccountName": {"S": "test-account"},
                            "AccountEmail": {"S": "test@example.com"},
                            "ManagedOrganizationalUnit": {"S": "ou-source"}
                        }
                    },
                    "ddb_event_name": {"S": "REMOVE"}
                }
            }
        }
    ]
}
```

### Account Closure Process

1. **Account Lookup**: Query AFT metadata table by email
2. **Role Assumption**: Assume cross-account role in CT account
3. **Product Termination**: Terminate Service Catalog product
4. **Account Movement**: Move from current OU to SUSPENDED OU
5. **Account Closure**: Call Organizations CloseAccount API
6. **Verification**: Confirm successful closure

## Security

### IAM Permissions

**Lambda Execution Role (AFT Account):**
- CloudWatch Logs access
- DynamoDB stream and table access
- SSM parameter access
- KMS decrypt permissions
- Cross-account role assumption

**Account Closure Role (CT Account):**
- Service Catalog terminate permissions
- Organizations account management
- Limited to specific operations only

### Security Features

- **Code Signing**: Lambda functions are signed for integrity
- **Least Privilege**: Minimal required permissions only
- **Cross-Account**: Secure role assumption between accounts
- **Encryption**: KMS encryption for DynamoDB streams
- **Audit Trail**: Comprehensive logging of all operations

### Network Security

- Lambda functions run in AWS managed VPC
- No internet access required for core functionality
- All AWS API calls use service endpoints

## Monitoring

### CloudWatch Logs

The Lambda function creates detailed logs:

```
/aws/lambda/aft-close-account-lambda
```

Log retention is configurable (default: 90 days).

### Key Metrics to Monitor

- Lambda function invocations
- Lambda function errors
- Lambda function duration
- DynamoDB stream processing lag
- Account closure success/failure rates

### Alerting

Consider setting up CloudWatch alarms for:

```bash
# Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name "AFT-Account-Closure-Errors" \
  --alarm-description "Lambda function errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold
```

## Troubleshooting

### Common Issues

#### Lambda Function Timeout
**Symptom**: Function times out during execution
**Solution**: Increase timeout value (current: 900 seconds)

#### Permission Denied
**Symptom**: Cross-account role assumption fails
**Solution**: Verify trust relationship and IAM policies

#### Account Not Found
**Symptom**: Cannot find account in AFT metadata
**Solution**: Verify account email and AFT table structure

#### Service Catalog Product Not Found
**Symptom**: Cannot terminate provisioned product
**Solution**: Verify product name matches account name exactly

### Debugging Steps

#### Pipeline Debugging

1. **Check pipeline logs:**
   ```bash
   # In GitLab UI: CI/CD → Pipelines → Select pipeline → View job logs
   # Look for specific error messages in plan/apply stages
   ```

2. **Verify runner configuration:**
   ```bash
   # On GitLab runner
   gitlab-runner verify
   terraform --version
   aws --version
   aws sts get-caller-identity
   ```

3. **Test Terraform locally:**
   ```bash
   cd close-and-suspend/configuration
   terraform init
   terraform validate
   terraform plan
   ```

#### Application Debugging

4. **Check Lambda logs:**
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/aft-close-account-lambda \
     --start-time $(date -d '1 hour ago' +%s)000 \
     --profile aft-account
   ```

5. **Verify DynamoDB stream:**
   ```bash
   aws dynamodb describe-table \
     --table-name aft-request-audit \
     --query 'Table.StreamSpecification' \
     --profile aft-account
   ```

6. **Test cross-account role assumption:**
   ```bash
   aws sts assume-role \
     --role-arn arn:aws:iam::210987654321:role/aft-account-closure-role \
     --role-session-name test-session \
     --profile aft-account
   ```

#### State Management Debugging

7. **Check Terraform state:**
   ```bash
   # List state resources
   terraform state list
   
   # Check specific resource
   terraform state show aws_lambda_function.aft-close-account-lambda
   
   # Verify backend connectivity
   terraform init -backend-config="bucket=aft-management-gitlab-runner-tfstate"
   ```

### Error Codes

#### Pipeline Errors
- `terraform init failed`: Backend configuration or credentials issue
- `terraform plan failed`: Configuration validation or permission errors
- `terraform apply failed`: Resource creation or dependency issues
- `Job failed: exit code 1`: General Terraform execution failure
- `Runner system failure`: GitLab runner connectivity or resource issues

#### Application Errors
- `ResourceNotFoundException`: Account or Service Catalog product not found
- `AccessDeniedException`: Insufficient permissions for AWS operations
- `ValidationException`: Invalid parameters passed to AWS APIs
- `ThrottlingException`: API rate limits exceeded
- `AssumeRoleFailure`: Cross-account role assumption failed
- `LambdaTimeoutException`: Function execution exceeded 900 seconds

## Best Practices

### Operational
- Test in non-production environment first
- Use GitLab CI/CD for consistent deployments
- Monitor both pipeline and CloudWatch logs regularly
- Set up appropriate alerting for pipeline failures
- Document account closure procedures and pipeline workflows
- Maintain audit trails for all deployments
- Regularly review and update GitLab runner configurations
- Implement proper backup strategies for Terraform state

### Security
- Regularly review IAM permissions
- Use least privilege principles
- Enable CloudTrail logging
- Implement proper backup procedures
- Regular security assessments

### Development
- Use infrastructure as code
- Version control all configurations
- Implement proper testing
- Document all changes
- Follow AWS Well-Architected principles

### Account Management
- Maintain accurate OU structure
- Document account lifecycle processes
- Implement proper approval workflows
- Regular compliance reviews
- Backup critical account data before closure

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Update documentation
6. Submit a pull request

### Development Guidelines

- Follow Terraform best practices
- Use consistent naming conventions
- Add appropriate comments
- Update README for any changes
- Test in development environment

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions or issues:
- Create an issue in this repository
- Review AWS Control Tower documentation
- Consult AWS Organizations documentation
- Check AWS Lambda best practices

## References

- [AWS Control Tower Documentation](https://docs.aws.amazon.com/controltower/)
- [AWS Organizations Documentation](https://docs.aws.amazon.com/organizations/)
- [Account Factory for Terraform](https://docs.aws.amazon.com/controltower/latest/userguide/aft-overview.html)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

## Changelog

### Version 1.0.0
- Initial release
- Basic account closure automation
- Cross-account role support
- CloudWatch logging integration
- Code signing implementation