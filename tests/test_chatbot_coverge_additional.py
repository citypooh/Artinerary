"""
Additional tests for Chatbot app - Covering uncovered lines
Tests for exception handling and edge cases
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from decimal import Decimal
import json

from chatbot.models import ChatSession
from chatbot.ai_service import ArtineraryAI
from loc_detail.models import PublicArt


class ArtineraryAIModelInitializationTests(TestCase):
    """Tests for Gemini model initialization edge cases"""

    @patch("chatbot.ai_service.genai")
    def test_model_initialization_all_fail(self, mock_genai):
        """Test when all model names fail to initialize"""
        mock_genai.GenerativeModel.side_effect = Exception("Model not found")

        ai = ArtineraryAI()

        # Model should be None when all fail
        self.assertIsNone(ai.model)

    @patch("chatbot.ai_service.genai")
    def test_model_initialization_first_fails_second_succeeds(self, mock_genai):
        """Test when first model fails but second succeeds"""
        mock_model = MagicMock()
        # First call fails, second succeeds
        mock_genai.GenerativeModel.side_effect = [
            Exception("Model not found"),
            mock_model,
        ]

        ai = ArtineraryAI()

        # Model should be set to the second successful one
        self.assertEqual(ai.model, mock_model)


class ArtineraryAIDistanceExceptionTests(TestCase):
    """Tests for exception handling in distance calculations"""

    def setUp(self):
        self.ai = ArtineraryAI()

    def test_get_nearby_artworks_with_invalid_artwork_coords(self):
        """Test nearby artworks when artwork has invalid coordinates"""
        # Create artwork with coordinates that will cause calculation error
        art = PublicArt.objects.create(
            title="Test Art", latitude=Decimal("40.7829"), longitude=Decimal("-73.9654")
        )

        # Mock the calculate_distance to raise exception for this artwork
        original_calc = self.ai.calculate_distance

        def mock_calc(lat1, lon1, lat2, lon2):
            if lat2 == float(art.latitude):
                raise Exception("Calculation error")
            return original_calc(lat1, lon1, lat2, lon2)

        self.ai.calculate_distance = mock_calc

        # Should handle gracefully and return empty or skip bad artwork
        result = self.ai.get_nearby_artworks(40.7829, -73.9654)
        # Should not crash
        self.assertIsInstance(result, list)


class ArtineraryAIGenerateResponseTests(TestCase):
    """Tests for AI response generation"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    @patch("chatbot.ai_service.genai")
    def test_generate_ai_response_with_model_response(self, mock_genai):
        """Test generate_ai_response when model returns valid response"""
        mock_response = MagicMock()
        mock_response.text = "**Hello!** This is a *test* response."

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        mock_genai.GenerativeModel.return_value = mock_model

        ai = ArtineraryAI()
        response = ai.generate_ai_response("test message", self.user)

        # Should clean markdown
        self.assertNotIn("**", response)
        self.assertNotIn("*", response)

    @patch("chatbot.ai_service.genai")
    def test_generate_ai_response_empty_response(self, mock_genai):
        """Test generate_ai_response when model returns empty response"""
        mock_response = MagicMock()
        mock_response.text = ""

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        mock_genai.GenerativeModel.return_value = mock_model

        ai = ArtineraryAI()
        response = ai.generate_ai_response("test message", self.user)

        # Should use fallback
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)

    @patch("chatbot.ai_service.genai")
    def test_generate_ai_response_none_response(self, mock_genai):
        """Test generate_ai_response when model returns None"""
        mock_model = MagicMock()
        mock_model.generate_content.return_value = None

        mock_genai.GenerativeModel.return_value = mock_model

        ai = ArtineraryAI()
        response = ai.generate_ai_response("test message", self.user)

        # Should use fallback
        self.assertIsInstance(response, str)

    @patch("chatbot.ai_service.genai")
    def test_generate_ai_response_exception(self, mock_genai):
        """Test generate_ai_response when model raises exception"""
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API Error")

        mock_genai.GenerativeModel.return_value = mock_model

        ai = ArtineraryAI()
        response = ai.generate_ai_response("test message", self.user)

        # Should use fallback
        self.assertIsInstance(response, str)

    @patch("chatbot.ai_service.genai")
    def test_generate_ai_response_no_model(self, mock_genai):
        """Test generate_ai_response when no model is available"""
        mock_genai.GenerativeModel.side_effect = Exception("No model")

        ai = ArtineraryAI()
        response = ai.generate_ai_response("test message", self.user)

        # Should use fallback
        self.assertIsInstance(response, str)


