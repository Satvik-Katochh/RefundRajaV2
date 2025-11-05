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
