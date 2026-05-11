import json
from unittest.mock import AsyncMock, MagicMock, patch
import requests

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import Client, TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from core.consumers import LeaderboardConsumer
from core.LLM_api import LLMAPI
from core.models import AnalyticsEvent, Answer, Profile, Question, Quiz, QuizAttempt

from core.hibp_client import check_breaches

class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pwd")
        self.quiz = Quiz.objects.create(title="Test Quiz", description="Desc")
        self.question = Question.objects.create(quiz=self.quiz, text="Q1", order=1)
        self.answer = Answer.objects.create(question=self.question, text="A1", is_correct=True)

    def test_profile_created_on_user_creation(self):
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_quiz_question_count(self):
        self.assertEqual(self.quiz.question_count, 1)

    def test_string_representations(self):
        self.assertEqual(str(self.quiz), "Test Quiz")
        self.assertEqual(str(self.question), "Q1")
        self.assertIn("✅", str(self.answer))


class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="pwd")
        self.quiz = Quiz.objects.create(title="Test Quiz")
        self.question = Question.objects.create(quiz=self.quiz, text="Q1")
        self.answer = Answer.objects.create(question=self.question, text="A1", is_correct=True)

    def test_home_view(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)

    def test_quiz_list_view(self):
        response = self.client.get(reverse('core:quiz_list'))
        self.assertEqual(response.status_code, 200)

    def test_take_quiz_post_correct(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('core:take_quiz', args=[self.quiz.id]), {
            f"q_{self.question.id}": self.answer.id
        })
        attempt = QuizAttempt.objects.get(user=self.user, quiz=self.quiz)
        self.assertEqual(attempt.score, 1)

    @patch('core.views.check_breaches')
    def test_breach_checker_post(self, mock_check):
        mock_check.return_value = [{"Name": "DataBreach2026"}]
        response = self.client.post(reverse('core:breach_checker'), {"email": "test@test.com"})
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# LLM Tests
# ---------------------------------------------------------------------------

class LLMAPIParseJsonTests(TestCase):
    def setUp(self):
        self.api = LLMAPI.__new__(LLMAPI)  # skip __init__ to avoid real API clients

    def test_parse_clean_json(self):
        text = '{"key": "value"}'
        result = self.api._parse_json(text)
        self.assertEqual(result, {"key": "value"})

    def test_parse_json_with_surrounding_text(self):
        text = 'Here is your JSON: {"key": "value"} Hope that helps!'
        result = self.api._parse_json(text)
        self.assertEqual(result, {"key": "value"})

    def test_parse_json_raises_on_invalid(self):
        with self.assertRaises(json.JSONDecodeError):
            self.api._parse_json("not json at all")

    def test_parse_json_raises_when_no_braces(self):
        with self.assertRaises(json.JSONDecodeError):
            self.api._parse_json("just a plain string")


class LLMAPIGetResponseTests(TestCase):
    def setUp(self):
        self.api = LLMAPI.__new__(LLMAPI)

    def test_empty_prompt_raises_value_error(self):
        self.api.providers = []
        with self.assertRaises(ValueError, msg="The given prompt was empty"):
            self.api.get_llm_response("   ")

    def test_returns_first_provider_response(self):
        self.api.providers = [
            MagicMock(return_value="response from provider 1"),
            MagicMock(return_value="response from provider 2"),
        ]
        result = self.api.get_llm_response("test prompt")
        self.assertEqual(result, "response from provider 1")
        self.api.providers[1].assert_not_called()

    @patch('core.LLM_api.logger.error')
    def test_falls_back_to_second_provider_on_failure(self, mock_logger_error):
        provider1 = MagicMock(side_effect=Exception("provider 1 down"))
        provider1.__name__ = "mock_provider_1"

        self.api.providers = [
            provider1,
            MagicMock(return_value="response from provider 2"),
        ]
        result = self.api.get_llm_response("test prompt")
        self.assertEqual(result, "response from provider 2")

    @patch('core.LLM_api.logger.error')
    def test_raises_connection_error_if_all_providers_fail(self, mock_logger_error):
        provider1 = MagicMock(side_effect=Exception("provider 1 down"))
        provider1.__name__ = "mock_provider_1"

        provider2 = MagicMock(side_effect=Exception("provider 2 down"))
        provider2.__name__ = "mock_provider_2"

        self.api.providers = [provider1, provider2]
        with self.assertRaises(ConnectionError):
            self.api.get_llm_response("test prompt")


