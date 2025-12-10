from django.urls import path
from . import views

app_name = "chatbot"

urlpatterns = [
    path("api/chat/", views.chat_view, name="chat"),
    path("api/history/", views.chat_history, name="history"),
    path("api/prepare-itinerary/", views.prepare_itinerary, name="prepare_itinerary"),
    path("api/clear/", views.clear_chat, name="clear_chat"),
]
