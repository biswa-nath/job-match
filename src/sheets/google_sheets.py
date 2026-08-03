import os

from google.auth.exceptions import RefreshError
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
            if config.LAMBDA_MODE:
                raise RefreshError(
                    f"Google Sheets token missing or fully expired. "
                    f"Re-authenticate locally and upload {config.GOOGLE_TOKEN_FILE} to EFS."
                )
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


def append_job_row(
    job: dict, score: int, recommendation: str, resume_name: str
) -> None:
    """
    Append a job row to the Google Sheet.

    Columns: Position, Company, Office, Location, Status, Tag, Applied on, Link, Score, Assessment, Resume
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
        resume_name,
    ]

    range_name = f"{config.SHEET_TAB}!A:K"
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


def deduplicate_sheet() -> int:
    """
    Remove duplicate rows identified by the same Link column value.

    - If any duplicate has Status 'Applied': keep the earliest such row, delete the rest.
    - If all duplicates have Status 'Pending': keep the last row, delete the earlier ones.

    Returns the number of rows deleted.
    """
    service = get_sheets_service()

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=config.SHEET_ID, range=f"{config.SHEET_TAB}")
        .execute()
    )
    rows = result.get("values", [])
    if len(rows) <= 1:
        return 0

    header = [h.strip() for h in rows[0]]
    try:
        link_col = header.index("Link")
        status_col = header.index("Status")
    except ValueError as e:
        raise ValueError(f"Required column not found in sheet header: {e}") from e

    # Map link → list of (1-based row index, status)
    link_rows: dict[str, list[tuple[int, str]]] = {}
    for i, row in enumerate(rows[1:], start=2):  # row 1 is header
        link = (row[link_col] if len(row) > link_col else "").strip()
        if not link:
            continue
        status = row[status_col] if len(row) > status_col else ""
        link_rows.setdefault(link, []).append((i, status))

    rows_to_delete: set[int] = set()
    for entries in link_rows.values():
        if len(entries) <= 1:
            continue
        applied = [idx for idx, s in entries if s.strip().lower() == "applied"]
        keep_idx = applied[0] if applied else entries[-1][0]
        rows_to_delete.update(idx for idx, _ in entries if idx != keep_idx)

    if not rows_to_delete:
        return 0

    spreadsheet = service.spreadsheets().get(spreadsheetId=config.SHEET_ID).execute()
    sheet_id = next(
        (
            s["properties"]["sheetId"]
            for s in spreadsheet["sheets"]
            if s["properties"]["title"] == config.SHEET_TAB
        ),
        None,
    )
    if sheet_id is None:
        raise ValueError(f"Sheet tab '{config.SHEET_TAB}' not found")

    # Delete from bottom to top so row indices stay valid
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row_idx - 1,
                    "endIndex": row_idx,
                }
            }
        }
        for row_idx in sorted(rows_to_delete, reverse=True)
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=config.SHEET_ID, body={"requests": requests}
    ).execute()

    return len(rows_to_delete)
