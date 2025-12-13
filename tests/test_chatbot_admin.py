"""
Comprehensive test suite for Chatbot app - Part 4
Tests for admin configuration
"""
# flake8: noqa

from unittest.mock import patch, MagicMock

genai_patcher = patch("chatbot.ai_service.genai")
mock_genai = genai_patcher.start()
mock_model = MagicMock()
mock_model.generate_content.return_value = MagicMock(text="Mocked AI response")
mock_genai.GenerativeModel.return_value = mock_model

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite

from chatbot.models import ChatSession, ChatMessage
from chatbot.admin import ChatSessionAdmin, ChatMessageAdmin


class ChatSessionAdminTests(TestCase):
    """Tests for ChatSessionAdmin"""

    def setUp(self):
        self.site = AdminSite()
        self.admin = ChatSessionAdmin(ChatSession, self.site)
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.session = ChatSession.objects.create(
            user=self.user, session_id="admin-test-session"
        )
        # Add some messages
        ChatMessage.objects.create(
            session=self.session, sender="user", message="Test message 1"
        )
        ChatMessage.objects.create(
            session=self.session, sender="bot", message="Test message 2"
        )

    def test_list_display(self):
        """Test list_display configuration"""
        expected = ["user", "session_id", "created_at", "updated_at", "message_count"]
        self.assertEqual(list(self.admin.list_display), expected)

    def test_list_filter(self):
        """Test list_filter configuration"""
        expected = ["created_at", "updated_at"]
        self.assertEqual(list(self.admin.list_filter), expected)

    def test_search_fields(self):
        """Test search_fields configuration"""
        expected = ["user__username", "session_id"]
        self.assertEqual(list(self.admin.search_fields), expected)

    def test_readonly_fields(self):
        """Test readonly_fields configuration"""
        expected = ["session_id", "created_at", "updated_at"]
        self.assertEqual(list(self.admin.readonly_fields), expected)

    def test_message_count_method(self):
        """Test message_count method"""
        count = self.admin.message_count(self.session)
        self.assertEqual(count, 2)

    def test_message_count_short_description(self):
        """Test message_count short_description"""
        self.assertEqual(self.admin.message_count.short_description, "Messages")


