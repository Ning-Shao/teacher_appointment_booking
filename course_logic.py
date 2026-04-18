from __future__ import annotations

from dataclasses import dataclass
from typing import Any


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
WEEKDAY_ORDER = {day: index for index, day in enumerate(WEEKDAYS)}
DAY_LABELS = {
    "en": {"Mon": "Mon", "Tue": "Tue", "Wed": "Wed", "Thu": "Thu", "Fri": "Fri"},
    "zh": {"Mon": "周一", "Tue": "周二", "Wed": "周三", "Thu": "周四", "Fri": "周五"},
}
AREA_LABELS = {
    "en": {
        "ai": "AI",
        "data": "Data",
        "humanities": "Humanities",
        "product": "Product",
        "education": "Education",
        "research": "Research",
    },
    "zh": {
        "ai": "人工智能",
        "data": "数据",
        "humanities": "人文",
        "product": "产品",
        "education": "教育",
        "research": "研究",
    },
}
LOAD_MAP = {"light": 9, "balanced": 12, "challenging": 15}


@dataclass(frozen=True)
class MeetingBlock:
    day: str
    start: str
    end: str


@dataclass(frozen=True)
class Course:
    course_id: str
    area: str
    level: str
    credits: int
    title_en: str
    title_zh: str
    description_en: str
    description_zh: str
    tags: tuple[str, ...]
    meetings: tuple[MeetingBlock, ...]
    outcomes_en: tuple[str, ...]
    outcomes_zh: tuple[str, ...]


