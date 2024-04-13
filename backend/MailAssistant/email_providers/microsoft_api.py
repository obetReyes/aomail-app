"""
Handles authentication and HTTP requests for the Microsoft Graph API.
"""

import base64
import datetime
import json
import logging
import threading
import time
import requests
from collections import defaultdict
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlencode
from rest_framework.response import Response
from django.http import HttpResponse, JsonResponse
from rest_framework.views import View
from django.utils.decorators import method_decorator
from django.shortcuts import redirect
from msal import ConfidentialClientApplication
import urllib.parse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from MailAssistant.constants import (
    ADMIN_EMAIL_LIST,
    BASE_URL,
    DEFAULT_CATEGORY,
    EMAIL_NO_REPLY,
    GRAPH_URL,
    IMPORTANT,
    INFORMATION,
    MAX_RETRIES,
    MICROSOFT_AUTHORITY,
    MICROSOFT_CLIENT_STATE,
    MICROSOFT_CONFIG,
    MICROSOFT_PROVIDER,
    MICROSOFT_SCOPES,
    REDIRECT_URI,
    USELESS,
)
from ..serializers import EmailDataSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from ..models import Contact, MicrosoftListener, Rule, SocialAPI
from ..models import SocialAPI, Contact, BulletPoint, Category, Email, Sender
from MailAssistant.ai_providers import gpt_3_5_turbo, mistral, claude
from .. import library


######################## LOGGING CONFIGURATION ########################
LOGGER = logging.getLogger(__name__)


######################## AUTHENTIFICATION ########################
def generate_auth_url(request):
    """Generate a connection URL to obtain the authorization code"""
    params = {
        "client_id": MICROSOFT_CONFIG["client_id"],
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        "scope": " ".join(MICROSOFT_SCOPES),
        "state": "0a590ac7-6a23-44b1-9237-287743818d32",
        "prompt": "consent",
    }
    authorization_url = (
        f"{MICROSOFT_AUTHORITY}/oauth2/v2.0/authorize?{urlencode(params)}"
    )

    return redirect(authorization_url)


def exchange_code_for_tokens(authorization_code):
    """Returns the access token and the refresh token"""
    app = ConfidentialClientApplication(
        client_id=MICROSOFT_CONFIG["client_id"],
        client_credential=MICROSOFT_CONFIG["client_secret"],
        authority=MICROSOFT_AUTHORITY,
    )

    result = app.acquire_token_by_authorization_code(
        authorization_code, scopes=MICROSOFT_SCOPES, redirect_uri=REDIRECT_URI
    )
    if result:
        return result["access_token"], result["refresh_token"]
    else:
        return Response({"error": "tokens not found"}, status=400)