class LLMAPIProviderTests(TestCase):
    def setUp(self):
        self.api = LLMAPI.__new__(LLMAPI)

    def test_groq_response_success(self):
        mock_message = MagicMock()
        mock_message.content = "groq answer"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        self.api.groq_client = MagicMock()
        self.api.groq_client.chat.completions.create.return_value = mock_response

        result = self.api._get_groq_response("what is phishing?")
        self.assertEqual(result, "groq answer")

    def test_groq_response_raises_on_none_content(self):
        mock_message = MagicMock()
        mock_message.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        self.api.groq_client = MagicMock()
        self.api.groq_client.chat.completions.create.return_value = mock_response

        with self.assertRaises(ValueError):
            self.api._get_groq_response("what is phishing?")

    def test_gemini_response_success(self):
        mock_response = MagicMock()
        mock_response.text = "gemini answer"

        self.api.gemini_client = MagicMock()
        self.api.gemini_client.models.generate_content.return_value = mock_response

        result = self.api._get_gemini_response("what is phishing?")
        self.assertEqual(result, "gemini answer")

    def test_gemini_response_raises_on_none_text(self):
        mock_response = MagicMock()
        mock_response.text = None

        self.api.gemini_client = MagicMock()
        self.api.gemini_client.models.generate_content.return_value = mock_response

        with self.assertRaises(ValueError):
            self.api._get_gemini_response("what is phishing?")


class LLMAPIQuizGenerationTests(TestCase):
    def setUp(self):
        self.api = LLMAPI.__new__(LLMAPI)

    def _make_quiz_response(self):
        return json.dumps({
            "title": "Phishing Quiz",
            "description": "Test your phishing knowledge",
            "questions": [
                {"text": "What is phishing?", "explanation": "It's a social engineering attack."},
                {"text": "What is spear phishing?", "explanation": "A targeted form of phishing."},
            ]
        })

    def _make_answers_response(self):
        return json.dumps({
            "answers": [
                {"text": "A cyberattack", "is_correct": True},
                {"text": "A fishing hobby", "is_correct": False},
                {"text": "An antivirus", "is_correct": False},
                {"text": "A firewall", "is_correct": False},
            ]
        })

    @patch.object(LLMAPI, 'get_llm_response')
    def test_generate_quiz_data_structure(self, mock_llm):
        mock_llm.side_effect = [
            self._make_quiz_response(),
            self._make_answers_response(),
            self._make_answers_response(),
        ]
        self.api.get_llm_response = mock_llm

        result = self.api.generate_quiz_data("phishing", "teens")

        self.assertIn("title", result)
        self.assertIn("questions", result)
        self.assertEqual(len(result["questions"]), 2)

    @patch.object(LLMAPI, 'get_llm_response')
    def test_each_question_has_four_answers(self, mock_llm):
        mock_llm.side_effect = [
            self._make_quiz_response(),
            self._make_answers_response(),
            self._make_answers_response(),
        ]
        self.api.get_llm_response = mock_llm

        result = self.api.generate_quiz_data("phishing", "teens")

        for question in result["questions"]:
            self.assertEqual(len(question["answers"]), 4)

    @patch.object(LLMAPI, 'get_llm_response')
    def test_each_question_has_exactly_one_correct_answer(self, mock_llm):
        mock_llm.side_effect = [
            self._make_quiz_response(),
            self._make_answers_response(),
            self._make_answers_response(),
        ]
        self.api.get_llm_response = mock_llm

        result = self.api.generate_quiz_data("phishing", "teens")

        for question in result["questions"]:
            correct = [a for a in question["answers"] if a["is_correct"]]
            self.assertEqual(len(correct), 1)

    @patch.object(LLMAPI, 'get_llm_response')
    def test_llm_called_once_per_question_plus_one(self, mock_llm):
        mock_llm.side_effect = [
            self._make_quiz_response(),
            self._make_answers_response(),
            self._make_answers_response(),
        ]
        self.api.get_llm_response = mock_llm

        self.api.generate_quiz_data("phishing", "teens")
        self.assertEqual(mock_llm.call_count, 3)


