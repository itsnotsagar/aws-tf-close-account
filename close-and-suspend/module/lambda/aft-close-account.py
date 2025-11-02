import json
import logging
import os
import time
from time import sleep
import boto3
import uuid
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.conditions import Attr

SSM_AFT_REQUEST_METADATA_PATH = "/aft/resources/ddb/aft-request-metadata-table-name"
AFT_REQUEST_METADATA_EMAIL_INDEX = "emailIndex"
REGION = os.getenv("REGION")

# Set up logging
logger = logging.getLogger()
if "log_level" in os.environ:
    logger.setLevel(os.environ["log_level"])
    logger.info("Log level set to %s" % logger.getEffectiveLevel())
else:
    logger.setLevel(logging.INFO)

# Initialize AWS clients
session = boto3.Session(region_name=REGION)
ssm = session.client("ssm")

# Get the table name from SSM parameter store
try:
    response = ssm.get_parameter(Name=SSM_AFT_REQUEST_METADATA_PATH)
    TABLE_NAME = response["Parameter"]["Value"]
    logger.info(f"Retrieved table name from SSM: {TABLE_NAME}")
except Exception as e:
    # Fallback to default if SSM parameter retrieval fails
    TABLE_NAME = "aft-request-metadata"
    logger.warning(
        f"Failed to get table name from SSM: {str(e)}. Using fallback: {TABLE_NAME}"
    )

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    """
    Main Lambda handler function that processes DynamoDB stream events
    """
    logger.info("------------------------")
    logger.info(json.dumps(event, default=str))

    try:
        for record in event["Records"]:
            if record["eventName"] == "INSERT":
                handle_insert(record)
            elif record["eventName"] == "REMOVE":
                logger.info("Ignore Remove Event")
            elif record["eventName"] == "MODIFY":
                logger.info("Ignore Modify Event")
        logger.info("------------------------")
        return {"statusCode": 200, "body": "Success!"}

    except Exception as e:
        logger.error(f"Error processing records: {str(e)}")
        logger.info("------------------------")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}


def handle_insert(record):
    """
    Handles INSERT events from DynamoDB stream
    """
    try:
        logger.info("Handling INSERT Event")

        # Get newImage content
        newImage = record["dynamodb"]["NewImage"]
        logger.debug(f"New image: {json.dumps(newImage, default=str)}")

        # Parse values
        acc_name = newImage["control_tower_parameters"]["M"]["AccountName"]["S"]
        acc_email = newImage["control_tower_parameters"]["M"]["AccountEmail"]["S"]
        sso_email = newImage["control_tower_parameters"]["M"]["SSOUserEmail"]["S"]
        sso_first_name = newImage["control_tower_parameters"]["M"]["SSOUserFirstName"]["S"]
        sso_last_name = newImage["control_tower_parameters"]["M"]["SSOUserLastName"]["S"]
        ddb_event = newImage["ddb_event_name"]["S"]
        source_ou = newImage["control_tower_parameters"]["M"]["ManagedOrganizationalUnit"]["S"]

        # Log account details
        logger.info(f"Account Email: {acc_email}")
        logger.info(f"Account Name: {acc_name}")
        logger.info(f"Account SSOEmail: {sso_email}")
        logger.info(f"Account SSOFirstName: {sso_first_name}")
        logger.info(f"Account SSOLastName: {sso_last_name}")
        logger.info(f"Account DDEvent: {ddb_event}")
        logger.info(f"Source OU: {source_ou}")

        if ddb_event == "REMOVE":
            # Query DynamoDB for account ID
            logger.info("Retrieving Account ID from AFT Metadata Table")
            response = table.query(
                IndexName=AFT_REQUEST_METADATA_EMAIL_INDEX,
                KeyConditionExpression=Key("email").eq(acc_email),
            )

            if not response.get("Items"):
                raise ValueError(f"No account found with email {acc_email}")

            logger.info("The query returned the following items:")
            account_id = response["Items"][0]["id"]
            logger.info(account_id)

            logger.info("------------------------")
            logger.info(
                f"{account_id} with Account Email as {acc_email} will be closed and moved from {source_ou} to SUSPENDED OU"
            )
            logger.info("------------------------")

            handle_account_close(account_id, acc_name)
            return True

    except Exception as e:
        logger.error(f"Error in handle_insert: {str(e)}")
        logger.info("------------------------")
        raise


