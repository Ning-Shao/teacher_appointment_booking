from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from booking_logic import (
    BEIJING_TZ,
    CANCELLATION_LIMIT_PER_DAY,
    build_booking_summary,
    cancellation_count_today,
    create_provisional_booking,
    finalize_booking,
    finalize_cancellation,
    get_available_slots,
    get_booking_by_cancel_token,
    get_booking_by_id,
    init_db,
    now_utc,
    open_db,
    prepare_cancellation,
)


class BookingLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_db(self.db_path)
        self.connection = open_db(self.db_path)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp_dir.cleanup()

    def test_availability_returns_slots(self) -> None:
        availability = get_available_slots(self.connection, "America/New_York", 30)
        self.assertTrue(availability["slots_by_local_date"])

    def test_overlapping_slot_cannot_be_double_booked(self) -> None:
        start = now_utc() + timedelta(days=2)
        payload = {
            "student_name": "Alice",
            "student_email": "alice@example.com",
            "comments": "",
            "slot_start_utc": start.replace(hour=1, minute=0, second=0, microsecond=0).isoformat(),
            "slot_length_minutes": 60,
            "student_timezone": "America/New_York",
            "locale": "en",
        }
        booking = create_provisional_booking(self.connection, payload)
        finalize_booking(self.connection, booking.booking_id, None, None)

        with self.assertRaises(ValueError):
            create_provisional_booking(self.connection, payload)

    def test_cancellation_limit_applies_by_email(self) -> None:
        start = (now_utc() + timedelta(days=3)).replace(hour=2, minute=0, second=0, microsecond=0)
        last_booking_id = None
        for index in range(CANCELLATION_LIMIT_PER_DAY):
            payload = {
                "student_name": f"Student {index}",
                "student_email": "limit@example.com",
                "comments": "",
                "slot_start_utc": (start + timedelta(hours=index * 2)).isoformat(),
                "slot_length_minutes": 30,
                "student_timezone": "Asia/Shanghai",
                "locale": "en",
            }
            booking = create_provisional_booking(self.connection, payload)
            finalize_booking(self.connection, booking.booking_id, None, None)
            prepared = prepare_cancellation(self.connection, booking.cancel_token)
            finalize_cancellation(self.connection, prepared.booking_id)
            last_booking_id = booking.booking_id

        self.assertEqual(cancellation_count_today(self.connection, "limit@example.com"), CANCELLATION_LIMIT_PER_DAY)

        payload = {
            "student_name": "Fourth",
            "student_email": "limit@example.com",
            "comments": "",
            "slot_start_utc": (start + timedelta(hours=10)).isoformat(),
            "slot_length_minutes": 30,
            "student_timezone": "Asia/Shanghai",
            "locale": "en",
        }
        booking = create_provisional_booking(self.connection, payload)
        finalize_booking(self.connection, booking.booking_id, None, None)
        with self.assertRaises(ValueError):
            prepare_cancellation(self.connection, booking.cancel_token)

        self.assertIsNotNone(get_booking_by_id(self.connection, last_booking_id))

    def test_booking_summary_contains_local_and_beijing_labels(self) -> None:
        start = (now_utc() + timedelta(days=2)).replace(hour=3, minute=0, second=0, microsecond=0)
        payload = {
            "student_name": "Chen",
            "student_email": "chen@example.com",
            "comments": "Need help with classes",
            "slot_start_utc": start.isoformat(),
            "slot_length_minutes": 30,
            "student_timezone": "Europe/London",
            "locale": "zh",
        }
        booking = create_provisional_booking(self.connection, payload)
        finalize_booking(self.connection, booking.booking_id, None, None)
        stored = get_booking_by_cancel_token(self.connection, booking.cancel_token)
        summary = build_booking_summary(stored)
        self.assertIn("Asia/Shanghai", summary["beijing_label"])
        self.assertIn("Europe/London", summary["local_label"])


if __name__ == "__main__":
    unittest.main()
