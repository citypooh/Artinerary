"""
Comprehensive test suite for Chatbot app - Part 5
End-to-end integration tests
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from decimal import Decimal
import json
import time

from chatbot.models import ChatSession, ChatMessage
from loc_detail.models import PublicArt


class ChatbotConversationFlowTests(TestCase):
    """End-to-end tests for conversation flows"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            first_name="Test",
            email="test@example.com",
            password="testpass123",
        )
        # Create test artworks
        self.art1 = PublicArt.objects.create(
            title="Central Park Statue",
            artist_name="Famous Artist",
            location="Central Park",
            borough="Manhattan",
            latitude=Decimal("40.7829"),
            longitude=Decimal("-73.9654"),
        )
        self.art2 = PublicArt.objects.create(
            title="Times Square Art",
            artist_name="Modern Artist",
            location="Times Square",
            borough="Manhattan",
            latitude=Decimal("40.7580"),
            longitude=Decimal("-73.9855"),
        )
        self.chat_url = "/chatbot/api/chat/"

    def test_complete_greeting_conversation(self):
        """Test a complete greeting conversation"""
        self.client.login(username="testuser", password="testpass123")

        # User says hi
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "hi"}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertIn("ArtBot", data["response"])

        # User says thanks
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "thanks", "session_id": data["session_id"]}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertIn("welcome", data["response"].lower())

    def test_location_based_artwork_flow(self):
        """Test location-based artwork search flow"""
        self.client.login(username="testuser", password="testpass123")

        # Ask about artworks in Central Park
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "show me art in central park"}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        # Should mention Central Park or artworks
        self.assertTrue(
            "central park" in data["response"].lower()
            or "artwork" in data["response"].lower()
            or "art" in data["response"].lower()
        )

    def test_nearby_artworks_flow_with_location(self):
        """Test nearby artworks flow with GPS location"""
        self.client.login(username="testuser", password="testpass123")

        # Ask for nearby artworks with location
        response = self.client.post(
            self.chat_url,
            data=json.dumps(
                {
                    "message": "show me nearby artworks",
                    "location": {"lat": 40.7829, "lng": -73.9654},
                }
            ),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_nearby_artworks_flow_without_location(self):
        """Test nearby artworks flow without GPS location"""
        self.client.login(username="testuser", password="testpass123")

        # Ask for nearby artworks without location
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "show me nearby artworks"}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        # Should request location or provide alternative
        self.assertTrue(
            data["metadata"].get("request_location")
            or "location" in data["response"].lower()
        )

    def test_multi_turn_conversation(self):
        """Test multi-turn conversation maintains context"""
        self.client.login(username="testuser", password="testpass123")
        session_id = None

        messages = [
            "hello",
            "show me art in manhattan",
            "what about brooklyn?",
            "thanks for your help!",
        ]

        for message in messages:
            payload = {"message": message}
            if session_id:
                payload["session_id"] = session_id

            response = self.client.post(
                self.chat_url, data=json.dumps(payload), content_type="application/json"
            )
            data = json.loads(response.content)
            self.assertTrue(data["success"])
            session_id = data["session_id"]
            time.sleep(0.01)

        # Verify all messages saved in same session
        session = ChatSession.objects.get(session_id=session_id)
        # 4 user messages + 4 bot responses = 8 messages
        self.assertEqual(session.messages.count(), 8)

    def test_content_moderation_flow(self):
        """Test content moderation in conversation"""
        self.client.login(username="testuser", password="testpass123")

        # Send inappropriate message
        response = self.client.post(
            self.chat_url,
            data=json.dumps({"message": "you stupid bot"}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertTrue(data["metadata"].get("content_warning"))

        # Follow up with clean message
        response = self.client.post(
            self.chat_url,
            data=json.dumps(
                {
                    "message": "sorry, show me art in central park",
                    "session_id": data["session_id"],
                }
            ),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertFalse(data["metadata"].get("content_warning"))

    def test_page_navigation_flow(self):
        """Test page navigation flow"""
        self.client.login(username="testuser", password="testpass123")

        navigation_tests = [
            ("where is the map?", "map"),
            ("show me events", "events"),
            ("where are my favorites?", "favorites"),
        ]

        for message, expected_page in navigation_tests:
            response = self.client.post(
                self.chat_url,
                data=json.dumps({"message": message}),
                content_type="application/json",
            )
            data = json.loads(response.content)
            self.assertTrue(data["success"])
            # Should provide helpful response about the page
            self.assertGreater(len(data["response"]), 10)


class ChatHistoryIntegrationTests(TestCase):
    """Integration tests for chat history"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_history_reflects_conversation(self):
        """Test that history accurately reflects conversation"""
        self.client.login(username="testuser", password="testpass123")

        # Have a conversation
        messages = ["hello", "show me art", "thanks"]
        session_id = None

        for msg in messages:
            payload = {"message": msg}
            if session_id:
                payload["session_id"] = session_id

            response = self.client.post(
                "/chatbot/api/chat/",
                data=json.dumps(payload),
                content_type="application/json",
            )
            data = json.loads(response.content)
            session_id = data["session_id"]

        # Get history
        response = self.client.get("/chatbot/api/history/", {"session_id": session_id})
        data = json.loads(response.content)

        self.assertTrue(data["success"])
        self.assertEqual(len(data["messages"]), 6)  # 3 user + 3 bot

        # Verify message order
        user_messages = [
            m["message"] for m in data["messages"] if m["sender"] == "user"
        ]
        self.assertEqual(user_messages, messages)


class ItineraryPreparationIntegrationTests(TestCase):
    """Integration tests for itinerary preparation"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # Create artworks
        for i in range(5):
            PublicArt.objects.create(
                title=f"Art {i}",
                location="Manhattan",
                latitude=Decimal("40.7829") + Decimal(str(i * 0.01)),
                longitude=Decimal("-73.9654"),
            )

    def test_prepare_itinerary_from_chat(self):
        """Test preparing itinerary from chat suggestions"""
        self.client.login(username="testuser", password="testpass123")

        # Get artwork IDs
        artwork_ids = list(PublicArt.objects.values_list("id", flat=True)[:3])

        # Prepare itinerary
        response = self.client.post(
            "/chatbot/api/prepare-itinerary/",
            data=json.dumps({"locations": artwork_ids}),
            content_type="application/json",
        )
        data = json.loads(response.content)

        self.assertTrue(data["success"])
        self.assertEqual(data["redirect_url"], "/itineraries/create/")

        # Verify session data
        session = self.client.session
        self.assertEqual(session["suggested_locations"], artwork_ids)


class ClearChatIntegrationTests(TestCase):
    """Integration tests for clearing chat"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_clear_chat_and_continue(self):
        """Test clearing chat and continuing conversation"""
        self.client.login(username="testuser", password="testpass123")

        # Have a conversation
        response = self.client.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        session_id = data["session_id"]

        # Add more messages
        for _ in range(3):
            self.client.post(
                "/chatbot/api/chat/",
                data=json.dumps(
                    {"message": "another message", "session_id": session_id}
                ),
                content_type="application/json",
            )

        # Verify messages exist
        session = ChatSession.objects.get(session_id=session_id)
        self.assertGreater(session.messages.count(), 0)

        # Clear chat
        response = self.client.post(
            "/chatbot/api/clear/",
            data=json.dumps({"session_id": session_id}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])

        # Verify messages cleared
        session.refresh_from_db()
        self.assertEqual(session.messages.count(), 0)

        # Continue conversation
        response = self.client.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": "hi again", "session_id": session_id}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])

        # Verify new message added
        self.assertEqual(session.messages.count(), 2)  # user + bot


class EdgeCaseTests(TestCase):
    """Tests for edge cases and error handling"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_very_long_message(self):
        """Test handling very long message"""
        self.client.login(username="testuser", password="testpass123")

        long_message = "hello " * 1000

        response = self.client.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": long_message}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_special_characters_in_message(self):
        """Test handling special characters"""
        self.client.login(username="testuser", password="testpass123")

        special_message = (
            "Hello! 🎨 What's the best art? " "@NYC #art <script>alert('test')</script>"
        )

        response = self.client.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": special_message}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_unicode_message(self):
        """Test handling unicode characters"""
        self.client.login(username="testuser", password="testpass123")

        unicode_message = "你好 مرحبا Привет 🌍"

        response = self.client.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": unicode_message}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_rapid_messages(self):
        """Test handling rapid sequential messages"""
        self.client.login(username="testuser", password="testpass123")

        session_id = None
        for i in range(10):
            payload = {"message": f"message {i}"}
            if session_id:
                payload["session_id"] = session_id

            response = self.client.post(
                "/chatbot/api/chat/",
                data=json.dumps(payload),
                content_type="application/json",
            )
            data = json.loads(response.content)
            self.assertTrue(data["success"])
            session_id = data["session_id"]

        # Verify all messages saved
        session = ChatSession.objects.get(session_id=session_id)
        self.assertEqual(session.messages.count(), 20)  # 10 user + 10 bot

    def test_empty_location_coordinates(self):
        """Test handling empty location coordinates"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": "show me nearby art", "location": {}}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_invalid_location_coordinates(self):
        """Test handling invalid location coordinates"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            "/chatbot/api/chat/",
            data=json.dumps(
                {
                    "message": "show me nearby art",
                    "location": {"lat": "invalid", "lng": "invalid"},
                }
            ),
            content_type="application/json",
        )
        data = json.loads(response.content)
        # Should handle gracefully
        self.assertTrue(data["success"])


class MultiUserTests(TestCase):
    """Tests for multi-user scenarios"""

    def setUp(self):
        self.client1 = Client()
        self.client2 = Client()
        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="testpass123"
        )

    def test_users_have_separate_sessions(self):
        """Test that users have separate chat sessions"""
        self.client1.login(username="user1", password="testpass123")
        self.client2.login(username="user2", password="testpass123")

        # User 1 starts conversation
        response1 = self.client1.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": "hello from user 1"}),
            content_type="application/json",
        )
        data1 = json.loads(response1.content)
        session_id1 = data1["session_id"]

        # User 2 starts conversation
        response2 = self.client2.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": "hello from user 2"}),
            content_type="application/json",
        )
        data2 = json.loads(response2.content)
        session_id2 = data2["session_id"]

        # Sessions should be different
        self.assertNotEqual(session_id1, session_id2)

        # Verify separate sessions
        session1 = ChatSession.objects.get(session_id=session_id1)
        session2 = ChatSession.objects.get(session_id=session_id2)

        self.assertEqual(session1.user, self.user1)
        self.assertEqual(session2.user, self.user2)

    def test_users_cannot_access_each_others_history(self):
        """Test that users cannot access each other's chat history"""
        self.client1.login(username="user1", password="testpass123")
        self.client2.login(username="user2", password="testpass123")

        # User 1 creates a session
        response1 = self.client1.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": "secret message from user 1"}),
            content_type="application/json",
        )
        data1 = json.loads(response1.content)
        session_id1 = data1["session_id"]

        # User 2 tries to access User 1's history
        response2 = self.client2.get(
            "/chatbot/api/history/", {"session_id": session_id1}
        )
        data2 = json.loads(response2.content)

        # Should not find any messages
        self.assertEqual(data2["messages"], [])
        self.assertIsNone(data2["session_id"])

    def test_users_cannot_clear_each_others_chat(self):
        """Test that users cannot clear each other's chat"""
        self.client1.login(username="user1", password="testpass123")
        self.client2.login(username="user2", password="testpass123")

        # User 1 creates a session with messages
        response1 = self.client1.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": "important message"}),
            content_type="application/json",
        )
        data1 = json.loads(response1.content)
        session_id1 = data1["session_id"]

        # User 2 tries to clear User 1's chat
        self.client2.post(
            "/chatbot/api/clear/",
            data=json.dumps({"session_id": session_id1}),
            content_type="application/json",
        )

        # User 1's messages should still exist
        session1 = ChatSession.objects.get(session_id=session_id1)
        self.assertGreater(session1.messages.count(), 0)


