from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BEIJING_TZ = ZoneInfo("Asia/Shanghai")
UTC_TZ = UTC
DB_LOCK = threading.Lock()
BOOKING_WINDOWS = [
    ("08:00", "11:30"),
    ("14:00", "18:00"),
    ("19:00", "23:00"),
]
ALLOWED_SLOT_MINUTES = {30, 60}
BOOKING_HORIZON_DAYS = 14
CANCELLATION_LIMIT_PER_DAY = 3
CANCELLATION_CUTOFF_HOURS = 24


def parse_env_file(path: str | Path = ".env.local") -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def now_utc() -> datetime:
    return datetime.now(UTC_TZ)


def now_beijing() -> datetime:
    return now_utc().astimezone(BEIJING_TZ)


def datetime_to_iso(value: datetime) -> str:
    return value.astimezone(UTC_TZ).replace(microsecond=0).isoformat()


def iso_to_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC_TZ)


def parse_clock(value: str) -> time:
    hour_text, minute_text = value.split(":")
    return time(hour=int(hour_text), minute=int(minute_text), tzinfo=BEIJING_TZ)


def combine_beijing(day_value: date, clock_value: str) -> datetime:
    parsed = parse_clock(clock_value)
    return datetime(
        year=day_value.year,
        month=day_value.month,
        day=day_value.day,
        hour=parsed.hour,
        minute=parsed.minute,
        tzinfo=BEIJING_TZ,
    )


def daterange(start_day: date, total_days: int) -> list[date]:
    return [start_day + timedelta(days=offset) for offset in range(total_days)]


def end_of_horizon(start_day: date, total_days: int) -> date:
    return start_day + timedelta(days=total_days - 1)


