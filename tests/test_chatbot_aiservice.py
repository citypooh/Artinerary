"""
Tests for Chatbot AI Service
Comprehensive tests for ArtineraryAI functionality
"""

from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
import pytest
from unittest.mock import patch, MagicMock

from chatbot.ai_service import ArtineraryAI, ContentModerator
from loc_detail.models import PublicArt


@pytest.fixture(autouse=True)
def fast_chatbot_mocks():
    """
    Autouse fixture to speed up chatbot-related tests by mocking slow/external ops:
    - mocks requests.get to return a simple empty response
    - no-ops time.sleep
    Adjust or narrow the patch targets if some tests depend on real external responses.
    """
    # Patch requests.get used by ai_service / other modules
    requests_get_patcher = patch("requests.get")
    mock_get = requests_get_patcher.start()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "{}"
    mock_resp.json.return_value = {}
    mock_get.return_value = mock_resp

    # No-op time.sleep to eliminate artificial delays
    sleep_patcher = patch("time.sleep", lambda *a, **k: None)
    sleep_patcher.start()

    yield

    # stop patchers
    requests_get_patcher.stop()
    sleep_patcher.stop()


class ContentModeratorTests(TestCase):
    """Tests for ContentModerator class"""

    def test_check_clean_content(self):
        """Test that clean content passes moderation"""
        is_inappropriate, severity, pattern = ContentModerator.check_content(
            "Show me art in Central Park"
        )
        self.assertFalse(is_inappropriate)
        self.assertIsNone(severity)
        self.assertIsNone(pattern)

    def test_check_inappropriate_content(self):
        """Test that inappropriate content is flagged"""
        is_inappropriate, severity, pattern = ContentModerator.check_content(
            "you stupid bot"
        )
        self.assertTrue(is_inappropriate)
        self.assertEqual(severity, ContentModerator.SEVERITY_WARN)

    def test_check_severe_content(self):
        """Test that severe content is properly flagged"""
        is_inappropriate, severity, pattern = ContentModerator.check_content(
            "go kill yourself"
        )
        self.assertTrue(is_inappropriate)
        self.assertEqual(severity, ContentModerator.SEVERITY_REPORT)

    def test_warning_response_warn(self):
        """Test warning response for warn severity"""
        response = ContentModerator.get_warning_response(ContentModerator.SEVERITY_WARN)
        self.assertIn("respectful", response.lower())

    def test_warning_response_report(self):
        """Test warning response for report severity"""
        response = ContentModerator.get_warning_response(
            ContentModerator.SEVERITY_REPORT
        )
        self.assertIn("flagged", response.lower())


class ArtineraryAIInitializationTests(TestCase):
    """Tests for ArtineraryAI initialization"""

    def test_ai_initialization(self):
        """Test that AI initializes without errors"""
        ai = ArtineraryAI()
        self.assertIsNotNone(ai)
        self.assertIsNotNone(ai.website_pages)
        self.assertIn("map", ai.website_pages)

    def test_website_pages_structure(self):
        """Test website pages have correct structure"""
        ai = ArtineraryAI()
        for page_key, page_info in ai.website_pages.items():
            self.assertIn("url", page_info)
            self.assertIn("name", page_info)
            self.assertIn("description", page_info)


class ArtineraryAILocationExtractionTests(TestCase):
    """Tests for location extraction functionality"""

    def setUp(self):
        self.ai = ArtineraryAI()

    def test_extract_borough_manhattan(self):
        """Test extracting Manhattan borough"""
        result = self.ai.extract_location_from_message("show me art in Manhattan")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "borough")
        # Use lower() for case-insensitive comparison
        self.assertEqual(result["value"].lower(), "manhattan")

    def test_extract_borough_brooklyn(self):
        """Test extracting Brooklyn borough"""
        result = self.ai.extract_location_from_message("what's in Brooklyn?")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "borough")
        self.assertEqual(result["value"].lower(), "brooklyn")

    def test_extract_neighborhood_central_park(self):
        """Test extracting Central Park neighborhood"""
        result = self.ai.extract_location_from_message("art near central park")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "neighborhood")
        self.assertEqual(result["value"].lower(), "central park")

    def test_extract_neighborhood_times_square(self):
        """Test extracting Times Square neighborhood"""
        result = self.ai.extract_location_from_message("show times square art")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "neighborhood")
        self.assertEqual(result["value"].lower(), "times square")

    def test_extract_no_location(self):
        """Test when no location is present"""
        result = self.ai.extract_location_from_message("hello there")
        self.assertIsNone(result)

    def test_extract_street_pattern(self):
        """Test extracting street pattern"""
        result = self.ai.extract_location_from_message("show me art on jay st")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "neighborhood")