######################## CREDENTIALS ########################
def get_headers(access_token) -> dict:
    """Returns the default access headers"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    return headers


def get_social_api(user, email):
    """Returns the SocialAPI instance"""
    try:
        social_api = SocialAPI.objects.get(user=user, email=email)
        return social_api
    except SocialAPI.DoesNotExist:
        LOGGER.error(
            f"No credentials found for user with ID {user.id} and email {email}"
        )
        return None


def is_token_valid(access_token):
    """Check if the access token is still valid by making a sample request"""
    sample_url = f"{GRAPH_URL}me"
    headers = get_headers(access_token)
    response = requests.get(sample_url, headers=headers)
    return response.status_code == 200


def refresh_access_token(social_api):
    """Returns a valid access token"""
    access_token = social_api.access_token

    if is_token_valid(access_token):
        return access_token

    refresh_url = f"{MICROSOFT_AUTHORITY}/oauth2/v2.0/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": social_api.refresh_token,
        "client_id": MICROSOFT_CONFIG["client_id"],
        "client_secret": MICROSOFT_CONFIG["client_secret"],
        "scope": " ".join(MICROSOFT_SCOPES),
    }

    response = requests.post(refresh_url, data=data)
    response_data = response.json()

    # Check if the refresh was successful
    if "access_token" in response_data:
        social_api.access_token = response_data["access_token"]
        social_api.save()
        return response_data["access_token"]
    else:
        LOGGER.error(
            f"Failed to refresh access token for email {social_api.email}: {response_data.get('error_description', response.reason)}"
        )
        return None


######################## PROFILE REQUESTS ########################
def get_info_contacts(access_token):
    """Fetch the name and the email of the contacts of the user"""
    graph_endpoint = f"{GRAPH_URL}me/contacts"

    try:
        headers = get_headers(access_token)

        params = {"$top": 1000}

        response = requests.get(graph_endpoint, headers=headers, params=params)
        response.raise_for_status()
        response_data = response.json()

        contacts = response_data.get("value", [])

        names_emails = []
        for contact in contacts:
            # Extract the name and email address of each contact
            name = contact.get("displayName")
            email_addresses = [
                email["address"] for email in contact.get("emailAddresses", [])
            ]

            names_emails.append({"name": name, "emails": email_addresses})

        return names_emails

    except:
        LOGGER.error(
            f"Failed to retrieve contacts: {response_data.get('error_description', response.reason)}"
        )
        return []


def get_unique_senders(access_token) -> dict:
    """Fetches unique sender information from Microsoft Graph API messages"""
    senders_info = {}

    try:
        headers = get_headers(access_token)

        limit = 50
        graph_endpoint = f"{GRAPH_URL}me/messages?$select=sender&$top={limit}"
        response = requests.get(graph_endpoint, headers=headers)
        response_data = response.json()

        if response.status_code == 200:
            messages = response_data.get("value", [])
            for message in messages:
                sender = message.get("sender", {})
                email_address = sender.get("emailAddress", {}).get("address", "")
                name = sender.get("emailAddress", {}).get("name", "")
                senders_info[email_address] = name
        else:
            LOGGER.error(
                f"Failed to fetch messages: {response_data.get('error_description', response.reason)}"
            )

        return senders_info

    except Exception as e:
        LOGGER.error(f"Error fetching senders: {str(e)}")
        return senders_info


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile_image(request):
    """Returns the profile image URL of the user"""
    user = request.user
    email = request.headers.get("email")
    access_token = refresh_access_token(get_social_api(user, email))

    try:
        headers = get_headers(access_token)

        graph_endpoint = f"{GRAPH_URL}me/photo/$value"
        response = requests.get(graph_endpoint, headers=headers)

        if response.status_code == 200:
            photo_data = response.content

            if photo_data:
                # convert image to url
                photo_data_base64 = base64.b64encode(photo_data).decode("utf-8")
                photo_url = f"data:image/png;base64,{photo_data_base64}"
                return Response({"profile_image_url": photo_url}, status=200)
            else:
                return Response(
                    {"error": "Profile image not found in response"}, status=404
                )
        elif response.status_code == 404:
            LOGGER.error(
                f"Failed to retrieve profile image: {response.json().get('error_description', response.reason)}"
            )
            return Response({"error": "Failed to retrieve profile image"}, status=404)
        else:
            LOGGER.error(
                f"Failed to retrieve profile image: {response.json().get('error_description', response.reason)}"
            )
            return Response(
                {"error": "Failed to retrieve profile image"},
                status=404,
            )

    except Exception as e:
        LOGGER.error(f"Failed to retrieve profile image: {str(e)}")
        return Response(
            {"error": f"Failed to retrieve profile image: {str(e)}"}, status=500
        )


def get_email(access_token):
    """Returns the primary email of the user from Microsoft Graph API"""
    if not access_token:
        return Response({"error": "Access token is missing"}, status=400)

    try:
        graph_api_endpoint = f"{GRAPH_URL}me"
        headers = get_headers(access_token)
        response = requests.get(graph_api_endpoint, headers=headers)

        if response.status_code == 200:
            email_data = response.json()
            email = email_data.get("mail")
            return email
        else:
            LOGGER.error(
                f"Failed to get email: {response.json().get('error_description', response.reason)}"
            )
            return None

    except Exception as e:
        LOGGER.error(f"Failed to get email: {str(e)}")
        return None


######################## EMAIL REQUESTS ########################
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_email(request):
    """Sends an email using the Microsoft Graph API."""

    user = request.user
    email = request.headers.get("email")
    access_token = refresh_access_token(get_social_api(user, email))
    serializer = EmailDataSerializer(data=request.data)

    if serializer.is_valid():
        data = serializer.validated_data
        try:
            subject = data["subject"]
            message = data["message"]
            to = data["to"]
            cc = data.get("cc")
            bcc = data.get("cci")
            attachments = data.get("attachments")
            all_recipients = to

            graph_endpoint = f"{GRAPH_URL}me/sendMail"
            headers = get_headers(access_token)

            email_content = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": message},
                    "toRecipients": [
                        {"emailAddress": {"address": email}} for email in to
                    ],
                }
            }

            if cc:
                email_content["message"]["ccRecipients"] = [
                    {"emailAddress": {"address": email}} for email in cc
                ]
                all_recipients += cc

            if bcc:
                email_content["message"]["bccRecipients"] = [
                    {"emailAddress": {"address": email}} for email in bcc
                ]
                all_recipients += bcc

            if attachments:
                email_content["message"]["attachments"] = []

                for file_data in attachments:
                    file_name = file_data.name
                    file_content = file_data.read()

                    attachment = base64.b64encode(file_content).decode("utf-8")
                    email_content["message"]["attachments"].append(
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": file_name,
                            "contentBytes": attachment,
                        }
                    )
            try:
                response = requests.post(
                    graph_endpoint, headers=headers, json=email_content
                )

                if response.status_code == 202:

                    threading.Thread(
                        target=library.save_contacts, args=(user, email, all_recipients)
                    ).start()

                    return JsonResponse(
                        {"message": "Email sent successfully!"}, status=202
                    )
                else:
                    LOGGER.error(
                        f"Failed to send email: {response.json().get('error', response.reason)}"
                    )
                    return JsonResponse(
                        {"error": response.json().get("error", response.reason)},
                        status=response.status_code,
                    )
            except Exception as e:
                LOGGER.error(f"Failed to send email: {str(e)}")
                return JsonResponse({"error": str(e)}, status=500)

        except Exception as e:
            LOGGER.error(f"Error preparing email data: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    LOGGER.error(f"Serializer errors preparing email data: {serializer.errors}")
    return JsonResponse(serializer.errors, status=400)


def delete_email(email_id, social_api) -> dict:
    """Moves the email to the bin of the user"""
    access_token = refresh_access_token(social_api)
    headers = get_headers(access_token)
    url = f"{GRAPH_URL}/me/messages/{email_id}/move"
    data = {"destinationId": "deleteditems"}

    response = requests.post(url, headers=headers, json=data)

    if "id" in response.text:
        return {"message": "Email moved to trash successfully!"}
    elif "error" in response.text:
        return {"message": "Email moved to trash successfully!"}
    else:
        LOGGER.error(f"Failed to move email to trash: {response.text}")
        return {"error": f"Failed to move email to trash: {response.text}"}


def find_user_in_emails(access_token, search_query):
    messages = search_emails(access_token, search_query)

    if not messages:
        return "No matching emails found."

    return messages


def search_emails(access_token, search_query, max_results=2):
    graph_endpoint = f"{GRAPH_URL}me/messages"

    try:
        headers = get_headers(access_token)

        # Use $filter to achieve search functionality
        filter_expression = f"startswith(subject, '{search_query}') or startswith(body/content, '{search_query}')"

        params = {"$filter": filter_expression, "$top": max_results}

        response = requests.get(graph_endpoint, headers=headers, params=params)
        response.raise_for_status()

        messages = response.json().get("value", [])

        found_emails = {}

        for message in messages:
            sender = message.get("from", {}).get("emailAddress", {}).get("address", "")

            if sender:
                email = sender.lower()
                name = sender.split("@")[0].lower()

                # Additional filtering: Check if the sender email/name matches the search query
                if search_query.lower() in email or search_query.lower() in name:
                    if email and not any(
                        substring in email for substring in ["noreply", "no-reply"]
                    ):
                        found_emails[email] = name

        return found_emails

    except Exception as e:
        LOGGER.error(f"Failed to search emails: {str(e)}")
        return {}


######################## UNDER CONSTRUCTION ########################
def set_all_contacts(access_token, user):
    """Stores all unique contacts of an email account in DB"""
    start = time.time()

    graph_api_contacts_endpoint = f"{GRAPH_URL}me/contacts"
    graph_api_messages_endpoint = f"{GRAPH_URL}me/messages?$top=500"
    headers = get_headers(access_token)

    try:
        all_contacts = defaultdict(set)

        # Part 1: Retrieve contacts from Microsoft Contacts
        response = requests.get(graph_api_contacts_endpoint, headers=headers)
        response.raise_for_status()
        contacts = response.json().get("value", [])

        for contact in contacts:
            name = contact.get("displayName", "")
            email_address = contact.get("emailAddresses", [{}])[0].get("address", "")
            provider_id = contact.get("id", "")
            all_contacts[(user, name, email_address, provider_id)].add(email_address)

        # Part 2: Retrieving from Outlook
        response = requests.get(graph_api_messages_endpoint, headers=headers)
        response.raise_for_status()
        messages = response.json().get("value", [])

        for message in messages:
            sender = message.get("from", {}).get("emailAddress", {}).get("address", "")
            if sender:
                name = sender.split("@")[0]
                if (user, name, sender, "") in all_contacts:
                    continue
                else:
                    all_contacts[(user, name, sender, "")].add(sender)

        # Part 3: Add the contacts to the database
        for contact_info, emails in all_contacts.items():
            _, name, email_address, provider_id = contact_info
            for _ in emails:
                library.save_email_sender(user, name, email_address, provider_id)

        formatted_time = str(datetime.timedelta(seconds=time.time() - start))
        LOGGER.info(
            f"Retrieved {len(all_contacts)} unique contacts in {formatted_time}"
        )

    except Exception as e:
        LOGGER.error(f"Error fetching contacts: {str(e)}")


def parse_name_and_email(sender):
    if not sender:
        return None, None

    name = sender.get("emailAddress", {}).get("name")
    email = sender.get("emailAddress", {}).get("address")

    return name, email


def parse_recipients(recipients):
    if not recipients:
        return []

    parsed_recipients = []
    for recipient in recipients:
        name, email = parse_name_and_email(recipient)
        parsed_recipients.append((name, email))

    return parsed_recipients


def parse_message_body(message_data):
    if "body" in message_data:
        body = message_data["body"]
        if body["contentType"] == "text":
            return body["content"]
        elif body["contentType"] == "html":
            return body["content"]
        elif body["contentType"] == "multipart":
            return body["content"]
    return None


def get_mail_to_db(access_token, int_mail=None, id_mail=None):
    """Retrieve email information for processing email to database."""

    url = f"{GRAPH_URL}me/mailFolders/inbox/messages"
    headers = get_headers(access_token)

    if int_mail is not None:
        response = requests.get(url, headers=headers)
        messages = response.json().get("value", [])

        if not messages:
            LOGGER.error("No new messages.")
            return None

        email_id = messages[int_mail]["id"]
    elif id_mail is not None:
        email_id = id_mail
    else:
        LOGGER.error("Either int_mail or id_mail must be provided")
        return None

    message_url = f"{url}/{email_id}"
    response = requests.get(message_url, headers=headers)
    message_data = response.json()

    conversation_id = message_data.get("conversationId")
    web_link = f"https://outlook.office.com/mail/inbox/id/{urllib.parse.quote(conversation_id)}"
    has_attachments = message_data["hasAttachments"]

    subject = message_data.get("subject")
    sender = message_data.get("from")
    from_info = parse_name_and_email(sender)
    sent_date = None
    decoded_data = parse_message_body(message_data)
    preprocessed_data = library.preprocess_email(decoded_data)

    return (
        subject,
        from_info,
        preprocessed_data,
        email_id,
        sent_date,
        web_link,
        has_attachments,
    )


def get_mail(access_token, int_mail=None, id_mail=None):
    """Retrieve email information for processing."""

    url = f"{GRAPH_URL}me/mailFolders/inbox/messages"
    headers = get_headers(access_token)

    if int_mail is not None:
        response = requests.get(url, headers=headers)
        messages = response.json().get("value", [])

        if not messages:
            LOGGER.error("No new messages.")
            return None

        email_id = messages[int_mail]["id"]
    elif id_mail is not None:
        email_id = id_mail
    else:
        LOGGER.error("Either int_mail or id_mail must be provided")
        return None

    message_url = f"{url}/{email_id}"
    response = requests.get(message_url, headers=headers)
    message_data = response.json()

    conversation_id = message_data.get("conversationId")
    web_link = f"https://outlook.office.com/mail/inbox/id/{urllib.parse.quote(conversation_id)}"

    subject = message_data.get("subject")
    sender = message_data.get("from")
    from_info = parse_name_and_email(sender)
    cc_info = parse_recipients(message_data.get("ccRecipients"))
    bcc_info = parse_recipients(message_data.get("bccRecipients"))
    sent_date = None

    for header in message_data.get("internetMessageHeaders", []):
        if header["name"] == "Date":
            sent_date = datetime.datetime.strptime(
                header["value"], "%a, %d %b %Y %H:%M:%S %z"
            )
            break

    decoded_data = parse_message_body(message_data)
    preprocessed_data = library.preprocess_email(decoded_data)

    return (
        subject,
        from_info,
        preprocessed_data,
        cc_info,
        bcc_info,
        email_id,
        sent_date,
        web_link,
    )


######################## MICROSOFT LISTENER ########################
def calculate_expiration_date(days=0, hours=0, minutes=0) -> str:
    """Returns the expiration date according to a delta time"""

    expiration_date = datetime.datetime.now() + datetime.timedelta(
        days=days, hours=hours, minutes=minutes
    )
    expiration_date_str = expiration_date.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
    return expiration_date_str


def subscribe_to_email_notifications(user, email) -> bool:
    """Subscribe the user to a webhook for email notifications"""

    access_token = refresh_access_token(get_social_api(user, email))
    notification_url = f"{BASE_URL}MailAssistant/microsoft/receive_mail_notifications/"
    lifecycle_notification_url = (
        f"{BASE_URL}MailAssistant/microsoft/receive_subscription_notifications/"
    )

    subscription_body = {
        "changeType": "created,deleted",
        "notificationUrl": notification_url,
        "lifecycleNotificationUrl": lifecycle_notification_url,
        "resource": "me/mailFolders('inbox')/messages",
        "expirationDateTime": calculate_expiration_date(minutes=4_230),
        "clientState": MICROSOFT_CLIENT_STATE,
    }
    url = f"{GRAPH_URL}subscriptions"
    headers = get_headers(access_token)

    try:
        response = requests.post(url, json=subscription_body, headers=headers)
        response_data = response.json()

        social_api = SocialAPI.objects.get(user=user, email=email)
        subscription_id = response_data["id"]

        MicrosoftListener.objects.create(
            subscription_id=subscription_id,
            user=social_api.user,
            email=email,
        )

        if response.status_code == 201:
            print("Subscription created successfully.")
            return True
        else:
            LOGGER.error(
                f"Failed to subscribe to email notifications for user with ID: {user.id} and email {email}: {response.reason}"
            )
            print(f"Debug error: {response.json()}")
            return False

    except Exception as e:
        LOGGER.error(
            f"An error occurred while subscribing to email notifications: {str(e)}"
        )
        return False


def subscribe_to_contact_notifications(user, email) -> bool:
    """Subscribe the user to a webhook for email notifications"""

    access_token = refresh_access_token(get_social_api(user, email))
    notification_url = (
        f"{BASE_URL}MailAssistant/microsoft/receive_contact_notifications/"
    )
    lifecycle_notification_url = (
        f"{BASE_URL}MailAssistant/microsoft/receive_subscription_notifications/"
    )

    subscription_body = {
        "changeType": "created,updated,deleted",
        "notificationUrl": notification_url,
        "lifecycleNotificationUrl": lifecycle_notification_url,
        "resource": "me/contacts",
        "expirationDateTime": calculate_expiration_date(minutes=4_230),
        "clientState": MICROSOFT_CLIENT_STATE,
    }
    url = f"{GRAPH_URL}subscriptions"
    headers = get_headers(access_token)

    try:
        response = requests.post(url, json=subscription_body, headers=headers)
        response_data = response.json()

        social_api = SocialAPI.objects.get(user=user, email=email)
        subscription_id = response_data["id"]

        MicrosoftListener.objects.create(
            subscription_id=subscription_id,
            user=social_api.user,
            email=email,
        )

        if response.status_code == 201:
            print("Subscription contact created successfully.")
            return True
        else:
            LOGGER.error(
                f"Failed to subscribe to contact notifications for user with ID: {user.id} and email {email}: {response.reason}"
            )
            print(f"Debug error: {response.json()}")
            return False

    except Exception as e:
        LOGGER.error(
            f"An error occurred while subscribing to contact notifications: {str(e)}"
        )
        return False


def delete_subscription(user, email, subscription_id):
    access_token = refresh_access_token(get_social_api(user, email))
    headers = get_headers(access_token)
    url = f"{GRAPH_URL}subscriptions/{subscription_id}"

    try:
        response = requests.delete(url, headers=headers)

        if response.status_code != 204:
            LOGGER.error(
                f"Failed to deleted the subscription {subscription_id}: {response.content}"
            )
        else:
            print("\nSuccessfully deleted the subscription\n")

    except Exception as e:
        LOGGER.error("Failed to deleted the subscription", str(e))


def renew_subscription(user, email, subscription_id):
    """Renew a Microsoft subscription"""

    access_token = refresh_access_token(get_social_api(user, email))
    headers = get_headers(access_token)
    url = f"{GRAPH_URL}subscriptions/{subscription_id}"
    new_expiration_date = calculate_expiration_date(minutes=4_230)

    try:
        payload = {"expirationDateTime": new_expiration_date}
        response = requests.patch(url, headers=headers, json=payload)

        if response.status_code != 200:
            LOGGER.error(
                f"Failed to renew the subscription {subscription_id}: {response.content}"
            )
        else:
            print("\nSuccessfully increased the expiration time\n")

    except Exception as e:
        LOGGER.error("CAN NOT RENEW", str(e))


def reauthorize_subscription(user, email, subscription_id):
    """Reauthorize a Microsoft subscription"""

    access_token = refresh_access_token(get_social_api(user, email))
    headers = get_headers(access_token)

    try:
        url = f"{GRAPH_URL}subscriptions/{subscription_id}/reauthorize"
        response = requests.post(url, headers=headers)

        if response.status_code != 200:
            LOGGER.error(
                f"Could not reauthorize the subscription {subscription_id}: {response.reason}"
            )
        else:
            print("successfully reauthotirezs")

    except Exception as e:
        LOGGER.error(
            f"Could not reauthorize the subscription {subscription_id}: {str(e)}"
        )


@method_decorator(csrf_exempt, name="dispatch")
class MicrosoftSubscriptionNotification(View):
    """Handles subscription expiration notifications"""

    def post(self, request):
        validation_token = request.GET.get("validationToken")
        if validation_token:
            return HttpResponse(validation_token, content_type="text/plain")

        try:
            subscription_data = json.loads(request.body.decode("utf-8"))

            if subscription_data["value"][0]["clientState"] == MICROSOFT_CLIENT_STATE:
                lifecycle_event = subscription_data["value"][0]["lifecycleEvent"]
                expiration_date_str = subscription_data["value"][0][
                    "subscriptionExpirationDateTime"
                ]
                subscription_expiration_date = datetime.datetime.fromisoformat(
                    expiration_date_str
                )
                subscription_id = subscription_data["value"][0]["subscriptionId"]
                subscription = MicrosoftListener.objects.get(
                    subscription_id=subscription_id
                )
                current_datetime = datetime.datetime.now(datetime.timezone.utc)

                if (
                    subscription_expiration_date - current_datetime
                    <= datetime.timedelta(minutes=15)
                ):
                    renew_subscription(
                        subscription.user, subscription.email, subscription_id
                    )

                if lifecycle_event == "reauthorizationRequired":
                    reauthorize_subscription(
                        subscription.user, subscription.email, subscription_id
                    )

                # TODO: handle "subscriptionRemoved or missed"
                if lifecycle_event == "subscriptionRemoved":
                    # https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/concepts/change-notifications-lifecycle-events.md#actions-to-take-1
                    LOGGER.error(
                        f"subscriptionRemoved: current time: {current_datetime}, expiration time: {expiration_date_str}"
                    )

                if lifecycle_event == "missed":
                    # https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/concepts/change-notifications-lifecycle-events.md#responding-to-missed-notifications
                    LOGGER.error(
                        f"missed: current time: {current_datetime}, expiration time: {expiration_date_str}"
                    )

            return JsonResponse({"status": "Notification received"}, status=202)

        except Exception as e:
            print(
                f"AN error occured in /MailAssistant/microsoft/receive_subscription_notifications/: {str(e)}"
            )
            return JsonResponse({"error": str(e)}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class MicrosoftEmailNotification(View):
    """Handles subscriptions and receives emails from Microsoft's email notification listener"""

    def post(self, request):
        validation_token = request.GET.get("validationToken")
        if validation_token:
            return HttpResponse(validation_token, content_type="text/plain")

        try:
            print("!!! [OUTLOOK] EMAIL RECEIVED !!!")
            email_data = json.loads(request.body.decode("utf-8"))

            if email_data["value"][0]["clientState"] == MICROSOFT_CLIENT_STATE:
                change_type = email_data["value"][0]["changeType"]
                email_id = email_data["value"][0]["resourceData"]["id"]
                subscription_id = email_data["value"][0]["subscriptionId"]
                subscription = MicrosoftListener.objects.filter(
                    subscription_id=subscription_id
                )

                if change_type == "deleted":
                    if subscription.exists():
                        subscription.delete()

                else:
                    for i in range(MAX_RETRIES):
                        print("STARTING THREAD TO PROCESS EMAIL SUCCESFULLY")
                        try:
                            threading.Thread(
                                target=email_to_db,
                                args=(
                                    subscription.first().user,
                                    subscription.first().email,
                                    email_id,
                                ),
                            ).start()
                            break
                        except Exception as e:
                            LOGGER.critical(
                                f"[Attempt n°{i+1}] Failed to process email with AI for email: {email_id}"
                            )
                            context = {
                                "attempt_number": i,
                                "email_id": email_id,
                                "email_provider": MICROSOFT_PROVIDER,
                                "user": subscription.first().user,
                            }
                            email_html = render_to_string(
                                "ai_failed_email.html", context
                            )
                            send_mail(
                                subject="Critical Alert: Email Processing Failure",
                                message="",
                                recipient_list=[ADMIN_EMAIL_LIST],
                                from_email=EMAIL_NO_REPLY,
                                html_message=email_html,
                                fail_silently=False,
                            )

                return JsonResponse({"status": "Notification received"}, status=202)
            else:
                return JsonResponse({"error": "Internal Server Error"}, status=500)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
