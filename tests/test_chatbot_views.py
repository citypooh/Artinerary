"""
Comprehensive test suite for Chatbot app - Part 2
Tests for views (chat_view, chat_history, prepare_itinerary, clear_chat)
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json

from chatbot.models import ChatSession, ChatMessage


class ChatViewTests(TestCase):
    """Tests for chat_view endpoint"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.chat_url = reverse("chatbot:chat")

    def test_login_required(self):
        """Test that login is required"""
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_request_rejected(self):
        """Test that GET request is rejected"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.chat_url)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["error"], "Invalid request method")

    def test_empty_message_rejected(self):
        """Test that empty message is rejected"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Message cannot be empty")

    def test_whitespace_only_message_rejected(self):
        """Test that whitespace-only message is rejected"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["success"])

    def test_invalid_json_rejected(self):
        """Test that invalid JSON is rejected"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.chat_url, data="not valid json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Invalid JSON data")

    def test_successful_chat_creates_session(self):
        """Test that successful chat creates a session"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertIn("session_id", data)
        self.assertIn("response", data)

        # Verify session was created
        self.assertTrue(
            ChatSession.objects.filter(
                user=self.user, session_id=data["session_id"]
            ).exists()
        )

    def test_successful_chat_creates_messages(self):
        """Test that successful chat creates user and bot messages"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )
        data = json.loads(response.content)

        session = ChatSession.objects.get(session_id=data["session_id"])
        messages = session.messages.all()

        # Should have user message and bot message
        self.assertEqual(messages.count(), 2)
        self.assertEqual(messages[0].sender, "user")
        self.assertEqual(messages[0].message, "Hello")
        self.assertEqual(messages[1].sender, "bot")

    def test_chat_with_existing_session(self):
        """Test chatting with an existing session"""
        self.client.login(username="testuser", password="testpass123")

        # First message creates session
        response1 = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "First message"}),
            content_type="application/json",
        )
        data1 = json.loads(response1.content)
        session_id = data1["session_id"]

        # Second message uses same session
        response2 = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "Second message", "session_id": session_id}),
            content_type="application/json",
        )
        data2 = json.loads(response2.content)
        self.assertEqual(data2["session_id"], session_id)

        # Should only be one session with 4 messages
        self.assertEqual(ChatSession.objects.filter(user=self.user).count(), 1)
        session = ChatSession.objects.get(session_id=session_id)
        self.assertEqual(session.messages.count(), 4)

    def test_chat_with_location(self):
        """Test chatting with user location"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps(
                {
                    "message": "Show me nearby artworks",
                    "location": {"lat": 40.7128, "lng": -74.0060},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_chat_response_contains_metadata(self):
        """Test that chat response contains metadata"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertIn("metadata", data)
        self.assertIn("message_id", data)

    def test_greeting_response(self):
        """Test greeting gets appropriate response"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "hi"}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertIn("ArtBot", data["response"])

    def test_thanks_response(self):
        """Test thanks gets appropriate response"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "thanks"}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertIn("welcome", data["response"].lower())


