from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg
from events.models import EventMembership
from itineraries.models import Itinerary
from loc_detail.models import PublicArt
from messages.models import Conversation


def landing_page(request):
    """Landing page for unauthenticated users"""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "landing.html")


@login_required
def dashboard(request):
    """User dashboard with overview of events, itineraries, and chats"""
    user = request.user

    # Get upcoming events (top 3)
    upcoming_events = (
        EventMembership.objects.filter(user=user)
        .select_related("event")
        .order_by("event__start_time")[:3]
    )

    # Get recent itineraries (top 3)
    my_itineraries = Itinerary.objects.filter(user=user).order_by("-updated_at")[:3]

    # Get recent chats (top 3)
    recent_chats = Conversation.objects.filter(Q(user1=user) | Q(user2=user)).order_by(
        "-updated_at"
    )[:3]

    # Get featured artworks (top 3 rated)
    featured_artworks = (
        PublicArt.objects.annotate(
            avg_rating=Avg("comments__rating", filter=Q(comments__parent__isnull=True))
        )
        .order_by("-avg_rating")[:3]
    )

    context = {
        "upcoming_events": upcoming_events,
        "my_itineraries": my_itineraries,
        "recent_chats": recent_chats,
        "featured_artworks": featured_artworks,
    }
    return render(request, "dashboard.html", context)


@login_required
def index(request):
    """Artinerary homepage with interactive map"""
    return render(request, "artinerary/home.html")