CATALOG: tuple[Course, ...] = (
    Course(
        course_id="AI201",
        area="ai",
        level="Intermediate",
        credits=3,
        title_en="Machine Learning Foundations",
        title_zh="机器学习基础",
        description_en="Supervised learning, model evaluation, and practical ML workflows for undergraduates.",
        description_zh="面向本科生的监督学习、模型评估与机器学习实践流程课程。",
        tags=("ai", "machine learning", "python", "modeling", "research"),
        meetings=(MeetingBlock("Mon", "15:00", "16:30"), MeetingBlock("Wed", "15:00", "16:30")),
        outcomes_en=("Build baseline ML models", "Read empirical papers", "Discuss evaluation tradeoffs"),
        outcomes_zh=("搭建基础机器学习模型", "阅读实证论文", "讨论评估与取舍"),
    ),
    Course(
        course_id="AI230",
        area="ai",
        level="Intermediate",
        credits=3,
        title_en="Natural Language Processing Studio",
        title_zh="自然语言处理工作坊",
        description_en="Tokenization, embeddings, transformer-era applications, and mini project demos.",
        description_zh="涵盖分词、向量表示、Transformer 时代应用与小型项目展示。",
        tags=("ai", "nlp", "language", "chatbot", "project"),
        meetings=(MeetingBlock("Tue", "14:00", "15:30"), MeetingBlock("Thu", "14:00", "15:30")),
        outcomes_en=("Prototype a chatbot workflow", "Compare language models", "Present an NLP use case"),
        outcomes_zh=("完成聊天机器人原型流程", "比较不同语言模型", "展示 NLP 应用场景"),
    ),
    Course(
        course_id="CS105",
        area="ai",
        level="Introductory",
        credits=3,
        title_en="Python for Problem Solving",
        title_zh="问题求解 Python",
        description_en="A beginner-friendly programming course focused on automation, logic, and readable code.",
        description_zh="面向初学者的编程课，强调自动化、逻辑与可读代码。",
        tags=("python", "programming", "automation", "logic", "intro"),
        meetings=(MeetingBlock("Tue", "09:00", "10:30"), MeetingBlock("Thu", "09:00", "10:30")),
        outcomes_en=("Write reusable scripts", "Break problems into steps", "Prepare for AI and data courses"),
        outcomes_zh=("编写可复用脚本", "拆解问题并分步求解", "为 AI 和数据课程打基础"),
    ),
    Course(
        course_id="DS210",
        area="data",
        level="Intermediate",
        credits=3,
        title_en="Statistics for Social Data",
        title_zh="社会数据统计",
        description_en="Inference, regression, and data interpretation with social science case studies.",
        description_zh="通过社会科学案例学习推断、回归与数据解读。",
        tags=("data", "statistics", "analysis", "research", "evidence"),
        meetings=(MeetingBlock("Tue", "11:00", "12:30"), MeetingBlock("Thu", "11:00", "12:30")),
        outcomes_en=("Interpret statistical output", "Design a small empirical study", "Support arguments with data"),
        outcomes_zh=("解读统计结果", "设计小型实证研究", "用数据支持论点"),
    ),
    Course(
        course_id="DATA310",
        area="data",
        level="Advanced",
        credits=3,
        title_en="Data Visualization for Decision Making",
        title_zh="决策数据可视化",
        description_en="Visual storytelling, dashboards, and responsible presentation of uncertainty.",
        description_zh="学习可视化叙事、仪表盘设计与不确定性的负责表达。",
        tags=("data", "visualization", "storytelling", "product", "communication"),
        meetings=(MeetingBlock("Fri", "13:00", "16:00"),),
        outcomes_en=("Design clear charts", "Explain decisions with visuals", "Critique misleading graphics"),
        outcomes_zh=("设计清晰图表", "用可视化解释决策", "识别误导性图形"),
    ),
    Course(
        course_id="HCI250",
        area="product",
        level="Intermediate",
        credits=3,
        title_en="Human-Computer Interaction",
        title_zh="人机交互",
        description_en="User interviews, prototyping, interaction patterns, and iterative testing.",
        description_zh="包含用户访谈、原型设计、交互模式与迭代测试。",
        tags=("product", "design", "ux", "research", "prototype"),
        meetings=(MeetingBlock("Mon", "10:30", "12:00"), MeetingBlock("Wed", "10:30", "12:00")),
        outcomes_en=("Turn needs into prototypes", "Run usability reviews", "Link design to user evidence"),
        outcomes_zh=("将需求转成原型", "开展可用性评估", "把设计决策与用户证据相连接"),
    ),
    Course(
        course_id="PHIL240",
        area="humanities",
        level="Intermediate",
        credits=3,
        title_en="Logic and Argumentation",
        title_zh="逻辑与论证",
        description_en="Formal and informal logic, argumentative writing, and structured reasoning.",
        description_zh="学习形式逻辑、非形式逻辑、论证写作与结构化思考。",
        tags=("logic", "writing", "philosophy", "reasoning", "humanities"),
        meetings=(MeetingBlock("Fri", "09:00", "12:00"),),
        outcomes_en=("Build stronger arguments", "Spot weak assumptions", "Improve analytical writing"),
        outcomes_zh=("构建更强论证", "识别薄弱前提", "提升分析写作能力"),
    ),
    Course(
        course_id="HUM205",
        area="humanities",
        level="Introductory",
        credits=2,
        title_en="Technology, Ethics, and Society",
        title_zh="技术、伦理与社会",
        description_en="Ethics of AI, platform governance, bias, privacy, and public impact.",
        description_zh="讨论 AI 伦理、平台治理、偏见、隐私与公共影响。",
        tags=("ethics", "ai", "policy", "writing", "humanities"),
        meetings=(MeetingBlock("Wed", "13:30", "15:30"),),
        outcomes_en=("Frame ethical dilemmas", "Write policy-style reflections", "Debate responsible innovation"),
        outcomes_zh=("界定伦理困境", "完成政策风格反思写作", "讨论负责任创新"),
    ),
    Course(
        course_id="EDU215",
        area="education",
        level="Intermediate",
        credits=3,
        title_en="Learning Sciences and Course Design",
        title_zh="学习科学与课程设计",
        description_en="How students learn, how feedback works, and how to build effective learning experiences.",
        description_zh="研究学生如何学习、反馈如何发挥作用，以及如何设计有效学习体验。",
        tags=("education", "learning", "curriculum", "edtech", "teaching"),
        meetings=(MeetingBlock("Tue", "16:00", "17:30"), MeetingBlock("Thu", "16:00", "17:30")),
        outcomes_en=("Design a lesson sequence", "Evaluate learning interventions", "Connect pedagogy to product thinking"),
        outcomes_zh=("设计课程单元", "评估学习干预", "把教学法与产品思维结合"),
    ),
    Course(
        course_id="BUS260",
        area="product",
        level="Intermediate",
        credits=3,
        title_en="Product Strategy for EdTech",
        title_zh="教育科技产品战略",
        description_en="Market discovery, product bets, and roadmap thinking for education-focused platforms.",
        description_zh="聚焦教育科技平台的市场发现、产品判断与路线图设计。",
        tags=("product", "strategy", "edtech", "startup", "business"),
        meetings=(MeetingBlock("Mon", "18:30", "20:00"), MeetingBlock("Wed", "18:30", "20:00")),
        outcomes_en=("Evaluate product-market fit", "Prioritize feature bets", "Communicate a roadmap"),
        outcomes_zh=("评估产品市场匹配", "排序功能优先级", "表达产品路线图"),
    ),
    Course(
        course_id="RES300",
        area="research",
        level="Advanced",
        credits=2,
        title_en="Undergraduate Research Seminar",
        title_zh="本科研究研讨课",
        description_en="Paper discussions, proposal writing, and faculty-style feedback on research plans.",
        description_zh="通过论文讨论、proposal 写作与教师式反馈推进研究计划。",
        tags=("research", "writing", "grad school", "papers", "presentation"),
        meetings=(MeetingBlock("Fri", "16:00", "18:00"),),
        outcomes_en=("Draft a proposal", "Lead a paper discussion", "Prepare for faculty mentoring"),
        outcomes_zh=("撰写研究计划", "主持论文讨论", "为导师交流做准备"),
    ),
    Course(
        course_id="DATA225",
        area="data",
        level="Intermediate",
        credits=3,
        title_en="Applied Data Analytics",
        title_zh="应用数据分析",
        description_en="Cleaning datasets, exploratory analysis, dashboards, and evidence-driven recommendations.",
        description_zh="学习数据清洗、探索分析、仪表盘与基于证据的建议。",
        tags=("data", "analytics", "python", "dashboard", "business"),
        meetings=(MeetingBlock("Mon", "15:00", "16:30"), MeetingBlock("Wed", "15:00", "16:30")),
        outcomes_en=("Build an analytics narrative", "Prepare practical reports", "Compare business metrics"),
        outcomes_zh=("形成分析故事线", "输出实践型报告", "比较业务指标"),
    ),
)


