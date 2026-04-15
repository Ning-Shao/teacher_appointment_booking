from __future__ import annotations

import html
import json
import os
import secrets
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse

from booking_logic import (
    BOOKING_HORIZON_DAYS,
    CANCELLATION_CUTOFF_HOURS,
    CANCELLATION_LIMIT_PER_DAY,
    BEIJING_TZ,
    build_booking_summary,
    create_provisional_booking,
    delete_pending_booking,
    finalize_booking,
    finalize_cancellation,
    get_available_slots,
    get_booking_by_cancel_token,
    get_booking_by_id,
    get_google_account,
    init_db,
    json_dump,
    open_db,
    parse_env_file,
    prepare_cancellation,
    release_orphaned_pending_bookings,
    rollback_cancellation,
    save_google_account,
)
from google_services import GoogleIntegrationError, GoogleService


LOCAL_ENV = parse_env_file()


def env_setting(key: str, default: str = "") -> str:
    return os.environ.get(key) or LOCAL_ENV.get(key, default)


def teacher_connect_allowlist() -> set[str]:
    raw = env_setting("TEACHER_CONNECT_ALLOWLIST", "")
    return {value.strip().lower() for value in raw.split(",") if value.strip()}


HOST = env_setting("HOST", "127.0.0.1")
PORT = int(env_setting("PORT", "3000"))
DB_PATH = Path("appointments.db")
GOOGLE_SERVICE = GoogleService()
SESSION_STATES: dict[str, str] = {}
APP_TITLE = "Teacher Appointment Booking"


TRANSLATIONS = {
    "en": {
        "title": "Teacher Appointment Booking",
        "subtitle": "Choose a time in your time zone, confirm your slot, and receive a custom email with a cancellation button.",
        "language": "Language",
        "timezone": "Time zone",
        "duration": "Appointment length",
        "duration_30": "30 minutes",
        "duration_60": "60 minutes",
        "connect_google": "Connect teacher Google account",
        "connected_google": "Connected teacher account",
        "not_connected": "Google integration is not connected yet. Booking still works in demo mode, but real email/calendar sync will start after you connect.",
        "available_dates": "Available dates",
        "available_slots": "Available time slots",
        "selected_slot": "Selected slot",
        "booking_form": "Booking form",
        "name": "Your name",
        "email": "Your email",
        "comments": "Comments or topics to discuss (optional)",
        "confirm_booking": "Confirm booking",
        "reset": "Reset",
        "booking_confirm_text": "Are you sure you want to book this appointment?",
        "cancel_confirm_text": "Are you sure you want to cancel this appointment?",
        "book_success": "Your appointment has been booked.",
        "cancel_success": "Your appointment has been canceled.",
        "no_slots": "No slots available for this date.",
        "choose_date": "Choose a date to see available slots.",
        "choose_slot": "Choose a slot before submitting the form.",
        "loading": "Loading...",
        "connect_hint": "Use this once as the teacher to authorize Gmail and Google Calendar.",
        "student_page_note": "Choose a date, pick a time slot, and confirm the appointment. A confirmation email will include a cancellation button.",
        "student_cancel_button": "Cancel appointment",
        "cancel_page_title": "Cancel appointment",
        "cancel_page_subtitle": "Review the appointment below before canceling it.",
        "cancel_limit_note": "A student email can cancel at most 3 times in one Beijing-calendar day.",
        "cancel_cutoff_note": "Appointments can only be canceled more than 24 hours before the start time.",
        "cancel_button": "Yes, cancel appointment",
        "back_button": "Back to booking page",
        "appointment_request_subject": "Appointment Request",
        "student_confirmation_subject": "Appointment Confirmation",
        "teacher_cancellation_subject": "Appointment Cancellation",
        "student_cancellation_subject": "Cancellation Confirmation",
        "beijing_time": "Beijing time",
        "student_time": "Your time",
        "status_connected": "connected",
        "status_mock": "mock mode",
        "success_popup_title": "Appointment confirmed",
        "success_popup_close": "Close",
        "success_popup_email_note": "Please check your email for the confirmation message and cancellation button.",
        "teacher_setup_title": "Teacher Google Connection",
        "teacher_setup_subtitle": "Use this private page once to connect Gmail and Google Calendar for appointment automation.",
        "teacher_setup_status": "Connection status",
        "teacher_setup_connected": "Connected teacher account",
        "teacher_setup_not_connected": "Google is not connected yet.",
        "teacher_setup_cta": "Connect teacher Google account",
        "teacher_setup_reconnect": "Reconnect Google account",
        "teacher_setup_back": "Back to student booking page",
        "teacher_setup_hidden_note": "Students do not need to use this page.",
        "teacher_setup_whitelist_note": "Only teacher emails on the allowlist can finish Google connection.",
        "teacher_setup_not_allowed": "This Google account is not on the teacher allowlist.",
    },
    "zh": {
        "title": "老师预约网站",
        "subtitle": "按你的所在时区选择时间，确认预约后会收到带取消按钮的自定义邮件。",
        "language": "语言",
        "timezone": "时区",
        "duration": "预约时长",
        "duration_30": "30 分钟",
        "duration_60": "60 分钟",
        "connect_google": "连接老师的 Google 账号",
        "connected_google": "已连接的老师账号",
        "not_connected": "Google 集成暂未连接。现在仍可用演示模式测试预约流程，连接后会自动开启真实日历和邮件同步。",
        "available_dates": "可预约日期",
        "available_slots": "可预约时段",
        "selected_slot": "已选时段",
        "booking_form": "预约表单",
        "name": "你的姓名",
        "email": "你的邮箱",
        "comments": "备注或想讨论的问题（可选）",
        "confirm_booking": "确认预约",
        "reset": "重置",
        "booking_confirm_text": "你确定要预约这个时间吗？",
        "cancel_confirm_text": "Are you sure you want to cancel this appointment?",
        "book_success": "你的预约已成功提交。",
        "cancel_success": "你的预约已取消。",
        "no_slots": "这一天目前没有可用时段。",
        "choose_date": "请先选择日期，再查看可用时段。",
        "choose_slot": "请先选择一个时段再提交表单。",
        "loading": "加载中...",
        "connect_hint": "老师只需操作一次，用来授权 Gmail 和 Google Calendar。",
        "student_page_note": "请选择日期与时段并确认预约。确认邮件里会包含取消预约按钮。",
        "student_cancel_button": "取消预约",
        "cancel_page_title": "取消预约",
        "cancel_page_subtitle": "取消前请先核对下面的预约信息。",
        "cancel_limit_note": "同一个学生邮箱在同一个北京时间自然日最多只能取消 3 次。",
        "cancel_cutoff_note": "预约开始前 24 小时以内不能在线取消。",
        "cancel_button": "确认取消预约",
        "back_button": "返回预约页面",
        "appointment_request_subject": "Appointment Request",
        "student_confirmation_subject": "预约确认",
        "teacher_cancellation_subject": "Appointment Cancellation",
        "student_cancellation_subject": "取消确认",
        "beijing_time": "北京时间",
        "student_time": "你的当地时间",
        "status_connected": "已连接",
        "status_mock": "演示模式",
        "success_popup_title": "预约成功",
        "success_popup_close": "关闭",
        "success_popup_email_note": "请查看你的邮箱，确认邮件里会包含取消预约按钮。",
        "teacher_setup_title": "老师 Google 连接页",
        "teacher_setup_subtitle": "这个私有页面只需要老师使用一次，用来连接 Gmail 和 Google Calendar。",
        "teacher_setup_status": "连接状态",
        "teacher_setup_connected": "已连接的老师账号",
        "teacher_setup_not_connected": "Google 尚未连接。",
        "teacher_setup_cta": "连接老师的 Google 账号",
        "teacher_setup_reconnect": "重新连接 Google 账号",
        "teacher_setup_back": "返回学生预约页面",
        "teacher_setup_hidden_note": "学生不需要进入这个页面。",
        "teacher_setup_whitelist_note": "只有被列入白名单的老师邮箱才能完成 Google 连接。",
        "teacher_setup_not_allowed": "这个 Google 账号不在老师邮箱白名单里。",
    },
}


