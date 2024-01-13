"""
Microsoft Graph API Handler

Manages authentication and HTTP requests for the Microsoft Graph API.
"""
import json
import logging
import requests
from urllib.parse import urlencode
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import redirect
from msal import ConfidentialClientApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from colorama import init, Fore
from rest_framework import status
from .serializers import EmailDataSerializer
from base64 import urlsafe_b64encode
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import SocialAPI

# Initialize colorama with autoreset
init(autoreset=True)



######################## MICROSOFT GRAPH API PROPERTIES ########################
MAIL_READ_SCOPE = 'Mail.Read'
MAIL_SEND_SCOPE = 'Mail.Send'
CALENDAR_READ_SCOPE = 'Calendars.Read'
CONTACTS_READ_SCOPE = 'Contacts.Read'
SCOPES = [
    MAIL_READ_SCOPE,
    MAIL_SEND_SCOPE,
    CALENDAR_READ_SCOPE,
    CONTACTS_READ_SCOPE
]
CONFIG = json.load(open('creds/microsoft_creds.json', 'r'))
# PRODUCTION authority
# AUTHORITY = f'https://login.microsoftonline.com/common'
# localhost authority
AUTHORITY = f'https://login.microsoftonline.com/{CONFIG["tenant_id"]}'
GRAPH_URL = 'https://graph.microsoft.com/v1.0/'
REDIRECT_URI = 'http://localhost:8080/signup_part2'



######################## AUTHENTIFICATION ########################
def generate_auth_url(request):
    """Generate a connection URL to obtain the authorization code"""
    params = {
        'client_id': CONFIG["client_id"],
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'response_mode': 'query',
        'scope': ' '.join(SCOPES),
        'state': '0a590ac7-6a23-44b1-9237-287743818d32'
    }
    authorization_url = f'{AUTHORITY}/oauth2/v2.0/authorize?{urlencode(params)}'

    # Redirect the user to Microsoft's consent screen
    return redirect(authorization_url)

def exchange_code_for_tokens(authorization_code):
    """Returns the access token and the refresh token"""
    app = ConfidentialClientApplication(
        client_id=CONFIG["client_id"],
        client_credential=CONFIG["client_secret"],
        authority=AUTHORITY
    )
    
    result = app.acquire_token_by_authorization_code(
        authorization_code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )    
    if result:
        return result['access_token'], result['refresh_token']
    else:
        return Response({'error': 'tokens not found'}, status=400)

######################## CREDENTIALS ########################
def get_social_api(user, email):
    """Returns the SocialAPI instance"""
    try:
        social_api = SocialAPI.objects.get(user=user, email=email)
        return social_api
    except SocialAPI.DoesNotExist:
        print(f"No credentials found for user {user.username} and email {email}")
        return None

def is_token_valid(access_token):
    """Check if the access token is still valid by making a sample request"""
    sample_url = f'{GRAPH_URL}me'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(sample_url, headers=headers)
    return response.status_code == 200

def refresh_access_token(social_api):
    """Returns a valid access token"""
    access_token = social_api.access_token

    if is_token_valid(access_token):
        return access_token

    refresh_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': social_api.refresh_token,
        'client_id': CONFIG["client_id"],
        'client_secret': CONFIG["client_secret"],
        'scope': SCOPES
    }

    response = requests.post(refresh_url, data=data)
    response_data = response.json()

    # Check if the refresh was successful
    if 'access_token' in response_data:
        social_api.access_token = response_data['access_token']
        social_api.save()
        return response_data['access_token']
    else:
        return None



######################## PROFILE REQUESTS ########################
def get_parsed_contacts(request) -> list:
    """Returns a list of parsed unique contacts with email types"""
    # TODO: ALGO to get the access token and check JWT
    access_token = ""

    try:
        if access_token:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            # Get contacts using Microsoft Graph API
            graph_endpoint = 'https://graph.microsoft.com/v1.0/me/contacts?$select=displayName,emailAddresses'
            response = requests.get(graph_endpoint, headers=headers)

            parsed_contacts = []
            if response.status_code == 200:
                contacts = response.json().get('value', [])
                for contact in contacts:
                    names = contact.get('displayName', '')
                    emails = contact.get('emailAddresses', [])
                    if names and emails:
                        for email_info in emails:
                            email = email_info.get('address', '')
                            email_type = email_info.get('type', '')  # Get the email type if available
                            if email_type:
                                name_with_type = f"[{email_type}] {names}"
                                parsed_contacts.append({'name': name_with_type, 'email': email})
                            else:
                                parsed_contacts.append({'name': names, 'email': email})

                # Get unique sender information from Outlook
                unique_senders = get_unique_senders(access_token)
                for email, name in unique_senders.items():
                    parsed_contacts.append({'name': name, 'email': email})
                
                logging.info(f"{Fore.YELLOW}Retrieved {len(parsed_contacts)} unique contacts")
                return JsonResponse(parsed_contacts)

            else:
                error_message = response.json().get('error', {}).get('message', 'Failed to fetch contacts')
                return JsonResponse({'error': error_message}, status=response.status_code)

        else:
            return JsonResponse({'error': 'Access token not found'}, status=400)

    except Exception as e:
        logging.exception(f"{Fore.YELLOW}Error fetching contacts: {e}")
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def get_unique_senders(access_token) -> dict:
    """Fetches unique sender information from Microsoft Graph API messages"""
    senders_info = {}

    try:
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        limit = 50
        graph_endpoint = f'https://graph.microsoft.com/v1.0/me/messages?$select=sender&$top={limit}'
        response = requests.get(graph_endpoint, headers=headers)

        if response.status_code == 200:
            messages = response.json().get('value', [])
            for message in messages:
                sender = message.get('sender', {})
                email_address = sender.get('emailAddress', {}).get('address', '')
                name = sender.get('emailAddress', {}).get('name', '')
                senders_info[email_address] = name
        else:
            logging.error(f"{Fore.RED}Failed to fetch messages: {response.text}")

        return senders_info

    except Exception as e:
        logging.exception(f"{Fore.RED}Error fetching senders: {e}")
        return senders_info