KEYWORD_MAP = {
    "ai": {
        "keywords": ("ai", "machine learning", "ml", "nlp", "chatbot", "人工智能", "机器学习", "自然语言处理"),
    },
    "data": {
        "keywords": ("data", "analytics", "statistics", "visualization", "dashboard", "数据", "统计", "可视化", "分析"),
    },
    "humanities": {
        "keywords": ("philosophy", "ethics", "writing", "logic", "humanities", "哲学", "伦理", "写作", "逻辑", "人文"),
    },
    "product": {
        "keywords": ("product", "ux", "design", "startup", "strategy", "产品", "设计", "交互", "创业"),
    },
    "education": {
        "keywords": ("education", "teaching", "learning", "curriculum", "edtech", "教育", "教学", "学习", "课程"),
    },
    "research": {
        "keywords": ("research", "paper", "proposal", "grad school", "研究", "论文", "申请", "科研"),
    },
}


def _clock_to_minutes(value: str) -> int:
    hour_text, minute_text = value.split(":")
    return int(hour_text) * 60 + int(minute_text)


def _localized(locale: str, en_text: str, zh_text: str) -> str:
    return zh_text if locale == "zh" else en_text


def _course_title(course: Course, locale: str) -> str:
    return course.title_zh if locale == "zh" else course.title_en


def _meeting_conflict(left: MeetingBlock, right: MeetingBlock) -> bool:
    if left.day != right.day:
        return False
    return _clock_to_minutes(left.start) < _clock_to_minutes(right.end) and _clock_to_minutes(right.start) < _clock_to_minutes(left.end)


def serialize_course(course: Course, locale: str = "en") -> dict[str, Any]:
    return {
        "course_id": course.course_id,
        "title": _course_title(course, locale),
        "title_en": course.title_en,
        "title_zh": course.title_zh,
        "area": course.area,
        "area_label": AREA_LABELS[locale].get(course.area, course.area),
        "level": course.level,
        "credits": course.credits,
        "description": _localized(locale, course.description_en, course.description_zh),
        "tags": list(course.tags),
        "meetings": [
            {"day": block.day, "day_label": DAY_LABELS[locale][block.day], "start": block.start, "end": block.end}
            for block in course.meetings
        ],
        "outcomes": list(course.outcomes_zh if locale == "zh" else course.outcomes_en),
    }


