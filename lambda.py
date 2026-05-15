import json
import requests
import boto3
import logging
import base64
from requests.auth import HTTPBasicAuth
from atlassian import Jira

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger()

def get_secret(secret_name):
    logger.info("Retrieving values from Secrets Manager")
    region_name = "us-east-1"

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            secret = base64.b64decode(get_secret_value_response['SecretBinary'])
        return json.loads(secret)
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise

# Extract credentials from secrets
secrets = get_secret('your-secret-name-here')  # Replace with your actual secret name
JIRA_API_TOKEN = secrets.get('JIRA_API_TOKEN')
JIRA_BASE_URL = secrets.get('JIRA_BASE_URL')
JIRA_API_USER_EMAIL = secrets.get('JIRA_API_USER_EMAIL')
ASSET_URL = secrets.get('ASSET_URL')  

# Initialize Jira instance
jira = Jira(
    url=JIRA_BASE_URL,
    username=JIRA_API_USER_EMAIL,
    password=JIRA_API_TOKEN,
    cloud=True
)

HEADERS = {"Content-Type": "application/json"}

# Function to get Jira issue details
def get_jira_issue(issue_key):
    url = f'{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}'
    logger.info(f"Requesting Jira issue data from URL: {url}")
    response = requests.get(url, auth=HTTPBasicAuth(JIRA_API_USER_EMAIL, JIRA_API_TOKEN), headers=HEADERS)
    logger.info(f"Response status code: {response.status_code}")

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Failed to retrieve issue data. Status Code: {response.status_code}, Response: {response.text}")
        return None

# Function to GET the object from the assets
def get_region_obj(workspace_id, object_id):
    if not ASSET_URL:
        logger.error("Error: ASSET_URL is not set correctly.")
        return None

    url = f"https://api.atlassian.com/jsm/assets/workspace/{workspace_id}/v1/object/{object_id}"
    logger.info(f"Requesting object from: {url}")
    
    try:
        response = requests.get(url, auth=HTTPBasicAuth(JIRA_API_USER_EMAIL, JIRA_API_TOKEN), headers=HEADERS)
        response.raise_for_status()  # Will raise an error for 4xx/5xx status codes
    except requests.exceptions.RequestException as e:
        logger.error(f"Error making request to {url}: {e}")
        return None

    if response.status_code == 200:
        data = response.json()
        logger.info(f"Fetched object: {data}")
        return data
    else:
        logger.error(f"Failed to retrieve object. Status Code: {response.status_code}, Response: {response.text}")
        return None
    
# Function to retrieve the Sales Support Agent for the region using the Region ID
def get_sales_support_agent(region_id, workspace_id):
    url = f"https://api.atlassian.com/jsm/assets/workspace/{workspace_id}/v1/object/{region_id}"
    logger.info(f"Requesting Region Object from: {url}")
    
    try:
        response = requests.get(url, auth=HTTPBasicAuth(JIRA_API_USER_EMAIL, JIRA_API_TOKEN), headers=HEADERS)
        response.raise_for_status()  
    except requests.exceptions.RequestException as e:
        logger.error(f"Error making request to {url}: {e}")
        return None

    if response.status_code == 200:
        data = response.json()
        logger.info(f"Fetched Region object: {data}")
        
        attributes = data.get('attributes', [])
        for attribute in attributes:
            if attribute.get('objectTypeAttributeId') == '762':  # Correct ID for SalesSupportAgent
                user = attribute.get('objectAttributeValues', [{}])[0].get('user', {})
                if user:
                    account_id = user.get('accountId', 'Unknown')
                    if account_id == 'Unknown':
                        account_id = get_jira_user_by_email(user.get('emailAddress'))
                    sales_support_agent = {
                        'name': user.get('displayName', 'Unknown'),
                        'email': user.get('emailAddress', 'Unknown'),
                        'accountId': account_id
                    }
                    logger.info(f"Found Sales Support Agent: {sales_support_agent}")
                    return sales_support_agent
        return {'error': 'Sales Support Agent not found in Region Object.'}
    else:
        logger.error(f"Failed to retrieve Region object. Status Code: {response.status_code}, Response: {response.text}")
        return None

