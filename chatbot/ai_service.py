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
        model_names = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]

        for model_name in model_names:
            try:
                self.model = genai.GenerativeModel(model_name)
                print(f"Successfully initialized Gemini model: {model_name}")
                break
            except Exception as e:
                print(f"Failed to initialize {model_name}: {e}")
                continue

        if self.model is None:
            print("Warning: Could not initialize any Gemini model")

        self.est_tz = pytz.timezone("America/New_York")

        # Website pages info for AI context
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
                "url": "/user_profile/edit/",
                "name": "My Profile",
                "description": ("Edit your profile info, change picture, update bio."),
            },
            "dashboard": {
                "url": "/dashboard/",
                "name": "Dashboard",
                "description": (
                    "Your home page with activity feed, "
                    "recent itineraries, and recommendations."
                ),
            },
            "chat": {
                "url": "/chat/",
                "name": "Messages",
                "description": ("Chat with other users, discuss art, plan meetups."),
            },
        }

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
        """Search artworks by location/neighborhood"""
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
        """Extract location/place names from user message"""
        message_lower = message.lower()

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
            "tribeca",
            "nolita",
            "noho",
        ]

        for neighborhood in neighborhoods:
            if neighborhood in message_lower:
                return {"type": "neighborhood", "value": neighborhood}

        return None

    def get_nearby_places_info(self, location_name):
        """Get suggestions for restaurants/bars near a location."""
        area_suggestions = {
            "columbus circle": [
                ("Per Se", "Fine dining", "10 Columbus Circle"),
                ("Landmarc", "French-American bistro", "Time Warner Center"),
            ],
            "central park": [
                ("Tavern on the Green", "American", "Central Park West"),
                ("The Loeb Boathouse", "Lakeside dining", "Central Park"),
            ],
            "times square": [
                ("Junior's", "Diner & cheesecake", "1515 Broadway"),
                ("Carmine's", "Italian family style", "200 W 44th St"),
            ],
            "broadway": [
                ("Sardi's", "Theater district classic", "234 W 44th St"),
                ("Joe Allen", "American bistro", "326 W 46th St"),
            ],
            "brooklyn": [
                ("Juliana's Pizza", "Pizzeria", "DUMBO"),
                ("The River Café", "Fine dining", "Brooklyn Bridge Park"),
            ],
            "dumbo": [
                ("Juliana's Pizza", "Famous pizzeria", "19 Old Fulton St"),
                ("Time Out Market", "Food hall", "55 Water St"),
            ],
            "soho": [
                ("Balthazar", "French brasserie", "80 Spring St"),
                ("The Mercer Kitchen", "American", "99 Prince St"),
            ],
            "williamsburg": [
                ("Peter Luger", "Steakhouse", "178 Broadway"),
                ("Lilia", "Italian", "567 Union Ave"),
            ],
            "chelsea": [
                ("Buddakan", "Asian fusion", "75 9th Ave"),
                ("Los Tacos No. 1", "Tacos", "Chelsea Market"),
            ],
            "east village": [
                ("Veselka", "Ukrainian diner", "144 2nd Ave"),
                ("Momofuku Noodle Bar", "Asian", "171 1st Ave"),
            ],
            "west village": [
                ("L'Artusi", "Italian", "228 W 10th St"),
                ("The Spotted Pig", "Gastropub", "314 W 11th St"),
            ],
            "upper west side": [
                ("Barney Greengrass", "Deli", "541 Amsterdam Ave"),
                ("Jacob's Pickles", "Southern", "509 Amsterdam Ave"),
            ],
            "upper east side": [
                ("Cafe Sabarsky", "Viennese café", "Neue Galerie"),
                ("JG Melon", "Burger joint", "1291 3rd Ave"),
            ],
            "harlem": [
                ("Red Rooster", "American", "310 Lenox Ave"),
                ("Sylvia's", "Soul food", "328 Malcolm X Blvd"),
            ],
            "financial district": [
                ("The Dead Rabbit", "Irish bar", "30 Water St"),
                ("Crown Shy", "New American", "70 Pine St"),
            ],
            "midtown": [
                ("Grand Central Oyster Bar", "Seafood", "Grand Central"),
                ("The Campbell", "Cocktail bar", "Grand Central"),
            ],
        }

        location_lower = location_name.lower()
        for area_key, places in area_suggestions.items():
            if area_key in location_lower or location_lower in area_key:
                suggestions = []
                for name, type_desc, address in places[:2]:
                    suggestions.append(f"• {name} ({type_desc}) - {address}")
                return "\n".join(suggestions)
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
                "join",
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
                "home",
            ],
            "chat": [
                "chat",
                "message",
                "messages",
                "talk to user",
                "dm",
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

    def generate_ai_response(self, message, user, context_type="general"):
        """
        Generate AI response using Gemini for any query.
        This is the main AI response generator.
        """
        # Build context about the website
        pages_context = "\n".join(
            [
                f"- {info['name']} ({info['url']}): {info['description']}"
                for info in self.website_pages.values()
            ]
        )

        system_prompt = f"""You are ArtBot, a friendly and helpful AI assistant \
for Artinerary - a platform for exploring NYC public art.

WEBSITE FEATURES:
{pages_context}

YOUR CAPABILITIES:
1. Help users find public artworks in NYC neighborhoods
2. Guide users to website features (map, events, favorites, etc.)
3. Answer questions about NYC public art
4. Help plan art tours and itineraries
5. Provide information about website features

RESPONSE GUIDELINES:
- Be conversational, friendly, and helpful
- Keep responses concise (2-4 sentences typically)
- When users ask about website features, explain AND offer to take them there
- For art location queries, suggest specific neighborhoods or use the map
- Do NOT use markdown formatting (no **, ##, bullet points with *)
- Use plain text with natural line breaks
- If asked about non-art topics, briefly acknowledge then redirect to art

CONTEXT: User "{user.username}" is asking: "{message}"
"""

        try:
            if self.model:
                response = self.model.generate_content(system_prompt)
                if response and response.text:
                    # Clean up any markdown that might slip through
                    cleaned = response.text.strip()
                    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
                    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
                    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
                    cleaned = re.sub(r"^\*\s+", "• ", cleaned, flags=re.MULTILINE)
                    cleaned = re.sub(r"^-\s+", "• ", cleaned, flags=re.MULTILINE)
                    return cleaned
                else:
                    return self._get_smart_fallback(message)
            else:
                return self._get_smart_fallback(message)
        except Exception as e:
            print(f"Gemini API error: {e}")
            return self._get_smart_fallback(message)

    def _get_smart_fallback(self, message):
        """Intelligent fallback when Gemini is unavailable"""
        message_lower = message.lower()

        # Page-specific fallbacks
        if any(w in message_lower for w in ["map", "where is the map"]):
            return (
                "The interactive map shows all NYC public artworks! "
                "You can click on markers to see artwork details, "
                "filter by borough, and plan your route. "
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

        if any(w in message_lower for w in ["chat", "message", "talk"]):
            return (
                "You can chat with other art enthusiasts, "
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

        # Default helpful response
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
            response_data["message"] = ContentModerator.get_warning_response(severity)
            response_data["metadata"]["content_warning"] = True
            response_data["metadata"]["moderation_severity"] = severity
            moderation_logger.warning(
                f"Content flagged | User: {user.username} | " f"Severity: {severity}"
            )
            return response_data

        # STEP 2: Check for nearby artworks request (needs location data)
        if any(
            word in message_lower
            for word in ["nearby", "near me", "around me", "close by", "close to me"]
        ):
            if user_location:
                lat = user_location.get("lat") or user_location.get("latitude")
                lng = user_location.get("lng") or user_location.get("longitude")
                if lat and lng:
                    nearby_art = self.get_nearby_artworks(lat, lng)
                    if nearby_art:
                        response_data["message"] = (
                            f"Found {len(nearby_art)} artworks near you!\n\n"
                            "Would you like to create an itinerary with these?"
                        )
                        response_data["metadata"]["artworks"] = nearby_art
                        response_data["metadata"]["show_itinerary_prompt"] = True
                        response_data["metadata"]["suggested_locations"] = [
                            art["id"] for art in nearby_art
                        ]
                    else:
                        response_data["message"] = (
                            "I couldn't find artworks within 2 miles. "
                            "Try exploring a specific neighborhood or the map!"
                        )
                        response_data["metadata"]["navigation"] = (
                            self.get_navigation_info("map")
                        )
                else:
                    response_data["message"] = (
                        "Please share your location using the 📍 button."
                    )
                    response_data["metadata"]["request_location"] = True
            else:
                response_data["message"] = (
                    "To find nearby artworks, please share your location "
                    "using the 📍 button below."
                )
                response_data["metadata"]["request_location"] = True
            return response_data

        # STEP 3: Check for restaurant/bar queries with location
        is_places_query, place_location = self.check_for_nearby_places_query(message)
        if is_places_query and place_location:
            location_info = self.extract_location_from_message(message)
            if location_info:
                if location_info["type"] == "borough":
                    artworks = self.get_artworks_by_borough(location_info["value"])
                else:
                    artworks = self.search_artworks_by_location(location_info["value"])

                places_info = self.get_nearby_places_info(place_location)

                if artworks:
                    msg = (
                        f"Here are public artworks in " f"{place_location.title()}!\n\n"
                    )
                    if places_info:
                        msg += (
                            f"Nearby dining options:\n{places_info}\n\n"
                            "Would you like to create an art itinerary?"
                        )
                    else:
                        msg += (
                            "For dining, I recommend Google Maps or Yelp "
                            "for current options.\n\n"
                            "Would you like to create an art itinerary?"
                        )

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
                    msg += f"\n\nNearby Recreational Spots to Chill:\n{places_info}"
                msg += "\n\nWould you like to create an itinerary?"

                response_data["message"] = msg
                response_data["metadata"]["artworks"] = artworks
                response_data["metadata"]["show_itinerary_prompt"] = True
                response_data["metadata"]["suggested_locations"] = [
                    art["id"] for art in artworks
                ]
            else:
                # Use AI to respond about the location
                response_data["message"] = self.generate_ai_response(
                    message, user, "location"
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
                # Generate AI response about this feature
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
                    response_data["message"] = f"Taking you to {page_info['name']}!"
                    response_data["metadata"]["navigation"] = page_info
                    return response_data

        # STEP 7: Check for explicit search/find requests
        if any(
            word in message_lower
            for word in ["find artwork", "search for", "look for artwork"]
        ):
            search_terms = message_lower
            for word in [
                "find",
                "search",
                "look for",
                "artwork",
                "artworks",
                "art",
                "the",
                "some",
                "any",
                "for",
            ]:
                search_terms = search_terms.replace(word, "")
            search_terms = search_terms.strip()

            if search_terms and len(search_terms) > 2:
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
        # This is where the magic happens for general questions
        response_data["message"] = self.generate_ai_response(message, user)

        # Check if we should add a navigation button based on AI response
        ai_response_lower = response_data["message"].lower()
        for page_key, page_info in self.website_pages.items():
            if page_info["name"].lower() in ai_response_lower:
                response_data["metadata"]["navigation"] = page_info
                break

        print(f"Response: {response_data['message'][:100]}...")
        return response_data