# ---------------------------------------------------------------------------
# WebSocket Helpers
# ---------------------------------------------------------------------------

def _make_communicator(path: str, *, quiz_id=None):
    kwargs = {"quiz_id": quiz_id} if quiz_id is not None else {}
    consumer = LeaderboardConsumer()
    communicator = WebsocketCommunicator(consumer, path)
    communicator.scope["url_route"] = {"kwargs": kwargs}
    return consumer, communicator


QUIZ_LEADERBOARD = [
    {
        "rank": 1,
        "username": "alice",
        "score": 8,
        "total": 10,
        "percentage": 80,
        "completed_at": "12:00:00",
    }
]

UNIVERSAL_LEADERBOARD = [
    {
        "rank": 1,
        "username": "bob",
        "score": 95,
        "total": 100,
        "percentage": 95,
        "completed_at": "11:00:00",
    }
]


# ---------------------------------------------------------------------------
# WebSocket Connection Tests
# ---------------------------------------------------------------------------

class LeaderboardConsumerConnectTests(TestCase):
    @patch.object(LeaderboardConsumer, "send_leaderboard", new_callable=AsyncMock)
    @patch.object(LeaderboardConsumer, "get_leaderboard", new_callable=AsyncMock, return_value=QUIZ_LEADERBOARD)
    async def test_connect_with_quiz_id_uses_quiz_group(self, _mock_get, mock_send):
        consumer, communicator = _make_communicator("/ws/leaderboard/42/", quiz_id=42)
        connected, _ = await communicator.connect()

        self.assertTrue(connected)
        self.assertEqual(consumer.group_name, "leaderboard_42")
        self.assertFalse(consumer.is_universal)
        mock_send.assert_awaited_once()

        await communicator.disconnect()

    @patch.object(LeaderboardConsumer, "send_leaderboard", new_callable=AsyncMock)
    @patch.object(LeaderboardConsumer, "get_universal_leaderboard", new_callable=AsyncMock, return_value=UNIVERSAL_LEADERBOARD)
    async def test_connect_without_quiz_id_uses_universal_group(self, _mock_get, mock_send):
        consumer, communicator = _make_communicator("/ws/leaderboard/")
        connected, _ = await communicator.connect()

        self.assertTrue(connected)
        self.assertEqual(consumer.group_name, "leaderboard_universal")
        self.assertTrue(consumer.is_universal)
        mock_send.assert_awaited_once()

        await communicator.disconnect()

    @patch.object(LeaderboardConsumer, "send_leaderboard", new_callable=AsyncMock)
    async def test_connect_joins_channel_layer_group(self, _mock_send):
        consumer, communicator = _make_communicator("/ws/leaderboard/7/", quiz_id=7)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        layer = get_channel_layer()
        channel_name = consumer.channel_name
        groups = layer.groups if hasattr(layer, "groups") else {}
        self.assertIn(channel_name, groups.get("leaderboard_7", set()))

        await communicator.disconnect()

    @patch.object(LeaderboardConsumer, "send_leaderboard", new_callable=AsyncMock)
    async def test_disconnect_leaves_channel_layer_group(self, _mock_send):
        consumer, communicator = _make_communicator("/ws/leaderboard/7/", quiz_id=7)
        await communicator.connect()

        channel_name = consumer.channel_name
        await communicator.disconnect()

        layer = get_channel_layer()
        groups = layer.groups if hasattr(layer, "groups") else {}
        self.assertNotIn(channel_name, groups.get("leaderboard_7", set()))


# ---------------------------------------------------------------------------
# send_leaderboard Tests
# ---------------------------------------------------------------------------