def list_courses(locale: str = "en") -> list[dict[str, Any]]:
    return [serialize_course(course, locale) for course in CATALOG]


def _normalize_locale(value: Any) -> str:
    return "zh" if str(value).strip().lower() == "zh" else "en"


def infer_profile(payload: dict[str, Any]) -> dict[str, Any]:
    locale = _normalize_locale(payload.get("locale", "en"))
    message = str(payload.get("message", "")).strip()
    current_profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    message_lower = message.lower()

    focus_areas = {
        area
        for area, config in KEYWORD_MAP.items()
        if any(keyword in message_lower for keyword in config["keywords"])
    }

    existing_focus = current_profile.get("focus_areas", [])
    if isinstance(existing_focus, list):
        focus_areas.update(str(value) for value in existing_focus if value)

    if not focus_areas:
        focus_areas.update(("ai", "data"))

    desired_load = str(current_profile.get("desired_load", "")).strip().lower()
    if desired_load not in LOAD_MAP:
        if any(token in message_lower for token in ("light", "轻松", "少一点", "not too much")):
            desired_load = "light"
        elif any(token in message_lower for token in ("challenging", "hard", "冲刺", "高强度", "ambitious")):
            desired_load = "challenging"
        else:
            desired_load = "balanced"

    avoid_mornings = bool(current_profile.get("avoid_mornings", False))
    if any(token in message_lower for token in ("avoid mornings", "no morning", "afternoon", "晚上", "不要早课", "不想早起", "prefer afternoons")):
        avoid_mornings = True

    preferred_days = current_profile.get("preferred_days", [])
    if not isinstance(preferred_days, list):
        preferred_days = []
    if not preferred_days:
        for day, day_tokens in {
            "Mon": ("monday", "周一"),
            "Tue": ("tuesday", "周二"),
            "Wed": ("wednesday", "周三"),
            "Thu": ("thursday", "周四"),
            "Fri": ("friday", "周五"),
        }.items():
            if any(token in message_lower for token in day_tokens):
                preferred_days.append(day)

    max_credits = current_profile.get("max_credits")
    if not isinstance(max_credits, int) or max_credits <= 0:
        max_credits = LOAD_MAP[desired_load]
        if any(token in message_lower for token in ("16 credits", "15 credits", "16 学分", "15 学分")):
            max_credits = 15
        if any(token in message_lower for token in ("12 credits", "12 学分")):
            max_credits = 12
        if any(token in message_lower for token in ("9 credits", "9 学分", "10 credits")):
            max_credits = 9

    career_goal = str(current_profile.get("career_goal") or "").strip()
    if not career_goal:
        if any(token in message_lower for token in ("research", "phd", "graduate school", "科研", "研究", "申请博士", "读研")):
            career_goal = _localized(locale, "Prepare for research and faculty conversations", "为科研和导师交流做准备")
            focus_areas.add("research")
        elif any(token in message_lower for token in ("product", "pm", "创业", "产品经理", "startup")):
            career_goal = _localized(locale, "Build toward product and education technology work", "为产品和教育科技方向做准备")
            focus_areas.add("product")
        elif any(token in message_lower for token in ("teacher", "education", "teaching", "教育", "教学")):
            career_goal = _localized(locale, "Develop a learning-focused interdisciplinary schedule", "形成以学习科学为核心的跨学科课表")
            focus_areas.add("education")
        else:
            career_goal = _localized(locale, "Explore an interdisciplinary AI-oriented semester", "探索一个偏 AI 的跨学期课程组合")

    return {
        "locale": locale,
        "message": message,
        "career_goal": career_goal,
        "focus_areas": sorted(focus_areas),
        "desired_load": desired_load,
        "max_credits": max_credits,
        "preferred_days": preferred_days,
        "avoid_mornings": avoid_mornings,
    }


