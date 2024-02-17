"""
Handles authentication and HTTP requests for the Gmail API.
"""
import base64
import datetime
import json
import logging
import re
import time
from collections import defaultdict
from colorama import Fore, init
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.db import IntegrityError
from django.shortcuts import redirect
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.auth import exceptions as auth_exceptions
from google.auth.transport.requests import Request
from google.oauth2 import credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from MailAssistant.serializers import EmailDataSerializer
from . import library
from .models import SocialAPI, Contact
from base64 import urlsafe_b64encode
from rest_framework.response import Response



######################## LOGGING CONFIGURATION ########################
init(autoreset=True)


######################## GOOGLE API PROPERTIES ########################
GMAIL_READONLY_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
GMAIL_SEND_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
CALENDAR_READONLY_SCOPE = 'https://www.googleapis.com/auth/calendar.readonly'
CONTACT_READONLY_SCOPE = 'https://www.googleapis.com/auth/contacts.readonly'
PROFILE_SCOPE = 'https://www.googleapis.com/auth/userinfo.profile'
EMAIL_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'
OPENID_SCOPE = 'openid'
OTHER_CONTACT_READONLY_SCOPE = 'https://www.googleapis.com/auth/contacts.other.readonly'
SCOPES = [
    GMAIL_READONLY_SCOPE,
    GMAIL_SEND_SCOPE,
    CALENDAR_READONLY_SCOPE,
    CONTACT_READONLY_SCOPE,PROFILE_SCOPE,
    EMAIL_SCOPE,
    OPENID_SCOPE,
    OTHER_CONTACT_READONLY_SCOPE
]
GOOGLE_CREDS = 'creds/google_creds.json'
CONFIG = json.load(open(GOOGLE_CREDS, 'r'))['web']
REDIRECT_URI = 'http://localhost:8080/signup_part2'



######################## AUTHENTIFICATION ########################
def generate_auth_url(request):
    """Generate a connection URL to obtain the authorization code"""
    flow = Flow.from_client_secrets_file(
        GOOGLE_CREDS,
        scopes = SCOPES,
        redirect_uri = REDIRECT_URI
    )

    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    # Redirect the user to Google's consent screen
    return redirect(authorization_url)


def exchange_code_for_tokens(authorization_code):
    """Return tokens Exchanged with authorization code"""
    print("DEBUG --------------------------------->", authorization_code)
    flow = Flow.from_client_secrets_file(
        GOOGLE_CREDS,
        scopes = SCOPES,
        redirect_uri = REDIRECT_URI
    )
    flow.fetch_token(code=authorization_code)

    credentials = flow.credentials

    if credentials:
        access_token = credentials.token
        refresh_token = credentials.refresh_token
        print(access_token, refresh_token)
        
        return access_token, refresh_token
    else:
        return Response({'error': 'tokens not found'}, status=400)



######################## CREDENTIALS ########################
def get_credentials(user, email):
    try:
        social_api = SocialAPI.objects.get(
            user = user,
            email = email
        )
        creds_data = {
            'token': social_api.access_token,
            'refresh_token': social_api.refresh_token,
            'token_uri': CONFIG['token_uri'],
            'client_id': CONFIG['client_id'],
            'client_secret': CONFIG['client_secret'],
            'scopes': SCOPES
        }
        creds = credentials.Credentials.from_authorized_user_info(creds_data)
        
    except ObjectDoesNotExist:
        print(f"An unexpected error occurred while retrieving credentials for user {user.username} and email {email}")
        creds = None
    return creds


def refresh_credentials(creds):
    try:
        creds.refresh(Request())
    except auth_exceptions.RefreshError as e:
        print(f"Failed to refresh credentials: {e}")
        creds = None
    return creds


def save_credentials(creds, user, email):
    """Update the database with valid access token"""
    try:
        social_api = SocialAPI.objects.get(
            user = user,
            email = email
        )
        social_api.access_token = creds.token
        social_api.save()
    except Exception as e:
        print(f"Failed to save credentials: {e}")


def build_services(creds) -> dict:
    """Returns a dictionary of endpoints"""
    services = {
        'gmail.readonly': build('gmail', 'v1', cache_discovery=False, credentials=creds),
        'gmail.send': build('gmail', 'v1', cache_discovery=False, credentials=creds),
        'calendar': build('calendar', 'v3', cache_discovery=False, credentials=creds),
        'contacts': build('people', 'v1', cache_discovery=False, credentials=creds),
        'profile': build('people', 'v1', cache_discovery=False, credentials=creds),
        'email': build('people', 'v1', cache_discovery=False, credentials=creds)
    }
    return services