class MicrosoftContactNotification(View):
    """Handles subscription and Microsoft contact changes notifications listener"""

    def post(self, request):
        validation_token = request.GET.get("validationToken")
        if validation_token:
            return HttpResponse(validation_token, content_type="text/plain")

        try:
            contact_data = json.loads(request.body.decode("utf-8"))

            if contact_data["value"][0]["clientState"] == MICROSOFT_CLIENT_STATE:
                id_contact = contact_data["value"][0]["resourceData"]["id"]
                subscription_id = contact_data["value"][0]["subscriptionId"]
                subscription = MicrosoftListener.objects.get(
                    subscription_id=subscription_id
                )
                access_token = refresh_access_token(
                    get_social_api(subscription.user, subscription.email)
                )
                change_type = contact_data["value"][0]["changeType"]

                if change_type == "deleted":
                    contact = Contact.objects.get(provider_id=id_contact)
                    contact.delete()

                else:
                    url = f"https://graph.microsoft.com/v1.0/me/contacts/{id_contact}"
                    headers = get_headers(access_token)

                    try:
                        response = requests.get(url, headers=headers)

                        if response.status_code == 200:
                            contact_data = response.json()
                            name = contact_data.get("displayName")
                            email = contact_data.get("emailAddresses")[0].get("address")
                        else:
                            print("Error get contact inof fail:", response.reason)

                    except Exception as e:
                        print("DEBUG>>>> get contact inof fail", str(e))

                    if change_type == "created":
                        library.save_email_sender(
                            subscription.user, name, email, id_contact
                        )

                    if change_type == "updated":
                        contact = Contact.objects.get(provider_id=id_contact)
                        contact.username = name
                        contact.email = email
                        contact.save()

                return JsonResponse({"status": "Notification received"}, status=202)
            else:
                return JsonResponse({"error": "Internal Server Error"}, status=500)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


