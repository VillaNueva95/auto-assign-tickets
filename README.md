# auto-assign-tickets

# Jira Asset-Based Ticket Auto-Assignment
 
An AWS Lambda function that automatically assigns Jira support tickets to the correct Sales Support Agent based on the customer's linked asset and region — eliminating the need for manual ticket routing.
 
---
 
## The Problem
 
When a support ticket is created in Jira, it includes a linked customer asset (a Sales Rep record). That Sales Rep belongs to a region, and each region has a designated Sales Support Agent responsible for handling tickets. Without automation, someone had to manually look up the asset, find the region, identify the correct agent, and assign the ticket — every single time.
 
## The Solution
 
This Lambda function is triggered by a Jira webhook the moment a ticket is created. It automatically:
 
1. Receives the ticket key from the webhook payload
2. Fetches the full Jira issue and extracts the linked customer asset
3. Looks up the asset in Jira Assets (JSM) to find the Sales Rep's region
4. Resolves the region object to identify the assigned Sales Support Agent
5. Assigns the Jira ticket to that agent automatically
The entire process happens in seconds with no human intervention.
 
---
 
## How It Works
 
```
Jira Webhook (ticket created)
        ↓
Lambda receives POST request
        ↓
Fetch Jira issue → extract linked asset (customfield_11103)
        ↓
Query Jira Assets API → get Sales Rep object → find Region
        ↓
Query Region object → find Sales Support Agent
        ↓
Assign ticket to agent via Jira API
        ↓
Return 200 success
```
 
---
 
## Tech Stack
 
- **Python 3.x**
- **AWS Lambda** — serverless compute, triggered by Jira webhook
- **AWS Secrets Manager** — secure storage for API credentials
- **AWS CloudWatch** — logging and monitoring
- **Jira REST API v3** — issue retrieval and ticket assignment
- **Jira Assets API (JSM)** — asset and region object lookups
- **GitHub** — CI/CD deployment to Lambda
---
 
## Project Structure
 
```
auto-assign-tickets/
│
└── lambda.py        # Main Lambda handler and all helper functions
```
 
---
 
## Key Functions
 
| Function | Description |
|---|---|
| `lambda_handler` | Entry point — parses webhook, orchestrates the full flow |
| `get_secret` | Retrieves credentials securely from AWS Secrets Manager |
| `get_jira_issue` | Fetches full issue data from Jira REST API |
| `get_region_obj` | Queries Jira Assets API for the customer asset object |
| `get_sales_support_agent` | Resolves the region object to find the assigned agent |
| `get_jira_user_by_email` | Fallback lookup to resolve agent account ID by email |
| `assign_ticket_to_agent` | Assigns the ticket to the resolved agent via Jira API |
 
---
 
## Security
 
- All API credentials (Jira token, base URL, email) are stored in **AWS Secrets Manager** — nothing is hardcoded
- The Lambda IAM role is scoped to only the permissions it needs
- Secrets are retrieved at runtime using `boto3`
---
 
## Error Handling
 
The function returns appropriate HTTP status codes at every failure point:
 
| Status Code | Scenario |
|---|---|
| `200` | Ticket successfully assigned |
| `400` | Missing issue key, workspace ID, or custom field data |
| `404` | Issue, asset, or Sales Support Agent not found |
| `500` | Unexpected error or failed assignment |
 
All errors are logged to **AWS CloudWatch** for monitoring and debugging.
 
---
 
## Setup
 
To deploy this in your own environment you will need:
 
1. A Jira Cloud instance with Jira Assets (JSM) enabled
2. An AWS account with Lambda and Secrets Manager access
3. The following values stored in AWS Secrets Manager:
```
JIRA_API_TOKEN
JIRA_BASE_URL
JIRA_API_USER_EMAIL
ASSET_URL
```
 
4. A Jira webhook configured to POST to your Lambda URL on issue creation
5. The `requests` and `atlassian-python-api` packages included in your Lambda deployment package
---
 
## Author
 
Nancy Galvez — [github.com/VillaNueva95](https://github.com/VillaNueva95)