def authenticate_service(user, email) -> dict:
    creds = get_credentials(user, email)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds = refresh_credentials(creds)
        if creds:
            save_credentials(creds, user, email)
        else:
            print("Failed to authenticate")
            return None
    
    services = build_services(creds)
    return services



######################## EMAIL REQUESTS ########################
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_mails(request):
    """Returns the number of unread emails"""
    try:
        user = request.user
        email = request.headers.get('email')
        unread_count = 0
        service = authenticate_service(user, email)
            
        if service is not None:
            try:
                response = service['gmail.readonly'].users().messages().list(userId='me', q='is:unread').execute()
                unread_count = len(response.get('messages', []))
                return JsonResponse({'unreadCount': unread_count}, status=200)
            except Exception as e:
                logging.error(f"Error getting unread emails: {e}")
                return JsonResponse({'error': 'Failed to retrieve unread count'}, status=500)
    
        logging.error(f"{Fore.RED}Failed to authenticate")
        return JsonResponse({'unreadCount': unread_count}, status=400)
    
    except Exception as e:
        logging.error(f"{Fore.RED}An error occurred: {e}")
        return JsonResponse({'unreadCount': 0}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_email(request):
    """Sends an email using the Gmail API."""
    try:
        user = request.user
        email = request.headers.get('email')
        service = authenticate_service(user, email)['gmail.send']
        serializer = EmailDataSerializer(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data

            subject = data['subject']
            message = data['message']
            to = data['to']
            cc = data['cc']
            bcc = data['cci']
            attachments = data.get('attachments', '')

            multipart_message = MIMEMultipart()
            multipart_message["Subject"] = subject
            multipart_message["from"] = "me"
            multipart_message["to"] = to

            if cc:
                multipart_message["cc"] = cc
            if bcc:
                multipart_message["bcc"] = bcc

            multipart_message.attach(MIMEText(message, "html"))

            # Attach each file in the attachments list
            if attachments:
                for uploaded_file in attachments:
                    # Read the contents of the uploaded file
                    file_content = uploaded_file.read()
                    part = MIMEApplication(file_content)
                    part.add_header('Content-Disposition', 'attachment', filename=uploaded_file.name)
                    multipart_message.attach(part)

            raw_message = urlsafe_b64encode(multipart_message.as_string().encode('UTF-8')).decode()
            body = {'raw': raw_message}
            service.users().messages().send(userId="me", body=body).execute()

            return Response({"message": "Email sent successfully!"}, status=200)
        
        else:            
            keys = serializer.errors.keys()

            if 'to' in keys:
                return Response({"error": "recipient is missing"}, status=400)
            elif 'subject' in keys:
                return Response({"error": "subject is missing"}, status=400)
            else:
                return Response({"error": serializer.errors}, status=400)
            
    except Exception as e:
        logging.error(f'Error in send_email view: {e}')
        return Response({"error": str(e)}, status=500)


def get_unique_email_senders(request):
    user = request.user
    email = request.headers.get('email')
    services = authenticate_service(user, email)

    if services:
        senders_info = get_unique_senders(services)
        contacts_info = get_info_contacts(services)            
    else:
        return Response({"error": "Failed to authenticate or access services"}, status=400)

    # Convert contacts_info to a dictionary format
    contacts_dict = {email: contact['name'] for contact in contacts_info for email in contact['emails']}

    # Merge the two dictionaries and remove duplicates
    merged_info = {**contacts_dict, **senders_info}  # In case of duplicates, senders_info will overwrite contacts_dict

    return Response(merged_info, status=200)


def get_info_contacts(services):
    """Fetch the name and the email of the contacts of the user"""
    service = services['contacts']

    # Request a list of all the user's connections (contacts)
    results = service.people().connections().list(
        resourceName='people/me',
        pageSize=1000,  # Adjust the page size as needed
        personFields='names,emailAddresses'
    ).execute()

    contacts = results.get('connections', [])

    names_emails = []
    for contact in contacts:
        # Extract the name and email address of each contact
        name = contact.get('names', [{}])[0].get('displayName')
        email_addresses = [email['value'] for email in contact.get('emailAddresses', [])]

        names_emails.append({'name': name, 'emails': email_addresses})

    return names_emails


def get_mail(services, int_mail=None, id_mail=None):
    """Retrieve email information including subject, sender, content, CC, BCC, and ID"""
    service = services['gmail.readonly']
    plaintext_var = [0]
    plaintext_var[0] = 0

    if int_mail is not None:
        results = service.users().messages().list(userId='me', labelIds=['INBOX']).execute()
        messages = results.get('messages', [])
        if not messages:
            print('No new messages.')
            return None
        message = messages[int_mail]
        email_id = message['id']
    elif id_mail is not None:
        email_id = id_mail
    else:
        print("Either int_mail or id_mail must be provided")
        return None

    msg = service.users().messages().get(userId='me', id=email_id).execute()

    # Initialize variables
    subject = from_info = cc_info = bcc_info = decoded_data = None
    email_data = msg['payload']['headers']

    for values in email_data:
        name = values['name']
        if name == 'Subject':
            subject = values['value']
        elif name == 'From':
            from_info = parse_name_and_email(values['value'])
        elif name == 'Cc':
            cc_info = parse_name_and_email(values['value'])
        elif name == 'Bcc':
            bcc_info = parse_name_and_email(values['value'])

    if 'parts' in msg['payload']:
        for part in msg['payload']['parts']:
            decoded_data_temp = library.process_part(part, plaintext_var)
            if decoded_data_temp:
                decoded_data = library.concat_text(decoded_data, decoded_data_temp)
    elif 'body' in msg['payload']:
        data = msg['payload']['body']['data']
        data = data.replace("-", "+").replace("_", "/")
        decoded_data_temp = base64.b64decode(data).decode('utf-8')
        decoded_data = library.html_clear(decoded_data_temp)
    
    preprocessed_data = library.preprocess_email(decoded_data)

    return subject, from_info, preprocessed_data, cc_info, bcc_info, email_id


#----------------------- READ EMAIL -----------------------#
def find_user_in_emails(services, search_query):
    """Search for user in emails based on a query"""
    emails = search_emails(services, search_query)

    if not emails:
        return "No matching emails found."

    return emails


def parse_name_and_email(header_value):
    if not header_value:
        return None, None

    # Regex to extract name and email
    match = re.match(r'(.*)\s*<(.+)>', header_value)
    if match:
        name, email = match.groups()
        return name.strip(), email.strip()
    else:
        # If the format doesn't match, assume the entire value is the email
        return None, header_value.strip()


# V2 : better to check the mail structure (comparing with the input)
def search_emails(services, search_query, max_results=2):
    """Searches for emails in the user's mailbox based on the provided search query in both the subject and body."""
    service = services['gmail.readonly']

    # Fetch the list of emails based on the query
    try:
        results = service.users().messages().list(userId='me', q=search_query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        found_emails = {}

        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id'], format='metadata', metadataHeaders=['From']).execute()
            headers = msg.get('payload', {}).get('headers', [])
            sender = next((header['value'] for header in headers if header['name'] == 'From'), None)

            if sender:
                email = sender.split('<')[-1].split('>')[0].strip().lower()
                name = sender.split('<')[0].strip().lower() if '<' in sender else email

                # Additional filtering: Check if the sender email/name matches the search query
                if search_query.lower() in email or search_query.lower() in name:
                    if email and not any(substring in email for substring in ["noreply", "no-reply"]):
                        found_emails[email] = name

        return found_emails

    except Exception as e:
        logging.error(f'{Fore.RED}ERROR in Gmail API request: {e}')
        return {}



######################## PROFILE REQUESTS ########################
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_parsed_contacts(request) -> list:
    """Returns a list of parsed unique contacts e.g: [{name: example, email: example@test.com}]"""
    start = time.time()

    user = request.user
    email = request.headers.get('email')
    # Authenticate the user and build the service
    credentials = get_credentials(user, email)
    services = build_services(credentials)
    contacts_service = services['contacts']

    try:
        # Get contacts
        contacts = contacts_service.people().connections().list(
            resourceName='people/me',
            personFields='names,emailAddresses'
        ).execute()

        # Get other contacts
        other_contacts = contacts_service.otherContacts().list(
            pageSize=1000,
            readMask='names,emailAddresses'
        ).execute()

        # Get unique sender information from Gmail
        unique_senders = get_unique_senders(services)

        # Combine all contacts into a dictionary to ensure uniqueness
        all_contacts = defaultdict(set)

        # Parse contacts and other contacts
        contact_types = {
            'connections': contacts.get('connections', []),
            'otherContacts': other_contacts.get('otherContacts', [])
        }

        # Parse contacts and other contacts
        for _, contact_list in contact_types.items():
            for contact in contact_list:
                names = contact.get('names', [])
                emails = contact.get('emailAddresses', [])
                if names and emails:
                    name = names[0].get('displayName', '')
                    email = emails[0].get('value', '')
                    all_contacts[email].add(name)

        # Add unique sender information
        for email, name in unique_senders.items():
            all_contacts[email].add(name)

        # Format the parsed contacts
        parsed_contacts = [{'name': ', '.join(names), 'email': email} for email, names in all_contacts.items()]

        formatted_time = str(datetime.timedelta(seconds=time.time() - start))
        print(f'{Fore.BLUE}{parsed_contacts}')
        logging.info(f"{Fore.YELLOW}Retrieved {len(parsed_contacts)} unique contacts in {formatted_time}")
        
        return Response(parsed_contacts)
    except Exception as e:
        logging.exception("Error fetching contacts:")
        return Response({'error': str(e)}, status=500)
    

def set_all_contacts(user, email):
    """Stores all unique contacts of an email account in DB"""
    start = time.time()

    # Authenticate the user and build the service
    credentials = get_credentials(user, email)
    services = build_services(credentials)
    contacts_service = services['contacts']

    try:
        # Get all contacts without specifying a page size
        all_contacts = defaultdict(set)
        next_page_token = None

        while True:
            connections = contacts_service.people().connections().list(
                resourceName='people/me',
                personFields='names,emailAddresses',
                pageSize=1000,
                pageToken=next_page_token
            ).execute().get('connections', [])

            # Parse and add connections
            for contact in connections:
                name = contact.get('names', [{}])[0].get('displayName', '')
                email_address = contact.get('emailAddresses', [{}])[0].get('value', '')
                all_contacts[name].add(email_address)

            # Update next_page_token directly from the list
            next_page_token = connections[-1].get('nextPageToken')

            if not next_page_token:
                break

        # Add contacts to the database
        for name, emails in all_contacts.items():
            for email in emails:
                try:
                    Contact.objects.create(email=email, username=name, user=user)
                except IntegrityError:
                    # TODO: Handle duplicates gracefully (e.g., update existing records)
                    pass

        formatted_time = str(datetime.timedelta(seconds=time.time() - start))
        logging.info(f"{Fore.GREEN}Retrieved {len(all_contacts)} unique contacts in {formatted_time}")

    except Exception as e:
        logging.exception(f"Error fetching contacts: {str(e)}")


def get_unique_senders(services) -> dict:
    """Fetches unique sender information from Gmail messages"""
    service = services['gmail.readonly']
    limit = 50
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=limit).execute()
    messages = results.get('messages', [])

    senders_info = {}

    if not messages:
        print('No messages found.')
    else:
        for message in messages:
            try:
                msg = service.users().messages().get(userId='me', id=message['id'], format='metadata', metadataHeaders=['From']).execute()
                headers = msg['payload']['headers']
                sender_header = next(header['value'] for header in headers if header['name'] == 'From')
                
                # Extracting the email address and name
                sender_parts = sender_header.split('<')
                sender_name = sender_parts[0].strip().strip('"')
                sender_email = sender_parts[-1].split('>')[0].strip() if len(sender_parts) > 1 else sender_name

                # Store the sender's name with the email address as the key
                senders_info[sender_email] = sender_name
            except Exception as e:
                print(f"Error processing message {message['id']}: {e}")

    return senders_info


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile_image(request):
    """Returns the profile image of the user"""
    user = request.user
    email = request.headers.get('email')
    credentials = get_credentials(user, email)
    service = build_services(credentials)['profile']

    try:
        profile = service.people().get(resourceName='people/me', personFields='photos').execute()

        if 'photos' in profile:
            photos = profile['photos']
            if photos:
                photo_url = photos[0]['url']
                return Response({'profile_image_url': photo_url})
        
        return Response({'profile_image_url': "Profile image URL not found in response"}, status=404)

    except Exception as e:
        return Response({'error': f"Error retrieving profile image: {e}"}, status=505)


def get_email(access_token, refresh_token):
    """Returns the primary email of the user"""
    creds_data = {
        'token': access_token,
        'refresh_token': refresh_token,
        'token_uri': CONFIG['token_uri'],
        'client_id': CONFIG['client_id'],
        'client_secret': CONFIG['client_secret'],
        'scopes': SCOPES
    }
    creds = credentials.Credentials.from_authorized_user_info(creds_data)
    
    try:
        service = build_services(creds)['profile']
        user_info = service.people().get(resourceName='people/me', personFields='emailAddresses').execute()
        email = user_info.get('emailAddresses', [{}])[0].get('value', '')
        return email    
    except Exception as e:
        print(f"{Fore.GREEN}Couldn't get email: {e}")
        return None