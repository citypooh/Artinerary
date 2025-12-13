import google.generativeai as genai
from django.conf import settings
from loc_detail.models import PublicArt
from django.db.models import Q
import re
import pytz
import math
import logging

# Set up moderation logger
moderation_logger = logging.getLogger("chatbot.moderation")


class ContentModerator:
    """Detects and handles inappropriate content"""

    INAPPROPRIATE_PATTERNS = [
        r"\b(fuck|shit|ass|bitch|dick|cock|pussy|cunt|whore|slut)\b",
        r"\b(f+u+c+k+|s+h+i+t+|a+s+s+)\b",
        r"\b(sex|porn|nude|naked|horny|cum|orgasm)\b",
        r"\b(send\s*(me\s*)?(nudes?|pics?|photos?))\b",
        r"\b(kill\s*(your)?self|kys|die|murder)\b",
        r"\b(hate\s*you|stupid\s*(bot|ai)|dumb\s*(bot|ai))\b",
        r"(.)\1{5,}",
    ]

    SEVERITY_WARN = "warn"
    SEVERITY_REPORT = "report"

    @classmethod
    def check_content(cls, message):
        message_lower = message.lower()
        for pattern in cls.INAPPROPRIATE_PATTERNS:
            if re.search(pattern, message_lower, re.IGNORECASE):
                if any(word in pattern for word in ["kill", "die", "murder", "kys"]):
                    severity = cls.SEVERITY_REPORT
                elif any(word in pattern for word in ["sex", "porn", "nude", "horny"]):
                    severity = cls.SEVERITY_REPORT
                else:
                    severity = cls.SEVERITY_WARN
                return True, severity, pattern
        return False, None, None

    @classmethod
    def get_warning_response(cls, severity):
        if severity == cls.SEVERITY_REPORT:
            return (
                "Your message has been flagged and reported. "
                "This incident has been logged for review.\n\n"
                "I'm happy to help you with finding artworks, "
                "planning itineraries, or navigating the website."
            )
        else:
            return (
                "Please keep our conversation respectful.\n\n"
                "Let's focus on exploring NYC public art! "
                "How can I help you today?"
            )


