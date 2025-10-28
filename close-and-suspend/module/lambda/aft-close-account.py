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

        # Deleting the SC product of the account
        sc_client = ct_session.client("servicecatalog", region_name=REGION)
        logger.info(f"Searching for SC provisioned product named '{acc_name}'")
        try:
            terminate_response = sc_client.terminate_provisioned_product(
                ProvisionedProductName=acc_name,
                TerminateToken=str(uuid.uuid4()),
                IgnoreErrors=True
            )
            logger.info(f"Terminate request sent for provisioned product '{acc_name}'")
            logger.info(f"Terminate response: {json.dumps(terminate_response, default=str)}")
            sleep(240)
        except sc_client.exceptions.ResourceNotFoundException:
            raise ValueError(f"No ServiceCatalog provisioned product named '{acc_name}' found - aborting.")
        except Exception as e:
            logger.error(f"Error terminating provisioned product '{acc_name}': {str(e)}")
            raise

        # Verify account is under the root OU
        org = ct_session.client("organizations", region_name=REGION)
        logger.info(f"Checking that account {account_id} is in ROOT OU {root_ou_id}")
        parents = org.list_parents(ChildId=account_id).get("Parents", [])
        if not any(p["Id"] == root_ou_id for p in parents):
            raise ValueError(f"Account {account_id} not found in root OU {root_ou_id}")

        source_ou_id = root_ou_id

        # Move account to SUSPENDED OU
        try:
            logger.info(f"Moving account from {source_ou_id} to {destination_ou}")
            move_response = org.move_account(
                AccountId=account_id,
                SourceParentId=source_ou_id,
                DestinationParentId=destination_ou,
            )
            logger.info(
                f"Move account response: {json.dumps(move_response, default=str)}"
            )
        except Exception as e:
            logger.error(f"Failed to move account to SUSPENDED OU: {str(e)}")
            raise

        logger.info("------------------------")
        logger.info("Account successfully moved to SUSPENDED OU ")
        logger.info("------------------------")


        # Wait for account closure to process before moving OU
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