def get_profile_image(request):
    """Returns the profile image URL of the user"""
    # TODO: ALGO to get the access token and check JWT
    access_token = ""

    try:
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        graph_endpoint = 'https://graph.microsoft.com/v1.0/me/photo/$value'
        response = requests.get(graph_endpoint, headers=headers)

        if response.status_code == 200:
            photo_url = response.json().get('@odata.mediaEditLink', '')
            if photo_url:
                return JsonResponse({'profile_image_url': photo_url}, status=200)
            else:
                return JsonResponse({'error': 'Profile image URL not found in response'}, status=404)
        elif response.status_code == 404:
            return JsonResponse({'error': 'Profile image not found'}, status=response.status_code)
        else:
            return JsonResponse({'error': "Failed to retrieve profile image"}, status=response.status_code)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_email(access_token):
    """Returns the primary email of the user from Microsoft Graph API"""
    if not access_token:
        return Response({'error': 'Access token is missing'}, status=400)

    try:
        graph_api_endpoint = f'{GRAPH_URL}me'
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        response = requests.get(graph_api_endpoint, headers=headers)

        if response.status_code == 200:
            email_data = response.json()
            email = email_data.get('mail', '')
            return Response({'email': email})        
        else:
            return Response({'error': f'Failed to get the email: {response.reason}'}, status=response.status_code)

    except Exception as e:
        return Response({'error': f'Failed to get the email: {e}'}, status=500)
    


######################## EMAIL REQUESTS ########################
def unread_mails(request):
    """Returns the number of unread emails"""
    
    #jwt_access_token = request.headers.get('jwt_access_token')
    #email = request.headers.get('email')
    #user_id = request.headers.get('user_id')

    # TODO: check if jwt_access_token is valid
    # Then get the access token associated with the user id & email
        # check if it is valid
    
    # email API OAuth access_token
    access_token = ""

    try:
        if access_token:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }
            unread_count = 0

            # Get unread messages using Microsoft Graph API
            graph_endpoint = 'https://graph.microsoft.com/v1.0/me/messages?$count=true&$filter=isRead eq false'
            response = requests.get(graph_endpoint, headers=headers)

            if response.status_code == 200:
                unread_count = response.json().get('@odata.count', 0)
                return JsonResponse({'unreadCount': unread_count}, status=200)
            else:
                error_message = response.json().get('error', {}).get('message', 'Failed to retrieve unread count')
                logging.error(f"{Fore.RED}Failed to retrieve unread count: {error_message}")
                return JsonResponse({'unreadCount': 0}, status=response.status_code)

        return JsonResponse({'unreadCount': 0}, status=400)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return JsonResponse({'unreadCount': 0}, status=400)

def send_email(request):
    # TODO: ALGO to get the access token and check JWT
    access_token = ""
    serializer = EmailDataSerializer(data=request.data)
    logger = logging.getLogger(__name__)
    
    if serializer.is_valid():
        data = serializer.validated_data

        try:
            # Prepare email data
            subject = data['subject']
            message = data['message']
            to = data['to']
            cc = data.get('cc')
            bcc = data.get('cci')
            attachments = data.get('attachments')

            graph_endpoint = 'https://graph.microsoft.com/v1.0/me/sendMail'
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            recipients = {'emailAddress': {'address': to}}
            if cc:
                recipients['ccRecipients'] = [{'emailAddress': {'address': cc}}]
            if bcc:
                recipients['bccRecipients'] = [{'emailAddress': {'address': bcc}}]

            body = {
                'message': {
                    'subject': subject,
                    'body': {
                        'contentType': 'HTML',
                        'content': message
                    },
                    'toRecipients': [recipients]
                }
            }

            if attachments:
                message_body = MIMEMultipart()
                message_body.attach(MIMEText(message, 'html'))

                for file_data in attachments:
                    file_name = file_data.name
                    file_content = file_data.read()
                    attachment = MIMEApplication(file_content)
                    attachment.add_header('Content-Disposition', 'attachment', filename=file_name)
                    message_body.attach(attachment)

                encoded_message = urlsafe_b64encode(message_body.as_bytes()).decode('utf-8')
                body['message']['raw'] = encoded_message

            try:
                response = requests.post(graph_endpoint, headers=headers, json=body)
                if response.status_code == 202:
                    return JsonResponse({"message": "Email sent successfully!"}, status=200)
                else:
                    return JsonResponse({"error": "Failed to send email"}, status=response.status_code)
            except Exception as e:
                logger.exception(f"Error sending email: {e}")
                return JsonResponse({"error": str(e)}, status=500)

        except Exception as e:
            logger.exception(f"Error preparing email data: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    logger.error(f"{Fore.RED}Serializer errors: {serializer.errors}")
    return JsonResponse(serializer.errors, status=400)