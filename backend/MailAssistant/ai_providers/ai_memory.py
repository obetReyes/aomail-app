"""
Handles conversations with prompt engineering for user/AI interaction.
"""

import json
from django.contrib.auth.models import User
from langchain_community.chat_message_histories import ChatMessageHistory
from MailAssistant.ai_providers import claude


class EmailReplyConversation:
    """Handles the conversation with the AI to reply to an email."""

    def __init__(
        self,
        user: User,
        importance: str,
        subject: str,
        body: str,
        history: ChatMessageHistory,
    ) -> None:
        self.user = user
        self.subject = subject
        self.importance = importance.lower()
        self.body = body
        self.history = history

    def update_history(self, user_input: str, new_body: str) -> None:
        """Updates the conversation history and the current email body response."""

        self.history.add_user_message(user_input)
        self.body = new_body

    def improve_email_response(self, user_input: str) -> str:
        """Improves the email response according to the conversation history."""

        template = f"""You are Ao, an email assistant, who helps a user reply to an {self.importance} email they received.
        The user has already entered the recipients and the subject: '{self.subject}' of the email.    
        Improve the email response following the user's guidelines.

        Current email body response:
        {self.body}

        Current Conversation:
        {self.history}
        User: {user_input}

        The response must retain the core information and incorporate the required user changes.
        If you hesitate or there is contradictory information, always prioritize the last user input.
        Keep the same email body length AND level of speech unless a change is explicitly mentioned by the user.

        ---
        The answer must include all new changes and match the same HTML format.
        """
        response = claude.get_prompt_response(template)
        body = response.content[0].text.strip()

        self.update_history(user_input, body)

        return body


class GenerateEmailConversation:
    """Handles the conversation with the AI to generate an email."""

    def __init__(
        self,
        user: User,
        length: str,
        formality: str,
        subject: str,
        body: str,
        history: ChatMessageHistory,
    ) -> None:
        self.user = user
        self.subject = subject
        self.body = body
        self.length = length
        self.formality = formality
        self.history = history

    def update_history(self, user_input: str, new_subject: str, new_body: str) -> None:
        """Updates the conversation history and the current email subject and body."""

        self.history.add_user_message(user_input)
        self.subject = new_subject
        self.body = new_body

    def improve_draft(
        self, user_input: str, language: str = "French"
    ) -> tuple[str, str]:
        """Improves the email subject and body generated by the AI."""

        template = f"""You are an email assistant, who helps a user redact an email in {language}.
        The user has already entered the recipients and the subject: '{self.subject}' of the email.    
        Improve the email body and subject following the user's guidelines.

        Current email body:
        {self.body}

        Current Conversation:
        {self.history}
        User: {user_input}

        The response must retain the core information and incorporate the required user changes.
        If you hesitate or there is contradictory information, always prioritize the last user input.
        Keep the same email body length: '{self.length}' AND level of speech: '{self.formality}' unless a change is explicitly mentioned by the user.

        ---
        Answer must ONLY be in JSON format with two keys: subject (STRING) and body in HTML format without spaces and unusual line breaks.
        """
        response = claude.get_prompt_response(template)
        clear_text = response.content[0].text.strip()

        result_json: dict[str, str] = json.loads(clear_text)
        new_subject = result_json.get("subject")
        new_body = result_json.get("body")
        self.update_history(user_input, new_subject, new_body)

        return new_subject, new_body