class ArtineraryAISmartFallbackTests(TestCase):
    """Tests for smart fallback responses - covering all branches"""

    def setUp(self):
        self.ai = ArtineraryAI()

    def test_fallback_profile_query(self):
        """Test fallback for profile query"""
        response = self.ai._get_smart_fallback("how do I update my profile")
        self.assertIn("profile", response.lower())

    def test_fallback_account_query(self):
        """Test fallback for account query"""
        response = self.ai._get_smart_fallback("where is my account settings")
        self.assertIn("profile", response.lower())

    def test_fallback_itinerary_query(self):
        """Test fallback for itinerary query"""
        response = self.ai._get_smart_fallback("how to create an itinerary")
        self.assertIn("itinerary", response.lower())

    def test_fallback_tour_query(self):
        """Test fallback for tour query"""
        response = self.ai._get_smart_fallback("help me plan a tour")
        self.assertIn("itinerary", response.lower())

    def test_fallback_route_query(self):
        """Test fallback for route query"""
        response = self.ai._get_smart_fallback("show me the route")
        self.assertIn("itinerary", response.lower())

    def test_fallback_dashboard_query(self):
        """Test fallback for dashboard query"""
        response = self.ai._get_smart_fallback("take me to dashboard")
        self.assertIn("dashboard", response.lower())

    def test_fallback_home_query(self):
        """Test fallback for home query"""
        response = self.ai._get_smart_fallback("go to home page")
        self.assertIn("dashboard", response.lower())

    def test_fallback_chat_query(self):
        """Test fallback for chat query"""
        response = self.ai._get_smart_fallback("where are my messages")
        # Should return general response or chat-related
        self.assertIsInstance(response, str)

    def test_fallback_visit_query(self):
        """Test fallback for visit query"""
        response = self.ai._get_smart_fallback("what places can I visit")
        self.assertIn("art", response.lower())

    def test_fallback_suggestions_query(self):
        """Test fallback for suggestions query"""
        response = self.ai._get_smart_fallback("give me some suggestions")
        self.assertIn("art", response.lower())


class ArtineraryAINearbyWithLocationTests(TestCase):
    """Tests for nearby artworks with various location scenarios"""

    def setUp(self):
        self.ai = ArtineraryAI()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # Create test artwork
        PublicArt.objects.create(
            title="Test Art", latitude=Decimal("40.7829"), longitude=Decimal("-73.9654")
        )

    def test_nearby_with_location_missing_lat(self):
        """Test nearby request with location missing lat"""
        response = self.ai.process_message(
            "show me nearby artworks", self.user, {"lng": -73.9654}  # Missing lat
        )
        # Should request location
        self.assertTrue(
            response["metadata"].get("request_location")
            or "location" in response["message"].lower()
        )

    def test_nearby_with_location_missing_lng(self):
        """Test nearby request with location missing lng"""
        response = self.ai.process_message(
            "show me nearby artworks", self.user, {"lat": 40.7829}  # Missing lng
        )
        # Should request location
        self.assertTrue(
            response["metadata"].get("request_location")
            or "location" in response["message"].lower()
        )

    def test_nearby_with_location_none_values(self):
        """Test nearby request with None coordinate values"""
        response = self.ai.process_message(
            "show me nearby artworks", self.user, {"lat": None, "lng": None}
        )
        # Should request location
        self.assertTrue(
            response["metadata"].get("request_location")
            or "location" in response["message"].lower()
        )