def _score_course(course: Course, profile: dict[str, Any]) -> tuple[int, list[str]]:
    locale = profile["locale"]
    focus_areas = set(profile.get("focus_areas", []))
    career_goal = str(profile.get("career_goal", "")).lower()
    message = str(profile.get("message", "")).lower()
    preferred_days = set(profile.get("preferred_days", []))
    avoid_mornings = bool(profile.get("avoid_mornings"))
    desired_load = profile.get("desired_load", "balanced")

    score = 0
    reasons: list[str] = []

    if course.area in focus_areas:
        score += 5
        reasons.append(_localized(locale, f"Directly supports your {AREA_LABELS['en'][course.area]} focus.", f"直接支持你的{AREA_LABELS['zh'][course.area]}方向。"))

    keyword_hits = [tag for tag in course.tags if tag.lower() in career_goal or tag.lower() in message]
    if keyword_hits:
        score += min(4, len(keyword_hits) + 1)
        reasons.append(_localized(locale, f"Matches your interest in {', '.join(keyword_hits[:2])}.", f"和你提到的 {', '.join(keyword_hits[:2])} 兴趣相匹配。"))

    course_days = {block.day for block in course.meetings}
    if preferred_days and course_days.issubset(preferred_days):
        score += 2
        reasons.append(_localized(locale, "Fits your preferred meeting days.", "符合你偏好的上课日期。"))

    has_morning_class = any(_clock_to_minutes(block.start) < 12 * 60 for block in course.meetings)
    if avoid_mornings and has_morning_class:
        score -= 3
        reasons.append(_localized(locale, "Includes a morning session, so it may not fit your preferred rhythm.", "这门课包含早课，和你当前的作息偏好不太一致。"))
    elif avoid_mornings and not has_morning_class:
        score += 2
        reasons.append(_localized(locale, "Avoids early-morning sessions.", "避开了早课时段。"))

    if desired_load == "light" and course.credits <= 2:
        score += 2
        reasons.append(_localized(locale, "Keeps the overall load manageable.", "有助于控制整体负担。"))
    elif desired_load == "challenging" and course.level in {"Advanced", "Intermediate"}:
        score += 2
        reasons.append(_localized(locale, "Offers a stronger stretch for an ambitious semester.", "更适合冲刺型学期安排。"))
    elif desired_load == "balanced" and course.level == "Intermediate":
        score += 1
        reasons.append(_localized(locale, "A solid fit for a balanced semester.", "适合均衡型学期配置。"))

    if not reasons:
        reasons.append(_localized(locale, "Adds breadth to your semester plan.", "能为你的学期计划补充跨学科广度。"))

    return score, reasons


def _find_conflicts(courses: list[Course], locale: str) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for left_index, left_course in enumerate(courses):
        for right_course in courses[left_index + 1 :]:
            for left_block in left_course.meetings:
                for right_block in right_course.meetings:
                    if not _meeting_conflict(left_block, right_block):
                        continue
                    conflicts.append(
                        {
                            "course_a": {
                                "course_id": left_course.course_id,
                                "title": _course_title(left_course, locale),
                            },
                            "course_b": {
                                "course_id": right_course.course_id,
                                "title": _course_title(right_course, locale),
                            },
                            "day": left_block.day,
                            "day_label": DAY_LABELS[locale][left_block.day],
                            "time_range": f"{left_block.start}-{left_block.end} vs {right_block.start}-{right_block.end}",
                            "summary": _localized(
                                locale,
                                f"{left_course.title_en} overlaps with {right_course.title_en} on {DAY_LABELS[locale][left_block.day]}.",
                                f"{left_course.title_zh} 与 {right_course.title_zh} 在 {DAY_LABELS[locale][left_block.day]} 时间冲突。",
                            ),
                        }
                    )
    return conflicts


def _build_schedule(courses: list[Course], locale: str) -> dict[str, Any]:
    by_day = {day: [] for day in WEEKDAYS}
    for course in courses:
        for block in course.meetings:
            by_day[block.day].append(
                {
                    "course_id": course.course_id,
                    "title": _course_title(course, locale),
                    "area_label": AREA_LABELS[locale].get(course.area, course.area),
                    "start": block.start,
                    "end": block.end,
                }
            )
    for day in WEEKDAYS:
        by_day[day].sort(key=lambda block: _clock_to_minutes(block["start"]))

    return {
        "days": [
            {
                "day": day,
                "label": DAY_LABELS[locale][day],
                "blocks": by_day[day],
            }
            for day in WEEKDAYS
        ],
        "total_credits": sum(course.credits for course in courses),
    }