def handle_account_close(account_id, acc_name):
    """
    Handles the account closure and movement to SUSPENDED OU
    """
    try:
        # Get environment variables with validation
        ct_account_id = os.getenv("CT_ACCOUNT")
        destination_ou = os.getenv("DESTINATION_OU")
        root_ou_id = os.getenv("ROOT_OU_ID")

        # Validate required environment variables
        if not all(
            [ct_account_id, destination_ou, root_ou_id]
        ):
            missing_vars = []
            if not ct_account_id:
                missing_vars.append("CT_ACCOUNT")
            if not destination_ou:
                missing_vars.append("DESTINATION_OU")
            if not root_ou_id:
                missing_vars.append("ROOT_OU_ID")
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        # ----- Assume CT Account Closure Role -----
        logger.info("Starting account closure process...")
        sts_client = boto3.client("sts")
        
        # Directly assume the CT account closure role
        ct_role_arn = f"arn:aws:iam::{ct_account_id}:role/aft-account-closure-role"
        logger.info(f"Assuming CT account closure role: {ct_role_arn}")

        try:
            ct_resp = sts_client.assume_role(
                RoleArn=ct_role_arn, RoleSessionName="AWSAFT-Acc-CloseSession"
            )
            ct_creds = ct_resp["Credentials"]
            ct_session = boto3.Session(
                aws_access_key_id=ct_creds["AccessKeyId"],
                aws_secret_access_key=ct_creds["SecretAccessKey"],
                aws_session_token=ct_creds["SessionToken"],
                region_name=REGION,
            )
        except Exception as e:
            logger.error(f"Failed to assume CT account closure role: {str(e)}")
            raise

        # ----- End AssumeRole -----

        # Step 1: Delete the SC product of the account first
        sc_client = ct_session.client("servicecatalog", region_name=REGION)
        logger.info(f"Starting SC provisioned product termination for '{acc_name}'")
        
        # Generate a single terminate token for idempotency
        terminate_token = str(uuid.uuid4())
        logger.info(f"Generated terminate token: {terminate_token}")

        # Step 1: First terminate attempt with IgnoreErrors=False
        record_id = None
        try:
            logger.info("Attempting termination with IgnoreErrors=False")
            terminate_response = sc_client.terminate_provisioned_product(
                ProvisionedProductName=acc_name,
                TerminateToken=terminate_token,
                IgnoreErrors=False
            )
            logger.info(f"Terminate request sent for provisioned product '{acc_name}' (IgnoreErrors=False)")
            logger.info(f"Terminate response: {json.dumps(terminate_response, default=str)}")
            
            # Get the record ID for tracking the termination operation
            record_id = terminate_response["RecordDetail"]["RecordId"]
            logger.info(f"Tracking termination with record ID: {record_id}")
            
        except sc_client.exceptions.ResourceNotFoundException:
            logger.info(f"ServiceCatalog provisioned product '{acc_name}' not found - already deleted or never existed")
            # Product doesn't exist, continue to OU movement
        except Exception as e:
            logger.error(f"Error terminating provisioned product '{acc_name}': {str(e)}")
            raise
        
        # Step 2: If we have a record ID, track the termination operation
        if record_id:
            # Wait initial period for termination to process
            logger.info("Waiting 180 seconds for termination to process...")
            sleep(180)
            
            # Step 3: Track termination operation using describe_record
            max_record_checks = 8  # Maximum record check attempts
            record_check_attempt = 0
            
            while record_check_attempt < max_record_checks:
                try:
                    logger.info(f"Checking termination record status (attempt {record_check_attempt + 1})")
                    record_response = sc_client.describe_record(Id=record_id)
                    record_status = record_response["RecordDetail"]["Status"]
                    logger.info(f"Termination record status: {record_status}")
                    
                    if record_status == "SUCCEEDED":
                        logger.info("Termination operation completed successfully")
                        break
                        
                    elif record_status == "FAILED":
                        logger.warning("Termination operation failed, retrying with IgnoreErrors=True")
                        try:
                            # Generate new terminate token for IgnoreErrors retry
                            ignore_terminate_token = str(uuid.uuid4())
                            logger.info(f"Generated new terminate token for IgnoreErrors retry: {ignore_terminate_token}")
                            terminate_ignore_response = sc_client.terminate_provisioned_product(
                                ProvisionedProductName=acc_name,
                                TerminateToken=ignore_terminate_token,  # New token for retry
                                IgnoreErrors=True
                            )
                            logger.info(f"Terminate with IgnoreErrors=True response: {json.dumps(terminate_ignore_response, default=str)}")
                            
                            # Get new record ID for the IgnoreErrors termination
                            ignore_record_id = terminate_ignore_response["RecordDetail"]["RecordId"]
                            logger.info(f"Tracking IgnoreErrors termination with record ID: {ignore_record_id}")
                            
                            # Wait and check the IgnoreErrors termination
                            logger.info("Waiting 120 seconds after IgnoreErrors=True termination...")
                            sleep(120)
                            
                            # Check the IgnoreErrors termination status
                            ignore_record_response = sc_client.describe_record(Id=ignore_record_id)
                            ignore_status = ignore_record_response["RecordDetail"]["Status"]
                            logger.info(f"IgnoreErrors termination status: {ignore_status}")
                            
                            if ignore_status in ["SUCCEEDED", "FAILED"]:
                                logger.info(f"IgnoreErrors termination completed with status: {ignore_status}")
                                break
                            else:
                                logger.info(f"IgnoreErrors termination still in progress: {ignore_status}")
                                break  # Continue with process regardless
                                
                        except Exception as e:
                            logger.error(f"Error in terminate with IgnoreErrors=True: {str(e)}")
                            break
                            
                    elif record_status in ["IN_PROGRESS", "IN_PROGRESS_IN_ERROR", "CREATED"]:
                        logger.info(f"Termination operation still in progress: {record_status}, waiting 30 seconds...")
                        sleep(30)
                        record_check_attempt += 1
                        continue
                        
                    else:
                        logger.warning(f"Unknown termination record status: {record_status}, continuing...")
                        break
                        
                except Exception as e:
                    logger.error(f"Error checking termination record status: {str(e)}")
                    record_check_attempt += 1
                    if record_check_attempt < max_record_checks:
                        logger.info("Retrying record status check in 30 seconds...")
                        sleep(30)
                    else:
                        logger.warning("Max record check attempts reached, continuing with process...")
                        break
            
            # Final verification: check if product still exists
            try:
                logger.info("Performing final verification that product is deleted...")
                sc_client.describe_provisioned_product(Name=acc_name)
                logger.warning(f"Product '{acc_name}' still exists after termination attempts")
            except sc_client.exceptions.ResourceNotFoundException:
                logger.info(f"Verified: Product '{acc_name}' successfully deleted")
            except Exception as e:
                logger.warning(f"Error verifying product deletion: {str(e)}")
        
        logger.info("Service Catalog product termination process completed")

        # Step 2: Move account to SUSPENDED OU from its current location
        org = ct_session.client("organizations", region_name=REGION)
        logger.info(f"Finding current OU for account {account_id}")
        
        # Get current parent OU
        parents = org.list_parents(ChildId=account_id).get("Parents", [])
        if not parents:
            raise ValueError(f"Account {account_id} has no parent OU")
        
        current_ou_id = parents[0]["Id"]
        logger.info(f"Account {account_id} is currently in OU: {current_ou_id}")
        
        # Move account to SUSPENDED OU if not already there
        if current_ou_id != destination_ou:
            try:
                logger.info(f"Moving account from {current_ou_id} to {destination_ou}")
                move_response = org.move_account(
                    AccountId=account_id,
                    SourceParentId=current_ou_id,
                    DestinationParentId=destination_ou,
                )
                logger.info(f"Move account response: {json.dumps(move_response, default=str)}")
                logger.info("Account successfully moved to SUSPENDED OU")
                # Wait for OU movement to propagate
                logger.info("Waiting 15 seconds for OU movement to propagate...")
                sleep(15)
            except Exception as e:
                logger.error(f"Failed to move account to SUSPENDED OU: {str(e)}")
                raise
        else:
            logger.info("Account is already in the SUSPENDED OU")

        # Step 3: Wait before closing account
        logger.info("------------------------")
        logger.info("Waiting for 30 seconds before closing account")
        logger.info("------------------------")
        sleep(30)

        logger.info("------------------------")
        logger.info(f"Account closure initiated for account: {account_id}")
        logger.info("------------------------")

        # Close the account
        try:
            logger.info(f"Initiating account closure for account: {account_id}")
            close_response = org.close_account(AccountId=account_id)
            logger.info(
                f"Close account response: {json.dumps(close_response, default=str)}"
            )
        except Exception as e:
            logger.error(f"Failed to close account: {str(e)}")
            raise

        logger.info("------------------------")
        logger.info("Account successfully closed")
        logger.info("------------------------")

        return True

    except Exception as e:
        logger.error(f"Error in handle_account_close: {str(e)}")
        logger.info("------------------------")
        raise
