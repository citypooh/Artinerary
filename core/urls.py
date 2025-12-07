"""
URL configuration for artinerary project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

from artinerary import views as artinerary_views

urlpatterns = [
    path("", artinerary_views.landing_page, name="landing_page"),
    path("dashboard/", artinerary_views.dashboard, name="dashboard"),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),  # Add allauth URLs
    path("artinerary/", include("artinerary.urls")),
    path("loc_detail/", include("loc_detail.urls")),
    path("events/", include(("events.urls", "events"), namespace="events")),
    path("itineraries/", include("itineraries.urls")),
    path("favorites/", include("favorites.urls")),
    path(
        "messages/",
        include(("messages.urls", "user_messages"), namespace="user_messages"),
    ),
    path("admin/", admin.site.urls),
    path("profile/", include("user_profile.urls")),
    path("chatbot/", include("chatbot.urls")),
]
