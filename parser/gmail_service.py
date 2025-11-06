# parser/gmail_service.py
"""
Gmail API Service
Handles fetching emails from user's Gmail account using OAuth tokens
"""
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.conf import settings
from allauth.socialaccount.models import SocialToken, SocialApp
from datetime import datetime, timedelta
import re


class GmailService:
    """
    Service class to interact with Gmail API

    Purpose:
    - Connect to Gmail using user's OAuth tokens
    - Fetch emails matching specific criteria
    - Return email data for processing
    """

    def __init__(self, user):
        """
        Initialize Gmail service for a user

        Args:
            user: Django User object (the logged-in user)

        What this does:
        1. Gets user's OAuth tokens from database
        2. Gets OAuth app credentials (Client ID/Secret)
        3. Builds Gmail API client
        """
        self.user = user
        self.service = self._build_service()

    def _build_service(self):
        """
        Build Gmail API service using user's OAuth tokens

        Private method (starts with _) - only used internally

        Returns:
            Gmail API service object (to make API calls)
        """
        # Step 1: Get user's OAuth tokens from database
        try:
            social_token = SocialToken.objects.get(
                account__user=self.user,
                app__provider='google'
            )
        except SocialToken.DoesNotExist:
            raise Exception(
                "User has not connected Google account. Please login with Google first.")

        # Step 2: Get OAuth app credentials (Client ID/Secret)
        try:
            social_app = SocialApp.objects.get(provider='google')
            client_id = social_app.client_id
            client_secret = social_app.secret
        except SocialApp.DoesNotExist:
            raise Exception(
                "Google OAuth app not configured. Please set up in Django admin.")

        # Step 3: Create credentials object
        credentials = Credentials(
            token=social_token.token,  # Access token
            refresh_token=social_token.token_secret,  # Refresh token
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret,
        )

        # Step 4: Refresh token if expired
        if credentials.expired:
            credentials.refresh(Request())

        # Step 5: Build Gmail API service
        service = build('gmail', 'v1', credentials=credentials)

        return service

    def fetch_emails(self, max_results=3):
        """
        Fetch emails from Gmail matching H&M delivery criteria

        Args:
            max_results: Maximum number of emails to fetch (default: 3)

        Returns:
            List of email dictionaries with subject, from, body, etc.
        """
        print(f"\n[GMAIL] Fetching emails (max: {max_results})")

        # Build Gmail search query for H&M delivery emails
        query = "from:(delivery.hm.com OR hm.com) subject:(delivered OR delivery)"

        try:
            # List messages (get email IDs)
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
        except Exception as e:
            print(f"❌ ERROR fetching emails: {str(e)}")
            raise Exception(f"Failed to fetch emails from Gmail: {str(e)}")

        # Extract message IDs
        messages = results.get('messages', [])
        print(f"[GMAIL] Found {len(messages)} email(s)")

        if not messages:
            return []  # No emails found

        # Get full email content for each message
        email_data_list = []

        for idx, msg in enumerate(messages, 1):
            message_id = msg['id']

            try:
                # Get full message
                message = self.service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format='full'
                ).execute()

                # Extract headers
                headers = self._extract_headers(message)

                # Extract body
                body = self._extract_body(message)

                # Extract date
                date_str = headers.get('date', '')
                received_at = self._parse_date(date_str)

                # Extract email from "Name <email>" format
                from_email_raw = headers.get('from', '')
                # Extract just email if it's in "Name <email>" format
                email_match = re.search(r'<([^>]+)>', from_email_raw)
                if email_match:
                    from_email = email_match.group(1)
                else:
                    from_email = from_email_raw

                html_len = len(body.get('html', ''))
                text_len = len(body.get('text', ''))
                print(
                    f"[GMAIL] Email {idx}: {headers.get('subject', '')[:50]}...")
                print(f"[GMAIL]   - HTML: {html_len} chars")
                print(f"[GMAIL]   - Text: {text_len} chars")

                # Build email data dictionary
                email_data = {
                    'id': message_id,
                    'subject': headers.get('subject', ''),
                    'from_email': from_email,
                    'raw_text': body.get('text', ''),
                    'raw_html': body.get('html', ''),
                    'received_at': received_at,
                }

                email_data_list.append(email_data)

            except Exception as e:
                # Skip this email if there's an error
                print(f"[GMAIL] ERROR email {idx}: {str(e)}")
                continue

        print(f"[GMAIL] Extracted {len(email_data_list)} email(s)\n")

        return email_data_list

    def _extract_headers(self, message):
        """Extract email headers (subject, from, date)"""
        headers = message['payload'].get('headers', [])

        # Convert list of dicts to single dict
        headers_dict = {}
        for header in headers:
            name = header['name'].lower()
            value = header['value']
            headers_dict[name] = value

        return {
            'subject': headers_dict.get('subject', ''),
            'from': headers_dict.get('from', ''),
            'date': headers_dict.get('date', '')
        }

    def _extract_body(self, message):
        """Extract email body (text and HTML)"""
        import base64
        payload = message['payload']

        # Check if email has parts (multipart) or single body
        if 'parts' in payload:
            # Multipart email (has HTML + text)
            text_body = ''
            html_body = ''

            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                body_data = part.get('body', {}).get('data', '')

                if not body_data:
                    continue

                # Decode base64
                try:
                    decoded = base64.urlsafe_b64decode(
                        body_data).decode('utf-8')

                    if mime_type == 'text/plain':
                        text_body = decoded
                    elif mime_type == 'text/html':
                        html_body = decoded
                except:
                    continue

            return {'text': text_body, 'html': html_body}
        else:
            # Single part email
            body_data = payload.get('body', {}).get('data', '')
            if body_data:
                try:
                    text_body = base64.urlsafe_b64decode(
                        body_data).decode('utf-8')
                    return {'text': text_body, 'html': ''}
                except:
                    return {'text': '', 'html': ''}

        return {'text': '', 'html': ''}

    def _parse_date(self, date_str):
        """Parse email date string to datetime"""
        from email.utils import parsedate_to_datetime

        if not date_str:
            from django.utils import timezone
            return timezone.now()

        try:
            return parsedate_to_datetime(date_str)
        except:
            from django.utils import timezone
            return timezone.now()
