"""
Comprehensive test suite for Chatbot app - Part 1
Tests for models (ChatSession, ChatMessage)
"""

from django.test import TestCase
from django.contrib.auth.models import User
import time

from chatbot.models import ChatSession, ChatMessage


class ChatSessionModelTests(TestCase):
    """Tests for ChatSession model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_create_chat_session(self):
        """Test creating a chat session"""
        session = ChatSession.objects.create(
            user=self.user, session_id="test-session-123"
        )
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.session_id, "test-session-123")
        self.assertIsNotNone(session.created_at)
        self.assertIsNotNone(session.updated_at)

    def test_chat_session_str_representation(self):
        """Test string representation of ChatSession"""
        session = ChatSession.objects.create(
            user=self.user, session_id="test-session-456"
        )
        expected_str = f"Chat session for {self.user.username} - test-session-456"
        self.assertEqual(str(session), expected_str)

    def test_session_id_unique(self):
        """Test that session_id must be unique"""
        ChatSession.objects.create(user=self.user, session_id="unique-session-id")
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            ChatSession.objects.create(user=self.user, session_id="unique-session-id")

    def test_chat_session_ordering(self):
        """Test that sessions are ordered by updated_at descending"""
        session1 = ChatSession.objects.create(user=self.user, session_id="session-1")
        time.sleep(0.01)
        session2 = ChatSession.objects.create(user=self.user, session_id="session-2")

        sessions = list(ChatSession.objects.all())
        self.assertEqual(sessions[0], session2)  # Most recent first
        self.assertEqual(sessions[1], session1)

    def test_chat_session_cascade_delete_user(self):
        """Test that sessions are deleted when user is deleted"""
        session = ChatSession.objects.create(user=self.user, session_id="cascade-test")
        session_id = session.id
        self.user.delete()
        self.assertFalse(ChatSession.objects.filter(id=session_id).exists())

    def test_user_can_have_multiple_sessions(self):
        """Test that a user can have multiple chat sessions"""
        ChatSession.objects.create(user=self.user, session_id="session-a")
        ChatSession.objects.create(user=self.user, session_id="session-b")
        ChatSession.objects.create(user=self.user, session_id="session-c")

        user_sessions = ChatSession.objects.filter(user=self.user)
        self.assertEqual(user_sessions.count(), 3)

    def test_session_updated_at_changes_on_save(self):
        """Test that updated_at changes when session is saved"""
        session = ChatSession.objects.create(user=self.user, session_id="update-test")
        original_updated_at = session.updated_at
        time.sleep(0.01)
        session.save()
        session.refresh_from_db()
        self.assertGreater(session.updated_at, original_updated_at)

    def test_session_related_name(self):
        """Test that user can access sessions via related_name"""
        ChatSession.objects.create(user=self.user, session_id="related-1")
        ChatSession.objects.create(user=self.user, session_id="related-2")

        self.assertEqual(self.user.chat_sessions.count(), 2)


class ChatMessageModelTests(TestCase):
    """Tests for ChatMessage model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.session = ChatSession.objects.create(
            user=self.user, session_id="test-session"
        )

    def test_create_user_message(self):
        """Test creating a user message"""
        message = ChatMessage.objects.create(
            session=self.session, sender="user", message="Hello, chatbot!"
        )
        self.assertEqual(message.session, self.session)
        self.assertEqual(message.sender, "user")
        self.assertEqual(message.message, "Hello, chatbot!")
        self.assertIsNotNone(message.created_at)

    def test_create_bot_message(self):
        """Test creating a bot message"""
        message = ChatMessage.objects.create(
            session=self.session, sender="bot", message="Hello! How can I help you?"
        )
        self.assertEqual(message.sender, "bot")

    def test_message_str_representation(self):
        """Test string representation of ChatMessage"""
        message = ChatMessage.objects.create(
            session=self.session,
            sender="user",
            message="This is a test message that is quite long",
        )
        self.assertIn("user:", str(message))
        self.assertIn("...", str(message))

    def test_message_str_short_message(self):
        """Test string representation for short messages"""
        message = ChatMessage.objects.create(
            session=self.session, sender="bot", message="Hi"
        )
        self.assertEqual(str(message), "bot: Hi...")

    def test_message_with_metadata(self):
        """Test creating a message with metadata"""
        metadata = {
            "artworks": [{"id": 1, "title": "Test Art"}],
            "show_itinerary_prompt": True,
        }
        message = ChatMessage.objects.create(
            session=self.session,
            sender="bot",
            message="Here are some artworks",
            metadata=metadata,
        )
        self.assertEqual(message.metadata["artworks"][0]["title"], "Test Art")
        self.assertTrue(message.metadata["show_itinerary_prompt"])

    def test_message_default_metadata(self):
        """Test that metadata defaults to empty dict"""
        message = ChatMessage.objects.create(
            session=self.session, sender="user", message="Test message"
        )
        self.assertEqual(message.metadata, {})

    def test_message_ordering(self):
        """Test that messages are ordered by created_at ascending"""
        msg1 = ChatMessage.objects.create(
            session=self.session, sender="user", message="First message"
        )
        time.sleep(0.01)
        msg2 = ChatMessage.objects.create(
            session=self.session, sender="bot", message="Second message"
        )
        time.sleep(0.01)
        msg3 = ChatMessage.objects.create(
            session=self.session, sender="user", message="Third message"
        )

        messages = list(self.session.messages.all())
        self.assertEqual(messages[0], msg1)
        self.assertEqual(messages[1], msg2)
        self.assertEqual(messages[2], msg3)

    def test_message_cascade_delete_session(self):
        """Test that messages are deleted when session is deleted"""
        ChatMessage.objects.create(
            session=self.session, sender="user", message="Test message"
        )
        self.assertEqual(ChatMessage.objects.count(), 1)
        self.session.delete()
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_session_messages_related_name(self):
        """Test accessing messages via session related_name"""
        ChatMessage.objects.create(
            session=self.session, sender="user", message="Message 1"
        )
        ChatMessage.objects.create(
            session=self.session, sender="bot", message="Message 2"
        )

        self.assertEqual(self.session.messages.count(), 2)

    def test_message_sender_choices(self):
        """Test that sender must be 'user' or 'bot'"""
        # Valid senders
        user_msg = ChatMessage.objects.create(
            session=self.session, sender="user", message="User message"
        )
        bot_msg = ChatMessage.objects.create(
            session=self.session, sender="bot", message="Bot message"
        )
        self.assertEqual(user_msg.sender, "user")
        self.assertEqual(bot_msg.sender, "bot")

    def test_message_with_complex_metadata(self):
        """Test message with complex nested metadata"""
        metadata = {
            "artworks": [
                {
                    "id": 1,
                    "title": "Statue",
                    "artist": "Artist A",
                    "location": "Central Park",
                    "distance": 0.5,
                },
                {
                    "id": 2,
                    "title": "Mural",
                    "artist": "Artist B",
                    "location": "Brooklyn",
                    "distance": 1.2,
                },
            ],
            "navigation": {"url": "/artinerary/", "name": "Interactive Map"},
            "show_itinerary_prompt": True,
            "suggested_locations": [1, 2],
        }
        message = ChatMessage.objects.create(
            session=self.session,
            sender="bot",
            message="Found artworks",
            metadata=metadata,
        )
        message.refresh_from_db()
        self.assertEqual(len(message.metadata["artworks"]), 2)
        self.assertEqual(message.metadata["navigation"]["name"], "Interactive Map")

    def test_message_with_content_warning_metadata(self):
        """Test message with content moderation metadata"""
        metadata = {"content_warning": True, "moderation_severity": "warn"}
        message = ChatMessage.objects.create(
            session=self.session,
            sender="bot",
            message="Please keep conversation respectful",
            metadata=metadata,
        )
        self.assertTrue(message.metadata["content_warning"])
        self.assertEqual(message.metadata["moderation_severity"], "warn")

    def test_long_message(self):
        """Test storing a very long message"""
        long_text = "A" * 10000
        message = ChatMessage.objects.create(
            session=self.session, sender="user", message=long_text
        )
        message.refresh_from_db()
        self.assertEqual(len(message.message), 10000)

    def test_message_with_special_characters(self):
        """Test message with special characters and emojis"""
        special_message = "Hello! 🎨 What's the best art in NYC? #art @user"
        message = ChatMessage.objects.create(
            session=self.session, sender="user", message=special_message
        )
        message.refresh_from_db()
        self.assertEqual(message.message, special_message)

    def test_message_with_unicode(self):
        """Test message with unicode characters"""
        unicode_message = "你好世界 مرحبا 🌍 Привет"
        message = ChatMessage.objects.create(
            session=self.session, sender="user", message=unicode_message
        )
        message.refresh_from_db()
        self.assertEqual(message.message, unicode_message)


