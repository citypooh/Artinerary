from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import ChatSession, ChatMessage
from .ai_service import ArtineraryAI
import json
import uuid
import logging

# Set up logger for moderation events
moderation_logger = logging.getLogger("chatbot.moderation")


@login_required
def chat_view(request):
    """Main chat endpoint"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            message = data.get("message", "")
            user_location = data.get("location", None)
            session_id = data.get("session_id", "")

            print(f"Received chat request from user: {request.user.username}")
            print(f"Message: {message}")
            print(f"Location data: {user_location}")
            print(f"Session ID: {session_id}")

            # Validate message
            if not message.strip():
                return JsonResponse(
                    {"success": False, "error": "Message cannot be empty"}, status=400
                )

            # Get or create session
            if not session_id:
                session_id = str(uuid.uuid4())

            session, created = ChatSession.objects.get_or_create(
                user=request.user,
                session_id=session_id,
                defaults={"user": request.user},
            )

            if created:
                print(f"Created new chat session: {session_id}")
            else:
                print(f"Using existing chat session: {session_id}")

            # Save user message
            ChatMessage.objects.create(session=session, sender="user", message=message)

            # Get AI response
            ai = ArtineraryAI()
            response_data = ai.process_message(message, request.user, user_location)

            # Log moderation events
            if response_data.get("metadata", {}).get("content_warning"):
                severity = response_data["metadata"].get("moderation_severity", "warn")
                moderation_logger.warning(
                    f"Content moderation triggered | "
                    f"User: {request.user.username} | "
                    f"Severity: {severity} | "
                    f"Session: {session_id} | "
                    f"Message: {message[:100]}..."
                )

            # Save bot response
            bot_message = ChatMessage.objects.create(
                session=session,
                sender="bot",
                message=response_data["message"],
                metadata=response_data.get("metadata", {}),
            )

            # Store suggested locations in session if present
            if response_data.get("metadata", {}).get("suggested_locations"):
                request.session["chatbot_suggested_locations"] = response_data[
                    "metadata"
                ]["suggested_locations"]
                print(
                    f"Stored {len(response_data['metadata']['suggested_locations'])} "
                    "locations in session"
                )

            print(f"Bot response: {response_data['message'][:100]}...")
            print(f"Metadata keys: {response_data.get('metadata', {}).keys()}")

            return JsonResponse(
                {
                    "success": True,
                    "response": response_data["message"],
                    "metadata": response_data.get("metadata", {}),
                    "session_id": session_id,
                    "message_id": bot_message.id,
                }
            )

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JsonResponse(
                {"success": False, "error": "Invalid JSON data"}, status=400
            )
        except Exception as e:
            print(f"Error in chat_view: {e}")
            import traceback

            traceback.print_exc()
            return JsonResponse(
                {
                    "success": False,
                    "error": "An error occurred processing your request",
                },
                status=500,
            )

    return JsonResponse({"error": "Invalid request method"}, status=400)


@login_required
def chat_history(request):
    """Get chat history for current user"""
    try:
        session_id = request.GET.get("session_id", "")

        if session_id:
            try:
                session = ChatSession.objects.get(
                    user=request.user, session_id=session_id
                )
                messages = session.messages.all()[:50]  # Last 50 messages
            except ChatSession.DoesNotExist:
                print(
                    f"Session {session_id} not found for user {request.user.username}"
                )
                messages = []
                session = None
        else:
            # Get most recent session
            session = ChatSession.objects.filter(user=request.user).first()
            if session:
                messages = session.messages.all()[:50]
            else:
                messages = []

        message_list = []
        for msg in messages:
            message_list.append(
                {
                    "sender": msg.sender,
                    "message": msg.message,
                    "metadata": msg.metadata,
                    "created_at": msg.created_at.strftime("%I:%M %p"),
                }
            )

        return JsonResponse(
            {
                "success": True,
                "messages": message_list,
                "session_id": session.session_id if session else None,
            }
        )

    except Exception as e:
        print(f"Error in chat_history: {e}")
        import traceback

        traceback.print_exc()
        return JsonResponse(
            {"success": False, "error": "Error loading chat history"}, status=500
        )


@login_required
def prepare_itinerary(request):
    """Prepare itinerary data for creation"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            locations = data.get("locations", [])

            print(f"Preparing itinerary with {len(locations)} locations")

            # Store in session for the create page
            request.session["suggested_locations"] = locations

            return JsonResponse(
                {"success": True, "redirect_url": "/itineraries/create/"}
            )

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JsonResponse(
                {"success": False, "error": "Invalid JSON data"}, status=400
            )
        except Exception as e:
            print(f"Error in prepare_itinerary: {e}")
            import traceback

            traceback.print_exc()
            return JsonResponse(
                {"success": False, "error": "Error preparing itinerary"}, status=500
            )

    return JsonResponse({"error": "Invalid request method"}, status=400)


@login_required
def clear_chat(request):
    """Clear chat history for current session"""
    if request.method == "POST":
        try:
            data = json.loads(request.body) if request.body else {}
            session_id = data.get("session_id", "")

            if session_id:
                try:
                    session = ChatSession.objects.get(
                        user=request.user, session_id=session_id
                    )
                    # Delete all messages in this session
                    session.messages.all().delete()
                    print(f"Cleared chat session: {session_id}")
                except ChatSession.DoesNotExist:
                    pass

            return JsonResponse({"success": True})

        except Exception as e:
            print(f"Error in clear_chat: {e}")
            return JsonResponse(
                {"success": False, "error": "Error clearing chat"}, status=500
            )

    return JsonResponse({"error": "Invalid request method"}, status=400)