class ChatHistoryViewTests(TestCase):
    """Tests for chat_history endpoint"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.history_url = reverse("chatbot:history")

        # Create a session with messages
        self.session = ChatSession.objects.create(
            user=self.user, session_id="test-session-history"
        )
        ChatMessage.objects.create(session=self.session, sender="user", message="Hello")
        ChatMessage.objects.create(
            session=self.session, sender="bot", message="Hi there!"
        )

    def test_login_required(self):
        """Test that login is required"""
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_history_without_session_id(self):
        """Test getting history without session_id returns most recent"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["messages"]), 2)

    def test_get_history_with_session_id(self):
        """Test getting history with specific session_id"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            self.history_url, {"session_id": "test-session-history"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["session_id"], "test-session-history")
        self.assertEqual(len(data["messages"]), 2)

    def test_get_history_invalid_session_id(self):
        """Test getting history with invalid session_id"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(
            self.history_url, {"session_id": "nonexistent-session"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["messages"], [])
        self.assertIsNone(data["session_id"])

    def test_history_message_format(self):
        """Test that history messages have correct format"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.history_url)
        data = json.loads(response.content)

        message = data["messages"][0]
        self.assertIn("sender", message)
        self.assertIn("message", message)
        self.assertIn("metadata", message)
        self.assertIn("created_at", message)

    def test_history_no_sessions(self):
        """Test getting history when user has no sessions"""
        User.objects.create_user(
            username="newuser", email="new@example.com", password="testpass123"
        )
        self.client.login(username="newuser", password="testpass123")
        response = self.client.get(self.history_url)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["messages"], [])
        self.assertIsNone(data["session_id"])

    def test_history_limit_50_messages(self):
        """Test that history is limited to 50 messages"""
        # Create 60 messages
        for i in range(60):
            ChatMessage.objects.create(
                session=self.session,
                sender="user" if i % 2 == 0 else "bot",
                message=f"Message {i}",
            )

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.history_url)
        data = json.loads(response.content)
        # Should have 50 messages (limited) + 2 from setUp = 52, but limited to 50
        self.assertEqual(len(data["messages"]), 50)

    def test_history_user_isolation(self):
        """Test that users can only see their own history"""
        other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="testpass123"
        )
        other_session = ChatSession.objects.create(
            user=other_user, session_id="other-session"
        )
        ChatMessage.objects.create(
            session=other_session, sender="user", message="Other user's message"
        )

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.history_url, {"session_id": "other-session"})
        data = json.loads(response.content)
        # Should not find other user's session
        self.assertEqual(data["messages"], [])


class PrepareItineraryViewTests(TestCase):
    """Tests for prepare_itinerary endpoint"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.prepare_url = reverse("chatbot:prepare_itinerary")

    def test_login_required(self):
        """Test that login is required"""
        response = self.client.post(
            self.prepare_url,
            data=json.dumps({"locations": [1, 2, 3]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_request_rejected(self):
        """Test that GET request is rejected"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.prepare_url)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["error"], "Invalid request method")

    def test_prepare_itinerary_success(self):
        """Test successful itinerary preparation"""
        self.client.login(username="testuser", password="testpass123")
        locations = [1, 2, 3, 4, 5]
        response = self.client.post(
            self.prepare_url,
            data=json.dumps({"locations": locations}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["redirect_url"], "/itineraries/create/")

        # Verify locations stored in session
        session = self.client.session
        self.assertEqual(session["suggested_locations"], locations)

    def test_prepare_itinerary_empty_locations(self):
        """Test preparing itinerary with empty locations"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.prepare_url,
            data=json.dumps({"locations": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_prepare_itinerary_invalid_json(self):
        """Test preparing itinerary with invalid JSON"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.prepare_url, data="not valid json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Invalid JSON data")


class ClearChatViewTests(TestCase):
    """Tests for clear_chat endpoint"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.clear_url = reverse("chatbot:clear_chat")

        # Create session with messages
        self.session = ChatSession.objects.create(
            user=self.user, session_id="clear-test-session"
        )
        ChatMessage.objects.create(
            session=self.session, sender="user", message="Message 1"
        )
        ChatMessage.objects.create(
            session=self.session, sender="bot", message="Message 2"
        )

    def test_login_required(self):
        """Test that login is required"""
        response = self.client.post(
            self.clear_url,
            data=json.dumps({"session_id": "clear-test-session"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_request_rejected(self):
        """Test that GET request is rejected"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.clear_url)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["error"], "Invalid request method")

    def test_clear_chat_success(self):
        """Test successfully clearing chat"""
        self.client.login(username="testuser", password="testpass123")
        self.assertEqual(self.session.messages.count(), 2)

        response = self.client.post(
            self.clear_url,
            data=json.dumps({"session_id": "clear-test-session"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

        # Verify messages cleared
        self.assertEqual(self.session.messages.count(), 0)

    def test_clear_chat_nonexistent_session(self):
        """Test clearing nonexistent session doesn't error"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.clear_url,
            data=json.dumps({"session_id": "nonexistent-session"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_clear_chat_empty_body(self):
        """Test clearing chat with empty body"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.clear_url, data="", content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_clear_chat_user_isolation(self):
        """Test that users can only clear their own sessions"""
        other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="testpass123"
        )
        other_session = ChatSession.objects.create(
            user=other_user, session_id="other-user-session"
        )
        ChatMessage.objects.create(
            session=other_session, sender="user", message="Other message"
        )

        # Try to clear other user's session
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            self.clear_url,
            data=json.dumps({"session_id": "other-user-session"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # Other user's messages should still exist
        self.assertEqual(other_session.messages.count(), 1)


class ChatURLTests(TestCase):
    """Tests for URL configuration"""

    def test_chat_url_resolves(self):
        """Test that chat URL resolves correctly"""
        url = reverse("chatbot:chat")
        self.assertEqual(url, "/chatbot/api/chat/")

    def test_history_url_resolves(self):
        """Test that history URL resolves correctly"""
        url = reverse("chatbot:history")
        self.assertEqual(url, "/chatbot/api/history/")

    def test_prepare_itinerary_url_resolves(self):
        """Test that prepare_itinerary URL resolves correctly"""
        url = reverse("chatbot:prepare_itinerary")
        self.assertEqual(url, "/chatbot/api/prepare-itinerary/")

    def test_clear_chat_url_resolves(self):
        """Test that clear_chat URL resolves correctly"""
        url = reverse("chatbot:clear_chat")
        self.assertEqual(url, "/chatbot/api/clear/")
