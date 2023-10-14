import json
import os
import boto3
from botocore.exceptions import ClientError
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import random


REGION = 'us-east-1'
HOST = 'search-restaurantsfinal-7lesph2cpilzzfraywkvxaw3m4.us-east-1.es.amazonaws.com'
INDEX = 'restaurants'


def lambda_handler(event, context):
    print('Received event: ' + json.dumps(event))

    # Create SQS client
    sqs = boto3.client('sqs')
    # replace with your SQS queue URL
    queue_url = 'https://sqs.us-east-1.amazonaws.com/062168545775/DiningQueue'

    # Receive message from SQS queue
    try:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            AttributeNames=[
                'All'
            ],
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout=20,
            WaitTimeSeconds=20
        )
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {
            'statusCode': 500,
            'body': json.dumps('Error in receiving message from SQS.')
        }

    if 'Messages' not in response:
        print("No messages in queue.")
        return {
            'statusCode': 200,
            'body': json.dumps('No messages in queue.')
        }

    # get fields from message
    message = response['Messages'][0]
    receipt_handle = message['ReceiptHandle']
    body = json.loads(message['Body'])

    cuisine = body['Cuisine']
    email = body['PhoneNumber']
    numPeople = body['NumPeople']
    time = body['Time']
    date = body['Date']
    location = body['Location']

    # query opensearch by cuisine to get restaurant IDs
    restaurant_ID_results = query(cuisine)
    chosen_IDs = random.choices(restaurant_ID_results, k=3)

    restaurant_names = []
    restaurant_addresses = []

    # query dynamodb
    table = boto3.resource('dynamodb').Table('yelop-restaurants')
    table.load()

    for ID in chosen_IDs:
        item = table.get_item(Key={'Business ID': ID})["Item"]
        # restaurant_name = item['Name']
        # restaurant_address = item['Address']
        restaurant_names.append(item['Name'])
        restaurant_addresses.append(item['Address'])

    send_message = f'Hello! Here are my {cuisine} suggestions for {numPeople} people, for {date} at {time}:\n'

    for i in range(len(restaurant_names)):
        send_message += f'{i+1}. {restaurant_names[i]} at {restaurant_addresses[i]}. \n'

    # #send email
    ses = boto3.client('ses')
    ses.send_email(
        Source='sh4350@columbia.edu',
        Destination={
            'ToAddresses': [
                email,
            ],
        },
        Message={
            'Subject': {
                'Data': 'Restaurant Recommendation',
            },
            'Body': {
                'Text': {
                    'Data': send_message
                },
            },
        }
    )

    # Delete received message from queue
    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle
    )
    # Change to `email` if using email
    print(f"Restaurant recommendation sent.")

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': '*',
        },
        'body': json.dumps({'results': send_message})
    }


# opensearch query
def query(cuisine):
    # q = {'size': 5, 'query': {'multi_match': {'query': term}}}
    q = {
        'size': 1000,
        'query': {
            'match': {
                'Cuisine': cuisine   # Updated this line to query the 'Cuisine' field
            }
        }
    }

    client = OpenSearch(hosts=[{
        'host': HOST,
        'port': 443
    }],
        http_auth=get_awsauth(REGION, 'es'),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection)

    res = client.search(index=INDEX, body=q)

    hits = res['hits']['hits']
    results = []
    for hit in hits:
        # Updated this line to return the 'restaurant' field
        results.append(hit['_source']['restaurant'])

    return results


def get_awsauth(region, service):
    cred = boto3.Session().get_credentials()
    return AWS4Auth(cred.access_key,
                    cred.secret_key,
                    region,
                    service,
                    session_token=cred.token)