class ChatMessageAdminTests(TestCase):
    """Tests for ChatMessageAdmin"""

    def setUp(self):
        self.site = AdminSite()
        self.admin = ChatMessageAdmin(ChatMessage, self.site)
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.session = ChatSession.objects.create(
            user=self.user, session_id="admin-test-session"
        )
        self.message = ChatMessage.objects.create(
            session=self.session,
            sender="user",
            message="This is a test message for admin",
            metadata={"key": "value", "nested": {"a": 1}},
        )
        self.long_message = ChatMessage.objects.create(
            session=self.session,
            sender="bot",
            message="A" * 100,  # Long message
            metadata={},
        )

    def test_list_display(self):
        """Test list_display configuration"""
        expected = [
            "id",
            "session_user",
            "sender",
            "message_preview",
            "created_at",
            "has_metadata",
        ]
        self.assertEqual(list(self.admin.list_display), expected)

    def test_list_filter(self):
        """Test list_filter configuration"""
        expected = ["sender", "created_at"]
        self.assertEqual(list(self.admin.list_filter), expected)

    def test_search_fields(self):
        """Test search_fields configuration"""
        expected = ["message", "session__user__username"]
        self.assertEqual(list(self.admin.search_fields), expected)

    def test_readonly_fields(self):
        """Test readonly_fields configuration"""
        expected = ["created_at", "formatted_metadata"]
        self.assertEqual(list(self.admin.readonly_fields), expected)

    def test_session_user_method(self):
        """Test session_user method"""
        username = self.admin.session_user(self.message)
        self.assertEqual(username, "testuser")

    def test_session_user_short_description(self):
        """Test session_user short_description"""
        self.assertEqual(self.admin.session_user.short_description, "User")

    def test_message_preview_short(self):
        """Test message_preview for short message"""
        preview = self.admin.message_preview(self.message)
        self.assertEqual(preview, "This is a test message for admin")

    def test_message_preview_long(self):
        """Test message_preview for long message"""
        preview = self.admin.message_preview(self.long_message)
        self.assertEqual(len(preview), 53)  # 50 chars + "..."
        self.assertTrue(preview.endswith("..."))

    def test_has_metadata_true(self):
        """Test has_metadata for message with metadata"""
        has_meta = self.admin.has_metadata(self.message)
        self.assertTrue(has_meta)

    def test_has_metadata_false(self):
        """Test has_metadata for message without metadata"""
        has_meta = self.admin.has_metadata(self.long_message)
        self.assertFalse(has_meta)

    def test_has_metadata_boolean(self):
        """Test has_metadata boolean attribute"""
        self.assertTrue(self.admin.has_metadata.boolean)

    def test_formatted_metadata_with_data(self):
        """Test formatted_metadata with metadata"""
        formatted = self.admin.formatted_metadata(self.message)
        self.assertIn("key", formatted)
        self.assertIn("value", formatted)
        self.assertIn("nested", formatted)

    def test_formatted_metadata_empty(self):
        """Test formatted_metadata with empty metadata"""
        formatted = self.admin.formatted_metadata(self.long_message)
        self.assertEqual(formatted, "No metadata")

    def test_fieldsets(self):
        """Test fieldsets configuration"""
        expected_fieldsets = (
            (
                "Message Info",
                {"fields": ("session", "sender", "message", "created_at")},
            ),
            ("Metadata", {"fields": ("formatted_metadata",), "classes": ("collapse",)}),
        )
        self.assertEqual(self.admin.fieldsets, expected_fieldsets)


class AdminIntegrationTests(TestCase):
    """Integration tests for admin interface"""

    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass123"
        )
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.session = ChatSession.objects.create(
            user=self.user, session_id="integration-test-session"
        )
        self.message = ChatMessage.objects.create(
            session=self.session, sender="user", message="Test message"
        )

    def test_admin_login_required(self):
        """Test that admin requires login"""
        response = self.client.get("/admin/chatbot/chatsession/")
        self.assertEqual(response.status_code, 302)

    def test_admin_session_list(self):
        """Test admin session list view"""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get("/admin/chatbot/chatsession/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "integration-test-session")

    def test_admin_session_detail(self):
        """Test admin session detail view"""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(
            f"/admin/chatbot/chatsession/{self.session.id}/change/"
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_message_list(self):
        """Test admin message list view"""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get("/admin/chatbot/chatmessage/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test message")

    def test_admin_message_detail(self):
        """Test admin message detail view"""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get(
            f"/admin/chatbot/chatmessage/{self.message.id}/change/"
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_session_search(self):
        """Test admin session search functionality"""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get("/admin/chatbot/chatsession/?q=testuser")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "integration-test-session")

    def test_admin_message_search(self):
        """Test admin message search functionality"""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get("/admin/chatbot/chatmessage/?q=Test")
        self.assertEqual(response.status_code, 200)

    def test_admin_message_filter_by_sender(self):
        """Test admin message filter by sender"""
        self.client.login(username="admin", password="adminpass123")
        response = self.client.get("/admin/chatbot/chatmessage/?sender=user")
        self.assertEqual(response.status_code, 200)


class AdminRegistrationTests(TestCase):
    """Tests for admin model registration"""

    def test_chatsession_registered(self):
        """Test that ChatSession is registered in admin"""
        from django.contrib.admin.sites import site

        self.assertIn(ChatSession, site._registry)

    def test_chatmessage_registered(self):
        """Test that ChatMessage is registered in admin"""
        from django.contrib.admin.sites import site

        self.assertIn(ChatMessage, site._registry)