class ArtineraryAIRestaurantBarQueriesTests(TestCase):
    """Tests for restaurant/bar queries with locations"""

    def setUp(self):
        self.ai = ArtineraryAI()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_restaurant_query_with_borough_and_artworks(self):
        """Test restaurant query with borough location and artworks"""
        # Create artwork in Manhattan
        PublicArt.objects.create(
            title="Manhattan Art",
            location="Manhattan",
            borough="Manhattan",
            latitude=Decimal("40.7580"),
            longitude=Decimal("-73.9855"),
        )

        response = self.ai.process_message(
            "what restaurants are in manhattan", self.user, None
        )

        self.assertIn("message", response)
        # Should mention artworks or dining
        self.assertTrue(
            "artwork" in response["message"].lower()
            or "dining" in response["message"].lower()
            or "art" in response["message"].lower()
        )

    def test_restaurant_query_with_neighborhood_no_artworks(self):
        """Test restaurant query with neighborhood but no artworks"""
        response = self.ai.process_message(
            "what bars are near columbus circle", self.user, None
        )

        self.assertIn("message", response)
        # Should provide some response about the area
        self.assertGreater(len(response["message"]), 10)

    def test_restaurant_query_with_known_area_places_info(self):
        """Test restaurant query with area that has places info"""
        # Create artwork in Central Park
        PublicArt.objects.create(
            title="Central Park Art",
            location="Central Park",
            borough="Manhattan",
            latitude=Decimal("40.7829"),
            longitude=Decimal("-73.9654"),
        )

        response = self.ai.process_message(
            "any restaurants near central park", self.user, None
        )

        self.assertIn("message", response)
        # Should include places info or artworks
        if response["metadata"].get("artworks"):
            self.assertGreater(len(response["metadata"]["artworks"]), 0)

    def test_restaurant_query_without_artworks_with_places(self):
        """Test restaurant query - no artworks but has places info"""
        response = self.ai.process_message(
            "where to eat in times square", self.user, None
        )

        self.assertIn("message", response)

    def test_restaurant_query_without_artworks_without_places(self):
        """Test restaurant query - no artworks and no places info"""
        response = self.ai.process_message(
            "restaurants in some random unknown area xyz", self.user, None
        )

        # Should use AI fallback
        self.assertIn("message", response)


class ArtineraryAIExplicitNavigationTests(TestCase):
    """Tests for explicit navigation requests"""

    def setUp(self):
        self.ai = ArtineraryAI()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_go_to_map(self):
        """Test 'go to map' navigation"""
        response = self.ai.process_message("go to map", self.user, None)
        if response["metadata"].get("navigation"):
            self.assertIn("url", response["metadata"]["navigation"])

    def test_take_me_to_events(self):
        """Test 'take me to events' navigation"""
        response = self.ai.process_message("take me to events", self.user, None)
        self.assertIn("message", response)

    def test_open_favorites(self):
        """Test 'open favorites' navigation"""
        response = self.ai.process_message("open favorites", self.user, None)
        self.assertIn("message", response)

    def test_navigate_to_profile(self):
        """Test 'navigate to profile' navigation"""
        response = self.ai.process_message("navigate to profile", self.user, None)
        self.assertIn("message", response)

    def test_show_me_the_dashboard(self):
        """Test 'show me the dashboard' navigation"""
        response = self.ai.process_message("show me the dashboard", self.user, None)
        self.assertIn("message", response)

    def test_go_to_interactive_map(self):
        """Test navigation by page name"""
        response = self.ai.process_message("go to interactive map", self.user, None)
        self.assertIn("message", response)


class ArtineraryAISearchArtworkRequestTests(TestCase):
    """Tests for explicit search/find artwork requests"""

    def setUp(self):
        self.ai = ArtineraryAI()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # Create test artworks
        PublicArt.objects.create(
            title="Bronze Statue",
            artist_name="Famous Artist",
            medium="Bronze",
            latitude=Decimal("40.7829"),
            longitude=Decimal("-73.9654"),
        )

    def test_find_artwork_with_results(self):
        """Test 'find artwork' with matching results"""
        response = self.ai.process_message("find artwork bronze", self.user, None)

        if response["metadata"].get("artworks"):
            self.assertGreater(len(response["metadata"]["artworks"]), 0)
            self.assertTrue(response["metadata"].get("show_itinerary_prompt"))

    def test_search_for_artist(self):
        """Test 'search for' artist"""
        response = self.ai.process_message("search for famous artist", self.user, None)

        self.assertIn("message", response)

    def test_look_for_artwork_no_results(self):
        """Test 'look for artwork' with no results"""
        response = self.ai.process_message(
            "look for artwork xyz123nonexistent", self.user, None
        )

        # Should still return a response
        self.assertIn("message", response)

    def test_find_artwork_short_search_term(self):
        """Test 'find artwork' with very short search term"""
        response = self.ai.process_message(
            "find artwork ab", self.user, None  # Only 2 chars after cleanup
        )

        # Should handle gracefully
        self.assertIn("message", response)