def email_to_db(user, email, id_email):
    """Saves email notifications from Microsoft listener to database"""

    social_api = get_social_api(user, email)
    access_token = refresh_access_token(social_api)
    subject, from_name, decoded_data, email_id, sent_date, web_link, has_attachments = (
        get_mail_to_db(access_token, None, id_email)
    )

    if not Email.objects.filter(provider_id=email_id).exists():
        sender = Sender.objects.filter(email=from_name[1]).first()

        if not decoded_data:
            return

        decoded_data = library.format_mail(decoded_data)
        category_dict = library.get_db_categories(user)
        category = Category.objects.get(name=DEFAULT_CATEGORY, user=user)
        rules = Rule.objects.filter(sender=sender)
        rule_category = None

        if rules.exists():
            for rule in rules:
                if rule.block:
                    return

                if rule.category:
                    category = rule.category
                    rule_category = True

        user_description = social_api.user_description if social_api.user_description != None else ""
        (
            topic,
            importance_dict,
            answer,
            summary_list,
            sentence,
            relevance,
        ) = claude.categorize_and_summarize_email(
            subject, decoded_data, category_dict, user_description
        )

        if (
            importance_dict["UrgentWorkInformation"] >= 50
        ):  # MAYBE TO UPDATE TO >50 =>  To test
            importance = IMPORTANT
        else:
            max_percentage = 0
            for key, value in importance_dict.items():
                if value > max_percentage:
                    importance = key
                    if importance == "Promotional" or importance == "News":
                        importance = USELESS
                    elif (
                        importance == "RoutineWorkUpdates"
                        or importance == "InternalCommunications"
                    ):
                        importance = INFORMATION
                    elif importance == "UrgentWorkInformation":
                        importance = IMPORTANT
                    max_percentage = importance_dict[key]
            if max_percentage == 0:
                importance = INFORMATION

        if not rule_category:
            if topic in category_dict.keys():
                category = Category.objects.get(name=topic, user=user)

        if not sender:
            sender_name, sender_email = from_name[0], from_name[1]
            if not sender_name:
                sender_name = sender_email

            sender = Sender.objects.filter(email=sender_email).first()
            if not sender:
                sender = Sender.objects.create(email=sender_email, name=sender_name)

        try:
            email_entry = Email.objects.create(
                email_linked=social_api.email,
                provider_id=email_id,
                email_provider=MICROSOFT_PROVIDER,
                email_short_summary=sentence,
                content=decoded_data,
                subject=subject,
                priority=importance,
                read=False,
                answer_later=False,
                sender=sender,
                category=category,
                user=user,
                date=sent_date,
                web_link=web_link,
                has_attachments=has_attachments,
            )

            if summary_list:
                for point in summary_list:
                    BulletPoint.objects.create(content=point, email=email_entry)

        except Exception as e:
            LOGGER.error(
                f"An error occurred when trying to create an email with ID {email_id}: {str(e)}"
            )