def build_calendar_months(start_day: date, total_days: int) -> list[dict[str, Any]]:
    end_day = end_of_horizon(start_day, total_days)
    months: list[dict[str, Any]] = []
    cursor = date(start_day.year, start_day.month, 1)
    final_month = date(end_day.year, end_day.month, 1)

    while cursor <= final_month:
        next_month = date(cursor.year + (cursor.month // 12), ((cursor.month % 12) + 1), 1)
        month_end = next_month - timedelta(days=1)
        grid_start = cursor - timedelta(days=cursor.weekday())
        grid_end = month_end + timedelta(days=(6 - month_end.weekday()))

        days = []
        current = grid_start
        while current <= grid_end:
            in_range = start_day <= current <= end_day
            days.append(
                {
                    "iso_date": current.isoformat(),
                    "day": current.day,
                    "current_month": current.month == cursor.month,
                    "selectable": in_range,
                }
            )
            current += timedelta(days=1)

        months.append(
            {
                "year": cursor.year,
                "month": cursor.month,
                "label": cursor.strftime("%B %Y"),
                "days": days,
            }
        )
        cursor = next_month

    return months


@dataclass
class BookingRecord:
    booking_id: str
    student_name: str
    student_email: str
    comments: str
    locale: str
    student_timezone: str
    slot_start_utc: datetime
    slot_end_utc: datetime
    slot_length_minutes: int
    cancel_token: str
    status: str
    teacher_email: str | None = None
    google_event_id: str | None = None
    created_at_utc: datetime | None = None
    canceled_at_utc: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "booking_id": self.booking_id,
            "student_name": self.student_name,
            "student_email": self.student_email,
            "comments": self.comments,
            "locale": self.locale,
            "student_timezone": self.student_timezone,
            "slot_start_utc": datetime_to_iso(self.slot_start_utc),
            "slot_end_utc": datetime_to_iso(self.slot_end_utc),
            "slot_length_minutes": self.slot_length_minutes,
            "cancel_token": self.cancel_token,
            "status": self.status,
            "teacher_email": self.teacher_email,
            "google_event_id": self.google_event_id,
            "created_at_utc": datetime_to_iso(self.created_at_utc or now_utc()),
            "canceled_at_utc": datetime_to_iso(self.canceled_at_utc) if self.canceled_at_utc else None,
        }


def init_db(db_path: str | Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                google_email TEXT,
                access_token TEXT,
                refresh_token TEXT,
                expiry_utc TEXT,
                scope TEXT,
                token_type TEXT,
                created_at_utc TEXT,
                updated_at_utc TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id TEXT PRIMARY KEY,
                student_name TEXT NOT NULL,
                student_email TEXT NOT NULL,
                comments TEXT NOT NULL,
                locale TEXT NOT NULL,
                student_timezone TEXT NOT NULL,
                slot_start_utc TEXT NOT NULL,
                slot_end_utc TEXT NOT NULL,
                slot_length_minutes INTEGER NOT NULL,
                cancel_token TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                teacher_email TEXT,
                google_event_id TEXT,
                created_at_utc TEXT NOT NULL,
                canceled_at_utc TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cancellation_audit (
                audit_id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL,
                student_email TEXT NOT NULL,
                canceled_at_utc TEXT NOT NULL,
                beijing_cancel_day TEXT NOT NULL
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def open_db(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def row_to_booking(row: sqlite3.Row) -> BookingRecord:
    return BookingRecord(
        booking_id=row["booking_id"],
        student_name=row["student_name"],
        student_email=row["student_email"],
        comments=row["comments"],
        locale=row["locale"],
        student_timezone=row["student_timezone"],
        slot_start_utc=iso_to_datetime(row["slot_start_utc"]),
        slot_end_utc=iso_to_datetime(row["slot_end_utc"]),
        slot_length_minutes=row["slot_length_minutes"],
        cancel_token=row["cancel_token"],
        status=row["status"],
        teacher_email=row["teacher_email"],
        google_event_id=row["google_event_id"],
        created_at_utc=iso_to_datetime(row["created_at_utc"]),
        canceled_at_utc=iso_to_datetime(row["canceled_at_utc"]) if row["canceled_at_utc"] else None,
    )


def build_slot(
    slot_start_bj: datetime,
    duration_minutes: int,
    display_timezone: str,
) -> dict[str, Any]:
    display_tz = ZoneInfo(display_timezone)
    slot_end_bj = slot_start_bj + timedelta(minutes=duration_minutes)
    slot_start_local = slot_start_bj.astimezone(display_tz)
    slot_end_local = slot_end_bj.astimezone(display_tz)
    return {
        "start_utc": datetime_to_iso(slot_start_bj.astimezone(UTC_TZ)),
        "end_utc": datetime_to_iso(slot_end_bj.astimezone(UTC_TZ)),
        "start_beijing": slot_start_bj.isoformat(),
        "end_beijing": slot_end_bj.isoformat(),
        "local_date": slot_start_local.date().isoformat(),
        "local_weekday": slot_start_local.strftime("%A"),
        "local_start_label": slot_start_local.strftime("%Y-%m-%d %H:%M"),
        "local_end_label": slot_end_local.strftime("%H:%M"),
        "beijing_label": f"{slot_start_bj.strftime('%Y-%m-%d %H:%M')} - {slot_end_bj.strftime('%H:%M')} CST",
        "duration_minutes": duration_minutes,
    }


def overlaps(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
) -> bool:
    return start_a < end_b and start_b < end_a


def list_reserved_bookings(
    connection: sqlite3.Connection,
    horizon_start_utc: datetime,
    horizon_end_utc: datetime,
) -> list[BookingRecord]:
    rows = connection.execute(
        """
        SELECT *
        FROM bookings
        WHERE status IN ('booked', 'pending', 'canceling')
          AND slot_end_utc > ?
          AND slot_start_utc < ?
        """,
        (datetime_to_iso(horizon_start_utc), datetime_to_iso(horizon_end_utc)),
    ).fetchall()
    return [row_to_booking(row) for row in rows]


def get_available_slots(
    connection: sqlite3.Connection,
    display_timezone: str,
    duration_minutes: int,
    start_day: date | None = None,
    total_days: int = BOOKING_HORIZON_DAYS,
) -> dict[str, Any]:
    if duration_minutes not in ALLOWED_SLOT_MINUTES:
        raise ValueError("Unsupported slot length.")

    target_timezone = ZoneInfo(display_timezone)
    beijing_today = (start_day or now_beijing().date())
    start_horizon_bj = datetime.combine(beijing_today, time(0, 0), tzinfo=BEIJING_TZ)
    end_horizon_bj = datetime.combine(
        beijing_today + timedelta(days=total_days),
        time(0, 0),
        tzinfo=BEIJING_TZ,
    )
    reserved = list_reserved_bookings(
        connection,
        start_horizon_bj.astimezone(UTC_TZ),
        end_horizon_bj.astimezone(UTC_TZ),
    )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for day_value in daterange(beijing_today, total_days):
        for window_start, window_end in BOOKING_WINDOWS:
            cursor = combine_beijing(day_value, window_start)
            window_end_dt = combine_beijing(day_value, window_end)
            while cursor + timedelta(minutes=duration_minutes) <= window_end_dt:
                slot_end = cursor + timedelta(minutes=duration_minutes)
                slot_start_utc = cursor.astimezone(UTC_TZ)
                slot_end_utc = slot_end.astimezone(UTC_TZ)
                if any(
                    overlaps(slot_start_utc, slot_end_utc, booking.slot_start_utc, booking.slot_end_utc)
                    for booking in reserved
                ):
                    cursor += timedelta(minutes=30)
                    continue

                slot = build_slot(cursor, duration_minutes, display_timezone)
                grouped.setdefault(slot["local_date"], []).append(slot)
                cursor += timedelta(minutes=30)

    local_start_day = start_horizon_bj.astimezone(target_timezone).date()
    local_end_day = (end_horizon_bj - timedelta(seconds=1)).astimezone(target_timezone).date()
    local_total_days = (local_end_day - local_start_day).days + 1
    return {
        "timezone": display_timezone,
        "duration_minutes": duration_minutes,
        "range_start": local_start_day.isoformat(),
        "range_end": local_end_day.isoformat(),
        "months": build_calendar_months(local_start_day, local_total_days),
        "slots_by_local_date": grouped,
    }


def create_provisional_booking(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
) -> BookingRecord:
    student_name = str(payload.get("student_name", "")).strip()
    student_email = str(payload.get("student_email", "")).strip().lower()
    comments = str(payload.get("comments", "")).strip()
    locale = str(payload.get("locale", "en")).strip() or "en"
    student_timezone = str(payload.get("student_timezone", "UTC")).strip()
    slot_start_utc = iso_to_datetime(str(payload.get("slot_start_utc", "")))
    slot_length_minutes = int(payload.get("slot_length_minutes", 0))

    if not student_name:
        raise ValueError("Student name is required.")
    if "@" not in student_email:
        raise ValueError("A valid student email is required.")
    if slot_length_minutes not in ALLOWED_SLOT_MINUTES:
        raise ValueError("Unsupported slot length.")

    try:
        ZoneInfo(student_timezone)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Unsupported time zone.") from exc

    slot_end_utc = slot_start_utc + timedelta(minutes=slot_length_minutes)
    slot_start_bj = slot_start_utc.astimezone(BEIJING_TZ)
    if slot_start_bj.date() < now_beijing().date():
        raise ValueError("Cannot book a slot in the past.")

    booking = BookingRecord(
        booking_id=str(uuid.uuid4()),
        student_name=student_name,
        student_email=student_email,
        comments=comments,
        locale=locale,
        student_timezone=student_timezone,
        slot_start_utc=slot_start_utc,
        slot_end_utc=slot_end_utc,
        slot_length_minutes=slot_length_minutes,
        cancel_token=secrets.token_urlsafe(24),
        status="pending",
        created_at_utc=now_utc(),
    )

    with DB_LOCK:
        conflicts = connection.execute(
            """
            SELECT 1
            FROM bookings
            WHERE status IN ('booked', 'pending', 'canceling')
              AND slot_start_utc < ?
              AND slot_end_utc > ?
            LIMIT 1
            """,
            (datetime_to_iso(booking.slot_end_utc), datetime_to_iso(booking.slot_start_utc)),
        ).fetchone()
        if conflicts:
            raise ValueError("This time slot is no longer available.")

        connection.execute(
            """
            INSERT INTO bookings (
                booking_id,
                student_name,
                student_email,
                comments,
                locale,
                student_timezone,
                slot_start_utc,
                slot_end_utc,
                slot_length_minutes,
                cancel_token,
                status,
                created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                booking.booking_id,
                booking.student_name,
                booking.student_email,
                booking.comments,
                booking.locale,
                booking.student_timezone,
                datetime_to_iso(booking.slot_start_utc),
                datetime_to_iso(booking.slot_end_utc),
                booking.slot_length_minutes,
                booking.cancel_token,
                booking.status,
                datetime_to_iso(booking.created_at_utc),
            ),
        )
        connection.commit()

    return booking


def finalize_booking(
    connection: sqlite3.Connection,
    booking_id: str,
    teacher_email: str | None,
    google_event_id: str | None,
) -> None:
    with DB_LOCK:
        connection.execute(
            """
            UPDATE bookings
            SET status = 'booked',
                teacher_email = ?,
                google_event_id = ?
            WHERE booking_id = ?
            """,
            (teacher_email, google_event_id, booking_id),
        )
        connection.commit()


def delete_pending_booking(connection: sqlite3.Connection, booking_id: str) -> None:
    with DB_LOCK:
        connection.execute("DELETE FROM bookings WHERE booking_id = ? AND status = 'pending'", (booking_id,))
        connection.commit()


def get_booking_by_id(connection: sqlite3.Connection, booking_id: str) -> BookingRecord | None:
    row = connection.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
    return row_to_booking(row) if row else None


def get_booking_by_cancel_token(connection: sqlite3.Connection, token: str) -> BookingRecord | None:
    row = connection.execute("SELECT * FROM bookings WHERE cancel_token = ?", (token,)).fetchone()
    return row_to_booking(row) if row else None


def build_booking_summary(booking: BookingRecord) -> dict[str, Any]:
    student_tz = ZoneInfo(booking.student_timezone)
    local_start = booking.slot_start_utc.astimezone(student_tz)
    local_end = booking.slot_end_utc.astimezone(student_tz)
    beijing_start = booking.slot_start_utc.astimezone(BEIJING_TZ)
    beijing_end = booking.slot_end_utc.astimezone(BEIJING_TZ)
    return {
        "booking_id": booking.booking_id,
        "student_name": booking.student_name,
        "student_email": booking.student_email,
        "comments": booking.comments,
        "locale": booking.locale,
        "student_timezone": booking.student_timezone,
        "status": booking.status,
        "slot_length_minutes": booking.slot_length_minutes,
        "local_label": f"{local_start.strftime('%Y-%m-%d %H:%M')} - {local_end.strftime('%H:%M')} ({booking.student_timezone})",
        "beijing_label": f"{beijing_start.strftime('%Y-%m-%d %H:%M')} - {beijing_end.strftime('%H:%M')} (Asia/Shanghai)",
        "cancel_token": booking.cancel_token,
        "can_cancel": can_cancel_booking(booking, now_utc()),
        "cancellation_limit": CANCELLATION_LIMIT_PER_DAY,
    }


def cancellation_count_today(
    connection: sqlite3.Connection,
    student_email: str,
    reference_time_utc: datetime | None = None,
) -> int:
    reference = (reference_time_utc or now_utc()).astimezone(BEIJING_TZ)
    beijing_day = reference.date().isoformat()
    row = connection.execute(
        """
        SELECT COUNT(*)
        FROM cancellation_audit
        WHERE student_email = ?
          AND beijing_cancel_day = ?
        """,
        (student_email.lower(), beijing_day),
    ).fetchone()
    return int(row[0]) if row else 0


def can_cancel_booking(booking: BookingRecord, reference_time_utc: datetime | None = None) -> bool:
    reference = reference_time_utc or now_utc()
    cutoff = booking.slot_start_utc - timedelta(hours=CANCELLATION_CUTOFF_HOURS)
    return booking.status == "booked" and reference < cutoff


def prepare_cancellation(
    connection: sqlite3.Connection,
    cancel_token: str,
) -> BookingRecord:
    with DB_LOCK:
        booking = get_booking_by_cancel_token(connection, cancel_token)
        if not booking:
            raise ValueError("Booking not found.")
        if booking.status != "booked":
            raise ValueError("This appointment is no longer active.")
        if not can_cancel_booking(booking):
            raise ValueError("This appointment can no longer be canceled online.")
        if cancellation_count_today(connection, booking.student_email) >= CANCELLATION_LIMIT_PER_DAY:
            raise ValueError("This email has reached the daily cancellation limit.")

        connection.execute(
            "UPDATE bookings SET status = 'canceling' WHERE booking_id = ?",
            (booking.booking_id,),
        )
        connection.commit()

    booking.status = "canceling"
    return booking


def rollback_cancellation(connection: sqlite3.Connection, booking_id: str) -> None:
    with DB_LOCK:
        connection.execute(
            "UPDATE bookings SET status = 'booked' WHERE booking_id = ? AND status = 'canceling'",
            (booking_id,),
        )
        connection.commit()


def finalize_cancellation(connection: sqlite3.Connection, booking_id: str) -> None:
    canceled_at = now_utc()
    booking = get_booking_by_id(connection, booking_id)
    if not booking:
        raise ValueError("Booking not found.")

    with DB_LOCK:
        connection.execute(
            """
            UPDATE bookings
            SET status = 'canceled',
                canceled_at_utc = ?
            WHERE booking_id = ?
            """,
            (datetime_to_iso(canceled_at), booking_id),
        )
        connection.execute(
            """
            INSERT INTO cancellation_audit (
                audit_id,
                booking_id,
                student_email,
                canceled_at_utc,
                beijing_cancel_day
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                booking_id,
                booking.student_email,
                datetime_to_iso(canceled_at),
                canceled_at.astimezone(BEIJING_TZ).date().isoformat(),
            ),
        )
        connection.commit()


def release_orphaned_pending_bookings(connection: sqlite3.Connection, older_than_minutes: int = 20) -> None:
    cutoff = now_utc() - timedelta(minutes=older_than_minutes)
    with DB_LOCK:
        connection.execute(
            "DELETE FROM bookings WHERE status = 'pending' AND created_at_utc < ?",
            (datetime_to_iso(cutoff),),
        )
        connection.commit()


def get_google_account(connection: sqlite3.Connection) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM oauth_account WHERE id = 1").fetchone()
    return dict(row) if row else None


def save_google_account(connection: sqlite3.Connection, account: dict[str, Any]) -> None:
    timestamp = datetime_to_iso(now_utc())
    with DB_LOCK:
        existing = get_google_account(connection)
        refresh_token = account.get("refresh_token") or (existing or {}).get("refresh_token")
        connection.execute(
            """
            INSERT INTO oauth_account (
                id,
                google_email,
                access_token,
                refresh_token,
                expiry_utc,
                scope,
                token_type,
                created_at_utc,
                updated_at_utc
            )
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                google_email = excluded.google_email,
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expiry_utc = excluded.expiry_utc,
                scope = excluded.scope,
                token_type = excluded.token_type,
                updated_at_utc = excluded.updated_at_utc
            """,
            (
                account.get("google_email"),
                account.get("access_token"),
                refresh_token,
                account.get("expiry_utc"),
                account.get("scope"),
                account.get("token_type"),
                (existing or {}).get("created_at_utc", timestamp),
                timestamp,
            ),
        )
        connection.commit()


def json_dump(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")