def teacher_email_template(locale: str, summary: dict[str, Any]) -> tuple[str, str]:
    if locale == "zh":
        plain = (
            f"你收到新的预约请求。\n\n"
            f"学生姓名：{summary['student_name']}\n"
            f"学生邮箱：{summary['student_email']}\n"
            f"学生时区时间：{summary['local_label']}\n"
            f"北京时间：{summary['beijing_label']}\n"
            f"备注：{summary['comments'] or '无'}\n"
        )
        html_text = f"""
        <p>你收到新的预约请求。</p>
        <ul>
          <li>学生姓名：{html.escape(summary['student_name'])}</li>
          <li>学生邮箱：{html.escape(summary['student_email'])}</li>
          <li>学生时区时间：{html.escape(summary['local_label'])}</li>
          <li>北京时间：{html.escape(summary['beijing_label'])}</li>
          <li>备注：{html.escape(summary['comments'] or '无')}</li>
        </ul>
        """
    else:
        plain = (
            f"You have a new appointment request.\n\n"
            f"Student name: {summary['student_name']}\n"
            f"Student email: {summary['student_email']}\n"
            f"Student local time: {summary['local_label']}\n"
            f"Beijing time: {summary['beijing_label']}\n"
            f"Comments: {summary['comments'] or 'None'}\n"
        )
        html_text = f"""
        <p>You have a new appointment request.</p>
        <ul>
          <li>Student name: {html.escape(summary['student_name'])}</li>
          <li>Student email: {html.escape(summary['student_email'])}</li>
          <li>Student local time: {html.escape(summary['local_label'])}</li>
          <li>Beijing time: {html.escape(summary['beijing_label'])}</li>
          <li>Comments: {html.escape(summary['comments'] or 'None')}</li>
        </ul>
        """
    return plain, html_text


def student_confirmation_template(locale: str, summary: dict[str, Any], cancel_url: str) -> tuple[str, str]:
    if locale == "zh":
        plain = (
            f"你的预约已确认。\n\n"
            f"当地时间：{summary['local_label']}\n"
            f"北京时间：{summary['beijing_label']}\n"
            f"如果你需要取消，请在开始前 {CANCELLATION_CUTOFF_HOURS} 小时点击下面链接：\n{cancel_url}\n"
        )
        html_text = f"""
        <p>你的预约已确认。</p>
        <p>当地时间：{html.escape(summary['local_label'])}<br>北京时间：{html.escape(summary['beijing_label'])}</p>
        <p>如果你需要取消，请在开始前 {CANCELLATION_CUTOFF_HOURS} 小时点击下面按钮：</p>
        <p><a href="{html.escape(cancel_url)}" style="background:#1f5fbf;color:#fff;padding:12px 18px;border-radius:8px;text-decoration:none;">取消预约</a></p>
        """
    else:
        plain = (
            f"Your appointment has been confirmed.\n\n"
            f"Your local time: {summary['local_label']}\n"
            f"Beijing time: {summary['beijing_label']}\n"
            f"To cancel more than {CANCELLATION_CUTOFF_HOURS} hours in advance, use this link:\n{cancel_url}\n"
        )
        html_text = f"""
        <p>Your appointment has been confirmed.</p>
        <p>Your local time: {html.escape(summary['local_label'])}<br>Beijing time: {html.escape(summary['beijing_label'])}</p>
        <p>If you need to cancel more than {CANCELLATION_CUTOFF_HOURS} hours in advance, use the button below:</p>
        <p><a href="{html.escape(cancel_url)}" style="background:#1f5fbf;color:#fff;padding:12px 18px;border-radius:8px;text-decoration:none;">Cancel appointment</a></p>
        """
    return plain, html_text


