import base64
import os
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.services.email.base import EmailService

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailService(EmailService):
    def __init__(self, client_secret_path=None, token_path="token.json"):
        self.client_secret_path = (
            client_secret_path
            or Path(__file__).resolve().parents[2]
            / "client_secret_158058258699-ld79uq83t5somoa2hnof0s2pvbuui269.apps.googleusercontent.com.json"
        )
        self.token_path = token_path
        self.creds = self._get_credentials()
        self.gmail = build("gmail", "v1", credentials=self.creds)

    def _get_credentials(self) -> Credentials:
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())
        return creds

    def send_email(self, to: str, subject: str, body: str) -> dict:
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return (
            self.gmail.users()
            .messages()
            .send(userId="me", body={"raw": encoded_message})
            .execute()
        )