class ArtineraryAINearbyArtworksTests(TestCase):
    """Tests for nearby artworks functionality"""

    def setUp(self):
        self.ai = ArtineraryAI()
        self.artwork = PublicArt.objects.create(
            title="Test Artwork",
            artist_name="Test Artist",
            location="Test Location",
            borough="Manhattan",
            latitude=Decimal("40.7829"),
            longitude=Decimal("-73.9654"),
        )

    def test_get_nearby_artworks(self):
        """Test getting nearby artworks"""
        nearby = self.ai.get_nearby_artworks(40.7829, -73.9654)
        self.assertGreater(len(nearby), 0)

    def test_get_nearby_artworks_empty(self):
        """Test nearby artworks when none in range"""
        nearby = self.ai.get_nearby_artworks(0, 0)
        self.assertEqual(len(nearby), 0)

    def test_get_nearby_artworks_invalid_coords(self):
        """Test nearby artworks with invalid coordinates"""
        nearby = self.ai.get_nearby_artworks("invalid", "coords")
        self.assertEqual(len(nearby), 0)

    def test_calculate_distance(self):
        """Test distance calculation"""
        distance = self.ai.calculate_distance(40.7829, -73.9654, 40.7831, -73.9656)
        self.assertIsInstance(distance, float)
        self.assertLess(distance, 1)


class ArtineraryAIPageIntentTests(TestCase):
    """Tests for page intent detection"""

    def setUp(self):
        self.ai = ArtineraryAI()

    def test_detect_map_intent(self):
        """Test detecting map page intent"""
        result = self.ai.detect_page_intent("where is the map?")
        self.assertEqual(result, "map")

    def test_detect_events_intent(self):
        """Test detecting events page intent"""
        result = self.ai.detect_page_intent("show me the events")
        self.assertEqual(result, "events")

    def test_detect_favorites_intent(self):
        """Test detecting favorites page intent"""
        result = self.ai.detect_page_intent("where are my favorites?")
        self.assertEqual(result, "favorites")

    def test_detect_profile_intent(self):
        """Test detecting profile page intent"""
        result = self.ai.detect_page_intent("how do I edit my profile?")
        self.assertEqual(result, "profile")

    def test_detect_itineraries_intent(self):
        """Test detecting itineraries page intent"""
        result = self.ai.detect_page_intent("show me my itineraries")
        self.assertEqual(result, "itineraries")

    def test_detect_dashboard_intent(self):
        """Test detecting dashboard page intent"""
        result = self.ai.detect_page_intent("take me to dashboard")
        self.assertEqual(result, "dashboard")

    def test_detect_no_intent(self):
        """Test when no page intent is detected"""
        result = self.ai.detect_page_intent("what is the weather today?")
        self.assertIsNone(result)


class ArtineraryAINearbyPlacesTests(TestCase):
    """Tests for nearby places functionality"""

    def setUp(self):
        self.ai = ArtineraryAI()

    def test_check_restaurant_query_with_location(self):
        """Test detecting restaurant query with location"""
        is_places, location = self.ai.check_for_nearby_places_query(
            "what restaurants are near central park?"
        )
        self.assertTrue(is_places)
        self.assertEqual(location, "central park")

    def test_check_bar_query_with_location(self):
        """Test detecting bar query with location"""
        is_places, location = self.ai.check_for_nearby_places_query(
            "any bars in times square?"
        )
        self.assertTrue(is_places)
        self.assertEqual(location, "times square")

    def test_check_places_query_no_location(self):
        """Test places query without location"""
        is_places, location = self.ai.check_for_nearby_places_query("where can I eat?")
        self.assertFalse(is_places)
        self.assertIsNone(location)

    def test_get_nearby_places_info_returns_string_or_none(self):
        """Test getting nearby places returns string or None"""
        places = self.ai.get_nearby_places_info("central park")
        self.assertTrue(places is None or isinstance(places, str))

    def test_get_nearby_places_info_any_location(self):
        """Test getting nearby places for any location"""
        places = self.ai.get_nearby_places_info("soho")
        self.assertTrue(places is None or isinstance(places, str))


class ArtineraryAINavigationTests(TestCase):
    """Tests for navigation functionality"""

    def setUp(self):
        self.ai = ArtineraryAI()

    def test_get_navigation_info_map(self):
        """Test getting navigation info for map"""
        nav = self.ai.get_navigation_info("map")
        self.assertIsNotNone(nav)
        self.assertEqual(nav["url"], "/artinerary/")
        self.assertEqual(nav["name"], "Interactive Map")

    def test_get_navigation_info_events(self):
        """Test getting navigation info for events"""
        nav = self.ai.get_navigation_info("events")
        self.assertIsNotNone(nav)
        self.assertEqual(nav["url"], "/events/")

    def test_get_navigation_info_favorites(self):
        """Test getting navigation info for favorites"""
        nav = self.ai.get_navigation_info("favorites")
        self.assertIsNotNone(nav)
        self.assertEqual(nav["url"], "/favorites/")

    def test_get_navigation_info_invalid(self):
        """Test getting navigation info for invalid key"""
        nav = self.ai.get_navigation_info("invalid_page")
        self.assertIsNone(nav)