def cancellation_template(locale: str, summary: dict[str, Any], audience: str) -> tuple[str, str]:
    if locale == "zh":
        first_line = "你的预约已取消。" if audience == "student" else "一条预约已被取消。"
        plain = f"{first_line}\n\n当地时间：{summary['local_label']}\n北京时间：{summary['beijing_label']}\n"
        html_text = f"<p>{html.escape(first_line)}</p><p>当地时间：{html.escape(summary['local_label'])}<br>北京时间：{html.escape(summary['beijing_label'])}</p>"
    else:
        first_line = "Your appointment has been canceled." if audience == "student" else "An appointment has been canceled."
        plain = f"{first_line}\n\nLocal time: {summary['local_label']}\nBeijing time: {summary['beijing_label']}\n"
        html_text = f"<p>{html.escape(first_line)}</p><p>Local time: {html.escape(summary['local_label'])}<br>Beijing time: {html.escape(summary['beijing_label'])}</p>"
    return plain, html_text


def app_html() -> str:
    translations_json = json.dumps(TRANSLATIONS, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{APP_TITLE}</title>
  <style>
    :root {{
      --bg: #f7f7f9;
      --panel: #ffffff;
      --ink: #1e293b;
      --muted: #64748b;
      --line: #d8dee9;
      --accent: #1459c7;
      --accent-soft: #e8f0ff;
      --danger: #a61b1b;
      --danger-soft: #ffe9e9;
      --success: #117a4d;
      --success-soft: #e8fbf2;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-size: clamp(1.8rem, 4vw, 2.6rem);
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
      gap: 18px;
      margin-top: 18px;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    label {{
      display: block;
      font-size: 0.9rem;
      margin-bottom: 6px;
      color: var(--muted);
    }}
    select, input, textarea, button {{
      font: inherit;
    }}
    select, input, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      background: #fff;
    }}
    button {{
      border: 0;
      border-radius: 10px;
      padding: 11px 14px;
      cursor: pointer;
    }}
    .primary {{ background: var(--accent); color: white; }}
    .secondary {{ background: #eef2f7; color: var(--ink); }}
    .danger {{ background: var(--danger); color: white; }}
    .note {{
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 12px;
      background: var(--accent-soft);
      color: #20437d;
      line-height: 1.5;
    }}
    .calendar-wrap {{
      display: grid;
      gap: 14px;
    }}
    .month {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
    }}
    .month h3 {{
      margin: 0 0 10px;
      font-size: 1rem;
    }}
    .calendar-grid {{
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 6px;
    }}
    .weekday {{
      text-align: center;
      font-size: 0.82rem;
      color: var(--muted);
      padding-bottom: 4px;
    }}
    .day-btn {{
      border: 1px solid var(--line);
      border-radius: 12px;
      background: white;
      min-height: 46px;
      padding: 8px 6px;
    }}
    .day-btn.muted {{
      background: #f1f5f9;
      color: #94a3b8;
      cursor: default;
    }}
    .day-btn.selected {{
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }}
    .slots {{
      display: grid;
      gap: 10px;
      max-height: 360px;
      overflow-y: auto;
    }}
    .slot {{
      border: 1px solid var(--line);
      border-radius: 12px;
      background: white;
      text-align: left;
    }}
    .slot.selected {{
      border-color: var(--accent);
      background: var(--accent-soft);
    }}
    .slot strong {{
      display: block;
      margin-bottom: 4px;
    }}
    .muted {{
      color: var(--muted);
    }}
    .summary {{
      margin-top: 10px;
      padding: 12px;
      border-radius: 12px;
      background: #f8fafc;
      border: 1px solid var(--line);
      line-height: 1.5;
    }}
    textarea {{
      min-height: 120px;
      resize: vertical;
    }}
    .footer-row {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      margin-top: 12px;
    }}
    .flash {{ margin-top: 12px; padding: 12px; border-radius: 12px; display: none; }}
    .flash.show {{ display: block; }}
    .flash.success {{ background: var(--success-soft); color: var(--success); }}
    .flash.error {{ background: var(--danger-soft); color: var(--danger); }}
    .modal-backdrop {{
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.38);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 50;
    }}
    .modal-backdrop.show {{ display: flex; }}
    .modal {{
      width: min(520px, 100%);
      background: white;
      border-radius: 18px;
      border: 1px solid var(--line);
      box-shadow: 0 18px 50px rgba(15, 23, 42, 0.18);
      overflow: hidden;
    }}
    .modal-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 18px 20px 12px;
      border-bottom: 1px solid var(--line);
    }}
    .modal-header h3 {{
      margin: 0;
      font-size: 1.3rem;
    }}
    .icon-btn {{
      background: transparent;
      color: var(--muted);
      font-size: 1.2rem;
      padding: 6px 10px;
    }}
    .modal-body {{
      padding: 18px 20px 10px;
      line-height: 1.6;
    }}
    .modal-body strong {{
      display: block;
      margin-bottom: 6px;
    }}
    .modal-footer {{
      padding: 12px 20px 20px;
      display: flex;
      justify-content: flex-end;
    }}
    @media (max-width: 980px) {{
      .toolbar, .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1 id="title"></h1>
      <p id="subtitle"></p>
      <div class="toolbar">
        <div>
          <label id="languageLabel" for="languageSelect"></label>
          <select id="languageSelect">
            <option value="en">English</option>
            <option value="zh">简体中文</option>
          </select>
        </div>
        <div>
          <label id="timezoneLabel" for="timezoneSelect"></label>
          <select id="timezoneSelect"></select>
        </div>
        <div>
          <label id="durationLabel" for="durationSelect"></label>
          <select id="durationSelect">
            <option value="30"></option>
            <option value="60"></option>
          </select>
        </div>
      </div>
      <div class="note" id="studentPageNote"></div>
    </section>

    <div class="grid">
      <section class="panel">
        <h2 id="datesHeading"></h2>
        <div id="calendarWrap" class="calendar-wrap"></div>
      </section>

      <section class="panel">
        <h2 id="slotsHeading"></h2>
        <div id="slotHint" class="muted"></div>
        <div id="slots" class="slots" style="margin-top:12px;"></div>

        <div class="summary" id="selectedSummary" style="display:none;"></div>

        <h2 id="formHeading" style="margin-top:18px;"></h2>
        <form id="bookingForm">
          <label id="nameLabel" for="studentName"></label>
          <input id="studentName" name="studentName" required />

          <label id="emailLabel" for="studentEmail" style="margin-top:12px;"></label>
          <input id="studentEmail" name="studentEmail" type="email" required />

          <label id="commentsLabel" for="comments" style="margin-top:12px;"></label>
          <textarea id="comments" name="comments"></textarea>

          <div class="footer-row">
            <button type="button" id="resetBtn" class="secondary"></button>
            <button type="submit" id="submitBtn" class="primary"></button>
          </div>
        </form>
        <div id="flash" class="flash"></div>
      </section>
    </div>

    <div id="successModal" class="modal-backdrop" aria-hidden="true">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="successModalTitle">
        <div class="modal-header">
          <h3 id="successModalTitle"></h3>
          <button type="button" id="closeSuccessModal" class="icon-btn" aria-label="Close">×</button>
        </div>
        <div class="modal-body">
          <strong id="successMessage"></strong>
          <div id="successTimeLocal"></div>
          <div id="successTimeBeijing" class="muted" style="margin-top:6px;"></div>
          <p id="successEmailNote" class="muted" style="margin-top:14px;"></p>
        </div>
        <div class="modal-footer">
          <button type="button" id="closeSuccessButton" class="secondary"></button>
        </div>
      </div>
    </div>
  </div>

  <script>
    const translations = {translations_json};
    const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const state = {{
      locale: "en",
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      duration: 30,
      availability: null,
      selectedDate: null,
      selectedSlot: null
    }};

    const languageSelect = document.getElementById("languageSelect");
    const timezoneSelect = document.getElementById("timezoneSelect");
    const durationSelect = document.getElementById("durationSelect");
    const calendarWrap = document.getElementById("calendarWrap");
    const slotsEl = document.getElementById("slots");
    const slotHint = document.getElementById("slotHint");
    const selectedSummary = document.getElementById("selectedSummary");
    const flash = document.getElementById("flash");
    const bookingForm = document.getElementById("bookingForm");
    const successModal = document.getElementById("successModal");
    const successModalTitle = document.getElementById("successModalTitle");
    const successMessage = document.getElementById("successMessage");
    const successTimeLocal = document.getElementById("successTimeLocal");
    const successTimeBeijing = document.getElementById("successTimeBeijing");
    const successEmailNote = document.getElementById("successEmailNote");
    const closeSuccessModal = document.getElementById("closeSuccessModal");
    const closeSuccessButton = document.getElementById("closeSuccessButton");
    let modalTimer = null;

    function t(key) {{
      return translations[state.locale][key];
    }}

    function setText(id, value) {{
      document.getElementById(id).textContent = value;
    }}

    function populateTimezones() {{
      const values = (Intl.supportedValuesOf && Intl.supportedValuesOf("timeZone")) || [
        "Asia/Shanghai", "America/New_York", "America/Chicago", "America/Los_Angeles", "Europe/London", "UTC"
      ];
      timezoneSelect.innerHTML = values.map(zone => {{
        const selected = zone === state.timezone ? "selected" : "";
        return `<option value="${{zone}}" ${{selected}}>${{zone}}</option>`;
      }}).join("");
      if (![...timezoneSelect.options].some(option => option.value === state.timezone)) {{
        const option = document.createElement("option");
        option.value = state.timezone;
        option.textContent = state.timezone;
        option.selected = true;
        timezoneSelect.appendChild(option);
      }}
    }}

    function applyTranslations() {{
      setText("title", t("title"));
      setText("subtitle", t("subtitle"));
      setText("languageLabel", t("language"));
      setText("timezoneLabel", t("timezone"));
      setText("durationLabel", t("duration"));
      setText("datesHeading", t("available_dates"));
      setText("slotsHeading", t("available_slots"));
      setText("formHeading", t("booking_form"));
      setText("nameLabel", t("name"));
      setText("emailLabel", t("email"));
      setText("commentsLabel", t("comments"));
      setText("submitBtn", t("confirm_booking"));
      setText("resetBtn", t("reset"));
      setText("studentPageNote", t("student_page_note"));
      document.querySelector('#durationSelect option[value="30"]').textContent = t("duration_30");
      document.querySelector('#durationSelect option[value="60"]').textContent = t("duration_60");
      successModalTitle.textContent = t("success_popup_title");
      successEmailNote.textContent = t("success_popup_email_note");
      closeSuccessButton.textContent = t("success_popup_close");
      renderCalendar();
      renderSlots();
    }}

    async function fetchAvailability() {{
      slotHint.textContent = t("loading");
      const params = new URLSearchParams({{
        timezone: state.timezone,
        duration: String(state.duration)
      }});
      const response = await fetch(`/api/availability?${{params.toString()}}`);
      const data = await response.json();
      state.availability = data;
      if (!state.selectedDate || !data.slots_by_local_date[state.selectedDate]) {{
        state.selectedDate = Object.keys(data.slots_by_local_date)[0] || null;
        state.selectedSlot = null;
      }}
      renderCalendar();
      renderSlots();
    }}

    function renderCalendar() {{
      const availability = state.availability;
      if (!availability) {{
        calendarWrap.innerHTML = "";
        return;
      }}
      calendarWrap.innerHTML = availability.months.map(month => {{
        const weekdayRow = weekdays.map(day => `<div class="weekday">${{day}}</div>`).join("");
        const dayCells = month.days.map(day => {{
          const selected = day.iso_date === state.selectedDate;
          const hasSlots = Boolean(availability.slots_by_local_date[day.iso_date]?.length);
          const classes = ["day-btn"];
          if (!day.selectable || !hasSlots) classes.push("muted");
          if (selected) classes.push("selected");
          const disabled = !day.selectable || !hasSlots ? "disabled" : "";
          return `<button class="${{classes.join(" ")}}" data-date="${{day.iso_date}}" ${{disabled}}>${{day.day}}</button>`;
        }}).join("");
        return `<section class="month"><h3>${{month.label}}</h3><div class="calendar-grid">${{weekdayRow}}${{dayCells}}</div></section>`;
      }}).join("");
      calendarWrap.querySelectorAll("button[data-date]").forEach(button => {{
        button.addEventListener("click", () => {{
          state.selectedDate = button.dataset.date;
          state.selectedSlot = null;
          renderCalendar();
          renderSlots();
        }});
      }});
    }}

    function renderSlots() {{
      const availability = state.availability;
      if (!availability) {{
        slotsEl.innerHTML = "";
        return;
      }}
      if (!state.selectedDate) {{
        slotHint.textContent = t("choose_date");
        slotsEl.innerHTML = "";
        selectedSummary.style.display = "none";
        return;
      }}
      const slots = availability.slots_by_local_date[state.selectedDate] || [];
      if (!slots.length) {{
        slotHint.textContent = t("no_slots");
        slotsEl.innerHTML = "";
        selectedSummary.style.display = "none";
        return;
      }}
      slotHint.textContent = "";
      slotsEl.innerHTML = slots.map(slot => {{
        const selected = state.selectedSlot && state.selectedSlot.start_utc === slot.start_utc;
        return `
          <button type="button" class="slot ${{selected ? "selected" : ""}}" data-start="${{slot.start_utc}}">
            <strong>${{slot.local_start_label}} - ${{slot.local_end_label}}</strong>
            <div class="muted">${{slot.beijing_label}}</div>
          </button>
        `;
      }}).join("");
      slotsEl.querySelectorAll("button[data-start]").forEach(button => {{
        button.addEventListener("click", () => {{
          state.selectedSlot = slots.find(slot => slot.start_utc === button.dataset.start);
          renderSlots();
        }});
      }});
      if (state.selectedSlot) {{
        selectedSummary.style.display = "block";
        selectedSummary.innerHTML = `<strong>${{t("selected_slot")}}</strong><br>${{state.selectedSlot.local_start_label}} - ${{state.selectedSlot.local_end_label}}<br><span class="muted">${{state.selectedSlot.beijing_label}}</span>`;
      }} else {{
        selectedSummary.style.display = "none";
      }}
    }}

    function showFlash(message, kind) {{
      flash.className = `flash show ${{kind}}`;
      flash.textContent = message;
    }}

    function hideSuccessModal() {{
      successModal.classList.remove("show");
      successModal.setAttribute("aria-hidden", "true");
      if (modalTimer) {{
        clearTimeout(modalTimer);
        modalTimer = null;
      }}
    }}

    function openSuccessModal(summary, message) {{
      successMessage.textContent = message;
      successTimeLocal.textContent = summary.local_label;
      successTimeBeijing.textContent = summary.beijing_label;
      successModal.classList.add("show");
      successModal.setAttribute("aria-hidden", "false");
      if (modalTimer) {{
        clearTimeout(modalTimer);
      }}
      modalTimer = setTimeout(hideSuccessModal, 3000);
    }}

    bookingForm.addEventListener("submit", async event => {{
      event.preventDefault();
      if (!state.selectedSlot) {{
        showFlash(t("choose_slot"), "error");
        return;
      }}
      if (!window.confirm(t("booking_confirm_text"))) {{
        return;
      }}

      const payload = {{
        student_name: document.getElementById("studentName").value,
        student_email: document.getElementById("studentEmail").value,
        comments: document.getElementById("comments").value,
        slot_start_utc: state.selectedSlot.start_utc,
        slot_length_minutes: state.duration,
        student_timezone: state.timezone,
        locale: state.locale
      }};

      const response = await fetch("/api/book", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload)
      }});
      const result = await response.json();
      if (!response.ok) {{
        showFlash(result.error || "Request failed.", "error");
        return;
      }}
      bookingForm.reset();
      state.selectedSlot = null;
      flash.className = "flash";
      flash.textContent = "";
      selectedSummary.style.display = "none";
      openSuccessModal(result.summary, result.message);
      await fetchAvailability();
    }});

    document.getElementById("resetBtn").addEventListener("click", () => {{
      bookingForm.reset();
      state.selectedSlot = null;
      selectedSummary.style.display = "none";
      flash.className = "flash";
      flash.textContent = "";
      renderSlots();
    }});

    languageSelect.addEventListener("change", async event => {{
      state.locale = event.target.value;
      applyTranslations();
    }});

    timezoneSelect.addEventListener("change", async event => {{
      state.timezone = event.target.value;
      await fetchAvailability();
    }});

    durationSelect.addEventListener("change", async event => {{
      state.duration = Number(event.target.value);
      await fetchAvailability();
    }});

    closeSuccessModal.addEventListener("click", hideSuccessModal);
    closeSuccessButton.addEventListener("click", hideSuccessModal);
    successModal.addEventListener("click", event => {{
      if (event.target === successModal) {{
        hideSuccessModal();
      }}
    }});

    async function boot() {{
      populateTimezones();
      durationSelect.value = String(state.duration);
      applyTranslations();
      await fetchAvailability();
    }}

    boot();
  </script>
