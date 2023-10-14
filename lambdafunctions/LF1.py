from datetime import datetime
import boto3
import json

""" helper functions """


def get_slot(intent, slot_name):
    return intent['slots'][slot_name]['value']['interpretedValue']


def elicit_slot(intent, slotToElicit, message):
    response = {
        "sessionState": {
            "dialogAction": {
                "slotToElicit": slotToElicit,
                "type": "ElicitSlot"
            },
            "intent": intent
        }
    }
    if message:
        response['messages'] = [
            {
                "contentType": "PlainText",
                "content": message
            }
        ]
    return response


def delegate(intent):
    response = {
        "sessionState": {
            "dialogAction": {
                "type": "Delegate"
            },
            "intent": intent
        }
    }


def close(intent, message):
    """
    send message back. does not expect further response
    """
    response = {
        'sessionState': {
            'dialogAction': {
                'type': 'Close',
            },
            'intent': intent,
        },
        'messages': [
            {
                'contentType': 'PlainText',
                'content': message,
            }
        ]
    }
    response['sessionState']['intent']['state'] = 'Fulfilled'

    return response


"""Handle dining suggestion parameters """


def validate_order(slots):

    # valdiate cuisine
    if not slots['Cuisine']:
        return {
            'isValid': False,
            'invalidSlot': 'Cuisine'
        }

    elif slots['Cuisine']:
        if 'interpretedValue' not in slots['Cuisine']['value']:
            error_message = 'Sorry, we dont provide that cuisine. we only provide: Chinese, Italian, Mexican, Indian, Japanese, French, Korean.'
            return {
                'isValid': False,
                'invalidSlot': 'Cuisine',
                'message': error_message
            }

        if slots['Cuisine']['value']['interpretedValue'] not in ["chinese", "italian", "mexican", "indian", "japanese", "french", "korean"]:
            return {
                'isValid': False,
                'invalidSlot': 'Location',
                'message': error_message
            }

    # validate location
    if not slots['Location']:
        return {
            'isValid': False,
            'invalidSlot': 'Location'
        }

    elif slots['Location']:
        if 'interpretedValue' not in slots['Location']['value']:
            error_message = 'Please enter a valid city.'
            return {
                'isValid': False,
                'invalidSlot': 'Location',
                'message': error_message
            }

        if slots['Location']['value']['interpretedValue'] not in ["New York", "Manhattan", "New york", 'manhattan', 'new york', "nyc", "NYC"]:
            return {
                'isValid': False,
                'invalidSlot': 'Location',
                'message': 'Sorry, we only serve Manhattan or New York. Other cities will be coming soon.'
            }

    # validate date
    if not slots['Date']:
        return {
            'isValid': False,
            'invalidSlot': 'Date'
        }

    elif slots['Date']:
        error_message = 'Please enter a valid date. Date must be today or in the future.'
        if 'interpretedValue' not in slots['Date']['value']:
            return {
                'isValid': False,
                'invalidSlot': 'Date',
                'message': error_message
            }

        date = slots['Date']['value']['interpretedValue']
        format_date = datetime.strptime(date, '%Y-%m-%d').date()
        format_date = format_date.replace(year=2023)
        todays_date = datetime.today().date()

        if format_date < todays_date:
            return {
                'isValid': False,
                'invalidSlot': 'Date',
                'message': error_message
            }

    # validate time
    if not slots['Time']:
        return {
            'isValid': False,
            'invalidSlot': 'Time'
        }

    elif slots['Time']:
        error_message = 'Please enter a valid time. Time must be in the future.'

        if 'interpretedValue' not in slots['Time']['value']:
            return {
                'isValid': False,
                'invalidSlot': 'Time',
                'message': 'Do you mean morning or afternoon? Please reply with time followed by PM/AM.'
            }

        # if the day is today, validate the time is after now
        if format_date == todays_date:
            reserve_time = slots['Time']['value']['interpretedValue']
            reserve_time = datetime.strptime(
                f'{todays_date} {reserve_time}', '%Y-%m-%d %H:%M')
            time_now = datetime.now()

            if reserve_time <= time_now:
                return {
                    'isValid': False,
                    'invalidSlot': 'Time',
                    'message': error_message
                }

    # validate number of people
    if not slots['NumPeople']:
        return {
            'isValid': False,
            'invalidSlot': 'NumPeople'
        }

    elif slots['NumPeople']:
        error_message = 'Please enter a valid number. Number must be greater than 0.'
        if 'interpretedValue' not in slots['NumPeople']['value']:
            return {
                'isValid': False,
                'invalidSlot': 'NumPeople',
                'message': error_message
            }

        numPeople = int(slots['NumPeople']['value']['interpretedValue'])

        if numPeople <= 0:
            return {
                'isValid': False,
                'invalidSlot': 'NumPeople',
                'message': error_message
            }

    return {'isValid': True}


def dining_suggestions(intent, source):

    slots = intent['slots']
    validation_result = validate_order(slots)

    if source == 'DialogCodeHook':

        if validation_result['isValid'] == False:
            if 'message' in validation_result:
                response = {
                    "sessionState": {
                        "dialogAction": {
                            "slotToElicit": validation_result['invalidSlot'],
                            "type": "ElicitSlot"
                        },
                        "intent": intent
                    },
                    "messages": [
                        {
                            "contentType": "PlainText",
                            "content": validation_result['message']
                        }
                    ]
                }
            else:
                response = {
                    "sessionState": {
                        "dialogAction": {
                            "slotToElicit": validation_result['invalidSlot'],
                            "type": "ElicitSlot"
                        },
                        "intent": intent
                    }
                }

        else:
            response = {
                "sessionState": {
                    "dialogAction": {
                        "type": "Delegate"
                    },
                    "intent": intent
                }
            }

        return response

    if source == 'FulfillmentCodeHook':
        # push to queue
        sqs_url = 'https://sqs.us-east-1.amazonaws.com/062168545775/DiningQueue'
        # Initialize the SQS client
        sqs = boto3.client('sqs')

        slot_info = {}
        for key, val in slots.items():
            slot_info[key] = val['value']['interpretedValue']

        message_body = json.dumps(slot_info)

        sqs.send_message(
            QueueUrl=sqs_url,
            MessageBody=message_body
        )

        # inform user we're done
        return close(intent, 'We have received your request and will send you an SMS once we have your restaurant suggestions!')


"""main handler"""


def lambda_handler(event, context):

    intent = event['sessionState']['intent']
    source = event['invocationSource']

    if intent['name'] == 'GreetingIntent':
        message = 'Hi there, how can I help you?'
        return close(intent, message)

    elif intent['name'] == 'ThankYouIntent':
        message = 'You are welcome good sir.'
        return close(intent, message)

    elif intent['name'] == 'DiningSuggestionsIntent':
        return dining_suggestions(intent, source)

    else:
        return close(intent, '')