def recommend_courses(payload: dict[str, Any]) -> dict[str, Any]:
    profile = infer_profile(payload)
    locale = profile["locale"]

    scored_courses: list[tuple[int, Course, list[str]]] = []
    for course in CATALOG:
        score, reasons = _score_course(course, profile)
        scored_courses.append((score, course, reasons))

    scored_courses.sort(
        key=lambda item: (
            -item[0],
            WEEKDAY_ORDER[item[1].meetings[0].day],
            _clock_to_minutes(item[1].meetings[0].start),
            item[1].course_id,
        )
    )

    recommended = scored_courses[:6]
    selected: list[tuple[int, Course, list[str]]] = []
    total_credits = 0
    for score, course, reasons in recommended:
        candidate_courses = [entry[1] for entry in selected] + [course]
        if total_credits + course.credits > profile["max_credits"]:
            continue
        if _find_conflicts(candidate_courses, locale):
            continue
        selected.append((score, course, reasons))
        total_credits += course.credits

    if not selected:
        for score, course, reasons in recommended:
            candidate_courses = [entry[1] for entry in selected] + [course]
            if _find_conflicts(candidate_courses, locale):
                continue
            selected.append((score, course, reasons))
            if len(selected) >= 3:
                break

    top_courses = [course for _, course, _ in recommended]
    selected_courses = [course for _, course, _ in selected]
    recommendation_cards = []
    for score, course, reasons in recommended:
        recommendation_cards.append(
            {
                **serialize_course(course, locale),
                "score": score,
                "match_reasons": reasons[:3],
                "recommended_for_schedule": course in selected_courses,
            }
        )

    schedule_cards = [serialize_course(course, locale) for course in selected_courses]
    focus_labels = [AREA_LABELS[locale].get(area, area) for area in profile["focus_areas"]]
    insights = [
        _localized(
            locale,
            f"This plan centers on {', '.join(focus_labels[:2])} while keeping the load around {profile['max_credits']} credits.",
            f"这份方案以 {', '.join(focus_labels[:2])} 为核心，同时把学分控制在 {profile['max_credits']} 左右。",
        ),
        _localized(
            locale,
            "Use the timetable below as a draft, then book an advising session to refine tradeoffs and prerequisites.",
            "你可以先把下面的周课表当作草案，再预约老师一起细化取舍和先修关系。",
        ),
    ]

    booking_prefill = _localized(
        locale,
        f"I would like to discuss this draft semester plan: {', '.join(course.title_en for course in selected_courses)}. Career goal: {profile['career_goal']}.",
        f"我想讨论这份学期课程草案：{', '.join(course.title_zh for course in selected_courses)}。当前目标：{profile['career_goal']}。",
    )

    return {
        "profile": profile,
        "insights": insights,
        "recommended_courses": recommendation_cards,
        "selected_schedule_courses": schedule_cards,
        "conflicts": _find_conflicts(top_courses, locale),
        "schedule": _build_schedule(selected_courses, locale),
        "booking_prefill": booking_prefill,
    }


def chatbot_response(payload: dict[str, Any]) -> dict[str, Any]:
    profile = infer_profile(payload)
    locale = profile["locale"]
    recommendation = recommend_courses(profile)
    top_titles = [course["title"] for course in recommendation["recommended_courses"][:3]]

    if profile["message"]:
        reply = _localized(
            locale,
            f"I read your note as a plan focused on {', '.join(AREA_LABELS['en'].get(area, area) for area in profile['focus_areas'][:2])}. A strong first shortlist is {', '.join(top_titles)}. I also drafted a conflict-aware schedule you can review below.",
            f"我把你的需求理解为一个以 {', '.join(AREA_LABELS['zh'].get(area, area) for area in profile['focus_areas'][:2])} 为核心的学期方案。第一轮优先课可以先看 {', '.join(top_titles)}。我也已经生成了一份带冲突检查的周课表草案，你可以直接在下方查看。",
        )
    else:
        reply = _localized(
            locale,
            "Tell me what you want from next semester, and I will turn it into a course shortlist plus a draft timetable.",
            "告诉我你下学期想要什么样的学习方向，我会把它整理成课程 shortlist 和周课表草案。",
        )

    follow_up = _localized(
        locale,
        "If you want a tighter recommendation, mention goals like research, product, grad school, avoiding morning classes, or a target credit load.",
        "如果你想要更精准的推荐，可以继续补充科研、产品、申研、避免早课、目标学分等信息。",
    )

    return {
        "reply": reply,
        "follow_up": follow_up,
        "profile": recommendation["profile"],
        "preview_courses": recommendation["recommended_courses"][:3],
        "recommendation": recommendation,
    }