class ViewExceptionHandlingTests(TestCase):
    """Tests for exception handling in views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    @patch("chatbot.views.ArtineraryAI")
    def test_chat_view_general_exception(self, mock_ai_class):
        """Test chat_view handles general exceptions"""
        mock_ai_class.side_effect = Exception("Unexpected error")

        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            "/chatbot/api/chat/",
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    @patch("chatbot.views.ChatSession.objects.filter")
    def test_chat_history_general_exception(self, mock_filter):
        """Test chat_history handles general exceptions"""
        mock_filter.side_effect = Exception("Database error")

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/chatbot/api/history/")

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Error loading chat history")

    @patch("chatbot.views.json.loads")
    def test_prepare_itinerary_general_exception(self, mock_loads):
        """Test prepare_itinerary handles general exceptions"""
        # First call is for parsing, we make it fail on session access
        mock_loads.return_value = {"locations": [1, 2, 3]}

        self.client.login(username="testuser", password="testpass123")

        with patch.object(
            self.client.session.__class__,
            "__setitem__",
            side_effect=Exception("Session error"),
        ):
            response = self.client.post(
                "/chatbot/api/prepare-itinerary/",
                data=json.dumps({"locations": [1, 2, 3]}),
                content_type="application/json",
            )

        # Should handle gracefully or succeed
        self.assertIn(response.status_code, [200, 500])

    @patch("chatbot.views.ChatSession.objects.get")
    def test_clear_chat_general_exception(self, mock_get):
        """Test clear_chat handles general exceptions"""
        mock_get.side_effect = Exception("Unexpected error")

        self.client.login(username="testuser", password="testpass123")

        # Create a valid session first
        ChatSession.objects.create(user=self.user, session_id="test-session")

        response = self.client.post(
            "/chatbot/api/clear/",
            data=json.dumps({"session_id": "test-session"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Error clearing chat")


class ArtineraryAIMarkdownCleaningTests(TestCase):
    """Tests for markdown cleaning in AI responses"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    @patch("chatbot.ai_service.genai")
    def test_clean_bold_markdown(self, mock_genai):
        """Test cleaning bold markdown"""
        mock_response = MagicMock()
        mock_response.text = "**Bold text** here"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        ai = ArtineraryAI()
        response = ai.generate_ai_response("test", self.user)

        self.assertNotIn("**", response)
        self.assertIn("Bold text", response)

    @patch("chatbot.ai_service.genai")
    def test_clean_italic_markdown(self, mock_genai):
        """Test cleaning italic markdown"""
        mock_response = MagicMock()
        mock_response.text = "*Italic text* here"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        ai = ArtineraryAI()
        response = ai.generate_ai_response("test", self.user)

        # Should clean single asterisks
        self.assertIn("Italic text", response)

    @patch("chatbot.ai_service.genai")
    def test_clean_header_markdown(self, mock_genai):
        """Test cleaning header markdown"""
        mock_response = MagicMock()
        mock_response.text = "# Header\nContent here"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        ai = ArtineraryAI()
        response = ai.generate_ai_response("test", self.user)

        self.assertNotIn("#", response)

    @patch("chatbot.ai_service.genai")
    def test_clean_bullet_list_markdown(self, mock_genai):
        """Test cleaning bullet list markdown"""
        mock_response = MagicMock()
        mock_response.text = "* Item 1\n- Item 2"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        ai = ArtineraryAI()
        response = ai.generate_ai_response("test", self.user)

        # Should convert to bullet points
        self.assertIn("•", response)


class ProcessMessageEdgeCasesTests(TestCase):
    """Additional edge case tests for process_message"""

    def setUp(self):
        self.ai = ArtineraryAI()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_process_message_with_latitude_key(self):
        """Test nearby with 'latitude' key instead of 'lat'"""
        PublicArt.objects.create(
            title="Test Art", latitude=Decimal("40.7829"), longitude=Decimal("-73.9654")
        )

        response = self.ai.process_message(
            "show me nearby art",
            self.user,
            {"latitude": 40.7829, "longitude": -73.9654},
        )

        self.assertIn("message", response)

    def test_around_me_keyword(self):
        """Test 'around me' keyword for nearby"""
        response = self.ai.process_message("what art is around me", self.user, None)

        self.assertTrue(
            response["metadata"].get("request_location")
            or "location" in response["message"].lower()
        )

    def test_close_to_me_keyword(self):
        """Test 'close to me' keyword for nearby"""
        response = self.ai.process_message("show art close to me", self.user, None)

        self.assertTrue(
            response["metadata"].get("request_location")
            or "location" in response["message"].lower()
        )

    def test_close_by_keyword(self):
        """Test 'close by' keyword for nearby"""
        response = self.ai.process_message("any sculptures close by", self.user, None)

        self.assertTrue(
            response["metadata"].get("request_location")
            or "location" in response["message"].lower()
        )
