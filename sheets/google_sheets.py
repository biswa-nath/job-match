import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from rich.console import Console

import config

console = Console()


def get_sheets_service():
    """Authenticate via OAuth2 and return a Google Sheets API service object."""
    creds = None

    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            config.GOOGLE_TOKEN_FILE, config.GOOGLE_SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.GOOGLE_CREDS_FILE):
                raise FileNotFoundError(
                    f"Google OAuth2 credentials not found: {config.GOOGLE_CREDS_FILE}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDS_FILE, config.GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(config.GOOGLE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)


def append_job_row(job: dict, score: int, recommendation: str) -> None:
    """
    Append a job row to the Google Sheet.

    Columns: Position, Company, Office, Location, Status, Tag, Applied on, Link, Score, Assessment
    """
    service = get_sheets_service()

    row = [
        job.get("position", ""),
        job.get("company", ""),
        job.get("office_type", ""),
        job.get("location", ""),
        "Pending",
        "EM",
        "",
        job.get("url", ""),
        score,
        recommendation,
    ]

    range_name = f"{config.SHEET_TAB}!A:I"
    body = {"values": [row]}

    service.spreadsheets().values().append(
        spreadsheetId=config.SHEET_ID,
        range=range_name,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()

    console.print(
        f"[green]Added to sheet:[/green] {job.get('position')} @ {job.get('company')}"
    )