class ArtineraryAIProcessMessageTests(TestCase):
    """Tests for main process_message functionality"""

    def setUp(self):
        self.ai = ArtineraryAI()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        PublicArt.objects.create(
            title="Central Park Statue",
            artist_name="Artist One",
            location="Central Park",
            borough="Manhattan",
            latitude=Decimal("40.7829"),
            longitude=Decimal("-73.9654"),
        )

    def test_process_inappropriate_message(self):
        """Test processing inappropriate message"""
        response = self.ai.process_message("you stupid bot", self.user, None)
        self.assertTrue(response["metadata"].get("content_warning"))
        self.assertIn("respectful", response["message"].lower())

    def test_process_greeting(self):
        """Test processing greeting"""
        response = self.ai.process_message("hi", self.user, None)
        self.assertIn("message", response)
        # Check it's a greeting response
        self.assertTrue(
            "ArtBot" in response["message"]
            or "help" in response["message"].lower()
            or "art" in response["message"].lower()
        )

    def test_process_thanks(self):
        """Test processing thanks message"""
        response = self.ai.process_message("thanks", self.user, None)
        self.assertIn("message", response)

    def test_process_location_query(self):
        """Test processing location-based query"""
        response = self.ai.process_message(
            "show me art in central park", self.user, None
        )
        self.assertIn("message", response)

    def test_process_nearby_without_location(self):
        """Test processing nearby request without location"""
        response = self.ai.process_message("show me nearby artworks", self.user, None)
        self.assertTrue(
            response["metadata"].get("request_location")
            or "location" in response["message"].lower()
        )

    def test_process_nearby_with_location(self):
        """Test processing nearby request with location"""
        response = self.ai.process_message(
            "show me nearby artworks", self.user, {"lat": 40.7829, "lng": -73.9654}
        )
        self.assertIn("message", response)

    def test_process_page_query(self):
        """Test processing page-related query"""
        response = self.ai.process_message("where is the map?", self.user, None)
        self.assertIn("message", response)

    def test_process_navigation_request(self):
        """Test processing explicit navigation request"""
        response = self.ai.process_message("take me to events", self.user, None)
        self.assertIn("message", response)

    def test_process_general_query(self):
        """Test processing general query goes to AI"""
        response = self.ai.process_message(
            "what can I do on this website?", self.user, None
        )
        self.assertIn("message", response)
        self.assertGreater(len(response["message"]), 10)


class ArtineraryAIFallbackResponseTests(TestCase):
    """Tests for fallback response functionality"""

    def setUp(self):
        self.ai = ArtineraryAI()

    def test_fallback_map_query(self):
        """Test fallback for map query"""
        response = self.ai._get_smart_fallback("where is the map")
        self.assertIn("map", response.lower())

    def test_fallback_events_query(self):
        """Test fallback for events query"""
        response = self.ai._get_smart_fallback("any events to attend")
        self.assertIn("event", response.lower())

    def test_fallback_favorites_query(self):
        """Test fallback for favorites query"""
        response = self.ai._get_smart_fallback("show my favorites")
        self.assertIn("favorite", response.lower())

    def test_fallback_generic_query(self):
        """Test fallback for generic query"""
        response = self.ai._get_smart_fallback("random question")
        self.assertIn("art", response.lower())


class ArtineraryAISearchByLocationTests(TestCase):
    """Tests for location-based artwork search"""

    def setUp(self):
        self.ai = ArtineraryAI()
        PublicArt.objects.create(
            title="Central Park Art",
            location="Central Park",
            borough="Manhattan",
            latitude=Decimal("40.7829"),
            longitude=Decimal("-73.9654"),
        )
        PublicArt.objects.create(
            title="Brooklyn Art",
            location="Williamsburg",
            borough="Brooklyn",
            latitude=Decimal("40.7081"),
            longitude=Decimal("-73.9571"),
        )

    def test_search_by_location_neighborhood(self):
        """Test searching by neighborhood"""
        results = self.ai.search_artworks_by_location("Central Park")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["title"], "Central Park Art")

    def test_search_by_borough(self):
        """Test getting artworks by borough"""
        results = self.ai.get_artworks_by_borough("Brooklyn")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["borough"], "Brooklyn")

    def test_search_by_location_limit(self):
        """Test that location search respects limit"""
        for i in range(10):
            PublicArt.objects.create(
                title=f"Manhattan Art {i}",
                location="Manhattan",
                borough="Manhattan",
                latitude=Decimal("40.7829"),
                longitude=Decimal("-73.9654"),
            )

        results = self.ai.search_artworks_by_location("Manhattan", limit=3)
        self.assertLessEqual(len(results), 3)