class LeaderboardConsumerSendTests(TestCase):
    @patch.object(LeaderboardConsumer, "get_leaderboard", new_callable=AsyncMock, return_value=QUIZ_LEADERBOARD)
    async def test_send_leaderboard_quiz_sends_correct_json(self, _mock_get):
        consumer, communicator = _make_communicator("/ws/leaderboard/42/", quiz_id=42)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        response = await communicator.receive_json_from()

        self.assertEqual(response["type"], "leaderboard_update")
        self.assertEqual(response["data"], QUIZ_LEADERBOARD)

        await communicator.disconnect()

    @patch.object(LeaderboardConsumer, "get_universal_leaderboard", new_callable=AsyncMock, return_value=UNIVERSAL_LEADERBOARD)
    async def test_send_leaderboard_universal_sends_correct_json(self, _mock_get):
        consumer, communicator = _make_communicator("/ws/leaderboard/")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        response = await communicator.receive_json_from()

        self.assertEqual(response["type"], "leaderboard_update")
        self.assertEqual(response["data"], UNIVERSAL_LEADERBOARD)

        await communicator.disconnect()


# ---------------------------------------------------------------------------
# leaderboard_update event handler Tests
# ---------------------------------------------------------------------------

class LeaderboardConsumerEventTests(TestCase):
    @patch.object(LeaderboardConsumer, "get_leaderboard", new_callable=AsyncMock, return_value=QUIZ_LEADERBOARD)
    async def test_leaderboard_update_event_triggers_send(self, _mock_get):
        consumer, communicator = _make_communicator("/ws/leaderboard/42/", quiz_id=42)
        await communicator.connect()
        await communicator.receive_json_from()

        await consumer.leaderboard_update({"type": "leaderboard.update"})

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "leaderboard_update")
        self.assertEqual(response["data"], QUIZ_LEADERBOARD)

        await communicator.disconnect()

    @patch.object(LeaderboardConsumer, "get_leaderboard", new_callable=AsyncMock, return_value=QUIZ_LEADERBOARD)
    async def test_leaderboard_update_called_twice_sends_twice(self, _mock_get):
        consumer, communicator = _make_communicator("/ws/leaderboard/42/", quiz_id=42)
        await communicator.connect()
        await communicator.receive_json_from()

        await consumer.leaderboard_update({"type": "leaderboard.update"})
        await consumer.leaderboard_update({"type": "leaderboard.update"})

        first = await communicator.receive_json_from()
        second = await communicator.receive_json_from()
        self.assertEqual(first["type"], "leaderboard_update")
        self.assertEqual(second["type"], "leaderboard_update")

        await communicator.disconnect()


# ---------------------------------------------------------------------------
# DB Helper Method Tests
# ---------------------------------------------------------------------------