####################################################################
######################## UNDER CONSTRUCTION ########################
####################################################################
"""

def processed_email_to_db(user, email):
    access_token = refresh_access_token(get_social_api(user, email))
    subject, from_name, decoded_data, _, _, email_id, date, web_link = get_mail(
        access_token, 0, None
    )

    if not Email.objects.filter(provider_id=email_id).exists():
        if decoded_data:
            decoded_data = library.format_mail(decoded_data)

        # Get user categories
        category_dict = library.get_db_categories(user)

        # Process the email data with AI/NLP
        # user_description = "Enseignant chercheur au sein d'une école d'ingénieur ESAIP."
        user_description = ""
        (
            topic,
            importance_dict,
            answer,
            summary,
            sentence,
            relevance,
        ) = mistral.categorize_and_summarize_email(
            subject, decoded_data, category_dict, user_description
        )

        # Extract the importance of the email
        if importance_dict[IMPORTANT] == 50:
            importance = IMPORTANT
        else:
            for key, value in importance_dict.items():
                if value >= 51:
                    importance = key

        sender_name, sender_email = from_name[0], from_name[1]
        sender, _ = Sender.objects.get_or_create(name=sender_name, email=sender_email)

        # Get the relevant category based
        category = Category.objects.get_or_create(name=topic, user=user)[0]

        try:
            email_entry = Email.objects.create(
                provider_id=email_id,
                email_provider=MICROSOFT_PROVIDER,
                email_short_summary=sentence,
                content=decoded_data,
                subject=subject,
                priority=importance,
                read=False,
                answer_later=False,
                sender=sender,
                category=category,
                user=user,
                date=date,
                web_link=web_link,
            )

            if summary:
                for point in summary:
                    BulletPoint.objects.create(content=point, email=email_entry)

        except Exception as e:
            LOGGER.error(
                f"An error occurred when trying to create an email with ID {email_id}: {str(e)}"
            )
"""