# Function to fetch Jira user by email (for accountId)
def get_jira_user_by_email(email):
    url = f'{JIRA_BASE_URL}/rest/api/3/user/search?query={email}'
    response = requests.get(url, auth=HTTPBasicAuth(JIRA_API_USER_EMAIL, JIRA_API_TOKEN), headers=HEADERS)
    
    if response.status_code == 200:
        users = response.json()
        for user in users:
            if user['emailAddress'] == email:
                return user['accountId']
    logger.error(f"User with email {email} not found in Jira.")
    return None

# Function to assign the Jira ticket to the Sales Support Agent
def assign_ticket_to_agent(issue_key, agent_account_id):
    url = f'{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/assignee'
    payload = {"accountId": agent_account_id}
    response = requests.put(url, json=payload, auth=HTTPBasicAuth(JIRA_API_USER_EMAIL, JIRA_API_TOKEN), headers=HEADERS)

    if response.status_code == 204:
        logger.info(f"Ticket {issue_key} successfully assigned to {agent_account_id}.")
        return True
    else:
        logger.error(f"Failed to assign ticket. Status code: {response.status_code}, Response: {response.text}")
        return False

# Function to extract Jira Asset customfield_11103 information from the issue data
def extract_customfield_11103_information(issue_data):
    if issue_data:
        issue_key = issue_data['key']
        
        # Extract customfield_11103 if it exists and is a list
        custom_field_data = issue_data['fields'].get('customfield_11103', [])
        
        # If customfield_11103 is not empty, extract the relevant data
        if custom_field_data:
            workspace_id = custom_field_data[0].get('workspaceId', None)
            object_id = custom_field_data[0].get('objectId', None)
        else:
            workspace_id = None
            object_id = None
        
        # Fetch the Sales Rep object using workspaceId and objectId
        if workspace_id and object_id:
            sales_rep_obj = get_region_obj(workspace_id, object_id)  # Fetch Sales Rep object
            if sales_rep_obj:
                # Initialize region_name and region_id to "Unknown"
                region_name = "Unknown"
                region_id = "Unknown"
                
                # Look for the objectAttributeValues that contain the Region Name and RegionObj
                attributes = sales_rep_obj.get('attributes', [])
                logger.info(f"Sales Rep object attributes: {attributes}")

                # Loop through attributes to find RegionName and RegionObj
                for attribute in attributes:
                    if attribute['objectTypeAttributeId'] == '637': #Atribute ID will differ based on your setup, this is just an example
                        region_name = attribute['objectAttributeValues'][0].get('value', 'Unknown')
                        logger.info(f"Found Region Name: {region_name}")
                    
                    if attribute['objectTypeAttributeId'] == '641': #Atribute ID will differ based on your setup, this is just an example
                        referenced_object = attribute['objectAttributeValues'][0].get('referencedObject', {})
                        region_id = referenced_object.get('id', 'Unknown')
                        logger.info(f"Found Region ID: {region_id}")

                # Use the region_id to get the Sales Support Agent from the Region Object
                if region_id != "Unknown":
                    sales_support_agent = get_sales_support_agent(region_id, workspace_id)
                    if sales_support_agent:
                        # Assign the ticket to the Sales Support Agent
                        if assign_ticket_to_agent(issue_key, sales_support_agent['accountId']):
                            return {
                                'issue_key': issue_key,
                                'customfield_11103.workspaceId': workspace_id,
                                'customfield_11103.objectId': object_id,
                                'region_name': region_name,
                                'region_id': region_id,
                                'sales_support_agent': sales_support_agent
                            }
                        else:
                            return {
                                'error': 'Failed to assign the ticket to Sales Support Agent.'
                            }
                    else:
                        return {
                            'error': 'Sales Support Agent not found.'
                        }
                
                return {
                    'issue_key': issue_key,
                    'customfield_11103.workspaceId': workspace_id,
                    'customfield_11103.objectId': object_id,
                    'region_name': region_name,
                    'region_id': region_id
                }
            else:
                return {'error': 'Sales Rep object not found.'}
        else:
            return {'error': 'Invalid workspaceId or objectId.'}
    return None

