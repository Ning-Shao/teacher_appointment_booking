from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from booking_logic import BookingRecord, datetime_to_iso, iso_to_datetime, now_utc, parse_env_file


TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
OAUTH_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]


class GoogleIntegrationError(RuntimeError):
    pass


class GoogleService:
    def __init__(self) -> None:
        env = parse_env_file()
        self.client_id = os.environ.get("GOOGLE_CLIENT_ID") or env.get("GOOGLE_CLIENT_ID", "")
        self.client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or env.get("GOOGLE_CLIENT_SECRET", "")
        self.base_url = os.environ.get("BASE_URL") or env.get("BASE_URL", "http://localhost:3000")

    @property
    def redirect_uri(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/auth/callback/google"

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.base_url)

    def oauth_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "scope": " ".join(OAUTH_SCOPES),
            "state": state,
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

    def _post_form(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(url, data=encoded, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
            body = exc.read().decode("utf-8", errors="replace")
            raise GoogleIntegrationError(body) from exc

    def _request_json(
        self,
        url: str,
        method: str = "GET",
        access_token: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if access_token:
            request.add_header("Authorization", f"Bearer {access_token}")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
            body = exc.read().decode("utf-8", errors="replace")
            raise GoogleIntegrationError(body) from exc

    def exchange_code(self, code: str) -> dict[str, Any]:
        tokens = self._post_form(
            TOKEN_URL,
            {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        userinfo = self._request_json(USERINFO_URL, access_token=tokens["access_token"])
        expiry = now_utc() + timedelta(seconds=int(tokens.get("expires_in", 3600)))
        return {
            "google_email": userinfo.get("email"),
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expiry_utc": datetime_to_iso(expiry),
            "scope": tokens.get("scope", ""),
            "token_type": tokens.get("token_type", "Bearer"),
        }

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        tokens = self._post_form(
            TOKEN_URL,
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        expiry = now_utc() + timedelta(seconds=int(tokens.get("expires_in", 3600)))
        return {
            "access_token": tokens.get("access_token"),
            "expiry_utc": datetime_to_iso(expiry),
            "scope": tokens.get("scope", ""),
            "token_type": tokens.get("token_type", "Bearer"),
        }

    def valid_access_token(
        self,
        connection,
        account_loader,
        account_saver,
    ) -> tuple[str | None, str | None]:
        account = account_loader(connection)
        if not self.configured() or not account:
            return None, None

        expiry = iso_to_datetime(account["expiry_utc"]) if account.get("expiry_utc") else datetime.now(UTC)
        if now_utc() + timedelta(minutes=5) >= expiry:
            refresh_token = account.get("refresh_token")
            if not refresh_token:
                raise GoogleIntegrationError("Google refresh token is missing.")
            refreshed = self.refresh_access_token(refresh_token)
            merged = {**account, **refreshed}
            account_saver(connection, merged)
            account = account_loader(connection)

        return account.get("access_token"), account.get("google_email")

    def create_calendar_event(
        self,
        access_token: str,
        booking: BookingRecord,
        teacher_email: str,
    ) -> dict[str, Any]:
        local_label = booking.slot_start_utc.astimezone().strftime("%Y-%m-%d %H:%M")
        payload = {
            "summary": f"Student Appointment: {booking.student_name}",
            "description": (
                f"Student name: {booking.student_name}\n"
                f"Student email: {booking.student_email}\n"
                f"Student timezone: {booking.student_timezone}\n"
                f"Requested slot length: {booking.slot_length_minutes} minutes\n"
                f"Comments: {booking.comments or 'None'}\n"
                f"Internal booking ID: {booking.booking_id}\n"
            ),
            "start": {"dateTime": booking.slot_start_utc.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": booking.slot_end_utc.isoformat(), "timeZone": "UTC"},
            "attendees": [{"email": booking.student_email, "displayName": booking.student_name}],
            "guestsCanModify": False,
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 30},
                    {"method": "popup", "minutes": 10},
                ],
            },
            "source": {"title": "Appointment Booking Website", "url": self.base_url},
        }
        url = CALENDAR_EVENTS_URL + "?sendUpdates=all"
        return self._request_json(url, method="POST", access_token=access_token, payload=payload)

    def delete_calendar_event(self, access_token: str, event_id: str) -> None:
        url = f"{CALENDAR_EVENTS_URL}/{urllib.parse.quote(event_id)}?sendUpdates=all"
        self._request_json(url, method="DELETE", access_token=access_token)

    def send_email(
        self,
        access_token: str,
        to_email: str,
        subject: str,
        plain_text: str,
        html_text: str,
    ) -> None:
        message = MIMEMultipart("alternative")
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(plain_text, "plain", "utf-8"))
        message.attach(MIMEText(html_text, "html", "utf-8"))
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        self._request_json(
            GMAIL_SEND_URL,
            method="POST",
            access_token=access_token,
            payload={"raw": raw_message},
        )

