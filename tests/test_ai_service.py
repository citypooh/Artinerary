"""
Comprehensive test suite for Chatbot app - Part 3
Tests for ai_service.py (ContentModerator, ArtineraryAI)
"""

from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal

from chatbot.ai_service import ContentModerator, ArtineraryAI
from loc_detail.models import PublicArt


class ContentModeratorTests(TestCase):
    """Tests for ContentModerator class"""

    def test_clean_message_not_flagged(self):
        """Test that clean messages are not flagged"""
        clean_messages = [
            "Hello, how are you?",
            "Show me art in Central Park",
            "What artworks are nearby?",
            "I love NYC public art!",
            "Can you help me plan an itinerary?",
        ]
        for message in clean_messages:
            is_inappropriate, severity, pattern = ContentModerator.check_content(
                message
            )
            self.assertFalse(is_inappropriate, f"Clean message flagged: {message}")

    def test_vulgar_content_flagged_warn(self):
        """Test that vulgar content is flagged with warn severity"""
        is_inappropriate, severity, pattern = ContentModerator.check_content(
            "This is stupid bot"
        )
        self.assertTrue(is_inappropriate)
        self.assertEqual(severity, ContentModerator.SEVERITY_WARN)

    def test_sexual_content_flagged_report(self):
        """Test that sexual content is flagged with report severity"""
        is_inappropriate, severity, pattern = ContentModerator.check_content(
            "Show me nude artworks"
        )
        self.assertTrue(is_inappropriate)
        self.assertEqual(severity, ContentModerator.SEVERITY_REPORT)

    def test_harassment_content_flagged_report(self):
        """Test that harassment content is flagged with report severity"""
        is_inappropriate, severity, pattern = ContentModerator.check_content("go die")
        self.assertTrue(is_inappropriate)
        self.assertEqual(severity, ContentModerator.SEVERITY_REPORT)

    def test_spam_pattern_flagged(self):
        """Test that spam patterns (repeated chars) are flagged"""
        is_inappropriate, severity, pattern = ContentModerator.check_content(
            "hellooooooo"
        )
        self.assertTrue(is_inappropriate)
        self.assertEqual(severity, ContentModerator.SEVERITY_WARN)

    def test_case_insensitive(self):
        """Test that moderation is case insensitive"""
        is_inappropriate1, _, _ = ContentModerator.check_content("HATE YOU")
        is_inappropriate2, _, _ = ContentModerator.check_content("Hate You")
        is_inappropriate3, _, _ = ContentModerator.check_content("hate you")
        self.assertTrue(is_inappropriate1)
        self.assertTrue(is_inappropriate2)
        self.assertTrue(is_inappropriate3)

    def test_warning_response_warn(self):
        """Test warning response for warn severity"""
        response = ContentModerator.get_warning_response(ContentModerator.SEVERITY_WARN)
        self.assertIn("respectful", response.lower())
        self.assertIn("art", response.lower())

    def test_warning_response_report(self):
        """Test warning response for report severity"""
        response = ContentModerator.get_warning_response(
            ContentModerator.SEVERITY_REPORT
        )
        self.assertIn("flagged", response.lower())
        self.assertIn("reported", response.lower())

    def test_repeated_letters_detection(self):
        """Test detection of repeated letters (spam)"""
        spam_messages = [
            "aaaaaaa",
            "hellllllllo",
            "yessssssss",
        ]
        for message in spam_messages:
            is_inappropriate, severity, _ = ContentModerator.check_content(message)
            self.assertTrue(is_inappropriate, f"Spam not detected: {message}")

    def test_embedded_inappropriate_content(self):
        """Test detection of inappropriate content within sentences"""
        is_inappropriate, _, _ = ContentModerator.check_content(
            "I think this is a stupid bot and doesn't work"
        )
        self.assertTrue(is_inappropriate)