'''@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_parsed_contacts(request) -> list:
    """Returns a list of parsed unique contacts with email types"""
    user = request.user
    email = request.headers.get("email")
    access_token = refresh_access_token(get_social_api(user, email))

    try:
        if access_token:
            headers = get_headers(access_token)

            # Get contacts using Microsoft Graph API
            graph_endpoint = (
                f"{GRAPH_URL}me/contacts?$select=displayName,emailAddresses"
            )
            response = requests.get(graph_endpoint, headers=headers)

            parsed_contacts = []
            if response.status_code == 200:
                contacts = response.json().get("value", [])
                for contact in contacts:
                    names = contact.get("displayName", "")
                    emails = contact.get("emailAddresses", [])
                    if names and emails:
                        for email_info in emails:
                            email = email_info.get("address", "")
                            email_type = email_info.get(
                                "type", ""
                            )  # Get the email type if available
                            if email_type:
                                name_with_type = f"[{email_type}] {names}"
                                parsed_contacts.append(
                                    {"name": name_with_type, "email": email}
                                )
                            else:
                                parsed_contacts.append({"name": names, "email": email})

                # Get unique sender information from Outlook
                unique_senders = get_unique_senders(access_token)
                for email, name in unique_senders.items():
                    parsed_contacts.append({"name": name, "email": email})

                logging.info(
                    f"{Fore.YELLOW}Retrieved {len(parsed_contacts)} unique contacts"
                )
                return JsonResponse(parsed_contacts)

            else:
                error_message = (
                    response.json()
                    .get("error", {})
                    .get("message", "Failed to fetch contacts")
                )
                return JsonResponse(
                    {"error": error_message}, status=response.status_code
                )

        else:
            return JsonResponse({"error": "Access token not found"}, status=400)

    except Exception as e:
        logging.exception(f"{Fore.YELLOW}Error fetching contacts: {e}")
        return JsonResponse({"error": e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)'''

