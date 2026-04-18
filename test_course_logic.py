from __future__ import annotations

import unittest

from course_logic import chatbot_response, infer_profile, recommend_courses


class CourseLogicTests(unittest.TestCase):
    def test_infer_profile_detects_research_and_avoids_mornings(self) -> None:
        profile = infer_profile(
            {
                "locale": "zh",
                "message": "我想走人工智能方向，准备申请科研，而且尽量不要早课，12 学分左右。",
                "profile": {},
            }
        )
        self.assertIn("ai", profile["focus_areas"])
        self.assertIn("research", profile["focus_areas"])
        self.assertTrue(profile["avoid_mornings"])
        self.assertEqual(profile["max_credits"], 12)

    def test_recommend_courses_returns_conflict_aware_schedule(self) -> None:
        result = recommend_courses(
            {
                "locale": "en",
                "message": "I want a balanced AI and data semester with some product exposure.",
                "profile": {"desired_load": "balanced", "max_credits": 12, "focus_areas": ["ai", "data", "product"]},
            }
        )
        self.assertLessEqual(result["schedule"]["total_credits"], 12)
        selected_ids = {course["course_id"] for course in result["selected_schedule_courses"]}
        self.assertIn("AI201", {course["course_id"] for course in result["recommended_courses"]})
        self.assertNotEqual({"AI201", "DATA225"}.issubset(selected_ids), True)

    def test_chatbot_response_contains_preview_and_recommendation(self) -> None:
        result = chatbot_response(
            {
                "locale": "en",
                "message": "I want to build a course plan for AI, NLP, and research opportunities.",
                "profile": {"focus_areas": ["ai", "research"], "max_credits": 12, "desired_load": "balanced"},
            }
        )
        self.assertTrue(result["preview_courses"])
        self.assertIn("recommendation", result)
        self.assertTrue(result["reply"])


if __name__ == "__main__":
    unittest.main()
