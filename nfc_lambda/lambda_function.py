import json
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from decimal import Decimal
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Medications')  # Replace with your DynamoDB table name

def lambda_handler(event, context):
    try:
        # Log the incoming event for debugging
        logger.info("Received event: %s", json.dumps(event))

        # Extract medicationId from the request body
        body = json.loads(event.get('body', '{}'))
        medication_id = body.get('medicationId')

        if not medication_id:
            raise ValueError("Error: medicationId not provided in the request body")

        # Retrieve the medication data from DynamoDB
        response = table.get_item(Key={'medicationId': medication_id})
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'body': json.dumps({"error": f"Medication {medication_id} not found."})
            }
        
        # Process the medication data
        medication_data = response['Item']
        last_taken = medication_data.get('lastTaken')
        timeframe = int(medication_data.get('timeframe', 24))
        now = datetime.utcnow()

        # Calculate next due time
        if last_taken:
            last_taken_time = datetime.fromisoformat(last_taken)
            next_due_time = last_taken_time + timedelta(hours=timeframe)
        else:
            next_due_time = now

        is_due = now >= next_due_time
        response_body = {
            "medicationId": medication_id,
            "isDue": is_due,
            "nextDue": next_due_time.isoformat()
        }

        # Check if action is "takeMedication" to log as taken
        if body.get('action') == 'takeMedication' and is_due:
            new_last_taken = now.isoformat()
            new_next_due = (now + timedelta(hours=timeframe)).isoformat()
            table.update_item(
                Key={'medicationId': medication_id},
                UpdateExpression="SET lastTaken = :lastTaken, nextDue = :nextDue",
                ExpressionAttributeValues={
                    ':lastTaken': new_last_taken,
                    ':nextDue': new_next_due
                }
            )
            response_body["message"] = f"Medication {medication_id} has been logged as taken."
            response_body["lastTaken"] = new_last_taken
            response_body["nextDue"] = new_next_due
        else:
            response_body["message"] = (
                f"Medication {medication_id} is due." if is_due else 
                f"Medication {medication_id} is not due yet. Next due time: {next_due_time.isoformat()}."
            )

        # Return successful response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps(response_body)
        }

    except ValueError as e:
        logger.error("ValueError: %s", str(e))
        return {
            'statusCode': 400,
            'body': json.dumps({"error": str(e)})
        }
    except ClientError as e:
        logger.error("ClientError: %s", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({"error": f"Database error: {e.response['Error']['Message']}"})
        }
    except Exception as e:
        logger.error("Exception: %s", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({"error": f"Internal Server Error: {str(e)}"})
        }
