from __future__ import annotations

import html
import json
import os
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from booking_logic import (
    CANCELLATION_CUTOFF_HOURS,
    build_booking_summary,
    create_contact_request,
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
from course_logic import chatbot_response, list_courses, recommend_courses
from google_services import GoogleIntegrationError, GoogleService


LOCAL_ENV = parse_env_file()


def env_setting(key: str, default: str = "") -> str:
    return os.environ.get(key) or LOCAL_ENV.get(key, default)


def resolved_host() -> str:
    configured_host = os.environ.get("HOST") or LOCAL_ENV.get("HOST", "")
    running_on_render = env_setting("RENDER", "").lower() == "true"
    if running_on_render and configured_host in {"127.0.0.1", "localhost"}:
        return "0.0.0.0"
    if configured_host:
        return configured_host
    return "0.0.0.0" if running_on_render else "127.0.0.1"


def teacher_connect_allowlist() -> set[str]:
    raw = env_setting("TEACHER_CONNECT_ALLOWLIST", "")
    return {value.strip().lower() for value in raw.split(",") if value.strip()}


HOST = resolved_host()
PORT = int(env_setting("PORT", "3000"))
DB_PATH = Path("appointments.db")
GOOGLE_SERVICE = GoogleService()
SESSION_STATES: dict[str, str] = {}
APP_TITLE = "AI Course Recommendation and Appointment Platform"


TRANSLATIONS = {
    "en": {
        "title": "AI Course Recommendation and Appointment Platform",
        "subtitle": "Explore undergraduate and graduate course options, chat with an AI-style advisor, build a conflict-aware weekly plan, and book time with a teacher in one place.",
        "platform_badge": "Portfolio Project Demo",
        "nav_overview": "Overview",
        "nav_advisor": "AI Advisor",
        "nav_results": "Results",
        "nav_catalog": "Course Library",
        "nav_booking": "Book Teacher",
        "nav_real_agent": "Real Agent",
        "hero_cta_advisor": "Start AI advising",
        "hero_cta_booking": "Jump to appointment",
        "hero_stat_courses_value": "12",
        "hero_stat_courses": "sample courses in the library",
        "hero_stat_schedule_value": "Smart",
        "hero_stat_schedule": "schedule planner ready",
        "hero_stat_booking_value": "Live",
        "hero_stat_booking": "teacher booking workflow",
        "language": "Language",
        "advisor_heading": "AI Course Advisor",
        "advisor_subtitle": "Chat first, then complete your planning preferences to unlock recommendation results.",
        "advisor_input_label": "Tell the advisor what you want",
        "advisor_placeholder": "Example: I want an AI-focused semester, not too many morning classes, and I may apply for research opportunities.",
        "advisor_send": "Send to advisor",
        "advisor_reset": "Reset chat",
        "chat_intro": "Share your goals, workload preference, and interests. I will help you explore ideas before you generate a full recommendation plan.",
        "profile_heading": "Planning preferences",
        "career_goal": "Career or semester goal",
        "focus_areas": "Focus areas",
        "focus_ai": "AI",
        "focus_data": "Data",
        "focus_humanities": "Humanities",
        "focus_product": "Product",
        "focus_education": "Education",
        "focus_research": "Research",
        "desired_load": "Semester load",
        "choose_load": "Choose semester load",
        "load_light": "Light",
        "load_balanced": "Balanced",
        "load_challenging": "Challenging",
        "max_credits": "Target credits",
        "preferred_days": "Preferred class days",
        "avoid_mornings": "Avoid morning classes when possible",
        "advisor_form_note": "Complete the required planning fields on the right before generating recommendation results.",
        "advisor_form_required": "Complete the required planning fields first:",
        "advisor_missing_load": "semester load",
        "advisor_missing_credits": "target credits",
        "advisor_missing_focus": "focus areas",
        "advisor_missing_days": "preferred class days",
        "generate_ready": "Your planning form is complete. You can now generate recommendation results.",
        "generate_plan": "Generate recommendations",
        "catalog_heading": "Simulated Course Library",
        "catalog_subtitle": "A mock catalog with both undergraduate and graduate-level courses for demos and portfolio presentations.",
        "results_heading": "Recommendation Results",
        "results_subtitle": "Use the shortlist as a draft and refine it with a teacher afterward.",
        "results_empty": "Recommendation cards, conflict checks, and your weekly schedule will appear here after you complete the planning form and click generate.",
        "insights_heading": "Advisor summary",
        "recommendations_heading": "Recommended courses",
        "conflicts_heading": "Conflict detection",
        "conflicts_none": "No major time conflicts were found in the shortlisted options.",
        "schedule_heading": "Suggested weekly schedule",
        "schedule_total_credits": "Total credits",
        "book_teacher_cta": "Book a teacher to discuss this plan",
        "booking_prefill_notice": "One click will bring this draft schedule into the appointment form comments box.",
        "booking_prefill_applied": "Recommendation summary inserted into the booking form.",
        "recommended_badge": "Included in draft schedule",
        "match_reasons": "Why it matches",
        "meeting_times": "Meeting times",
        "outcomes": "Learning outcomes",
        "program_level": "Program level",
        "program_undergraduate": "Undergraduate",
        "program_graduate": "Graduate",
        "no_class_blocks": "No class blocks on this day.",
        "booking_section_title": "Teacher Appointment",
        "booking_section_subtitle": "Keep the original scheduling workflow and use it as the advising step after recommendation.",
        "timezone": "Time zone",
        "duration": "Appointment length",
        "duration_30": "30 minutes",
        "duration_60": "60 minutes",
        "available_dates": "Available dates",
        "available_slots": "Available time slots",
        "selected_slot": "Selected slot",
        "booking_form": "Booking form",
        "name": "Your name",
        "email": "Your email",
        "phone": "Phone number",
        "comments": "Comments or topics to discuss",
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
        "student_page_note": "Pick a time, confirm the appointment, and continue the advising conversation with your generated course plan.",
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
        "success_popup_email_note": "Check your email for the confirmation message and cancellation button.",
        "teacher_setup_title": "Teacher Google Connection",
        "teacher_setup_subtitle": "Use this private page once to connect Gmail and Google Calendar for appointment automation.",
        "teacher_setup_status": "Connection status",
        "teacher_setup_connected": "Connected teacher account",
        "teacher_setup_not_connected": "Google is not connected yet.",
        "teacher_setup_cta": "Connect teacher Google account",
        "teacher_setup_reconnect": "Reconnect Google account",
        "teacher_setup_back": "Back to platform",
        "teacher_setup_hidden_note": "Students do not need to use this page.",
        "teacher_setup_whitelist_note": "Only teacher emails on the allowlist can finish Google connection.",
        "teacher_setup_not_allowed": "This Google account is not on the teacher allowlist.",
        "cancel_page_title": "Cancel appointment",
        "cancel_page_subtitle": "Review the appointment below before canceling it.",
        "cancel_limit_note": "A student email can cancel at most 3 times in one Beijing-calendar day.",
        "cancel_cutoff_note": "Appointments can only be canceled more than 24 hours before the start time.",
        "cancel_button": "Yes, cancel appointment",
        "back_button": "Back to platform",
        "real_agent_heading": "Want To Talk To A Real Agent?",
        "real_agent_subtitle": "Leave your contact details and a short note. A real teacher can follow up with you afterward.",
        "real_agent_contact_hint": "Please leave at least one contact method: email or phone.",
        "real_agent_button": "Request human follow-up",
        "real_agent_success": "Your request has been received. A teacher can follow up with you later.",
        "contact_us": "Contact us",
        "technology_support": "Technology support",
        "footer_rights": "Copyright 2026 AI Course Recommendation and Appointment Platform. All rights reserved.",
        "day_mon": "Mon",
        "day_tue": "Tue",
        "day_wed": "Wed",
        "day_thu": "Thu",
        "day_fri": "Fri",
    },
    "zh": {
        "title": "AI 课程推荐与预约平台",
        "subtitle": "在一个平台里完成本科与研究生课程探索、AI 顾问对话、时间冲突检测、周课表生成，以及老师预约。",
        "platform_badge": "简历项目 Demo",
        "nav_overview": "平台概览",
        "nav_advisor": "AI 顾问",
        "nav_results": "推荐结果",
        "nav_catalog": "课程库",
        "nav_booking": "预约老师",
        "nav_real_agent": "真人咨询",
        "hero_cta_advisor": "开始 AI 推荐",
        "hero_cta_booking": "直接去预约",
        "hero_stat_courses_value": "12",
        "hero_stat_courses": "门课程样例",
        "hero_stat_schedule_value": "智能",
        "hero_stat_schedule": "排课引擎已就绪",
        "hero_stat_booking_value": "在线",
        "hero_stat_booking": "老师预约流程可用",
        "language": "语言",
        "advisor_heading": "AI 选课顾问",
        "advisor_subtitle": "先聊天，再补全右侧规划信息，最后解锁完整推荐结果。",
        "advisor_input_label": "告诉顾问你的需求",
        "advisor_placeholder": "例如：我想走 AI 方向，不想太多早课，而且可能想申请科研机会。",
        "advisor_send": "发送给顾问",
        "advisor_reset": "重置对话",
        "chat_intro": "告诉我你的目标、课程负担偏好和兴趣方向，我会先帮你梳理思路，再生成完整推荐。",
        "profile_heading": "规划偏好",
        "career_goal": "学期目标或职业方向",
        "focus_areas": "重点方向",
        "focus_ai": "人工智能",
        "focus_data": "数据",
        "focus_humanities": "人文",
        "focus_product": "产品",
        "focus_education": "教育",
        "focus_research": "研究",
        "desired_load": "学期负担",
        "choose_load": "请选择学期负担",
        "load_light": "轻量",
        "load_balanced": "均衡",
        "load_challenging": "冲刺",
        "max_credits": "目标学分",
        "preferred_days": "偏好的上课日",
        "avoid_mornings": "尽量避免早课",
        "advisor_form_note": "请先在右侧补全必填规划信息，再生成推荐结果。",
        "advisor_form_required": "请先补全这些必填项：",
        "advisor_missing_load": "学期负担",
        "advisor_missing_credits": "目标学分",
        "advisor_missing_focus": "重点方向",
        "advisor_missing_days": "偏好的上课日",
        "generate_ready": "你的规划表单已经完整，现在可以生成推荐结果。",
        "generate_plan": "生成推荐方案",
        "catalog_heading": "模拟课程库",
        "catalog_subtitle": "这是为作品集、演示和面试展示设计的 mock 课程目录，包含本科与研究生两个层级。",
        "results_heading": "推荐结果",
        "results_subtitle": "先把它当作草案，再预约老师进一步讨论和调整。",
        "results_empty": "补全规划表单并点击生成后，这里会展示推荐卡片、冲突检测和周课表。",
        "insights_heading": "顾问总结",
        "recommendations_heading": "推荐课程",
        "conflicts_heading": "时间冲突检测",
        "conflicts_none": "当前 shortlist 中没有明显的时间冲突。",
        "schedule_heading": "建议周课表",
        "schedule_total_credits": "总学分",
        "book_teacher_cta": "预约老师讨论这份方案",
        "booking_prefill_notice": "点击后会把这份课表草案自动带入预约表单备注。",
        "booking_prefill_applied": "推荐结果已经填入预约表单备注。",
        "recommended_badge": "已纳入草案课表",
        "match_reasons": "匹配原因",
        "meeting_times": "上课时间",
        "outcomes": "学习产出",
        "program_level": "课程层级",
        "program_undergraduate": "本科",
        "program_graduate": "研究生",
        "no_class_blocks": "这一天没有安排课程。",
        "booking_section_title": "老师预约",
        "booking_section_subtitle": "保留原有预约功能，并把它作为推荐结果后的老师咨询入口。",
        "timezone": "时区",
        "duration": "预约时长",
        "duration_30": "30 分钟",
        "duration_60": "60 分钟",
        "available_dates": "可预约日期",
        "available_slots": "可预约时段",
        "selected_slot": "已选时段",
        "booking_form": "预约表单",
        "name": "你的姓名",
        "email": "你的邮箱",
        "phone": "电话号码",
        "comments": "备注或想讨论的问题",
        "confirm_booking": "确认预约",
        "reset": "重置",
        "booking_confirm_text": "你确定要预约这个时间吗？",
        "cancel_confirm_text": "你确定要取消这个预约吗？",
        "book_success": "你的预约已成功提交。",
        "cancel_success": "你的预约已取消。",
        "no_slots": "这一天目前没有可用时段。",
        "choose_date": "请先选择日期，再查看可用时段。",
        "choose_slot": "请先选择一个时段再提交表单。",
        "loading": "加载中...",
        "student_page_note": "选择时段并完成预约后，你可以继续围绕生成的课程方案和老师讨论。",
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
        "teacher_setup_back": "返回平台",
        "teacher_setup_hidden_note": "学生不需要进入这个页面。",
        "teacher_setup_whitelist_note": "只有被列入白名单的老师邮箱才能完成 Google 连接。",
        "teacher_setup_not_allowed": "这个 Google 账号不在老师邮箱白名单里。",
        "cancel_page_title": "取消预约",
        "cancel_page_subtitle": "取消前请先核对下面的预约信息。",
        "cancel_limit_note": "同一个学生邮箱在同一个北京时间自然日最多只能取消 3 次。",
        "cancel_cutoff_note": "预约开始前 24 小时以内不能在线取消。",
        "cancel_button": "确认取消预约",
        "back_button": "返回平台",
        "real_agent_heading": "想和真人顾问沟通吗？",
        "real_agent_subtitle": "留下你的联系方式和简短说明，后续可以由真实老师继续跟进。",
        "real_agent_contact_hint": "请至少留下一个联系方式：邮箱或电话。",
        "real_agent_button": "提交真人跟进请求",
        "real_agent_success": "你的请求已收到，老师后续可以联系你。",
        "contact_us": "联系我们",
        "technology_support": "技术支持",
        "footer_rights": "Copyright 2026 AI 课程推荐与预约平台。保留所有权利。",
        "day_mon": "周一",
        "day_tue": "周二",
        "day_wed": "周三",
        "day_thu": "周四",
        "day_fri": "周五",
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
        <p><a href="{html.escape(cancel_url)}" style="background:#1459c7;color:#fff;padding:12px 18px;border-radius:8px;text-decoration:none;">取消预约</a></p>
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
        <p><a href="{html.escape(cancel_url)}" style="background:#1459c7;color:#fff;padding:12px 18px;border-radius:8px;text-decoration:none;">Cancel appointment</a></p>
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


def app_html(initial_section: str = "overview") -> str:
    translations_json = json.dumps(TRANSLATIONS, ensure_ascii=False)
    template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__APP_TITLE__</title>
  <style>
    :root {
      --bg: #f6efe3;
      --ink: #172033;
      --muted: #5f6b84;
      --panel: rgba(255, 252, 248, 0.88);
      --panel-strong: #fffdf8;
      --line: rgba(23, 32, 51, 0.1);
      --accent: #0e766e;
      --accent-soft: rgba(14, 118, 110, 0.12);
      --accent-strong: #d96b2b;
      --danger: #9c2d2d;
      --danger-soft: rgba(200, 56, 56, 0.12);
      --shadow: 0 22px 48px rgba(23, 32, 51, 0.08);
      --radius: 24px;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(217, 107, 43, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(14, 118, 110, 0.16), transparent 24%),
        linear-gradient(180deg, #f8f1e7 0%, #f4eadc 45%, #f7f2ea 100%);
      font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
    }
    a { color: inherit; }
    .shell {
      max-width: 1320px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 8px 14px;
      background: rgba(255, 255, 255, 0.62);
      border: 1px solid var(--line);
      color: var(--accent);
      font-size: 0.92rem;
      letter-spacing: 0.02em;
    }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.9fr);
      gap: 20px;
      align-items: stretch;
      margin-bottom: 22px;
    }
    .hero-main, .hero-side, .panel, .footer {
      background: var(--panel);
      backdrop-filter: blur(8px);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .hero-main {
      padding: 28px;
      position: relative;
      overflow: hidden;
    }
    .hero-main::after {
      content: "";
      position: absolute;
      right: -60px;
      top: -70px;
      width: 220px;
      height: 220px;
      border-radius: 50%;
      background: linear-gradient(135deg, rgba(14, 118, 110, 0.16), rgba(217, 107, 43, 0.18));
      filter: blur(4px);
    }
    .hero-main h1 {
      margin: 18px 0 12px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(2.25rem, 4vw, 3.8rem);
      line-height: 1.08;
      max-width: 11ch;
    }
    .hero-main p {
      position: relative;
      z-index: 1;
      max-width: 60ch;
      line-height: 1.7;
      color: var(--muted);
      margin: 0;
    }
    .hero-actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 24px;
    }
    .primary-link, .primary, .secondary, .ghost {
      border: 0;
      border-radius: 999px;
      padding: 12px 16px;
      font: inherit;
      cursor: pointer;
      text-decoration: none;
      transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
    }
    .primary-link, .primary {
      background: linear-gradient(135deg, var(--accent) 0%, #0d9488 100%);
      color: white;
      box-shadow: 0 12px 24px rgba(14, 118, 110, 0.24);
    }
    .secondary, .ghost {
      background: rgba(255, 255, 255, 0.86);
      color: var(--ink);
      border: 1px solid var(--line);
    }
    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }
    .hero-side {
      padding: 24px;
      display: grid;
      gap: 14px;
      background: linear-gradient(180deg, rgba(255, 252, 248, 0.95), rgba(255, 246, 237, 0.88));
    }
    .hero-stat {
      padding: 18px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
    }
    .hero-stat strong {
      display: block;
      font-size: 1.9rem;
      margin-bottom: 6px;
      font-family: Georgia, "Times New Roman", serif;
    }
    .nav {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 22px;
      padding: 14px;
      border-radius: 20px;
      background: rgba(246, 239, 227, 0.88);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(23, 32, 51, 0.08);
    }
    .nav-links, .nav-tools {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .nav a {
      text-decoration: none;
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--line);
    }
    .nav-tools label {
      color: var(--muted);
      margin: 0;
      font-size: 0.9rem;
    }
    .nav-tools select {
      width: auto;
      min-width: 136px;
    }
    .section {
      margin-top: 26px;
      scroll-margin-top: 96px;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: end;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }
    .section-head h2 {
      margin: 0;
      font-size: clamp(1.5rem, 3vw, 2.2rem);
      font-family: Georgia, "Times New Roman", serif;
    }
    .section-head p {
      margin: 0;
      max-width: 62ch;
      line-height: 1.6;
      color: var(--muted);
    }
    .two-col, .booking-grid, .results-grid {
      display: grid;
      gap: 18px;
    }
    .two-col { grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr); }
    .results-grid { grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr); }
    .booking-grid { grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr); }
    .panel {
      padding: 22px;
      overflow: hidden;
    }
    .panel h3 {
      margin: 0 0 10px;
      font-size: 1.15rem;
    }
    .panel p.lead {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.6;
    }
    .input-row, .toolbar, .checkbox-grid, .weekday-grid, .button-row, .contact-grid {
      display: grid;
      gap: 12px;
    }
    .toolbar { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 18px; }
    .checkbox-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .weekday-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .button-row { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 14px; }
    .contact-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    label {
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 0.94rem;
    }
    input, textarea, select, button { font: inherit; }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      background: rgba(255, 255, 255, 0.9);
      color: var(--ink);
    }
    textarea { min-height: 120px; resize: vertical; }
    .check-pill {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
    }
    .check-pill input { width: auto; }
    .chat-log {
      display: grid;
      gap: 12px;
      min-height: 220px;
      max-height: 460px;
      overflow: auto;
      padding-right: 4px;
    }
    .chat-msg {
      padding: 14px 16px;
      border-radius: 20px;
      line-height: 1.6;
      border: 1px solid var(--line);
      max-width: 92%;
      white-space: pre-wrap;
    }
    .chat-msg.user {
      margin-left: auto;
      background: rgba(14, 118, 110, 0.12);
      border-bottom-right-radius: 8px;
    }
    .chat-msg.assistant {
      background: rgba(255, 255, 255, 0.85);
      border-bottom-left-radius: 8px;
    }
    .prompt-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-top: 14px;
    }
    .subtle-note {
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(14, 118, 110, 0.08);
      color: #0f5d58;
      line-height: 1.6;
    }
    .empty-state {
      padding: 20px;
      border-radius: 20px;
      border: 1px dashed rgba(23, 32, 51, 0.22);
      color: var(--muted);
      background: rgba(255, 255, 255, 0.48);
      line-height: 1.6;
    }
    .insight-list, .course-grid, .conflict-list, .catalog-grid, .schedule-grid {
      display: grid;
      gap: 14px;
    }
    .catalog-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .course-card, .insight-card, .conflict-card, .schedule-day {
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.78);
      padding: 16px;
    }
    .course-card h4, .schedule-day h4 { margin: 0 0 8px; font-size: 1.05rem; }
    .meta-row, .tag-row, .reason-list, .meeting-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .meta-pill, .tag, .reason-pill, .meeting-pill, .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 7px 10px;
      font-size: 0.88rem;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.9);
    }
    .status-pill {
      background: var(--accent-soft);
      color: var(--accent);
      border-color: rgba(14, 118, 110, 0.2);
    }
    .reason-list { display: grid; gap: 8px; margin-top: 12px; }
    .reason-pill {
      border-radius: 14px;
      white-space: normal;
      line-height: 1.5;
      justify-content: start;
      background: rgba(217, 107, 43, 0.08);
      border-color: rgba(217, 107, 43, 0.18);
    }
    .schedule-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .schedule-block {
      margin-top: 10px;
      padding: 12px;
      border-radius: 14px;
      background: rgba(14, 118, 110, 0.08);
      border: 1px solid rgba(14, 118, 110, 0.14);
    }
    .schedule-block strong { display: block; margin-bottom: 4px; }
    .calendar-wrap { display: grid; gap: 14px; }
    .month {
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
      background: rgba(255, 255, 255, 0.7);
    }
    .month h3 { margin: 0 0 12px; font-size: 1rem; }
    .calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }
    .weekday { text-align: center; font-size: 0.82rem; color: var(--muted); }
    .day-btn, .slot {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.9);
      padding: 10px;
      cursor: pointer;
    }
    .day-btn.muted {
      background: rgba(235, 238, 244, 0.85);
      color: #97a0b5;
      cursor: default;
    }
    .day-btn.selected, .slot.selected {
      background: var(--accent-soft);
      border-color: rgba(14, 118, 110, 0.28);
    }
    .slots { display: grid; gap: 10px; max-height: 360px; overflow: auto; }
    .slot strong { display: block; margin-bottom: 4px; }
    .muted { color: var(--muted); }
    .summary {
      margin-top: 12px;
      padding: 14px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.75);
      line-height: 1.6;
    }
    .flash {
      margin-top: 14px;
      padding: 14px;
      border-radius: 18px;
      display: none;
      line-height: 1.6;
    }
    .flash.show { display: block; }
    .flash.success { background: rgba(14, 118, 110, 0.12); color: #0f5d58; }
    .flash.error { background: var(--danger-soft); color: var(--danger); }
    .footer {
      margin-top: 26px;
      padding: 20px 22px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      align-items: center;
    }
    .footer-links {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(23, 32, 51, 0.36);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 50;
    }
    .modal-backdrop.show { display: flex; }
    .modal {
      width: min(520px, 100%);
      background: var(--panel-strong);
      border-radius: 24px;
      border: 1px solid var(--line);
      box-shadow: 0 28px 60px rgba(23, 32, 51, 0.18);
      overflow: hidden;
    }
    .modal-header, .modal-footer {
      padding: 18px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-body { padding: 0 20px 20px; line-height: 1.7; }
    .icon-btn {
      background: transparent;
      border: 0;
      padding: 4px 8px;
      cursor: pointer;
      color: var(--muted);
      font-size: 1.3rem;
    }
    @media (max-width: 1120px) {
      .hero, .two-col, .results-grid, .booking-grid, .catalog-grid, .schedule-grid, .toolbar, .checkbox-grid, .weekday-grid, .contact-grid {
        grid-template-columns: 1fr;
      }
      .nav { position: static; }
      .prompt-actions, .footer { flex-direction: column; align-items: stretch; }
      .footer-links { justify-content: flex-start; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="topbar">
      <span class="badge" data-i18n="platform_badge"></span>
    </div>

    <section class="hero" id="overview">
      <div class="hero-main">
        <h1 data-i18n="title"></h1>
        <p data-i18n="subtitle"></p>
        <div class="hero-actions">
          <a class="primary-link" href="#advisor" data-i18n="hero_cta_advisor"></a>
          <a class="ghost" href="#booking" data-i18n="hero_cta_booking"></a>
        </div>
      </div>
      <div class="hero-side">
        <div class="hero-stat"><strong data-i18n="hero_stat_courses_value"></strong><span data-i18n="hero_stat_courses"></span></div>
        <div class="hero-stat"><strong data-i18n="hero_stat_schedule_value"></strong><span data-i18n="hero_stat_schedule"></span></div>
        <div class="hero-stat"><strong data-i18n="hero_stat_booking_value"></strong><span data-i18n="hero_stat_booking"></span></div>
      </div>
    </section>

    <nav class="nav">
      <div class="nav-links">
        <a href="#overview" data-i18n="nav_overview"></a>
        <a href="#advisor" data-i18n="nav_advisor"></a>
        <a href="#results" data-i18n="nav_results"></a>
        <a href="#catalog" data-i18n="nav_catalog"></a>
        <a href="#booking" data-i18n="nav_booking"></a>
        <a href="#real-agent" data-i18n="nav_real_agent"></a>
      </div>
      <div class="nav-tools">
        <label for="languageSelect" data-i18n="language"></label>
        <select id="languageSelect">
          <option value="en">English</option>
          <option value="zh">简体中文</option>
        </select>
      </div>
    </nav>

    <section class="section" id="advisor">
      <div class="section-head">
        <div>
          <h2 data-i18n="advisor_heading"></h2>
          <p data-i18n="advisor_subtitle"></p>
        </div>
      </div>
      <div class="two-col">
        <section class="panel">
          <div class="section-head" style="margin-bottom: 12px;">
            <h3 data-i18n="advisor_heading"></h3>
            <button type="button" id="resetAdvisorBtn" class="secondary" data-i18n="advisor_reset"></button>
          </div>
          <div id="chatLog" class="chat-log"></div>
          <div style="margin-top: 16px;">
            <label for="advisorInput" data-i18n="advisor_input_label"></label>
            <textarea id="advisorInput" data-i18n-placeholder="advisor_placeholder"></textarea>
            <div class="prompt-actions">
              <div></div>
              <button type="button" id="sendAdvisorBtn" class="primary" data-i18n="advisor_send"></button>
            </div>
          </div>
        </section>

        <section class="panel">
          <h3 data-i18n="profile_heading"></h3>
          <p class="lead" data-i18n="advisor_form_note"></p>
          <div id="advisorStatusNote" class="subtle-note"></div>
          <div id="advisorFlash" class="flash"></div>
          <div class="input-row">
            <div>
              <label for="careerGoal" data-i18n="career_goal"></label>
              <input id="careerGoal" />
            </div>
            <div>
              <label for="desiredLoad" data-i18n="desired_load"></label>
              <select id="desiredLoad">
                <option value="" data-i18n="choose_load"></option>
                <option value="light" data-i18n="load_light"></option>
                <option value="balanced" data-i18n="load_balanced"></option>
                <option value="challenging" data-i18n="load_challenging"></option>
              </select>
            </div>
            <div>
              <label for="maxCredits" data-i18n="max_credits"></label>
              <input id="maxCredits" type="number" min="6" max="18" step="1" />
            </div>
            <div>
              <label data-i18n="focus_areas"></label>
              <div class="checkbox-grid">
                <label class="check-pill"><input type="checkbox" class="focus-area" value="ai" /><span data-i18n="focus_ai"></span></label>
                <label class="check-pill"><input type="checkbox" class="focus-area" value="data" /><span data-i18n="focus_data"></span></label>
                <label class="check-pill"><input type="checkbox" class="focus-area" value="humanities" /><span data-i18n="focus_humanities"></span></label>
                <label class="check-pill"><input type="checkbox" class="focus-area" value="product" /><span data-i18n="focus_product"></span></label>
                <label class="check-pill"><input type="checkbox" class="focus-area" value="education" /><span data-i18n="focus_education"></span></label>
                <label class="check-pill"><input type="checkbox" class="focus-area" value="research" /><span data-i18n="focus_research"></span></label>
              </div>
            </div>
            <div>
              <label data-i18n="preferred_days"></label>
              <div class="weekday-grid">
                <label class="check-pill"><input type="checkbox" class="preferred-day" value="Mon" /><span data-i18n="day_mon"></span></label>
                <label class="check-pill"><input type="checkbox" class="preferred-day" value="Tue" /><span data-i18n="day_tue"></span></label>
                <label class="check-pill"><input type="checkbox" class="preferred-day" value="Wed" /><span data-i18n="day_wed"></span></label>
                <label class="check-pill"><input type="checkbox" class="preferred-day" value="Thu" /><span data-i18n="day_thu"></span></label>
                <label class="check-pill"><input type="checkbox" class="preferred-day" value="Fri" /><span data-i18n="day_fri"></span></label>
              </div>
            </div>
            <label class="check-pill"><input id="avoidMornings" type="checkbox" /><span data-i18n="avoid_mornings"></span></label>
            <button type="button" id="generatePlanBtn" class="primary" data-i18n="generate_plan"></button>
          </div>
        </section>
      </div>
    </section>

    <section class="section" id="results">
      <div class="section-head">
        <div>
          <h2 data-i18n="results_heading"></h2>
          <p data-i18n="results_subtitle"></p>
        </div>
      </div>
      <div id="resultsEmpty" class="empty-state" data-i18n="results_empty"></div>
      <div id="resultsContent" style="display:none;">
        <section class="panel" style="margin-bottom: 18px;">
          <h3 data-i18n="insights_heading"></h3>
          <div id="insightsList" class="insight-list"></div>
        </section>
        <div class="results-grid">
          <section class="panel">
            <h3 data-i18n="recommendations_heading"></h3>
            <div id="recommendationsList" class="course-grid"></div>
          </section>
          <section class="panel">
            <h3 data-i18n="conflicts_heading"></h3>
            <div id="conflictsList" class="conflict-list"></div>
          </section>
        </div>
        <section class="panel" style="margin-top: 18px;">
          <div class="section-head" style="margin-bottom: 12px;">
            <h3 data-i18n="schedule_heading"></h3>
            <span id="scheduleCredits" class="status-pill"></span>
          </div>
          <div id="scheduleGrid" class="schedule-grid"></div>
        </section>
        <section class="panel" style="margin-top: 18px; background: linear-gradient(135deg, rgba(14, 118, 110, 0.12), rgba(217, 107, 43, 0.12));">
          <p id="bookingPrefillNotice" class="lead" data-i18n="booking_prefill_notice"></p>
          <button type="button" id="bookTeacherBtn" class="primary" data-i18n="book_teacher_cta"></button>
        </section>
      </div>
    </section>

    <section class="section" id="catalog">
      <div class="section-head">
        <div>
          <h2 data-i18n="catalog_heading"></h2>
          <p data-i18n="catalog_subtitle"></p>
        </div>
      </div>
      <section class="panel">
        <div id="catalogGrid" class="catalog-grid"></div>
      </section>
    </section>

    <section class="section" id="booking">
      <div class="section-head">
        <div>
          <h2 data-i18n="booking_section_title"></h2>
          <p data-i18n="booking_section_subtitle"></p>
        </div>
      </div>
      <section class="panel">
        <div class="toolbar">
          <div>
            <label for="timezoneSelect" data-i18n="timezone"></label>
            <select id="timezoneSelect"></select>
          </div>
          <div>
            <label for="durationSelect" data-i18n="duration"></label>
            <select id="durationSelect">
              <option value="30" data-i18n="duration_30"></option>
              <option value="60" data-i18n="duration_60"></option>
            </select>
          </div>
        </div>
        <p class="lead" data-i18n="student_page_note"></p>
      </section>
      <div class="booking-grid" style="margin-top: 18px;">
        <section class="panel">
          <h3 data-i18n="available_dates"></h3>
          <div id="calendarWrap" class="calendar-wrap"></div>
        </section>
        <section class="panel">
          <h3 data-i18n="available_slots"></h3>
          <div id="slotHint" class="muted"></div>
          <div id="slots" class="slots" style="margin-top:12px;"></div>
          <div class="summary" id="selectedSummary" style="display:none;"></div>
          <h3 style="margin-top:20px;" data-i18n="booking_form"></h3>
          <form id="bookingForm">
            <label for="studentName" data-i18n="name"></label>
            <input id="studentName" name="studentName" required />
            <label for="studentEmail" style="margin-top:12px;" data-i18n="email"></label>
            <input id="studentEmail" name="studentEmail" type="email" required />
            <label for="comments" style="margin-top:12px;" data-i18n="comments"></label>
            <textarea id="comments" name="comments"></textarea>
            <div class="button-row">
              <button type="button" id="resetBtn" class="secondary" data-i18n="reset"></button>
              <button type="submit" id="submitBtn" class="primary" data-i18n="confirm_booking"></button>
            </div>
          </form>
          <div id="flash" class="flash"></div>
        </section>
      </div>
    </section>

    <section class="section" id="real-agent">
      <div class="section-head">
        <div>
          <h2 data-i18n="real_agent_heading"></h2>
          <p data-i18n="real_agent_subtitle"></p>
        </div>
      </div>
      <section class="panel">
        <p class="lead" data-i18n="real_agent_contact_hint"></p>
        <form id="realAgentForm">
          <div class="contact-grid">
            <div>
              <label for="agentName" data-i18n="name"></label>
              <input id="agentName" required />
            </div>
            <div>
              <label for="agentPhone" data-i18n="phone"></label>
              <input id="agentPhone" />
            </div>
          </div>
          <div class="contact-grid" style="margin-top: 12px;">
            <div>
              <label for="agentEmail" data-i18n="email"></label>
              <input id="agentEmail" type="email" />
            </div>
            <div></div>
          </div>
          <div style="margin-top: 12px;">
            <label for="agentMessage" data-i18n="comments"></label>
            <textarea id="agentMessage" required></textarea>
          </div>
          <div class="prompt-actions">
            <div></div>
            <button type="submit" id="realAgentBtn" class="primary" data-i18n="real_agent_button"></button>
          </div>
        </form>
        <div id="agentFlash" class="flash"></div>
      </section>
    </section>

    <footer class="footer">
      <div class="footer-links">
        <a href="mailto:contact@aicourseplatform.demo" data-i18n="contact_us"></a>
        <a href="mailto:support@aicourseplatform.demo" data-i18n="technology_support"></a>
      </div>
      <div class="muted" data-i18n="footer_rights"></div>
    </footer>

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
    const translations = __TRANSLATIONS__;
    const initialSection = __INITIAL_SECTION__;
    const bookingWeekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const state = {
      locale: "en",
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      duration: 30,
      availability: null,
      selectedDate: null,
      selectedSlot: null,
      courses: [],
      recommendation: null,
      chatMessages: [],
      advisorProfile: {
        career_goal: "",
        focus_areas: [],
        desired_load: "",
        max_credits: null,
        preferred_days: [],
        avoid_mornings: false,
      }
    };

    const languageSelect = document.getElementById("languageSelect");
    const timezoneSelect = document.getElementById("timezoneSelect");
    const durationSelect = document.getElementById("durationSelect");
    const chatLog = document.getElementById("chatLog");
    const advisorInput = document.getElementById("advisorInput");
    const careerGoal = document.getElementById("careerGoal");
    const desiredLoad = document.getElementById("desiredLoad");
    const maxCredits = document.getElementById("maxCredits");
    const avoidMornings = document.getElementById("avoidMornings");
    const advisorStatusNote = document.getElementById("advisorStatusNote");
    const advisorFlash = document.getElementById("advisorFlash");
    const generatePlanBtn = document.getElementById("generatePlanBtn");
    const resultsEmpty = document.getElementById("resultsEmpty");
    const resultsContent = document.getElementById("resultsContent");
    const insightsList = document.getElementById("insightsList");
    const recommendationsList = document.getElementById("recommendationsList");
    const conflictsList = document.getElementById("conflictsList");
    const scheduleGrid = document.getElementById("scheduleGrid");
    const scheduleCredits = document.getElementById("scheduleCredits");
    const catalogGrid = document.getElementById("catalogGrid");
    const bookTeacherBtn = document.getElementById("bookTeacherBtn");
    const calendarWrap = document.getElementById("calendarWrap");
    const slotsEl = document.getElementById("slots");
    const slotHint = document.getElementById("slotHint");
    const selectedSummary = document.getElementById("selectedSummary");
    const flash = document.getElementById("flash");
    const bookingForm = document.getElementById("bookingForm");
    const agentForm = document.getElementById("realAgentForm");
    const agentFlash = document.getElementById("agentFlash");
    const successModal = document.getElementById("successModal");
    const successModalTitle = document.getElementById("successModalTitle");
    const successMessage = document.getElementById("successMessage");
    const successTimeLocal = document.getElementById("successTimeLocal");
    const successTimeBeijing = document.getElementById("successTimeBeijing");
    const successEmailNote = document.getElementById("successEmailNote");
    const closeSuccessModal = document.getElementById("closeSuccessModal");
    const closeSuccessButton = document.getElementById("closeSuccessButton");
    let modalTimer = null;

    function t(key) {
      return translations[state.locale][key] || key;
    }

    function preferredDayInputs() {
      return [...document.querySelectorAll(".preferred-day")];
    }

    function focusAreaInputs() {
      return [...document.querySelectorAll(".focus-area")];
    }

    function advisorConversationText() {
      const messages = state.chatMessages.filter(message => message.role === "user").map(message => message.text.trim()).filter(Boolean);
      const goal = careerGoal.value.trim();
      if (goal) {
        messages.push(goal);
      }
      return messages.join(" ");
    }

    function addChatMessage(role, text) {
      state.chatMessages.push({ role, text });
      renderChat();
    }

    function resetChat() {
      state.chatMessages = [{ role: "assistant", text: t("chat_intro") }];
      renderChat();
    }

    function showAdvisorFlash(message, kind) {
      advisorFlash.className = `flash show ${kind}`;
      advisorFlash.textContent = message;
    }

    function showAgentFlash(message, kind) {
      agentFlash.className = `flash show ${kind}`;
      agentFlash.textContent = message;
    }

    function clearAdvisorFlash() {
      advisorFlash.className = "flash";
      advisorFlash.textContent = "";
    }

    function requiredProfileIssues() {
      const issues = [];
      if (!desiredLoad.value) {
        issues.push(t("advisor_missing_load"));
      }
      if (!maxCredits.value || Number(maxCredits.value) <= 0) {
        issues.push(t("advisor_missing_credits"));
      }
      if (!focusAreaInputs().some(input => input.checked)) {
        issues.push(t("advisor_missing_focus"));
      }
      if (!preferredDayInputs().some(input => input.checked)) {
        issues.push(t("advisor_missing_days"));
      }
      return issues;
    }

    function setAdvisorFormState() {
      const issues = requiredProfileIssues();
      if (issues.length) {
        advisorStatusNote.textContent = `${t("advisor_form_required")} ${issues.join(", ")}`;
        generatePlanBtn.disabled = true;
      } else {
        advisorStatusNote.textContent = t("generate_ready");
        generatePlanBtn.disabled = false;
      }
    }

    function applyTranslations() {
      document.documentElement.lang = state.locale;
      document.title = t("title");
      document.querySelectorAll("[data-i18n]").forEach(element => {
        element.textContent = t(element.dataset.i18n);
      });
      document.querySelectorAll("[data-i18n-placeholder]").forEach(element => {
        element.placeholder = t(element.dataset.i18nPlaceholder);
      });
      closeSuccessButton.textContent = t("success_popup_close");
      successModalTitle.textContent = t("success_popup_title");
      successEmailNote.textContent = t("success_popup_email_note");
      if (state.chatMessages.length <= 1 && state.chatMessages[0]?.role === "assistant") {
        state.chatMessages[0].text = t("chat_intro");
      }
      renderChat();
      renderCatalog();
      renderResults();
      renderCalendar();
      renderSlots();
      setAdvisorFormState();
    }

    function populateTimezones() {
      const values = (Intl.supportedValuesOf && Intl.supportedValuesOf("timeZone")) || [
        "Asia/Shanghai", "America/New_York", "America/Chicago", "America/Los_Angeles", "Europe/London", "UTC"
      ];
      timezoneSelect.innerHTML = values.map(zone => {
        const selected = zone === state.timezone ? "selected" : "";
        return `<option value="${zone}" ${selected}>${zone}</option>`;
      }).join("");
      if (![...timezoneSelect.options].some(option => option.value === state.timezone)) {
        const option = document.createElement("option");
        option.value = state.timezone;
        option.textContent = state.timezone;
        option.selected = true;
        timezoneSelect.appendChild(option);
      }
    }

    function renderChat() {
      chatLog.innerHTML = state.chatMessages.map(message => `<div class="chat-msg ${message.role}">${message.text.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>`).join("");
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    function renderCatalog() {
      catalogGrid.innerHTML = state.courses.map(course => {
        const meetings = course.meetings.map(meeting => `${meeting.day_label} ${meeting.start}-${meeting.end}`).join(" · ");
        const outcomes = course.outcomes.slice(0, 2).join(" · ");
        return `
          <article class="course-card">
            <div class="meta-row">
              <span class="meta-pill">${course.course_id}</span>
              <span class="meta-pill">${course.area_label}</span>
              <span class="meta-pill">${course.program_level_label}</span>
              <span class="meta-pill">${course.credits} cr</span>
            </div>
            <h4>${course.title}</h4>
            <p class="muted">${course.description}</p>
            <div class="meeting-list"><span class="meeting-pill">${t("meeting_times")}: ${meetings}</span></div>
            <div class="tag-row">${course.tags.slice(0, 4).map(tag => `<span class="tag">${tag}</span>`).join("")}</div>
            <div class="reason-list"><span class="reason-pill">${t("outcomes")}: ${outcomes}</span></div>
          </article>
        `;
      }).join("");
    }

    function renderResults() {
      if (!state.recommendation) {
        resultsEmpty.style.display = "block";
        resultsContent.style.display = "none";
        return;
      }
      resultsEmpty.style.display = "none";
      resultsContent.style.display = "block";
      insightsList.innerHTML = state.recommendation.insights.map(item => `<div class="insight-card">${item}</div>`).join("");
      recommendationsList.innerHTML = state.recommendation.recommended_courses.map(course => {
        const reasons = course.match_reasons.map(reason => `<span class="reason-pill">${reason}</span>`).join("");
        const meetings = course.meetings.map(meeting => `${meeting.day_label} ${meeting.start}-${meeting.end}`).join(" · ");
        return `
          <article class="course-card">
            <div class="meta-row">
              <span class="meta-pill">${course.course_id}</span>
              <span class="meta-pill">${course.area_label}</span>
              <span class="meta-pill">${course.program_level_label}</span>
              <span class="meta-pill">${course.credits} cr</span>
              ${course.recommended_for_schedule ? `<span class="status-pill">${t("recommended_badge")}</span>` : ""}
            </div>
            <h4>${course.title}</h4>
            <p class="muted">${course.description}</p>
            <div class="meeting-list"><span class="meeting-pill">${t("meeting_times")}: ${meetings}</span></div>
            <div class="reason-list">${reasons}</div>
          </article>
        `;
      }).join("");
      if (state.recommendation.conflicts.length) {
        conflictsList.innerHTML = state.recommendation.conflicts.map(conflict => `<div class="conflict-card"><strong>${conflict.course_a.title}</strong> + <strong>${conflict.course_b.title}</strong><br><span class="muted">${conflict.summary} ${conflict.time_range}</span></div>`).join("");
      } else {
        conflictsList.innerHTML = `<div class="conflict-card">${t("conflicts_none")}</div>`;
      }
      scheduleCredits.textContent = `${t("schedule_total_credits")}: ${state.recommendation.schedule.total_credits}`;
      scheduleGrid.innerHTML = state.recommendation.schedule.days.map(day => {
        const blocks = day.blocks.length
          ? day.blocks.map(block => `<div class="schedule-block"><strong>${block.title}</strong>${block.start}-${block.end}<br><span class="muted">${block.area_label} · ${block.program_level_label}</span></div>`).join("")
          : `<div class="schedule-block" style="background: rgba(255,255,255,0.7); border-color: rgba(23,32,51,0.08);">${t("no_class_blocks")}</div>`;
        return `<div class="schedule-day"><h4>${day.label}</h4>${blocks}</div>`;
      }).join("");
    }

    function collectProfile() {
      return {
        career_goal: careerGoal.value.trim(),
        focus_areas: focusAreaInputs().filter(input => input.checked).map(input => input.value),
        desired_load: desiredLoad.value,
        max_credits: maxCredits.value ? Number(maxCredits.value) : null,
        preferred_days: preferredDayInputs().filter(input => input.checked).map(input => input.value),
        avoid_mornings: avoidMornings.checked,
      };
    }

    function syncProfile(profile) {
      state.advisorProfile = { ...state.advisorProfile, ...profile };
      careerGoal.value = state.advisorProfile.career_goal || "";
      desiredLoad.value = state.advisorProfile.desired_load || "";
      maxCredits.value = state.advisorProfile.max_credits ? String(state.advisorProfile.max_credits) : "";
      avoidMornings.checked = Boolean(state.advisorProfile.avoid_mornings);
      focusAreaInputs().forEach(input => {
        input.checked = (state.advisorProfile.focus_areas || []).includes(input.value);
      });
      preferredDayInputs().forEach(input => {
        input.checked = (state.advisorProfile.preferred_days || []).includes(input.value);
      });
      setAdvisorFormState();
    }

    async function fetchCourses() {
      const response = await fetch(`/api/courses?lang=${state.locale}`);
      state.courses = await response.json();
      renderCatalog();
    }

    async function generatePlan(message = "") {
      clearAdvisorFlash();
      const issues = requiredProfileIssues();
      if (issues.length) {
        showAdvisorFlash(`${t("advisor_form_required")} ${issues.join(", ")}`, "error");
        return;
      }
      const response = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale: state.locale, message, profile: collectProfile() }),
      });
      const result = await response.json();
      if (!response.ok) {
        showAdvisorFlash(result.error || "Request failed.", "error");
        return;
      }
      syncProfile(result.profile);
      state.recommendation = result;
      renderResults();
      document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
    }

    async function sendAdvisorMessage() {
      clearAdvisorFlash();
      const message = advisorInput.value.trim();
      if (!message) {
        return;
      }
      addChatMessage("user", message);
      advisorInput.value = "";
      const response = await fetch("/api/chatbot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale: state.locale, message, profile: collectProfile() }),
      });
      const result = await response.json();
      if (!response.ok) {
        showAdvisorFlash(result.error || "Request failed.", "error");
        return;
      }
      if (!careerGoal.value.trim() && result.profile?.career_goal) {
        careerGoal.value = result.profile.career_goal;
      }
      addChatMessage("assistant", `${result.reply}

${result.follow_up}`);
      setAdvisorFormState();
    }

    function showFlash(message, kind) {
      flash.className = `flash show ${kind}`;
      flash.textContent = message;
    }

    function hideSuccessModal() {
      successModal.classList.remove("show");
      successModal.setAttribute("aria-hidden", "true");
      if (modalTimer) {
        clearTimeout(modalTimer);
        modalTimer = null;
      }
    }

    function openSuccessModal(summary, message) {
      successMessage.textContent = message;
      successTimeLocal.textContent = summary.local_label;
      successTimeBeijing.textContent = summary.beijing_label;
      successModal.classList.add("show");
      successModal.setAttribute("aria-hidden", "false");
      if (modalTimer) {
        clearTimeout(modalTimer);
      }
      modalTimer = setTimeout(hideSuccessModal, 3000);
    }

    async function fetchAvailability() {
      slotHint.textContent = t("loading");
      const params = new URLSearchParams({ timezone: state.timezone, duration: String(state.duration) });
      const response = await fetch(`/api/availability?${params.toString()}`);
      const data = await response.json();
      state.availability = data;
      if (!state.selectedDate || !data.slots_by_local_date[state.selectedDate]) {
        state.selectedDate = Object.keys(data.slots_by_local_date)[0] || null;
        state.selectedSlot = null;
      }
      renderCalendar();
      renderSlots();
    }

    function renderCalendar() {
      const availability = state.availability;
      if (!availability) {
        calendarWrap.innerHTML = "";
        return;
      }
      calendarWrap.innerHTML = availability.months.map(month => {
        const weekdayRow = bookingWeekdays.map(day => `<div class="weekday">${day}</div>`).join("");
        const dayCells = month.days.map(day => {
          const selected = day.iso_date === state.selectedDate;
          const hasSlots = Boolean(availability.slots_by_local_date[day.iso_date]?.length);
          const classes = ["day-btn"];
          if (!day.selectable || !hasSlots) classes.push("muted");
          if (selected) classes.push("selected");
          const disabled = !day.selectable || !hasSlots ? "disabled" : "";
          return `<button class="${classes.join(" ")}" data-date="${day.iso_date}" ${disabled}>${day.day}</button>`;
        }).join("");
        return `<section class="month"><h3>${month.label}</h3><div class="calendar-grid">${weekdayRow}${dayCells}</div></section>`;
      }).join("");
      calendarWrap.querySelectorAll("button[data-date]").forEach(button => {
        button.addEventListener("click", () => {
          state.selectedDate = button.dataset.date;
          state.selectedSlot = null;
          renderCalendar();
          renderSlots();
        });
      });
    }

    function renderSlots() {
      const availability = state.availability;
      if (!availability) {
        slotsEl.innerHTML = "";
        return;
      }
      if (!state.selectedDate) {
        slotHint.textContent = t("choose_date");
        slotsEl.innerHTML = "";
        selectedSummary.style.display = "none";
        return;
      }
      const slots = availability.slots_by_local_date[state.selectedDate] || [];
      if (!slots.length) {
        slotHint.textContent = t("no_slots");
        slotsEl.innerHTML = "";
        selectedSummary.style.display = "none";
        return;
      }
      slotHint.textContent = "";
      slotsEl.innerHTML = slots.map(slot => {
        const selected = state.selectedSlot && state.selectedSlot.start_utc === slot.start_utc;
        return `
          <button type="button" class="slot ${selected ? "selected" : ""}" data-start="${slot.start_utc}">
            <strong>${slot.local_start_label} - ${slot.local_end_label}</strong>
            <div class="muted">${slot.beijing_label}</div>
          </button>
        `;
      }).join("");
      slotsEl.querySelectorAll("button[data-start]").forEach(button => {
        button.addEventListener("click", () => {
          state.selectedSlot = slots.find(slot => slot.start_utc === button.dataset.start);
          renderSlots();
        });
      });
      if (state.selectedSlot) {
        selectedSummary.style.display = "block";
        selectedSummary.innerHTML = `<strong>${t("selected_slot")}</strong><br>${state.selectedSlot.local_start_label} - ${state.selectedSlot.local_end_label}<br><span class="muted">${state.selectedSlot.beijing_label}</span>`;
      } else {
        selectedSummary.style.display = "none";
      }
    }

    async function submitRealAgentRequest(event) {
      event.preventDefault();
      const payload = {
        student_name: document.getElementById("agentName").value,
        student_email: document.getElementById("agentEmail").value,
        student_phone: document.getElementById("agentPhone").value,
        message: document.getElementById("agentMessage").value,
        locale: state.locale,
      };
      const response = await fetch("/api/contact-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) {
        showAgentFlash(result.error || "Request failed.", "error");
        return;
      }
      agentForm.reset();
      showAgentFlash(result.message, "success");
    }

    document.getElementById("sendAdvisorBtn").addEventListener("click", sendAdvisorMessage);
    document.getElementById("resetAdvisorBtn").addEventListener("click", () => {
      state.recommendation = null;
      syncProfile({ career_goal: "", focus_areas: [], desired_load: "", max_credits: null, preferred_days: [], avoid_mornings: false });
      clearAdvisorFlash();
      resetChat();
      renderResults();
    });
    generatePlanBtn.addEventListener("click", () => generatePlan(advisorConversationText()));
    advisorInput.addEventListener("keydown", event => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        sendAdvisorMessage();
      }
    });
    [careerGoal, desiredLoad, maxCredits, avoidMornings, ...focusAreaInputs(), ...preferredDayInputs()].forEach(input => {
      input.addEventListener("change", setAdvisorFormState);
      input.addEventListener("input", setAdvisorFormState);
    });
    bookTeacherBtn.addEventListener("click", () => {
      if (!state.recommendation) {
        return;
      }
      document.getElementById("comments").value = state.recommendation.booking_prefill;
      showFlash(t("booking_prefill_applied"), "success");
      document.getElementById("booking").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    agentForm.addEventListener("submit", submitRealAgentRequest);

    bookingForm.addEventListener("submit", async event => {
      event.preventDefault();
      if (!state.selectedSlot) {
        showFlash(t("choose_slot"), "error");
        return;
      }
      if (!window.confirm(t("booking_confirm_text"))) {
        return;
      }
      const payload = {
        student_name: document.getElementById("studentName").value,
        student_email: document.getElementById("studentEmail").value,
        comments: document.getElementById("comments").value,
        slot_start_utc: state.selectedSlot.start_utc,
        slot_length_minutes: state.duration,
        student_timezone: state.timezone,
        locale: state.locale,
      };
      const response = await fetch("/api/book", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) {
        showFlash(result.error || "Request failed.", "error");
        return;
      }
      bookingForm.reset();
      state.selectedSlot = null;
      flash.className = "flash";
      flash.textContent = "";
      selectedSummary.style.display = "none";
      openSuccessModal(result.summary, result.message);
      await fetchAvailability();
    });

    document.getElementById("resetBtn").addEventListener("click", () => {
      bookingForm.reset();
      state.selectedSlot = null;
      selectedSummary.style.display = "none";
      flash.className = "flash";
      flash.textContent = "";
      renderSlots();
    });

    languageSelect.addEventListener("change", async event => {
      state.locale = event.target.value;
      applyTranslations();
      await fetchCourses();
      if (state.recommendation) {
        await generatePlan(advisorConversationText());
      }
    });
    timezoneSelect.addEventListener("change", async event => {
      state.timezone = event.target.value;
      await fetchAvailability();
    });
    durationSelect.addEventListener("change", async event => {
      state.duration = Number(event.target.value);
      await fetchAvailability();
    });

    closeSuccessModal.addEventListener("click", hideSuccessModal);
    closeSuccessButton.addEventListener("click", hideSuccessModal);
    successModal.addEventListener("click", event => {
      if (event.target === successModal) {
        hideSuccessModal();
      }
    });

    async function boot() {
      languageSelect.value = state.locale;
      populateTimezones();
      durationSelect.value = String(state.duration);
      syncProfile(state.advisorProfile);
      resetChat();
      applyTranslations();
      await Promise.all([fetchCourses(), fetchAvailability()]);
      if (initialSection && initialSection !== "overview") {
        const node = document.getElementById(initialSection);
        if (node) {
          setTimeout(() => node.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
        }
      }
    }

    boot();
  </script>
</body>
</html>
"""
    return template.replace("__APP_TITLE__", html.escape(APP_TITLE)).replace("__TRANSLATIONS__", translations_json).replace("__INITIAL_SECTION__", json.dumps(initial_section))


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
  <title>{html.escape(t['teacher_setup_title'])}</title>
  <style>
    body {{ font-family: "Avenir Next", "Trebuchet MS", sans-serif; background:#f7f2ea; margin:0; color:#172033; }}
    .page {{ max-width: 760px; margin: 40px auto; padding: 24px; }}
    .panel {{ background: white; border:1px solid rgba(23,32,51,0.08); border-radius: 24px; padding:24px; box-shadow: 0 18px 40px rgba(23,32,51,0.08); }}
    .toolbar {{ display:flex; justify-content:space-between; gap:12px; align-items:center; flex-wrap:wrap; }}
    .note {{ margin-top: 16px; padding: 12px 14px; border-radius: 16px; background:#e8f6f4; color:#0f5d58; line-height:1.6; }}
    .status {{ margin-top: 14px; padding: 12px 14px; border-radius: 16px; background:#fbfcfe; border:1px solid rgba(23,32,51,0.08); color:#5f6b84; }}
    .status.good {{ background:#e8fbf2; color:#117a4d; border-color:#bee3d0; }}
    .actions {{ display:flex; gap:12px; flex-wrap:wrap; margin-top: 18px; }}
    a.button {{ display:inline-block; border-radius:999px; padding:11px 14px; text-decoration:none; }}
    .primary {{ background:#0e766e; color:white; }}
    .secondary {{ background:#eef2f7; color:#172033; }}
    .muted {{ color:#5f6b84; }}
  </style>
</head>
<body>
  <div class="page">
    <section class="panel">
      <div class="toolbar">
        <h1 style="margin:0;">{html.escape(t['teacher_setup_title'])}</h1>
        <a href="/teacher/connect?lang={language_switch}" class="secondary button">{language_label}</a>
      </div>
      <p class="muted">{html.escape(t['teacher_setup_subtitle'])}</p>
      <div class="note">{html.escape(t['teacher_setup_hidden_note'])}</div>
      <div class="note" style="background:#fff8ec;color:#7a4a20;">{html.escape(t['teacher_setup_whitelist_note'])}</div>
      <div class="status {status_class}"><strong>{html.escape(t['teacher_setup_status'])}:</strong> {html.escape(status_text)}</div>
      <div class="actions">
        <a href="/auth/google/start" class="primary button">{html.escape(button_label)}</a>
        <a href="/" class="secondary button">{html.escape(t['teacher_setup_back'])}</a>
      </div>
    </section>
  </div>
</body>
</html>"""


def cancel_html(token: str, locale: str) -> str:
    locale = locale if locale in TRANSLATIONS else "en"
    template = """<!DOCTYPE html>
<html lang="__LOCALE__">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__TITLE__</title>
  <style>
    body { font-family: "Avenir Next", "Trebuchet MS", sans-serif; background:#f7f2ea; margin:0; color:#172033; }
    .page { max-width: 760px; margin: 40px auto; padding: 24px; }
    .panel { background: white; border:1px solid rgba(23,32,51,0.08); border-radius: 24px; padding:24px; }
    button { border:0; border-radius:999px; padding:12px 16px; cursor:pointer; font:inherit; }
    .primary { background:#a61b1b; color:white; }
    .secondary { background:#eef2f7; color:#172033; }
    .summary { margin:18px 0; padding:14px; border-radius:16px; border:1px solid rgba(23,32,51,0.08); background:#f8fafc; line-height:1.6; }
    .flash { margin-top: 12px; padding: 12px; border-radius: 16px; display:none; }
    .flash.show { display:block; }
    .flash.error { background:#ffe9e9; color:#a61b1b; }
    .flash.success { background:#e8fbf2; color:#117a4d; }
  </style>
</head>
<body>
  <div class="page">
    <section class="panel">
      <h1>__TITLE__</h1>
      <p>__SUBTITLE__</p>
      <div class="summary" id="summary">__LOADING__</div>
      <p>__CUTOFF__</p>
      <p>__LIMIT__</p>
      <div style="display:flex;gap:10px;flex-wrap:wrap;">
        <button class="primary" id="cancelButton">__CANCEL_BUTTON__</button>
        <a href="/" style="text-decoration:none;"><button class="secondary">__BACK__</button></a>
      </div>
      <div id="flash" class="flash"></div>
    </section>
  </div>
  <script>
    async function loadInfo() {
      const response = await fetch("/api/cancel-info?token=__TOKEN__");
      const result = await response.json();
      const summary = document.getElementById("summary");
      if (!response.ok) {
        summary.textContent = result.error || "Unable to load appointment.";
        return;
      }
      summary.innerHTML = `
        <strong>${result.summary.student_name}</strong><br>
        ${result.summary.local_label}<br>
        ${result.summary.beijing_label}<br>
        ${result.summary.student_email}
      `;
    }
    function showFlash(message, kind) {
      const flash = document.getElementById("flash");
      flash.className = `flash show ${kind}`;
      flash.textContent = message;
    }
    document.getElementById("cancelButton").addEventListener("click", async () => {
      if (!window.confirm(__CONFIRM_TEXT__)) {
        return;
      }
      const response = await fetch("/api/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cancel_token: __TOKEN_JSON__ })
      });
      const result = await response.json();
      if (!response.ok) {
        showFlash(result.error || "Cancellation failed.", "error");
        return;
      }
      showFlash(result.message, "success");
      document.getElementById("cancelButton").disabled = true;
    });
    loadInfo();
  </script>
</body>
</html>"""
    return (
        template.replace("__LOCALE__", locale)
        .replace("__TOKEN__", html.escape(token))
        .replace("__TOKEN_JSON__", json.dumps(token))
        .replace("__CONFIRM_TEXT__", json.dumps(TRANSLATIONS[locale]["cancel_confirm_text"], ensure_ascii=False))
        .replace("__TITLE__", html.escape(TRANSLATIONS[locale]["cancel_page_title"]))
        .replace("__SUBTITLE__", html.escape(TRANSLATIONS[locale]["cancel_page_subtitle"]))
        .replace("__LOADING__", html.escape(TRANSLATIONS[locale]["loading"]))
        .replace("__CUTOFF__", html.escape(TRANSLATIONS[locale]["cancel_cutoff_note"]))
        .replace("__LIMIT__", html.escape(TRANSLATIONS[locale]["cancel_limit_note"]))
        .replace("__CANCEL_BUTTON__", html.escape(TRANSLATIONS[locale]["cancel_button"]))
        .replace("__BACK__", html.escape(TRANSLATIONS[locale]["back_button"]))
    )


class BookingHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any] | list[dict[str, Any]], status: HTTPStatus = HTTPStatus.OK) -> None:
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
        release_orphaned_pending_bookings(self.server.connection)
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/chatbot", "/courses", "/booking"}:
            initial_section = {
                "/": "overview",
                "/chatbot": "advisor",
                "/courses": "catalog",
                "/booking": "booking",
            }.get(parsed.path, "overview")
            self._send_html(app_html(initial_section))
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
            self._send_json({"integration": self._integration_status(), "base_url": GOOGLE_SERVICE.base_url})
            return
        if parsed.path == "/api/availability":
            query = self._parse_query()
            timezone = query.get("timezone", ["UTC"])[0]
            duration = int(query.get("duration", ["30"])[0])
            availability = get_available_slots(self.server.connection, timezone, duration)
            availability["integration"] = self._integration_status()
            self._send_json(availability)
            return
        if parsed.path == "/api/courses":
            locale = self._parse_query().get("lang", ["en"])[0]
            self._send_json(list_courses(locale if locale in TRANSLATIONS else "en"))
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
                        f"<h1>{html.escape(TRANSLATIONS['en']['teacher_setup_not_allowed'])}</h1><p>{html.escape(google_email)}</p>",
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
        release_orphaned_pending_bookings(self.server.connection)
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
        if parsed.path == "/api/chatbot":
            try:
                payload = self._read_json()
                self._send_json(chatbot_response(payload))
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": f"Advisor request failed: {exc}"}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/recommend":
            try:
                payload = self._read_json()
                self._send_json(recommend_courses(payload))
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": f"Recommendation failed: {exc}"}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/contact-request":
            try:
                payload = self._read_json()
                record = create_contact_request(self.server.connection, payload)
                locale = record.locale if record.locale in TRANSLATIONS else "en"
                self._send_json({"message": TRANSLATIONS[locale]["real_agent_success"], "request_id": record.request_id})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": f"Contact request failed: {exc}"}, status=HTTPStatus.BAD_GATEWAY)
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
    print(f"AI course recommendation platform running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        connection.close()
        server.server_close()


if __name__ == "__main__":
    run_server()