class ArtineraryAIDistanceCalculationTests(TestCase):
    """Tests for distance calculation in ArtineraryAI"""

    def setUp(self):
        self.ai = ArtineraryAI()

    def test_distance_same_location(self):
        """Test distance between same coordinates is 0"""
        distance = self.ai.calculate_distance(40.7128, -74.0060, 40.7128, -74.0060)
        self.assertEqual(distance, 0)

    def test_distance_known_locations(self):
        """Test distance between known NYC locations"""
        # Times Square to Central Park (roughly 0.5 miles)
        distance = self.ai.calculate_distance(
            40.7580, -73.9855, 40.7829, -73.9654  # Times Square  # Central Park
        )
        self.assertGreater(distance, 0)
        self.assertLess(distance, 5)  # Should be less than 5 miles

    def test_distance_symmetry(self):
        """Test that distance is symmetric (A to B = B to A)"""
        distance1 = self.ai.calculate_distance(40.7128, -74.0060, 40.7580, -73.9855)
        distance2 = self.ai.calculate_distance(40.7580, -73.9855, 40.7128, -74.0060)
        self.assertAlmostEqual(distance1, distance2, places=10)


class ArtineraryAINearbyArtworksTests(TestCase):
    """Tests for nearby artworks functionality"""

    def setUp(self):
        self.ai = ArtineraryAI()
        # Create test artworks
        self.art1 = PublicArt.objects.create(
            title="Central Park Statue",
            artist_name="Artist One",
            location="Central Park",
            borough="Manhattan",
            latitude=Decimal("40.7829"),
            longitude=Decimal("-73.9654"),
        )
        self.art2 = PublicArt.objects.create(
            title="Times Square Art",
            artist_name="Artist Two",
            location="Times Square",
            borough="Manhattan",
            latitude=Decimal("40.7580"),
            longitude=Decimal("-73.9855"),
        )
        self.art3 = PublicArt.objects.create(
            title="Brooklyn Bridge Art",
            artist_name="Artist Three",
            location="Brooklyn Bridge",
            borough="Brooklyn",
            latitude=Decimal("40.7061"),
            longitude=Decimal("-73.9969"),
        )

    def test_get_nearby_artworks_valid_location(self):
        """Test getting nearby artworks with valid location"""
        # Near Times Square
        nearby = self.ai.get_nearby_artworks(40.7580, -73.9855, limit=5, radius_miles=2)
        self.assertIsInstance(nearby, list)
        # Should find at least Times Square Art (at exact location)
        self.assertGreater(len(nearby), 0)

    def test_get_nearby_artworks_invalid_coordinates(self):
        """Test getting nearby artworks with invalid coordinates"""
        nearby = self.ai.get_nearby_artworks("invalid", "coords")
        self.assertEqual(nearby, [])

    def test_get_nearby_artworks_none_coordinates(self):
        """Test getting nearby artworks with None coordinates"""
        nearby = self.ai.get_nearby_artworks(None, None)
        self.assertEqual(nearby, [])

    def test_get_nearby_artworks_sorted_by_distance(self):
        """Test that nearby artworks are sorted by distance"""
        nearby = self.ai.get_nearby_artworks(
            40.7580, -73.9855, limit=10, radius_miles=10
        )
        if len(nearby) > 1:
            distances = [art["distance"] for art in nearby]
            self.assertEqual(distances, sorted(distances))

    def test_get_nearby_artworks_respects_limit(self):
        """Test that nearby artworks respects limit parameter"""
        # Create more artworks
        for i in range(10):
            PublicArt.objects.create(
                title=f"Test Art {i}",
                latitude=Decimal("40.7580") + Decimal(str(i * 0.001)),
                longitude=Decimal("-73.9855"),
            )

        nearby = self.ai.get_nearby_artworks(
            40.7580, -73.9855, limit=3, radius_miles=10
        )
        self.assertLessEqual(len(nearby), 3)

    def test_get_nearby_artworks_respects_radius(self):
        """Test that nearby artworks respects radius parameter"""
        # Get artworks within very small radius
        nearby = self.ai.get_nearby_artworks(
            40.7580, -73.9855, limit=10, radius_miles=0.001  # Very small radius
        )
        for art in nearby:
            self.assertLess(art["distance"], 0.001)


