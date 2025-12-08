"""
URL configuration for itineraries app
"""

from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = "itineraries"

urlpatterns = [
    path("", views.itinerary_list, name="list"),
    path(
        "favorites/",
        RedirectView.as_view(url="/favorites/?tab=itineraries", permanent=False),
        name="favorites",
    ),
    path("create/", views.itinerary_create, name="create"),
    path("<int:pk>/", views.itinerary_detail, name="detail"),
    path("<int:pk>/edit/", views.itinerary_edit, name="edit"),
    path("<int:pk>/delete/", views.itinerary_delete, name="delete"),
    path("<int:pk>/favorite/", views.favorite_itinerary, name="favorite"),
    path("<int:pk>/unfavorite/", views.unfavorite_itinerary, name="unfavorite"),
    path(
        "<int:pk>/create-event/",
        views.create_event_from_itinerary,
        name="create_event",
    ),
    path(
        "api/search-locations/", views.api_search_locations, name="api_search_locations"
    ),
    path(
        "api/user-itineraries/",
        views.api_get_user_itineraries,
        name="api_user_itineraries",
    ),
    path(
        "api/add-to-itinerary/", views.api_add_to_itinerary, name="api_add_to_itinerary"
    ),
]