class PerformanceTests(TestCase):
    """Tests for performance considerations"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_large_conversation_history(self):
        """Test handling large conversation history"""
        self.client.login(username="testuser", password="testpass123")

        # Create a session with many messages
        session = ChatSession.objects.create(
            user=self.user, session_id="large-history-session"
        )

        # Create 100 messages
        for i in range(100):
            ChatMessage.objects.create(
                session=session,
                sender="user" if i % 2 == 0 else "bot",
                message=f"Message number {i}",
            )

        # Get history (should be limited to 50)
        response = self.client.get(
            "/chatbot/api/history/", {"session_id": "large-history-session"}
        )
        data = json.loads(response.content)

        self.assertTrue(data["success"])
        self.assertEqual(len(data["messages"]), 50)

    def test_many_artworks_search(self):
        """Test searching with many artworks in database"""
        self.client.login(username="testuser", password="testpass123")

        # Create many artworks
        for i in range(50):
            PublicArt.objects.create(
                title=f"Manhattan Art {i}",
                location="Manhattan",
                borough="Manhattan",
                latitude=Decimal("40.7829") + Decimal(str(i * 0.001)),
                longitude=Decimal("-73.9654"),
            )

        # Search should still work efficiently
        response = self.client.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": "show me art in manhattan"}),
            content_type="application/json",
        )
        data = json.loads(response.content)
        self.assertTrue(data["success"])