</body>
</html>"""


def teacher_connect_html(locale: str, integration: dict[str, Any]) -> str:
    locale = locale if locale in TRANSLATIONS else "en"
    t = TRANSLATIONS[locale]
    language_switch = "zh" if locale == "en" else "en"
    language_label = "简体中文" if locale == "en" else "English"
    connected = integration.get("mode") == "connected"
    status_text = (
        f"{t['teacher_setup_connected']}: {integration.get('google_email')} ({t['status_connected']})"
        if connected
        else t["teacher_setup_not_connected"]
    )
    button_label = t["teacher_setup_reconnect"] if connected else t["teacher_setup_cta"]
    status_class = "good" if connected else ""
    return f"""<!DOCTYPE html>
<html lang="{locale}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(t["teacher_setup_title"])}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f7f7f9; margin:0; color:#1e293b; }}
    .page {{ max-width: 760px; margin: 40px auto; padding: 24px; }}
    .panel {{ background: white; border:1px solid #d8dee9; border-radius: 16px; padding:24px; box-shadow: 0 10px 24px rgba(15,23,42,0.05); }}
    .toolbar {{ display:flex; justify-content:space-between; gap:12px; align-items:center; flex-wrap:wrap; }}
    .note {{ margin-top: 16px; padding: 12px 14px; border-radius: 12px; background:#e8f0ff; color:#20437d; line-height:1.6; }}
    .status {{ margin-top: 14px; padding: 12px 14px; border-radius: 12px; background:#f8fafc; border:1px solid #d8dee9; color:#64748b; }}
    .status.good {{ background:#e8fbf2; color:#117a4d; border-color:#bee3d0; }}
    .actions {{ display:flex; gap:12px; flex-wrap:wrap; margin-top: 18px; }}
    a.button {{ display:inline-block; border-radius:10px; padding:11px 14px; text-decoration:none; }}
    .primary {{ background:#1459c7; color:white; }}
    .secondary {{ background:#eef2f7; color:#1e293b; }}
    .muted {{ color:#64748b; }}
  </style>
</head>
<body>
  <div class="page">
    <section class="panel">
      <div class="toolbar">
        <h1 style="margin:0;">{html.escape(t["teacher_setup_title"])}</h1>
        <a href="/teacher/connect?lang={language_switch}" class="secondary button">{language_label}</a>
      </div>
      <p class="muted">{html.escape(t["teacher_setup_subtitle"])}</p>
      <div class="note">{html.escape(t["teacher_setup_hidden_note"])}</div>
      <div class="note" style="background:#f8fafc;color:#475569;">{html.escape(t["teacher_setup_whitelist_note"])}</div>
      <div class="status {status_class}"><strong>{html.escape(t["teacher_setup_status"])}:</strong> {html.escape(status_text)}</div>
      <div class="actions">
        <a href="/auth/google/start" class="primary button">{html.escape(button_label)}</a>
        <a href="/" class="secondary button">{html.escape(t["teacher_setup_back"])}</a>
      </div>
    </section>
  </div>
</body>
</html>"""


def cancel_html(token: str, locale: str) -> str:
    safe_token = html.escape(token)
    locale = locale if locale in TRANSLATIONS else "en"
    return f"""<!DOCTYPE html>
<html lang="{locale}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{TRANSLATIONS[locale]["cancel_page_title"]}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f7f7f9; margin:0; color:#1e293b; }}
    .page {{ max-width: 760px; margin: 40px auto; padding: 24px; }}
    .panel {{ background: white; border:1px solid #d8dee9; border-radius: 16px; padding:24px; }}
    button {{ border:0; border-radius:10px; padding:12px 16px; cursor:pointer; font:inherit; }}
    .primary {{ background:#a61b1b; color:white; }}
    .secondary {{ background:#eef2f7; color:#1e293b; }}
    .summary {{ margin:18px 0; padding:14px; border-radius:12px; border:1px solid #d8dee9; background:#f8fafc; line-height:1.6; }}
    .flash {{ margin-top: 12px; padding: 12px; border-radius: 12px; display:none; }}
    .flash.show {{ display:block; }}
    .flash.error {{ background:#ffe9e9; color:#a61b1b; }}
    .flash.success {{ background:#e8fbf2; color:#117a4d; }}
  </style>
</head>
<body>
  <div class="page">
    <section class="panel">
      <h1>{html.escape(TRANSLATIONS[locale]["cancel_page_title"])}</h1>
      <p>{html.escape(TRANSLATIONS[locale]["cancel_page_subtitle"])}</p>
      <div class="summary" id="summary">{html.escape(TRANSLATIONS[locale]["loading"])}</div>
      <p>{html.escape(TRANSLATIONS[locale]["cancel_cutoff_note"])}</p>
      <p>{html.escape(TRANSLATIONS[locale]["cancel_limit_note"])}</p>
      <div style="display:flex;gap:10px;flex-wrap:wrap;">
        <button class="primary" id="cancelButton">{html.escape(TRANSLATIONS[locale]["cancel_button"])}</button>
        <a href="/" style="text-decoration:none;"><button class="secondary">{html.escape(TRANSLATIONS[locale]["back_button"])}</button></a>
      </div>
      <div id="flash" class="flash"></div>
    </section>
  </div>
  <script>
    async function loadInfo() {{
      const response = await fetch("/api/cancel-info?token={safe_token}");
      const result = await response.json();
      const summary = document.getElementById("summary");
      if (!response.ok) {{
        summary.textContent = result.error || "Unable to load appointment.";
        return;
      }}
      summary.innerHTML = `
        <strong>${{result.summary.student_name}}</strong><br>
        ${{result.summary.local_label}}<br>
        ${{result.summary.beijing_label}}<br>
        ${{result.summary.student_email}}
      `;
    }}

    function showFlash(message, kind) {{
      const flash = document.getElementById("flash");
      flash.className = `flash show ${{kind}}`;
      flash.textContent = message;
    }}

    document.getElementById("cancelButton").addEventListener("click", async () => {{
      if (!window.confirm({json.dumps(TRANSLATIONS[locale]["cancel_confirm_text"], ensure_ascii=False)})) {{
        return;
      }}
      const response = await fetch("/api/cancel", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ cancel_token: {json.dumps(token)} }})
      }});
      const result = await response.json();
      if (!response.ok) {{
        showFlash(result.error || "Cancellation failed.", "error");
        return;
      }}
      showFlash(result.message, "success");
      document.getElementById("cancelButton").disabled = true;
    }});

    loadInfo();
  </script>
</body>
</html>"""


class BookingHandler(BaseHTTPRequestHandler):
    def _open_connection(self):
        release_orphaned_pending_bookings(self.server.connection)
        return self.server.connection

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json_dump(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, payload: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _parse_query(self) -> dict[str, list[str]]:
        return parse_qs(urlparse(self.path).query)

    def _integration_status(self) -> dict[str, Any]:
        account = get_google_account(self.server.connection)
        if GOOGLE_SERVICE.configured() and account:
            return {"mode": "connected", "google_email": account.get("google_email")}
        return {"mode": "mock", "google_email": None}

    def _build_cancel_url(self, token: str, locale: str) -> str:
        return f"{GOOGLE_SERVICE.base_url.rstrip('/')}/cancel?token={quote(token)}&lang={quote(locale)}"

    def _maybe_send_google_side_effects(self, booking_id: str) -> tuple[str | None, str | None]:
        booking = get_booking_by_id(self.server.connection, booking_id)
        if not booking:
            raise ValueError("Booking not found after creation.")

        summary = build_booking_summary(booking)
        account = get_google_account(self.server.connection)
        if not GOOGLE_SERVICE.configured() or not account:
            return None, None

        access_token, teacher_email = GOOGLE_SERVICE.valid_access_token(
            self.server.connection,
            get_google_account,
            save_google_account,
        )
        if not access_token or not teacher_email:
            raise GoogleIntegrationError("Google account is not connected.")

        event = GOOGLE_SERVICE.create_calendar_event(access_token, booking, teacher_email)
        cancel_url = self._build_cancel_url(booking.cancel_token, booking.locale)

        teacher_plain, teacher_html = teacher_email_template(booking.locale, summary)
        student_plain, student_html = student_confirmation_template(booking.locale, summary, cancel_url)

        try:
            GOOGLE_SERVICE.send_email(
                access_token,
                teacher_email,
                TRANSLATIONS[booking.locale]["appointment_request_subject"],
                teacher_plain,
                teacher_html,
            )
            GOOGLE_SERVICE.send_email(
                access_token,
                booking.student_email,
                TRANSLATIONS[booking.locale]["student_confirmation_subject"],
                student_plain,
                student_html,
            )
        except Exception:
            if event.get("id"):
                GOOGLE_SERVICE.delete_calendar_event(access_token, event["id"])
            raise

        return teacher_email, event.get("id")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(app_html())
            return

        if parsed.path == "/teacher/connect":
            locale = self._parse_query().get("lang", ["en"])[0]
            self._send_html(teacher_connect_html(locale, self._integration_status()))
            return

        if parsed.path == "/cancel":
            query = self._parse_query()
            token = query.get("token", [""])[0]
            locale = query.get("lang", ["en"])[0]
            self._send_html(cancel_html(token, locale))
            return

        if parsed.path == "/api/status":
            self._send_json(
                {
                    "integration": self._integration_status(),
                    "base_url": GOOGLE_SERVICE.base_url,
                }
            )
            return

        if parsed.path == "/api/availability":
            query = self._parse_query()
            timezone = query.get("timezone", ["UTC"])[0]
            duration = int(query.get("duration", ["30"])[0])
            availability = get_available_slots(self.server.connection, timezone, duration)
            availability["integration"] = self._integration_status()
            self._send_json(availability)
            return

        if parsed.path == "/api/cancel-info":
            token = self._parse_query().get("token", [""])[0]
            booking = get_booking_by_cancel_token(self.server.connection, token)
            if not booking:
                self._send_json({"error": "Appointment not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json({"summary": build_booking_summary(booking)})
            return

        if parsed.path == "/auth/google/start":
            if not GOOGLE_SERVICE.configured():
                self._send_html("<h1>Google credentials are not configured.</h1>", status=HTTPStatus.BAD_REQUEST)
                return
            state = secrets.token_urlsafe(24)
            SESSION_STATES[state] = "google_oauth"
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", GOOGLE_SERVICE.oauth_url(state))
            self.end_headers()
            return

        if parsed.path == "/api/auth/callback/google":
            query = self._parse_query()
            state = query.get("state", [""])[0]
            code = query.get("code", [""])[0]
            if not code or SESSION_STATES.pop(state, None) != "google_oauth":
                self._send_html("<h1>Invalid Google OAuth response.</h1>", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                account = GOOGLE_SERVICE.exchange_code(code)
                allowed_teachers = teacher_connect_allowlist()
                google_email = (account.get("google_email") or "").strip().lower()
                if allowed_teachers and google_email not in allowed_teachers:
                    self._send_html(
                        f"<h1>{html.escape(TRANSLATIONS['en']['teacher_setup_not_allowed'])}</h1>"
                        f"<p>{html.escape(google_email)}</p>",
                        status=HTTPStatus.FORBIDDEN,
                    )
                    return
                save_google_account(self.server.connection, account)
                self.send_response(HTTPStatus.FOUND)
                self.send_header("Location", "/teacher/connect")
                self.end_headers()
            except Exception as exc:  # noqa: BLE001
                self._send_html(f"<h1>Google connection failed.</h1><pre>{html.escape(str(exc))}</pre>", status=HTTPStatus.BAD_GATEWAY)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/book":
            try:
                payload = self._read_json()
                booking = create_provisional_booking(self.server.connection, payload)
                try:
                    teacher_email, event_id = self._maybe_send_google_side_effects(booking.booking_id)
                except Exception as exc:  # noqa: BLE001
                    delete_pending_booking(self.server.connection, booking.booking_id)
                    raise exc

                finalize_booking(self.server.connection, booking.booking_id, teacher_email, event_id)
                summary = build_booking_summary(get_booking_by_id(self.server.connection, booking.booking_id))
                message = TRANSLATIONS[payload.get("locale", "en")]["book_success"]
                self._send_json({"message": message, "summary": summary, "integration_mode": self._integration_status()["mode"]})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": f"Booking failed: {exc}"}, status=HTTPStatus.BAD_GATEWAY)
            return

        if parsed.path == "/api/cancel":
            booking = None
            try:
                payload = self._read_json()
                token = str(payload.get("cancel_token", "")).strip()
                booking = prepare_cancellation(self.server.connection, token)
                summary = build_booking_summary(booking)

                account = get_google_account(self.server.connection)
                if GOOGLE_SERVICE.configured() and account:
                    access_token, teacher_email = GOOGLE_SERVICE.valid_access_token(
                        self.server.connection,
                        get_google_account,
                        save_google_account,
                    )
                    if booking.google_event_id:
                        GOOGLE_SERVICE.delete_calendar_event(access_token, booking.google_event_id)
                    teacher_plain, teacher_html = cancellation_template(booking.locale, summary, "teacher")
                    student_plain, student_html = cancellation_template(booking.locale, summary, "student")
                    GOOGLE_SERVICE.send_email(
                        access_token,
                        teacher_email,
                        TRANSLATIONS[booking.locale]["teacher_cancellation_subject"],
                        teacher_plain,
                        teacher_html,
                    )
                    GOOGLE_SERVICE.send_email(
                        access_token,
                        booking.student_email,
                        TRANSLATIONS[booking.locale]["student_cancellation_subject"],
                        student_plain,
                        student_html,
                    )

                finalize_cancellation(self.server.connection, booking.booking_id)
                self._send_json({"message": TRANSLATIONS[booking.locale]["cancel_success"]})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # noqa: BLE001
                if booking is not None:
                    rollback_cancellation(self.server.connection, booking.booking_id)
                self._send_json({"error": f"Cancellation failed: {exc}"}, status=HTTPStatus.BAD_GATEWAY)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_server(host: str = HOST, port: int = PORT) -> None:
    init_db(DB_PATH)
    connection = open_db(DB_PATH)
    server = ThreadingHTTPServer((host, port), BookingHandler)
    server.connection = connection  # type: ignore[attr-defined]
    print(f"Appointment booking site running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        connection.close()
        server.server_close()


if __name__ == "__main__":
    run_server()