'''@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_mails(request):
    """Returns the number of unread emails"""
    user = request.user
    email = request.headers.get("email")
    access_token = refresh_access_token(get_social_api(user, email))

    try:
        if access_token:
            headers = get_headers(access_token)
            unread_count = 0

            # Get unread messages using Microsoft Graph API
            graph_endpoint = (
                f"{GRAPH_URL}me/messages"  # ?$count=true&$filter=isRead eq false'
            )
            response = requests.get(graph_endpoint, headers=headers)

            response_json = response.json()

            if response.status_code == 200:
                unread_count = response_json.get("@odata.count", 0)
                return JsonResponse({"unreadCount": unread_count}, status=200)
            else:
                error_message = response_json.get("error", {}).get(
                    "message", "No error message"
                )
                error_code = response_json.get("error", {}).get("code")

                if error_code == "MailboxNotEnabledForRESTAPI": 
                    # TODO: display a pop-up                   
                    LOGGER.error(
                        "The account you are using does not have a proper license to access the required endpoints"
                    )

                LOGGER.error(f"Failed to retrieve unread count: {error_message}")
                return JsonResponse({"unreadCount": 0}, status=response.status_code)

        return JsonResponse({"unreadCount": 0}, status=400)

    except Exception as e:
        LOGGER.error(f"An error occurred: {str(e)}")
        return JsonResponse({"unreadCount": 0}, status=400)'''