def lambda_handler(event, context):
    try:
        logger.info(f"Incoming event: {event}")
        
        # Check if the body exists in the incoming event
        if "body" not in event:
            logger.error("Error: No data received in event.")
            return {"statusCode": 400, "body": json.dumps({"error": "No data received"})}

        # Parse the incoming body
        data = json.loads(event["body"])

        # Retrieve the issue key from the parsed data
        issue_key = data.get("key")
        if not issue_key:
            logger.error(f"Error: issue_key is missing. Data received: {json.dumps(data)}")
            return {"statusCode": 400, "body": json.dumps({"error": "issue_key is missing"})}

        logger.info(f"Issue Key: {issue_key}")

        # Get the Jira issue data using the issue key
        issue_data = get_jira_issue(issue_key)
        if not issue_data:
            logger.error(f"Issue {issue_key} not found or failed to retrieve data.")
            return {"statusCode": 404, "body": json.dumps({"error": "Issue not found"})}

        # Retrieve and validate customfield_11103 for necessary data
        customfield_11103 = issue_data["fields"].get("customfield_11103", [])
        if not customfield_11103:
            logger.error("Custom field 11103 is missing or invalid.")
            return {"statusCode": 400, "body": json.dumps({"error": "Custom field 11103 is missing"})}

        workspace_id = customfield_11103[0].get("workspaceId")
        object_id = customfield_11103[0].get("objectId")
        if not workspace_id or not object_id:
            logger.error(f"Error: Workspace ID or Object ID missing. Data: {customfield_11103}")
            return {"statusCode": 400, "body": json.dumps({"error": "Workspace ID or Object ID is missing"})}

        # Fetch the region object using the workspace_id and object_id
        asset_data = get_region_obj(workspace_id, object_id)
        if not asset_data:
            logger.error(f"Failed to retrieve asset data for workspace_id: {workspace_id}, object_id: {object_id}")
            return {"statusCode": 404, "body": json.dumps({"error": "Failed to retrieve asset data"})}

        # Extract region ID from the asset data
        region_attributes = asset_data.get("attributes", [])
        region_id = None  # Default value
        for attribute in region_attributes:
            if attribute.get('objectTypeAttributeId') == '641':  # Example ID for region
                referenced_object = attribute.get('objectAttributeValues', [{}])[0].get('referencedObject', {})
                region_id = referenced_object.get('id')
                if region_id:
                    logger.info(f"Region ID extracted: {region_id}")
                    break

        if not region_id:
            logger.error("Region ID not found in the asset data.")
            return {"statusCode": 400, "body": json.dumps({"error": "Region ID not found in asset data"})}

        # Retrieve the Sales Support Agent based on the region_id and workspace_id
        sales_support_agent = get_sales_support_agent(region_id, workspace_id)
        if not sales_support_agent:
            logger.error(f"Sales Support Agent not found for Region ID: {region_id}, Workspace ID: {workspace_id}")
            return {"statusCode": 404, "body": json.dumps({"error": "Sales Support Agent not found"})}

        # Attempt to assign the ticket to the Sales Support Agent
        assignment_success = assign_ticket_to_agent(issue_key, sales_support_agent['accountId'])
        if not assignment_success:
            logger.error(f"Failed to assign ticket {issue_key} to Sales Support Agent.")
            return {"statusCode": 500, "body": json.dumps({"error": "Failed to assign the ticket to Sales Support Agent"})}

        # Return success message
        return {"statusCode": 200, "body": json.dumps({"message": f"Issue {issue_key} successfully assigned to Sales Support Agent"})}

    except ValueError as ve:
        logger.error(f"Value Error: {ve}")
        return {"statusCode": 400, "body": json.dumps({"error": str(ve)})}
    except Exception as e:
        logger.error(f"Exception: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
