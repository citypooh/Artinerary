from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = "events"

urlpatterns = [
    # BROWSE & MANAGE (Phase 2)
    path("", views.index, name="index"),
    path("public/", views.public_events, name="public"),
    path("invitations/", views.invitations, name="invitations"),
    # SHARE LINKS
    path("e/<str:code>/", views.event_share_redirect, name="share_redirect"),
    path(
        "favorites/",
        RedirectView.as_view(url="/favorites/?tab=events", permanent=False),
        name="favorites",
    ),
    # CREATE (Phase 1)
    path("create/", views.create, name="create"),
    # ACTIONS (Phase 2)
    path("<slug:slug>/join/", views.join_event, name="join"),
    path("<slug:slug>/accept/", views.accept_invite, name="accept"),
    path("<slug:slug>/decline/", views.decline_invite, name="decline"),
    # FAVORITES
    path("<slug:slug>/favorite/", views.favorite_event_view, name="favorite"),
    path("<slug:slug>/unfavorite/", views.unfavorite_event_view, name="unfavorite"),
    # UPDATE & DELETE (Host only)
    path("<slug:slug>/edit/", views.update_event, name="update"),
    path("<slug:slug>/delete/", views.delete_event, name="delete"),
    path("<slug:slug>/leave/", views.leave_event, name="leave"),
    # CHAT & REQUESTS (Phase 3)
    path("<slug:slug>/chat/send/", views.chat_send, name="chat_send"),
    path("<slug:slug>/request/", views.request_join_view, name="request_join"),
    path(
        "<slug:slug>/request/<int:request_id>/approve/",
        views.approve_request,
        name="approve_request",
    ),
    path(
        "<slug:slug>/request/<int:request_id>/decline/",
        views.decline_request,
        name="decline_request",
    ),
    # DETAIL (Phase 3 - fully implemented)
    path("<slug:slug>/", views.detail, name="detail"),
    # HELPER APIs (autocomplete for create form & map pins)
    path(
        "api/locations/search/", views.api_locations_search, name="api_locations_search"
    ),
    path("api/users/search/", views.api_users_search, name="api_users_search"),
    path("api/pins/", views.api_event_pins, name="api_event_pins"),
    # REALTIME CHAT API
    path("<slug:slug>/chat/api/", views.api_chat_messages, name="api_chat_messages"),
    # MESSAGE REPORTING
    path(
        "messages/<int:message_id>/report/", views.report_message, name="report_message"
    ),
    # DIRECT CHAT (1-on-1)
    path(
        "<slug:slug>/chat/create/",
        views.create_or_get_direct_chat,
        name="create_direct_chat",
    ),
    path(
        "chat/<int:chat_id>/send/",
        views.send_direct_message,
        name="send_direct_message",
    ),
    path(
        "chat/<int:chat_id>/api/", views.api_direct_messages, name="api_direct_messages"
    ),
    path(
        "chat/<int:chat_id>/delete/",
        views.delete_direct_chat,
        name="delete_direct_chat",
    ),
    path("chats/list/", views.list_user_direct_chats, name="list_direct_chats"),
]