"""def get_unique_email_senders(request):
    user = request.user
    email = request.headers.get("email")
    access_token = refresh_access_token(get_social_api(user, email))

    senders_info = get_unique_senders(access_token)
    contacts_info = get_info_contacts(access_token)
    # Convert contacts_info to a dictionary format
    contacts_dict = {
        email: contact["name"]
        for contact in contacts_info
        for email in contact["emails"]
    }

    # Merge the two dictionaries and remove duplicates
    merged_info = {
        **contacts_dict,
        **senders_info,
    }  # In case of duplicates, senders_info will overwrite contacts_dict

    return Response(merged_info, status=200)"""


'''def get_mail(access_token, int_mail=None, id_mail=None):
    """Retrieve email information including subject, sender, content, CC, BCC, attachments, and ID"""

    url = f"{GRAPH_URL}me/mailFolders/inbox/messages"
    headers = get_headers(access_token)

    if int_mail is not None:
        response = requests.get(url, headers=headers)
        messages = response.json().get("value", [])

        if not messages:
            LOGGER.error("No new messages.")
            return None

        email_id = messages[int_mail]["id"]
    elif id_mail is not None:
        email_id = id_mail
    else:
        LOGGER.error("Either int_mail or id_mail must be provided")
        return None

    message_url = f"{url}/{email_id}"
    response = requests.get(message_url, headers=headers)
    message_data = response.json()

    conversation_id = message_data.get("conversationId")
    web_link = f"https://outlook.office.com/mail/inbox/id/{urllib.parse.quote(conversation_id)}"

    subject = message_data.get("subject")
    sender = message_data.get("from")
    from_info = parse_name_and_email(sender)
    cc_info = parse_recipients(message_data.get("ccRecipients"))
    bcc_info = parse_recipients(message_data.get("bccRecipients"))
    sent_date = None

    attachments_data = []

    if message_data["hasAttachments"]:
        attachments_data = get_attachments(access_token, email_id)

    decoded_data = parse_message_body(message_data)
    preprocessed_data = library.preprocess_email(decoded_data)

    return (
        subject,
        from_info,
        preprocessed_data,
        cc_info,
        bcc_info,
        email_id,
        sent_date,
        web_link,
        attachments_data,
    )'''


'''def get_attachments(access_token, email_id) -> list:
    """Returns all attachments data encoded in base 64"""
    attachments_url = f"{GRAPH_URL}me/messages/{email_id}/attachments"
    headers = get_headers(access_token)
    response = requests.get(attachments_url, headers=headers)
    attachments_data = []

    if response.status_code == 200:
        attachments = response.json().get("value", [])
        for attachment in attachments:
            attachment_name = attachment.get("name")
            attachment_data = download_attachment(
                access_token, email_id, attachment["id"]
            )
            attachments_data.append(
                {"attachmentName": attachment_name, "data": attachment_data}
            )

    return attachments_data



def download_attachment(access_token, email_id, attachment_id):
    """Returns the data of the attachment in base 64"""
    attachment_url = (
        f"{GRAPH_URL}me/messages/{email_id}/attachments/{attachment_id}/$value"
    )
    headers = get_headers(access_token)
    response = requests.get(attachment_url, headers=headers)
    attachment_data = response.content
    return base64.b64encode(attachment_data).decode("utf-8")'''
