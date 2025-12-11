# Events Module - Complete Technical Documentation

> **Generated**: December 2024  
> **Module Path**: `events/`  
> **Django App Name**: `events`

---

## Table of Contents

1. [Module Overview](#1-module-overview)
2. [Data Models](#2-data-models)
3. [Enums & Constants](#3-enums--constants)
4. [Architecture Pattern](#4-architecture-pattern)
5. [Services Layer](#5-services-layer)
6. [Selectors Layer](#6-selectors-layer)
7. [Views & URL Routing](#7-views--url-routing)
8. [API Endpoints](#8-api-endpoints)
9. [Business Rules & Constraints](#9-business-rules--constraints)
10. [Frontend Templates](#10-frontend-templates)
11. [Test Coverage](#11-test-coverage)

---

## 1. Module Overview

The Events module is a core feature of **Artinerary** that enables users to create, manage, and participate in art-focused events. Events can be single-location meetups or multi-stop art tours (itineraries).

### Core Capabilities

| Feature | Description |
|---------|-------------|
| Event Creation | Create events with title, time, location(s), visibility |
| Multi-Stop Itineraries | Add up to 5 additional locations beyond the starting point |
| Visibility Controls | PUBLIC_OPEN, PUBLIC_INVITE, PRIVATE |
| Invitations | Invite users to events, track accept/decline |
| Join Requests | Request-to-join flow for PUBLIC_INVITE events |
| Group Chat | Real-time chat for event members (20 message limit) |
| Direct Messages | 1-on-1 chat between event attendees |
| Message Reporting | Report inappropriate chat messages |
| Favorites | Bookmark events for later |

### Dependencies

- `loc_detail.models.PublicArt` - Art location model
- `django.contrib.auth.models.User` - User authentication

---

## 2. Data Models

### 2.1 Event (Core Model)

```python
class Event(models.Model):
    slug = models.SlugField(unique=True, max_length=100, db_index=True)
    title = models.CharField(max_length=80)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name="hosted_events")
    visibility = models.CharField(max_length=20, choices=EventVisibility.choices, default=EventVisibility.PUBLIC_OPEN)
    start_time = models.DateTimeField(db_index=True)
    start_location = models.ForeignKey(PublicArt, on_delete=models.PROTECT, related_name="events")
    description = models.TextField(blank=True)
    is_deleted = models.BooleanField(default=False)  # Soft delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Key Behaviors**:
- Slug auto-generated from title + UUID (8 chars) on save
- Soft delete pattern (`is_deleted=True` hides from queries)
- `start_location` uses PROTECT to prevent orphan events

### 2.2 EventLocation (Itinerary Stops)

```python
class EventLocation(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="locations")
    location = models.ForeignKey(PublicArt, on_delete=models.PROTECT)
    order = models.PositiveSmallIntegerField()
    note = models.CharField(max_length=100, blank=True)
```

**Constraints**:
- `UniqueConstraint(event, order)` - No duplicate order numbers per event
- `UniqueConstraint(event, location)` - No duplicate locations per event
- **Max 5 additional locations** (validated in services layer)

### 2.3 EventMembership

```python
class EventMembership(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="event_memberships")
    role = models.CharField(max_length=20, choices=MembershipRole.choices)
    joined_at = models.DateTimeField(auto_now_add=True)
```

**Roles**: `HOST`, `ATTENDEE`, `INVITED`

### 2.4 EventInvite

```python
class EventInvite(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="invites")
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    invitee = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=InviteStatus.choices, default=InviteStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
```

**Statuses**: `PENDING`, `ACCEPTED`, `DECLINED`, `EXPIRED`

### 2.5 EventJoinRequest

```python
class EventJoinRequest(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="join_requests")
    requester = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=JoinRequestStatus.choices, default=JoinRequestStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
```

**Statuses**: `PENDING`, `APPROVED`, `DECLINED`

### 2.6 EventChatMessage (Group Chat)

```python
class EventChatMessage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="chat_messages")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

**Retention**: Only latest 20 messages kept per event (enforced in service)

### 2.7 MessageReport

```python
class MessageReport(models.Model):
    message = models.ForeignKey(EventChatMessage, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.CharField(max_length=20, choices=MessageReportReason.choices)
    description = models.TextField(blank=True, max_length=500)
    status = models.CharField(max_length=20, choices=ReportStatus.choices, default=ReportStatus.PENDING)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, related_name="reviewed_message_reports")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
```

### 2.8 EventFavorite

```python
class EventFavorite(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="favorited_by")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorite_events")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

### 2.9 DirectChat (1-on-1 Messaging)

```python
class DirectChat(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="direct_chats")
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="direct_chats_initiated")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="direct_chats_received")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Methods**:
- `get_other_user(user)` - Get the other participant
- `has_user_left(user)` - Check if user left the chat
- `get_active_users()` - Get users who haven't left

### 2.10 DirectMessage

```python
class DirectMessage(models.Model):
    chat = models.ForeignKey(DirectChat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

### 2.11 DirectChatLeave

```python
class DirectChatLeave(models.Model):
    chat = models.ForeignKey(DirectChat, on_delete=models.CASCADE, related_name="leaves")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_leaves")
    left_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

**Behavior**: When user leaves, they no longer see the chat. If other user sends a message, leave record is deleted (auto-restore).

---

## 3. Enums & Constants

Located in `events/enums.py`:

```python
class EventVisibility(models.TextChoices):
    PUBLIC_OPEN = "PUBLIC_OPEN", "Public - Open to All"
    PUBLIC_INVITE = "PUBLIC_INVITE", "Public - Invite Only"
    PRIVATE = "PRIVATE", "Private"

class MembershipRole(models.TextChoices):
    HOST = "HOST", "Host"
    ATTENDEE = "ATTENDEE", "Attendee"
    INVITED = "INVITED", "Invited"

class InviteStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    EXPIRED = "EXPIRED", "Expired"

class JoinRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    DECLINED = "DECLINED", "Declined"

class MessageReportReason(models.TextChoices):
    INAPPROPRIATE = "INAPPROPRIATE", "Inappropriate content"
    SPAM = "SPAM", "Spam"
    HARASSMENT = "HARASSMENT", "Harassment"
    OFF_TOPIC = "OFF_TOPIC", "Off-topic"
    OTHER = "OTHER", "Other"

class ReportStatus(models.TextChoices):
    PENDING = "PENDING", "Pending Review"
    REVIEWING = "REVIEWING", "Under Review"
    RESOLVED = "RESOLVED", "Resolved"
    DISMISSED = "DISMISSED", "Dismissed"
```

---

## 4. Architecture Pattern

The events module follows a **layered architecture** pattern:

```
┌─────────────────────────────────────────┐
│               VIEWS LAYER               │
│   (HTTP handling, auth, routing)        │
├─────────────────────────────────────────┤
│             SERVICES LAYER              │
│   (Business logic, transactions)        │
├─────────────────────────────────────────┤
│            SELECTORS LAYER              │
│   (Read-only queries, filtering)        │
├─────────────────────────────────────────┤
│              MODELS LAYER               │
│   (Data structures, constraints)        │
└─────────────────────────────────────────┘
```

### Key Principles

1. **Views** only handle HTTP concerns (request/response, auth decorators)
2. **Services** handle all write operations with `@transaction.atomic`
3. **Selectors** handle all read operations with optimized queries
4. **Models** define data structure and DB constraints

---

## 5. Services Layer

Located in `events/services.py`. All functions use `@transaction.atomic` for data integrity.

### 5.1 Event Lifecycle

| Service | Purpose | Key Logic |
|---------|---------|-----------|
| `create_event(host, form, locations, invites)` | Create event with all related data | Validates locations (max 5), dedupes, creates memberships |
| `update_event(event, form, locations, invites)` | Update existing event | Clears & recreates locations, only adds new invites |
| `delete_event(event)` | Soft delete | Sets `is_deleted=True` |

### 5.2 Membership Management

| Service | Purpose | Business Rules |
|---------|---------|----------------|
| `join_event(event, user)` | Join PUBLIC_OPEN event | Checks visibility, duplicate membership |
| `leave_event(event, user)` | Deregister from event | Host cannot leave; removes ATTENDEE membership |
| `accept_invite(invite)` | Accept invitation | Updates status, creates/upgrades membership to ATTENDEE |
| `decline_invite(invite)` | Decline invitation | Updates status, removes INVITED membership |

### 5.3 Join Request Flow (PUBLIC_INVITE)

| Service | Purpose |
|---------|---------|
| `request_join(event, user)` | Create pending request (idempotent) |
| `approve_join_request(join_request)` | Approve & create ATTENDEE membership |
| `decline_join_request(join_request)` | Mark as declined |

### 5.4 Chat & Favorites

| Service | Purpose | Notes |
|---------|---------|-------|
| `post_chat_message(event, user, message)` | Post to group chat | Validates membership, 1-300 chars, enforces 20-message retention |
| `favorite_event(event, user)` | Add to favorites | Idempotent, cannot favorite deleted events |
| `unfavorite_event(event, user)` | Remove from favorites | Returns boolean for success |

---

## 6. Selectors Layer

Located in `events/selectors.py`. All functions are read-only with optimized queries.

### 6.1 Search & Autocomplete

```python
search_locations(term, limit=10)  # Search PublicArt by title/artist/location
search_users(term, limit=10)      # Search Users by username/email
```

### 6.2 Event Queries

```python
public_event_pins()                              # Map pins for public events
list_public_events(query, visibility_filter, order)  # Paginated public events
user_has_joined(event, user)                     # Check if user is HOST/ATTENDEE
```

### 6.3 User-Specific Queries

```python
list_user_invitations(user)    # Pending invites with prefetched event data
```

### 6.4 Event Detail Helpers

```python
get_event_detail(slug)              # Event with all relationships prefetched
user_role_in_event(event, user)     # Returns 'HOST' | 'ATTENDEE' | 'VISITOR'
list_event_attendees(event)         # All HOST + ATTENDEE memberships
list_chat_messages(event, limit=20) # Latest messages, oldest-first order
get_join_request(event, user)       # User's pending request (if any)
list_pending_join_requests(event)   # All pending requests (for host)
```

---

## 7. Views & URL Routing

### 7.1 URL Structure

```python
app_name = "events"

# BROWSE
path("", views.index, name="index")                    # → Redirects to public
path("public/", views.public_events, name="public")    # Public events list
path("invitations/", views.invitations, name="invitations")
path("favorites/", RedirectView → /favorites/?tab=events)

# CREATE/EDIT
path("create/", views.create, name="create")
path("<slug:slug>/edit/", views.update_event, name="update")
path("<slug:slug>/delete/", views.delete_event, name="delete")

# DETAIL
path("<slug:slug>/", views.detail, name="detail")

# JOIN/LEAVE
path("<slug:slug>/join/", views.join_event, name="join")
path("<slug:slug>/leave/", views.leave_event, name="leave")
path("<slug:slug>/accept/", views.accept_invite, name="accept")
path("<slug:slug>/decline/", views.decline_invite, name="decline")

# FAVORITES
path("<slug:slug>/favorite/", views.favorite_event_view, name="favorite")
path("<slug:slug>/unfavorite/", views.unfavorite_event_view, name="unfavorite")

# JOIN REQUESTS
path("<slug:slug>/request/", views.request_join_view, name="request_join")
path("<slug:slug>/request/<int:request_id>/approve/", views.approve_request)
path("<slug:slug>/request/<int:request_id>/decline/", views.decline_request)

# CHAT
path("<slug:slug>/chat/send/", views.chat_send, name="chat_send")
path("<slug:slug>/chat/api/", views.api_chat_messages, name="api_chat_messages")

# MESSAGE REPORTING
path("messages/<int:message_id>/report/", views.report_message)

# DIRECT CHAT
path("<slug:slug>/chat/create/", views.create_or_get_direct_chat)
path("chat/<int:chat_id>/send/", views.send_direct_message)
path("chat/<int:chat_id>/api/", views.api_direct_messages)
path("chat/<int:chat_id>/delete/", views.delete_direct_chat)
path("chats/list/", views.list_user_direct_chats)

# API (Autocomplete)
path("api/locations/search/", views.api_locations_search)
path("api/users/search/", views.api_users_search)
path("api/pins/", views.api_event_pins)
```

### 7.2 View Decorators

- All views require `@login_required`
- POST-only views use `@require_POST`

---

## 8. API Endpoints

### 8.1 Autocomplete APIs (JSON)

**Location Search**
```
GET /events/api/locations/search/?q=<term>
Response: { "results": [{ "id", "t": title, "a": artist, "y": lat, "x": lng }] }
```

**User Search**
```
GET /events/api/users/search/?q=<term>
Response: { "results": [{ "id", "u": username }] }
```

**Event Pins**
```
GET /events/api/pins/
Response: { "points": [{ "id", "t": title, "y": lat, "x": lng, "slug" }] }
```

### 8.2 Chat APIs

**Group Chat Messages**
```
GET /events/<slug>/chat/api/
Response: { "messages": [{ "id", "author", "is_host", "message", "created_at" }] }
Access: HOST or ATTENDEE only (403 for VISITOR)
```

**Direct Chat Messages**
```
GET /events/chat/<chat_id>/api/
Response: { "messages": [{ "id", "sender", "content", "created_at", "is_own" }] }
Side Effect: Marks messages as read
```

**List User's Direct Chats**
```
GET /events/chats/list/
Response: { "chats": [{ "chat_id", "event_title", "event_slug", "other_user", "latest_message", "unread_count" }] }
```

---

## 9. Business Rules & Constraints

### 9.1 Event Visibility Rules

| Visibility | Who Can See | Who Can Join | Request to Join |
|------------|-------------|--------------|-----------------|
| PUBLIC_OPEN | Everyone | Anyone | N/A |
| PUBLIC_INVITE | Everyone | Invited users only | Yes |
| PRIVATE | Invited users only | Invited users only | No |

### 9.2 Membership State Machine

```
[None] ──invite──> [INVITED] ──accept──> [ATTENDEE]
                       │                      │
                       └──decline──> [None]   │
                                              │
[None] ──join (PUBLIC_OPEN)──────────────────>┘
```

### 9.3 Join Request Flow (PUBLIC_INVITE)

```
[VISITOR] ──request──> [PENDING] ──approve──> [ATTENDEE]
                           │
                           └──decline──> [DECLINED]
```

### 9.4 Validation Rules

| Field | Rule |
|-------|------|
| `Event.title` | Max 80 characters |
| `Event.start_time` | Must be in the future |
| `Event.locations` | Max 5 additional locations |
| `EventChatMessage.message` | 1-300 characters |
| `DirectMessage.content` | Max 500 characters |
| `MessageReport.description` | Max 500 characters |

### 9.5 Data Integrity Constraints

- Event slug is unique
- One membership per user per event
- One invite per user per event
- One join request per user per event
- One favorite per user per event
- One report per user per message

---

## 10. Frontend Templates

### 10.1 Template Hierarchy

```
templates/events/
├── base_tabs.html          # Events section with tabs (Public, Invitations)
├── create.html             # Create/Edit event form
├── detail.html             # Event detail page
├── public_events.html      # Public events grid
├── invitations.html        # User's pending invitations
├── favorites.html          # User's favorited events
└── partials/
    ├── _chat_panel.html         # Group chat (for HOST/ATTENDEE)
    ├── _cta_panel.html          # Join/Request CTA (for VISITOR)
    ├── _details_panel.html      # Event info, attendees, join requests
    └── _direct_chat_widget.html # Floating 1-on-1 chat widget
```

### 10.2 Detail Page Layout

```
┌─────────────────────────────────────────────────────────┐
│ [Header: Title, Host, Actions (Edit/Delete/Leave)]      │
├────────────────────────┬────────────────────────────────┤
│   DETAILS PANEL        │   CONTEXT PANEL                │
│   - When (date/time)   │   [HOST/ATTENDEE]: Chat Panel  │
│   - Starting Point     │   [VISITOR]: CTA Panel         │
│   - Itinerary          │                                │
│   - Description        │                                │
│   - Visibility Badge   │                                │
│   - Attendees List     │                                │
│   - Join Requests      │                                │
│     (host only)        │                                │
└────────────────────────┴────────────────────────────────┘
```

### 10.3 Create/Edit Form Fields

1. **Event Title** (required, max 80 chars)
2. **Date & Time** (required, datetime-local input)
3. **Starting Location** (required, dropdown of PublicArt)
4. **Description** (optional, textarea)
5. **Additional Locations** (optional, dropdown + chips, max 5)
6. **Invite Members** (optional, autocomplete + chips)
7. **Visibility** (required, dropdown)

### 10.4 JavaScript Features

Located in `static/events/create.js`:

- **Location Dropdown**: Select-to-chip for additional locations
- **User Autocomplete**: Debounced search with chip selection
- **Form Submission**: Injects hidden inputs for locations[] and invites[]
- **Edit Mode**: Pre-populates existing locations and invites

### 10.5 Real-Time Features

**Group Chat** (`_chat_panel.html`):
- Polls `/events/<slug>/chat/api/` every 1 second
- AJAX form submission (no page reload)
- Auto-scrolls if user was at bottom
- Report modal with AJAX submission

**Direct Chat** (`_direct_chat_widget.html`):
- Fixed-position widget at bottom-right
- Polls for new messages every 2-3 seconds
- localStorage persistence of open chat state
- Minimize/maximize/close functionality
- Leave chat option (with auto-restore on new message)

---

## 11. Test Coverage

### 11.1 Test Classes (1281 lines)

| Test Class | Focus Area |
|------------|------------|
| `EventModelTests` | Slug generation, __str__ |
| `EventServiceTests` | create_event with locations/invites |
| `EventFormTests` | Form validation |
| `PublicEventsTests` | list_public_events, search, filters |
| `JoinEventTests` | Visibility rules, duplicate prevention |
| `InvitationTests` | Accept/decline flow |
| `EventDetailTests` | Role detection |
| `ChatMessageTests` | Posting, retention limit |
| `JoinRequestTests` | Request/approve/decline |
| `EventSelectorTests` | Query correctness |
| `EventUpdateTests` | Host-only access |
| `EventDeleteTests` | Soft delete |
| `EventLeaveTests` | Attendee leave, host cannot leave |
| `EventFavoritesTests` | Favorite/unfavorite |
| `APIEndpointsTests` | JSON responses |
| `DirectChatTests` | Chat listing |
| `ChatSendMessageTests` | Message posting |
| `APIChatMessagesTests` | Visitor forbidden |
| `JoinRequestFlowTests` | Full request flow |
| `EventDetailContextTests` | Template context |
| `EventIndexViewTests` | Redirect behavior |
| `CreateEventFormTests` | GET request, validation |
| `UpdateEventFormTests` | Edit page context |

### 11.2 Key Test Scenarios

- ✅ Event slug auto-generation
- ✅ Host membership created on event creation
- ✅ Location and invite deduplication
- ✅ Form validation (future datetime)
- ✅ PUBLIC_OPEN anyone can join
- ✅ PUBLIC_INVITE requires invite or request
- ✅ PRIVATE blocks direct join
- ✅ Cannot join event twice
- ✅ Accept/decline updates membership
- ✅ Chat retention limit (20 messages)
- ✅ Visitor cannot post messages
- ✅ Host can approve/decline requests
- ✅ Soft delete hides event
- ✅ Host cannot leave own event

---

## Appendix: Entity Relationship Diagram

```
                    ┌──────────────┐
                    │     User     │
                    └──────────────┘
                           │
         ┌─────────────────┼─────────────────────────┐
         │                 │                         │
         ▼                 ▼                         ▼
┌─────────────────┐ ┌─────────────────┐    ┌─────────────────┐
│     Event       │ │ EventMembership │    │ EventFavorite   │
│                 │ │  (event, user,  │    │ (event, user)   │
│  - host (FK)    │ │   role)         │    └─────────────────┘
│  - start_loc    │ └─────────────────┘
│  - visibility   │          │
└─────────────────┘          │
         │                   │
         ├───────────────────┼─────────────────┐
         │                   │                 │
         ▼                   ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ EventLocation   │ │   EventInvite   │ │EventJoinRequest │
│ (event, loc,    │ │ (event, invitee,│ │ (event,         │
│  order)         │ │  status)        │ │  requester)     │
└─────────────────┘ └─────────────────┘ └─────────────────┘

         │
         ├─────────────────────────────────────┐
         │                                     │
         ▼                                     ▼
┌─────────────────┐                   ┌─────────────────┐
│EventChatMessage │                   │   DirectChat    │
│ (event, author, │                   │ (event, user1,  │
│  message)       │                   │  user2)         │
└─────────────────┘                   └─────────────────┘
         │                                     │
         ▼                                     ▼
┌─────────────────┐                   ┌─────────────────┐
│ MessageReport   │                   │ DirectMessage   │
│ (message,       │                   │ (chat, sender,  │
│  reporter)      │                   │  content)       │
└─────────────────┘                   └─────────────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │ DirectChatLeave │
                                      │ (chat, user)    │
                                      └─────────────────┘
```

---

## Appendix: Quick Reference

### Creating an Event

```python
from events.services import create_event
from events.forms import EventForm

form = EventForm(request.POST)
if form.is_valid():
    event = create_event(
        host=request.user,
        form=form,
        locations=[101, 102],  # PublicArt IDs
        invites=[5, 10]        # User IDs
    )
```

### Checking User Role

```python
from events.selectors import user_role_in_event

role = user_role_in_event(event, request.user)
# Returns: 'HOST' | 'ATTENDEE' | 'VISITOR'
```

### Posting a Chat Message

```python
from events.services import post_chat_message

post_chat_message(
    event=event,
    user=request.user,
    message="Hello everyone!"
)
```

---

*End of Documentation*