class GetLeaderboardTests(TestCase):
    def setUp(self):
        self.consumer = LeaderboardConsumer()
        self.consumer.is_universal = False
        self.user = User.objects.create_user(username="alice", first_name="Alice", last_name="Smith", password="pwd")

    def _make_attempt(self, *, score, total, completed_at=None):
        from core.models import Quiz, QuizAttempt
        quiz = Quiz.objects.create(title="Test Quiz")
        attempt = QuizAttempt.objects.create(user=self.user, quiz=quiz, score=score, total_questions=total)
        if completed_at:
            QuizAttempt.objects.filter(pk=attempt.pk).update(completed_at=completed_at)
            attempt.refresh_from_db()
        return quiz, attempt

    def test_get_leaderboard_returns_list_with_correct_fields(self):
        quiz, _ = self._make_attempt(score=7, total=10)
        result = self.consumer.get_leaderboard.__wrapped__(self.consumer, quiz.id)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        entry = result[0]
        for field in ("rank", "username", "score", "total", "percentage", "completed_at"):
            self.assertIn(field, entry)

    def test_get_leaderboard_rank_starts_at_one(self):
        quiz, _ = self._make_attempt(score=5, total=10)
        result = self.consumer.get_leaderboard.__wrapped__(self.consumer, quiz.id)
        self.assertEqual(result[0]["rank"], 1)

    def test_get_leaderboard_percentage_calculated_correctly(self):
        quiz, _ = self._make_attempt(score=8, total=10)
        result = self.consumer.get_leaderboard.__wrapped__(self.consumer, quiz.id)
        self.assertEqual(result[0]["percentage"], 80)

    def test_get_leaderboard_percentage_zero_when_no_total(self):
        quiz, _ = self._make_attempt(score=0, total=0)
        result = self.consumer.get_leaderboard.__wrapped__(self.consumer, quiz.id)
        self.assertEqual(result[0]["percentage"], 0)

    def test_get_leaderboard_uses_full_name_when_available(self):
        quiz, _ = self._make_attempt(score=6, total=10)
        result = self.consumer.get_leaderboard.__wrapped__(self.consumer, quiz.id)
        self.assertEqual(result[0]["username"], "Alice Smith")

    def test_get_leaderboard_falls_back_to_username(self):
        user2 = User.objects.create_user(username="bob_noname", password="pwd")
        from core.models import Quiz, QuizAttempt
        quiz = Quiz.objects.create(title="Quiz B")
        QuizAttempt.objects.create(user=user2, quiz=quiz, score=3, total_questions=10)

        result = self.consumer.get_leaderboard.__wrapped__(self.consumer, quiz.id)
        self.assertEqual(result[0]["username"], "bob_noname")

    def test_get_leaderboard_ordered_by_score_descending(self):
        from core.models import Quiz, QuizAttempt
        quiz = Quiz.objects.create(title="Multi-score Quiz")
        user2 = User.objects.create_user(username="charlie", password="pwd")
        QuizAttempt.objects.create(user=self.user, quiz=quiz, score=4, total_questions=10)
        QuizAttempt.objects.create(user=user2, quiz=quiz, score=9, total_questions=10)

        result = self.consumer.get_leaderboard.__wrapped__(self.consumer, quiz.id)
        self.assertEqual(result[0]["score"], 9)
        self.assertEqual(result[1]["score"], 4)

    def test_get_leaderboard_capped_at_20_entries(self):
        from core.models import Quiz, QuizAttempt
        quiz = Quiz.objects.create(title="Large Quiz")
        for i in range(25):
            u = User.objects.create_user(username=f"user_{i}", password="pwd")
            QuizAttempt.objects.create(user=u, quiz=quiz, score=i, total_questions=25)

        result = self.consumer.get_leaderboard.__wrapped__(self.consumer, quiz.id)
        self.assertLessEqual(len(result), 20)

    @patch("core.models.compute_universal_leaderboard", return_value=UNIVERSAL_LEADERBOARD)
    def test_get_universal_leaderboard_delegates_to_model_function(self, mock_compute):
        result = self.consumer.get_universal_leaderboard.__wrapped__(self.consumer)
        mock_compute.assert_called_once()
        self.assertEqual(result, UNIVERSAL_LEADERBOARD)



class HIBPClientTests(SimpleTestCase):
    def test_empty_email(self):
        self.assertEqual(check_breaches(""), [])
        self.assertEqual(check_breaches(None), [])

    @override_settings(HIBP_API_KEY=None)
    def test_missing_api_key(self):
        self.assertIsNone(check_breaches("test@example.com"))

    @override_settings(HIBP_API_KEY="fake-key")
    @patch("core.hibp_client.requests.get")
    def test_success_200(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"Name": "DataBreach2026"}]
        mock_get.return_value = mock_response

        result = check_breaches("test@example.com")
        self.assertEqual(result, [{"Name": "DataBreach2026"}])
        mock_get.assert_called_once()

    @override_settings(HIBP_API_KEY="fake-key")
    @patch("core.hibp_client.requests.get")
    def test_not_found_404(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = check_breaches("clean@example.com")
        self.assertEqual(result, [])

    @override_settings(HIBP_API_KEY="fake-key")
    @patch("core.hibp_client.requests.get")
    def test_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("API Down")

        result = check_breaches("test@example.com")
        self.assertIsNone(result)

    @override_settings(HIBP_API_KEY="fake-key")
    @patch("core.hibp_client.requests.get")
    def test_other_status_code(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = check_breaches("test@example.com")
        self.assertIsNone(result)