class ArtineraryAISearchArtworksTests(TestCase):
    """Tests for artwork search functionality"""

    def setUp(self):
        self.ai = ArtineraryAI()
        self.art1 = PublicArt.objects.create(
            title="Liberty Statue",
            artist_name="Bartholdi",
            location="Liberty Island",
            borough="Manhattan",
            medium="Bronze",
        )
        self.art2 = PublicArt.objects.create(
            title="Brooklyn Mural",
            artist_name="Local Artist",
            location="Williamsburg",
            borough="Brooklyn",
            medium="Paint",
        )

    def test_search_by_title(self):
        """Test searching artworks by title"""
        results = self.ai.search_artworks("Liberty")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Liberty Statue")

    def test_search_by_artist(self):
        """Test searching artworks by artist name"""
        results = self.ai.search_artworks("Bartholdi")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["artist"], "Bartholdi")

    def test_search_by_borough(self):
        """Test searching artworks by borough"""
        results = self.ai.search_artworks("Brooklyn")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["borough"], "Brooklyn")

    def test_search_by_medium(self):
        """Test searching artworks by medium"""
        results = self.ai.search_artworks("Bronze")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Liberty Statue")

    def test_search_case_insensitive(self):
        """Test that search is case insensitive"""
        results1 = self.ai.search_artworks("liberty")
        results2 = self.ai.search_artworks("LIBERTY")
        results3 = self.ai.search_artworks("Liberty")
        self.assertEqual(len(results1), len(results2))
        self.assertEqual(len(results2), len(results3))

    def test_search_no_results(self):
        """Test search with no results"""
        results = self.ai.search_artworks("nonexistent artwork xyz")
        self.assertEqual(results, [])


class ArtineraryAILocationExtractionTests(TestCase):
    """Tests for location extraction from messages"""

    def setUp(self):
        self.ai = ArtineraryAI()

    def test_extract_borough_manhattan(self):
        """Test extracting Manhattan borough"""
        result = self.ai.extract_location_from_message("Show me art in Manhattan")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "borough")
        self.assertEqual(result["value"], "Manhattan")

    def test_extract_borough_brooklyn(self):
        """Test extracting Brooklyn borough"""
        result = self.ai.extract_location_from_message("What's in Brooklyn?")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "borough")
        self.assertEqual(result["value"], "Brooklyn")

    def test_extract_neighborhood_central_park(self):
        """Test extracting Central Park neighborhood"""
        result = self.ai.extract_location_from_message(
            "Show me artworks near central park"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "neighborhood")
        self.assertEqual(result["value"], "central park")

    def test_extract_neighborhood_times_square(self):
        """Test extracting Times Square neighborhood"""
        result = self.ai.extract_location_from_message("What art is in Times Square?")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "neighborhood")
        self.assertEqual(result["value"], "times square")

    def test_extract_no_location(self):
        """Test extraction with no location mentioned"""
        result = self.ai.extract_location_from_message("Hello, how are you?")
        self.assertIsNone(result)

    def test_extract_location_case_insensitive(self):
        """Test that extraction is case insensitive"""
        result = self.ai.extract_location_from_message("Show me MANHATTAN art")
        self.assertIsNotNone(result)
        self.assertEqual(result["value"], "Manhattan")


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
        result = self.ai.detect_page_intent("are there any events I can attend?")
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

    def test_get_nearby_places_info_known_area(self):
        """Test getting nearby places for known area"""
        places = self.ai.get_nearby_places_info("central park")
        self.assertIsNotNone(places)
        self.assertIn("•", places)

    def test_get_nearby_places_info_unknown_area(self):
        """Test getting nearby places for unknown area"""
        places = self.ai.get_nearby_places_info("unknown random area xyz")
        self.assertIsNone(places)


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
        # Create some test artworks
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
        self.assertIn("ArtBot", response["message"])
        self.assertIn(self.user.username, response["message"])

    def test_process_thanks(self):
        """Test processing thanks message"""
        response = self.ai.process_message("thanks", self.user, None)
        self.assertIn("welcome", response["message"].lower())

    def test_process_location_query(self):
        """Test processing location-based query"""
        response = self.ai.process_message(
            "show me art in central park", self.user, None
        )
        # Should either find artworks or provide helpful response
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
        # Should provide info about map and navigation
        self.assertIn("message", response)

    def test_process_navigation_request(self):
        """Test processing explicit navigation request"""
        response = self.ai.process_message("take me to events", self.user, None)
        if response["metadata"].get("navigation"):
            self.assertIn("url", response["metadata"]["navigation"])

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
        # Create more artworks
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