class ChatSessionMessageIntegrationTests(TestCase):
    """Integration tests for ChatSession and ChatMessage"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="testpass123"
        )

    def test_multiple_users_multiple_sessions(self):
        """Test multiple users with multiple sessions each"""
        # User 1 sessions
        session1a = ChatSession.objects.create(
            user=self.user1, session_id="user1-session-a"
        )
        session1b = ChatSession.objects.create(
            user=self.user1, session_id="user1-session-b"
        )

        # User 2 sessions
        session2a = ChatSession.objects.create(
            user=self.user2, session_id="user2-session-a"
        )

        # Add messages to sessions
        ChatMessage.objects.create(
            session=session1a, sender="user", message="User 1, Session A"
        )
        ChatMessage.objects.create(
            session=session1b, sender="user", message="User 1, Session B"
        )
        ChatMessage.objects.create(
            session=session2a, sender="user", message="User 2, Session A"
        )

        # Verify counts
        self.assertEqual(self.user1.chat_sessions.count(), 2)
        self.assertEqual(self.user2.chat_sessions.count(), 1)
        self.assertEqual(session1a.messages.count(), 1)
        self.assertEqual(session1b.messages.count(), 1)
        self.assertEqual(session2a.messages.count(), 1)

    def test_conversation_flow(self):
        """Test a typical conversation flow"""
        session = ChatSession.objects.create(
            user=self.user1, session_id="conversation-test"
        )

        # Simulate conversation
        messages = [
            ("user", "Hello!"),
            ("bot", "Hello! I'm ArtBot. How can I help you?"),
            ("user", "Show me art near Central Park"),
            ("bot", "Here are artworks near Central Park!"),
            ("user", "Thanks!"),
            ("bot", "You're welcome!"),
        ]

        for sender, text in messages:
            ChatMessage.objects.create(session=session, sender=sender, message=text)
            time.sleep(0.001)

        # Verify conversation
        conversation = list(session.messages.all())
        self.assertEqual(len(conversation), 6)
        self.assertEqual(conversation[0].message, "Hello!")
        self.assertEqual(conversation[-1].message, "You're welcome!")

    def test_session_with_many_messages(self):
        """Test session with many messages"""
        session = ChatSession.objects.create(
            user=self.user1, session_id="many-messages"
        )

        # Create 100 messages
        for i in range(100):
            sender = "user" if i % 2 == 0 else "bot"
            ChatMessage.objects.create(
                session=session, sender=sender, message=f"Message {i}"
            )

        self.assertEqual(session.messages.count(), 100)

        # Test slicing (like in chat_history view)
        recent_messages = session.messages.all()[:50]
        self.assertEqual(len(list(recent_messages)), 50)
