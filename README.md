# Appointment Booking Website

This project adds a teacher appointment-booking website with:

- English and Simplified Chinese UI switching
- Beijing-time availability windows
- 30-minute and 60-minute slots
- Next-14-days booking horizon
- Conflict prevention with SQLite persistence
- Cancellation flow with a 24-hour cutoff
- Per-student-email cancellation limit of 3 per Beijing-calendar day
- Google Calendar and Gmail integration hooks

## Run locally

1. Copy `.env.example` to `.env.local`
2. Fill in:
   - `HOST`
   - `PORT`
   - `BASE_URL`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `TEACHER_CONNECT_ALLOWLIST`
3. Start the server:

```bash
python3 booking_app.py
```

4. Open [http://localhost:3000](http://localhost:3000)

If Google credentials are not configured or the teacher has not connected the Google account yet, the app still runs in mock mode so you can test the full booking and cancellation flow locally.

Teachers can connect Google only if their email is included in `TEACHER_CONNECT_ALLOWLIST`.

## Tests

```bash
python3 -m unittest test_booking_logic.py
```