class ArtineraryAI:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = None
        self.available_models = []

        # Auto-select the best available model
        try:
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    skip_keywords = [
                        "exp",
                        "preview",
                        "image",
                        "tts",
                        "vision",
                        "embedding",
                        "aqa",
                    ]
                    if any(skip in m.name.lower() for skip in skip_keywords):
                        continue
                    self.available_models.append(m.name.replace("models/", ""))

            priority_keywords = [
                "gemini-2.0-flash-lite",
                "gemini-2.0-flash",
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-flash",
                "gemini-pro",
            ]

            selected_model = None
            for keyword in priority_keywords:
                for model_name in self.available_models:
                    if keyword in model_name:
                        selected_model = model_name
                        break
                if selected_model:
                    break

            if not selected_model and self.available_models:
                selected_model = self.available_models[0]

            if selected_model:
                self.model = genai.GenerativeModel(selected_model)
                self.current_model_name = selected_model
                print(f"Successfully initialized Gemini model: {selected_model}")
            else:
                print("Warning: No suitable Gemini model found")
                self.current_model_name = None

        except Exception as e:
            print(f"Error initializing Gemini model: {e}")
            self.model = None
            self.current_model_name = None

        self.est_tz = pytz.timezone("America/New_York")

        self.website_pages = {
            "map": {
                "url": "/artinerary/",
                "name": "Interactive Map",
                "description": (
                    "Shows all NYC public artworks on an interactive map. "
                    "Click markers to see details, filter by borough."
                ),
            },
            "artworks": {
                "url": "/loc_detail/",
                "name": "Browse Artworks",
                "description": (
                    "Browse and search all public artworks. "
                    "Filter by artist, location, or type."
                ),
            },
            "events": {
                "url": "/events/",
                "name": "Events",
                "description": (
                    "Browse art events, join community tours, "
                    "or create your own art meetups."
                ),
            },
            "itineraries": {
                "url": "/itineraries/",
                "name": "My Itineraries",
                "description": (
                    "View and manage your saved art tour itineraries. "
                    "Create new custom routes."
                ),
            },
            "favorites": {
                "url": "/favorites/",
                "name": "My Favorites",
                "description": (
                    "View artworks you've saved to favorites. "
                    "Add artworks by clicking the heart icon."
                ),
            },
            "profile": {
                "url": "/profile/",
                "name": "My Profile",
                "description": ("View and edit your profile, update settings."),
            },
            "dashboard": {
                "url": "/dashboard/",
                "name": "Dashboard",
                "description": (
                    "Your personalized dashboard with recent activity "
                    "and recommendations."
                ),
            },
            "messages": {
                "url": "/messages/",
                "name": "Messages",
                "description": (
                    "Chat with other art enthusiasts, "
                    "share discoveries, plan meetups."
                ),
            },
        }

    def _try_generate_with_fallback(self, prompt):
        """Try to generate content, falling back to other models if rate limited"""
        tried_models = set()

        # First try with current model
        if self.model:
            try:
                tried_models.add(self.current_model_name)
                response = self.model.generate_content(prompt)
                if response and response.text:
                    return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower():
                    print(f"Rate limited on {self.current_model_name}, trying fallback")
                else:
                    print(f"Error with current model: {e}")

        # Try fallback models if rate limited
        for model_name in self.available_models:
            if model_name in tried_models:
                continue
            tried_models.add(model_name)

            try:
                print(f"Trying fallback model: {model_name}")
                fallback_model = genai.GenerativeModel(model_name)
                response = fallback_model.generate_content(prompt)
                if response and response.text:
                    self.model = fallback_model
                    self.current_model_name = model_name
                    print(f"Switched to model: {model_name}")
                    return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower():
                    print(f"Rate limited on {model_name} too, trying next")
                    continue
                else:
                    print(f"Error with {model_name}: {e}")
                    continue

        print("All models rate limited or failed")
        return None

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 3959
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_nearby_artworks(self, user_lat, user_lon, limit=5, radius_miles=2):
        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except (ValueError, TypeError) as e:
            print(f"Invalid coordinates: {e}")
            return []

        artworks = PublicArt.objects.filter(
            latitude__isnull=False, longitude__isnull=False
        )
        nearby = []

        for art in artworks:
            try:
                distance = self.calculate_distance(
                    user_lat,
                    user_lon,
                    float(art.latitude),
                    float(art.longitude),
                )
                if distance <= radius_miles:
                    nearby.append(
                        {
                            "id": art.id,
                            "title": art.title or "Untitled",
                            "artist": art.artist_name or "Unknown",
                            "location": art.location or "Location not specified",
                            "borough": art.borough or "",
                            "distance": round(distance, 2),
                            "latitude": float(art.latitude),
                            "longitude": float(art.longitude),
                        }
                    )
            except Exception:
                continue

        nearby.sort(key=lambda x: x["distance"])
        return nearby[:limit]

    def search_artworks(self, query, limit=10):
        """Search artworks by various criteria"""
        artworks = PublicArt.objects.filter(
            Q(title__icontains=query)
            | Q(artist_name__icontains=query)
            | Q(location__icontains=query)
            | Q(borough__icontains=query)
            | Q(medium__icontains=query)
        )[:limit]

        return [
            {
                "id": art.id,
                "title": art.title or "Untitled",
                "artist": art.artist_name or "Unknown",
                "location": art.location or "Location not specified",
                "borough": art.borough or "",
                "medium": art.medium or "",
            }
            for art in artworks
        ]

    def search_artworks_by_location(self, location_query, limit=6):
        """Search artworks by location/neighborhood - DYNAMIC from database"""
        artworks = PublicArt.objects.filter(
            Q(location__icontains=location_query) | Q(borough__icontains=location_query)
        ).filter(latitude__isnull=False, longitude__isnull=False)[:limit]

        return [
            {
                "id": art.id,
                "title": art.title or "Untitled",
                "artist": art.artist_name or "Unknown",
                "location": art.location or "Location not specified",
                "borough": art.borough or "",
                "latitude": float(art.latitude) if art.latitude else None,
                "longitude": float(art.longitude) if art.longitude else None,
            }
            for art in artworks
        ]

    def get_artworks_by_borough(self, borough, limit=6):
        """Get artworks from a specific borough"""
        artworks = PublicArt.objects.filter(
            borough__icontains=borough,
            latitude__isnull=False,
            longitude__isnull=False,
        )[:limit]

        return [
            {
                "id": art.id,
                "title": art.title or "Untitled",
                "artist": art.artist_name or "Unknown",
                "location": art.location or "Location not specified",
                "borough": art.borough or "",
                "latitude": float(art.latitude) if art.latitude else None,
                "longitude": float(art.longitude) if art.longitude else None,
            }
            for art in artworks
        ]

    def extract_location_from_message(self, message):
        """Extract location/place names from user message - ROBUST VERSION"""
        message_lower = message.lower()

        # Check for boroughs first
        boroughs = {
            "manhattan": "Manhattan",
            "brooklyn": "Brooklyn",
            "queens": "Queens",
            "bronx": "Bronx",
            "staten island": "Staten Island",
        }

        for key, value in boroughs.items():
            if key in message_lower:
                return {"type": "borough", "value": value}

        # Common NYC neighborhoods - quick matches
        neighborhoods = [
            "central park",
            "times square",
            "soho",
            "tribeca",
            "chelsea",
            "harlem",
            "williamsburg",
            "dumbo",
            "astoria",
            "flushing",
            "greenpoint",
            "bushwick",
            "prospect park",
            "battery park",
            "high line",
            "midtown",
            "downtown",
            "uptown",
            "east village",
            "west village",
            "lower east side",
            "upper west side",
            "upper east side",
            "columbus circle",
            "union square",
            "washington square",
            "bryant park",
            "rockefeller",
            "lincoln center",
            "wall street",
            "chinatown",
            "little italy",
            "greenwich village",
            "financial district",
            "meatpacking",
            "flatiron",
            "gramercy",
            "murray hill",
            "hell's kitchen",
            "long island city",
            "red hook",
            "park slope",
            "cobble hill",
            "fort greene",
            "bed stuy",
            "crown heights",
            "sunset park",
            "broadway",
            "5th avenue",
            "fifth avenue",
            "herald square",
            "madison square",
            "nolita",
            "noho",
        ]

        for neighborhood in neighborhoods:
            if neighborhood in message_lower:
                return {"type": "neighborhood", "value": neighborhood}

        # Pattern 1: Street names (jay st, main street, 5th ave)
        street_pattern = (
            r"\b(\w+)\s+(st|street|ave|avenue|blvd|boulevard|"
            r"rd|road|way|place|ln|lane)\b"
        )
        street_match = re.search(street_pattern, message_lower)
        if street_match:
            return {"type": "neighborhood", "value": street_match.group(0)}

        # Pattern 2: Parks, Squares, Plazas, Gardens (abingdon square park, etc)
        place_pattern = (
            r"\b([\w\s]+?)\s*(square|park|plaza|garden|gardens|circle|center)\b"
        )
        place_match = re.search(place_pattern, message_lower)
        if place_match:
            full_match = place_match.group(0).strip()
            skip_words = [
                "the",
                "a",
                "an",
                "in",
                "at",
                "on",
                "near",
                "around",
                "any",
                "show",
                "find",
                "art",
                "artworks",
                "artwork",
                "what",
                "where",
                "is",
                "are",
                "me",
                "to",
            ]
            words = full_match.split()
            cleaned_words = [w for w in words if w not in skip_words]
            if cleaned_words:
                cleaned_match = " ".join(cleaned_words)
                if len(cleaned_match) > 3:
                    return {"type": "neighborhood", "value": cleaned_match}

        # Pattern 3: Location after prepositions (near X, in X, at X)
        prep_pattern = r"\b(?:near|in|at|around|by)\s+([a-z\s]{3,30}?)(?:\?|$|,|\.|\!)"
        prep_match = re.search(prep_pattern, message_lower)
        if prep_match:
            potential_location = prep_match.group(1).strip()
            non_locations = [
                "me",
                "here",
                "this",
                "that",
                "the",
                "area",
                "my location",
                "my",
                "i",
                "we",
                "you",
                "there",
                "it",
            ]
            if potential_location not in non_locations and len(potential_location) > 2:
                test_results = PublicArt.objects.filter(
                    Q(location__icontains=potential_location)
                ).exists()
                if test_results:
                    return {"type": "neighborhood", "value": potential_location}

        # FALLBACK: Database search for multi-word phrases
        words = message_lower.split()
        for n in [3, 2]:
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i : i + n])
                skip_phrases = [
                    "show me",
                    "find me",
                    "any art",
                    "public art",
                    "what is",
                    "where is",
                    "can you",
                    "i want",
                    "artworks near",
                    "artworks in",
                    "art near",
                    "art in",
                ]
                if phrase in skip_phrases:
                    continue
                if PublicArt.objects.filter(Q(location__icontains=phrase)).exists():
                    return {"type": "neighborhood", "value": phrase}

        return None

    def get_nearby_places_info(self, location_name):
        """Get AI-generated suggestions for restaurants/bars near a location."""
        if not self.model and not self.available_models:
            return None

        prompt = f"""Suggest 2-3 popular restaurants or cafes near \
{location_name} in NYC.
Format each as: • Name (Type) - Address or cross street
Keep it brief, no extra text. Just the list.
Example format:
• Joe's Pizza (Pizzeria) - Carmine St
• Blue Ribbon (American) - Sullivan St"""

        try:
            response_text = self._try_generate_with_fallback(prompt)
            if response_text:
                return response_text.strip()
        except Exception as e:
            print(f"Error getting places info: {e}")

        return None

    def get_navigation_info(self, page_key):
        """Get navigation info for a specific page"""
        if page_key in self.website_pages:
            return self.website_pages[page_key]
        return None

    def detect_page_intent(self, message):
        """Detect which website page user is asking about"""
        message_lower = message.lower()

        page_keywords = {
            "map": ["map", "interactive map", "see map", "view map", "where is map"],
            "artworks": [
                "browse artwork",
                "see artwork",
                "view artwork",
                "all artwork",
                "browse art",
                "see art",
            ],
            "events": [
                "event",
                "events",
                "attend",
                "meetup",
                "gathering",
            ],
            "itineraries": [
                "itinerary",
                "itineraries",
                "my tour",
                "my route",
                "saved tour",
            ],
            "favorites": [
                "favorite",
                "favorites",
                "my favorite",
                "saved artwork",
                "liked",
                "my saved",
            ],
            "profile": [
                "profile",
                "my profile",
                "edit profile",
                "account",
                "my account",
            ],
            "dashboard": [
                "dashboard",
                "home page",
                "main page",
            ],
            "messages": [
                "message",
                "messages",
                "chat with user",
                "dm",
                "inbox",
            ],
        }

        for page_key, keywords in page_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return page_key
        return None

    def check_for_nearby_places_query(self, message):
        """Check if user is asking about restaurants, bars, etc."""
        message_lower = message.lower()

        place_keywords = [
            "restaurant",
            "restaurants",
            "food",
            "eat",
            "dining",
            "bar",
            "bars",
            "drink",
            "drinks",
            "pub",
            "cafe",
            "coffee",
            "entertainment",
            "nightlife",
            "club",
        ]

        has_place_keyword = any(kw in message_lower for kw in place_keywords)

        if has_place_keyword:
            location = self.extract_location_from_message(message)
            if location:
                return True, location["value"]
        return False, None

    def generate_ai_response(self, message, user, context=None):
        """Generate AI response using Gemini"""
        username = user.first_name or user.username

        system_context = f"""You are ArtBot, a friendly NYC public art guide assistant.
User's name: {username}

Key website features:
- Interactive Map: View all artworks on a map at /artinerary/
- Browse Artworks: Search and filter artworks at /loc_detail/
- Events: Art events and meetups at /events/
- Favorites: Save artworks at /favorites/
- Itineraries: Plan art tours at /itineraries/

Keep responses concise, friendly, and helpful.
Focus on NYC public art but be conversational.
Don't use markdown formatting like ** or ##."""

        if context:
            system_context += f"\nContext: {context}"

        prompt = f"{system_context}\n\nUser: {message}\nArtBot:"

        try:
            response_text = self._try_generate_with_fallback(prompt)
            if response_text:
                cleaned = response_text.strip()
                cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
                cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
                cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r"^\*\s+", "• ", cleaned, flags=re.MULTILINE)
                cleaned = re.sub(r"^-\s+", "• ", cleaned, flags=re.MULTILINE)
                return cleaned
        except Exception as e:
            print(f"Error generating AI response: {e}")

        return self._get_smart_fallback(message)

    def _get_smart_fallback(self, message):
        """Provide contextual fallback responses"""
        message_lower = message.lower()

        if any(w in message_lower for w in ["map", "where", "location", "find"]):
            return (
                "You can explore all NYC public artworks on our Interactive Map! "
                "It shows artwork locations across all five boroughs. "
                "Would you like me to take you there?"
            )

        if any(w in message_lower for w in ["event", "attend", "join"]):
            return (
                "You can browse art events, join community tours, "
                "or create your own meetups on the Events page. "
                "It's a great way to explore art with others! "
                "Want me to show you the events?"
            )

        if any(w in message_lower for w in ["favorite", "saved", "liked"]):
            return (
                "Your favorites are artworks you've saved by clicking "
                "the heart icon. You can view all your saved artworks "
                "in My Favorites. Would you like to see them?"
            )

        if any(w in message_lower for w in ["profile", "account"]):
            return (
                "In your profile, you can update your info, "
                "change your picture, and add a bio. "
                "Would you like to edit your profile?"
            )

        if any(w in message_lower for w in ["itinerary", "tour", "route", "plan"]):
            return (
                "You can create custom art tour itineraries! "
                "Add artworks, arrange your stops, and save routes. "
                "Tell me an area and I can suggest artworks to include."
            )

        if any(w in message_lower for w in ["dashboard", "home"]):
            return (
                "Your dashboard shows your activity, recent itineraries, "
                "and personalized recommendations. "
                "Would you like to go to your dashboard?"
            )

        if any(w in message_lower for w in ["message", "chat", "inbox"]):
            return (
                "You can message other art enthusiasts, "
                "discuss artworks, and plan meetups together. "
                "Would you like to see your messages?"
            )

        if any(
            w in message_lower
            for w in ["visit", "places", "where", "what can i", "suggestions"]
        ):
            return (
                "I can help you discover NYC public art! "
                "Try asking about a specific area like 'Show me art in "
                "Central Park' or 'What's in Brooklyn?' "
                "You can also explore our interactive map."
            )

        if any(w in message_lower for w in ["help", "what can you"]):
            return (
                "I'm here to help you explore NYC public art! "
                "You can ask me about artworks in specific areas, "
                "website features like the map or events, "
                "or how to plan an art tour. What interests you?"
            )

        return (
            "I'm here to help you explore NYC public art! "
            "You can ask me about artworks in specific areas, "
            "website features like the map or events, "
            "or how to plan an art tour. What interests you?"
        )

    def process_message(self, message, user, user_location=None):
        """Main message processing function"""
        message_lower = message.lower()
        response_data = {"message": "", "metadata": {}}

        print(f"Processing message: {message}")
        print(f"User location received: {user_location}")

        # STEP 1: Check for inappropriate content
        is_inappropriate, severity, pattern = ContentModerator.check_content(message)
        if is_inappropriate:
            moderation_logger.warning(
                f"Inappropriate content detected - User: {user.username}, "
                f"Severity: {severity}, Message: {message[:100]}"
            )
            response_data["message"] = ContentModerator.get_warning_response(severity)
            response_data["metadata"]["content_warning"] = True
            response_data["metadata"]["severity"] = severity
            return response_data

        # STEP 2: Check for nearby request with user's location
        nearby_keywords = [
            "nearby",
            "near me",
            "around me",
            "close by",
            "close to me",
            "closest",
            "nearest",
        ]
        is_nearby_request = any(kw in message_lower for kw in nearby_keywords)

        if is_nearby_request:
            lat = None
            lng = None
            if user_location:
                lat = user_location.get("lat") or user_location.get("latitude")
                lng = user_location.get("lng") or user_location.get("longitude")

            if lat and lng:
                nearby_artworks = self.get_nearby_artworks(lat, lng)
                if nearby_artworks:
                    response_data["message"] = (
                        f"Found {len(nearby_artworks)} artworks near you!"
                    )
                    response_data["metadata"]["artworks"] = nearby_artworks
                    response_data["metadata"]["show_map"] = True
                    response_data["metadata"]["show_itinerary_prompt"] = True
                    response_data["metadata"]["suggested_locations"] = [
                        art["id"] for art in nearby_artworks
                    ]
                else:
                    response_data["message"] = (
                        "No artworks found within 2 miles of your location. "
                        "Try exploring the map or searching for a nearby area!"
                    )
                    response_data["metadata"]["navigation"] = self.get_navigation_info(
                        "map"
                    )
            else:
                response_data["message"] = (
                    "I'd love to show you nearby artworks! "
                    "Please enable location sharing or tell me what "
                    "area you'd like to explore."
                )
                response_data["metadata"]["request_location"] = True
            return response_data

        # STEP 3: Check for restaurant/bar/places queries
        is_places_query, place_location = self.check_for_nearby_places_query(message)
        if is_places_query and place_location:
            location_info = self.extract_location_from_message(message)
            if location_info:
                if location_info["type"] == "borough":
                    artworks = self.get_artworks_by_borough(location_info["value"])
                else:
                    artworks = self.search_artworks_by_location(place_location)

                places_info = self.get_nearby_places_info(place_location)

                if artworks:
                    if places_info:
                        msg = (
                            f"Great choice! Here are artworks and dining spots "
                            f"near {place_location.title()}:\n\n"
                            f"Nearby places:\n{places_info}\n\n"
                            "I also found some artworks in this area!"
                        )
                    else:
                        msg = f"Here are artworks near {place_location.title()}!"

                    response_data["message"] = msg
                    response_data["metadata"]["artworks"] = artworks
                    response_data["metadata"]["show_itinerary_prompt"] = True
                    response_data["metadata"]["suggested_locations"] = [
                        art["id"] for art in artworks
                    ]
                else:
                    if places_info:
                        response_data["message"] = (
                            f"Here are some spots near "
                            f"{place_location.title()}:\n\n"
                            f"{places_info}\n\n"
                            "I can also help you find art in this area!"
                        )
                    else:
                        response_data["message"] = self.generate_ai_response(
                            message, user, "places"
                        )
                return response_data

        # STEP 4: Check for specific location/neighborhood queries
        location_info = self.extract_location_from_message(message)
        if location_info:
            if location_info["type"] == "borough":
                artworks = self.get_artworks_by_borough(location_info["value"])
            else:
                artworks = self.search_artworks_by_location(location_info["value"])

            if artworks:
                places_info = self.get_nearby_places_info(location_info["value"])
                msg = (
                    f"Here are public artworks in " f"{location_info['value'].title()}!"
                )
                if places_info:
                    msg += f"\n\nNearby spots:\n{places_info}"
                msg += "\n\nWould you like to create an itinerary?"

                response_data["message"] = msg
                response_data["metadata"]["artworks"] = artworks
                response_data["metadata"]["show_itinerary_prompt"] = True
                response_data["metadata"]["suggested_locations"] = [
                    art["id"] for art in artworks
                ]
            else:
                response_data["message"] = (
                    f"I couldn't find artworks specifically in "
                    f"{location_info['value'].title()} in our database. "
                    f"Try browsing the map or searching for a nearby area!"
                )
                response_data["metadata"]["navigation"] = self.get_navigation_info(
                    "map"
                )
            return response_data

        # STEP 5: Check for website page queries
        page_intent = self.detect_page_intent(message)
        if page_intent:
            page_info = self.get_navigation_info(page_intent)
            if page_info:
                ai_response = self.generate_ai_response(
                    message, user, f"page_{page_intent}"
                )
                response_data["message"] = ai_response
                response_data["metadata"]["navigation"] = page_info
                return response_data

        # STEP 6: Check for explicit navigation requests
        if any(
            word in message_lower
            for word in ["go to", "take me", "open", "navigate to", "show me the"]
        ):
            for page_key, page_info in self.website_pages.items():
                if page_key in message_lower or page_info["name"].lower() in (
                    message_lower
                ):
                    response_data["message"] = (
                        f"Taking you to {page_info['name']}! "
                        f"{page_info['description']}"
                    )
                    response_data["metadata"]["navigation"] = page_info
                    return response_data

        # STEP 7: Check for artwork search queries
        search_indicators = [
            "find artwork",
            "search for",
            "look for",
            "show me artwork",
            "any artwork",
        ]
        if any(indicator in message_lower for indicator in search_indicators):
            search_terms = message_lower
            for indicator in search_indicators:
                search_terms = search_terms.replace(indicator, "")
            search_terms = search_terms.strip()

            if search_terms:
                results = self.search_artworks(search_terms)
                if results:
                    response_data["message"] = (
                        f"Found {len(results)} artworks for '{search_terms}'!"
                    )
                    response_data["metadata"]["artworks"] = results
                    response_data["metadata"]["show_itinerary_prompt"] = True
                    response_data["metadata"]["suggested_locations"] = [
                        art["id"] for art in results
                    ]
                    return response_data

        # STEP 8: Handle simple greetings specially
        if message_lower.strip() in [
            "hi",
            "hello",
            "hey",
            "hi!",
            "hello!",
            "hey!",
        ]:
            response_data["message"] = (
                f"Hello {user.first_name or user.username}! "
                "I'm ArtBot, your NYC public art guide.\n\n"
                "I can help you find artworks, explore the map, "
                "browse events, or plan an art tour. "
                "What would you like to do?"
            )
            return response_data

        # STEP 9: Handle thanks
        if any(
            word in message_lower for word in ["thank", "thanks", "thx", "appreciate"]
        ):
            response_data["message"] = (
                "You're welcome! Happy to help you explore NYC's "
                "amazing public art. Let me know if you need anything else!"
            )
            return response_data

        # STEP 10: For ALL other queries - use AI to generate response
        response_data["message"] = self.generate_ai_response(message, user)

        print(f"Response: {response_data['message'][:100]}...")
        return response_data
