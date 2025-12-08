"""
Views for the itineraries app
COMPLETE FIX - Gen-AI logic intact + cleaned_data check
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.forms import formset_factory
from .models import Itinerary, ItineraryStop
from .forms import ItineraryForm, ItineraryStopForm, ItineraryStopFormSet
from loc_detail.models import PublicArt


@login_required
def itinerary_list(request):
    """View for listing all user's itineraries"""
    from .models import ItineraryFavorite

    itineraries = Itinerary.objects.filter(user=request.user).prefetch_related(
        "stops", "stops__location"
    )

    # Get favorited itinerary IDs for this user
    favorited_ids = set(
        ItineraryFavorite.objects.filter(user=request.user).values_list(
            "itinerary_id", flat=True
        )
    )

    # Add is_favorited attribute to each itinerary
    for itinerary in itineraries:
        itinerary.is_favorited = itinerary.id in favorited_ids

    context = {
        "itineraries": itineraries,
        "is_favorites_view": False,
    }
    return render(request, "itineraries/list.html", context)


@login_required
def itinerary_detail(request, pk):
    """View for displaying a single itinerary"""
    from .models import ItineraryFavorite

    itinerary = get_object_or_404(
        Itinerary.objects.prefetch_related("stops", "stops__location"),
        pk=pk,
        user=request.user,
    )

    # Check if favorited
    is_favorited = ItineraryFavorite.objects.filter(
        itinerary=itinerary, user=request.user
    ).exists()

    context = {
        "itinerary": itinerary,
        "is_favorited": is_favorited,
    }
    return render(request, "itineraries/detail.html", context)


@login_required
def itinerary_create(request):
    """Create a new itinerary - Shows exact chatbot suggestions"""

    # Check for chatbot-suggested locations in session FIRST
    suggested_location_ids = request.session.get("chatbot_suggested_locations", [])
    initial_stops = []
    has_chatbot_suggestions = False

    if suggested_location_ids:
        num_locations = len(suggested_location_ids)
        print(f"Found {num_locations} chatbot-suggested locations in session")

        # Pre-populate with suggested locations
        for i, location_id in enumerate(suggested_location_ids):
            try:
                location = PublicArt.objects.get(id=location_id)
                initial_stops.append(
                    {
                        "location": location.id,
                        "order": i + 1,
                    }
                )
                print(f"  - Added location {i+1}: {location.title}")
            except PublicArt.DoesNotExist:
                print(f"  - Location ID {location_id} not found, skipping")
                continue

        has_chatbot_suggestions = True
        print(f"Total initial_stops prepared: {len(initial_stops)}")

    if request.method == "POST":
        form = ItineraryForm(request.POST)

        # Use same formset type for POST as we used in GET
        if has_chatbot_suggestions:
            DynamicStopFormSet = formset_factory(
                ItineraryStopForm,
                extra=0,
                can_delete=True,
                min_num=1,
                validate_min=False,
            )
            formset = DynamicStopFormSet(request.POST, prefix="stops")
        else:
            formset = ItineraryStopFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    itinerary = form.save(commit=False)
                    itinerary.user = request.user
                    itinerary.save()

                    stops_data = []
                    for form_instance in formset.forms:
                        if (
                            form_instance.cleaned_data
                            and not form_instance.cleaned_data.get("DELETE", False)
                        ):
                            location = form_instance.cleaned_data.get("location")
                            if location:
                                stops_data.append(
                                    {
                                        "location": location,
                                        "visit_time": (
                                            form_instance.cleaned_data.get("visit_time")
                                        ),
                                        "notes": (
                                            form_instance.cleaned_data.get("notes", "")
                                        ),
                                    }
                                )

                    for i, stop_data in enumerate(stops_data):
                        ItineraryStop.objects.create(
                            itinerary=itinerary,
                            location=stop_data["location"],
                            order=i + 1,
                            visit_time=stop_data["visit_time"],
                            notes=stop_data["notes"],
                        )

                    # Clear session after successful save
                    if "chatbot_suggested_locations" in request.session:
                        del request.session["chatbot_suggested_locations"]
                        request.session.modified = True

                    if has_chatbot_suggestions:
                        messages.success(
                            request,
                            f'Itinerary "{itinerary.title}" created '
                            f"successfully with your chatbot suggestions!",
                        )
                    else:
                        messages.success(
                            request,
                            f'Itinerary "{itinerary.title}" created ' f"successfully!",
                        )
                    return redirect("itineraries:detail", pk=itinerary.pk)
            except Exception as e:
                messages.error(request, f"Error creating itinerary: {str(e)}")
        else:
            if not form.is_valid():
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
            if not formset.is_valid():
                for i, form_errors in enumerate(formset.errors):
                    for field, errors in form_errors.items():
                        for error in errors:
                            messages.error(request, f"Stop {i+1} - {field}: {error}")
    else:
        form = ItineraryForm()

        if initial_stops:
            print(f"Creating formset for {len(initial_stops)} " f"chatbot suggestions")

            DynamicStopFormSet = formset_factory(
                ItineraryStopForm,
                extra=0,
                can_delete=True,
                min_num=1,
                validate_min=False,
            )

            formset = DynamicStopFormSet(initial=initial_stops, prefix="stops")

            print(f"  Formset created with {len(formset.forms)} forms")

            messages.info(
                request,
                f"We've pre-filled {len(initial_stops)} locations "
                f"from your chatbot conversation. "
                f"You can edit, reorder, or add more locations below.",
            )
        else:
            formset = ItineraryStopFormSet()

    locations = PublicArt.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).order_by("title")

    context = {
        "form": form,
        "formset": formset,
        "locations": locations,
        "is_edit": False,
        "has_chatbot_suggestions": has_chatbot_suggestions,
    }
    return render(request, "itineraries/create_improved.html", context)


@login_required
def itinerary_edit(request, pk):
    """View for editing an existing itinerary - COMPLETE FIX"""
    itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)

    if request.method == "POST":
        form = ItineraryForm(request.POST, instance=itinerary)
        formset = ItineraryStopFormSet(request.POST, instance=itinerary)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Save the itinerary form
                    form.save()

                    # Collect new stops data
                    new_stops_data = []

                    for form_instance in formset.forms:
                        # CRITICAL FIX: Check if cleaned_data exists first
                        if not hasattr(form_instance, "cleaned_data"):
                            continue
                        if not form_instance.cleaned_data:
                            continue

                        # Skip if marked for deletion
                        if form_instance.cleaned_data.get("DELETE", False):
                            continue

                        # Only process if has location
                        location = form_instance.cleaned_data.get("location")
                        if location:
                            new_stops_data.append(
                                {
                                    "location": location,
                                    "visit_time": (
                                        form_instance.cleaned_data.get("visit_time")
                                    ),
                                    "notes": (
                                        form_instance.cleaned_data.get("notes", "")
                                    ),
                                }
                            )

                    # Delete ALL existing stops
                    itinerary.stops.all().delete()

                    # Recreate stops with new sequential ordering
                    for i, stop_data in enumerate(new_stops_data):
                        ItineraryStop.objects.create(
                            itinerary=itinerary,
                            location=stop_data["location"],
                            order=i + 1,
                            visit_time=stop_data["visit_time"],
                            notes=stop_data["notes"],
                        )

                    messages.success(
                        request,
                        f'Itinerary "{itinerary.title}" updated ' f"successfully!",
                    )
                    return redirect("itineraries:detail", pk=itinerary.pk)
            except Exception as e:
                messages.error(request, f"Error updating itinerary: {str(e)}")
        else:
            if not form.is_valid():
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
            if not formset.is_valid():
                for i, form_errors in enumerate(formset.errors):
                    for field, errors in form_errors.items():
                        for error in errors:
                            messages.error(request, f"Stop {i+1} - {field}: {error}")
    else:
        form = ItineraryForm(instance=itinerary)
        formset = ItineraryStopFormSet(instance=itinerary)

    locations = PublicArt.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).order_by("title")

    context = {
        "form": form,
        "formset": formset,
        "locations": locations,
        "itinerary": itinerary,
        "is_edit": True,
    }
    return render(request, "itineraries/create_improved.html", context)


@login_required
def itinerary_delete(request, pk):
    """View for deleting an itinerary"""
    itinerary = get_object_or_404(Itinerary, pk=pk, user=request.user)

    if request.method == "POST":
        title = itinerary.title
        itinerary.delete()
        messages.success(request, f'Itinerary "{title}" deleted successfully!')
        return redirect("itineraries:list")

    context = {
        "itinerary": itinerary,
    }
    return render(request, "itineraries/delete_confirm.html", context)


@login_required
def api_search_locations(request):
    """API endpoint for searching locations"""
    query = request.GET.get("q", "").strip()

    if len(query) < 2:
        return JsonResponse({"results": []})

    locations = PublicArt.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).filter(title__icontains=query)[:20]

    results = [
        {
            "id": loc.id,
            "title": loc.title or "Untitled",
            "artist": loc.artist_name or "Unknown",
            "borough": loc.borough or "",
            "location": loc.location or "",
        }
        for loc in locations
    ]

    return JsonResponse({"results": results})


@login_required
def api_get_user_itineraries(request):
    """API endpoint for getting user's itineraries"""
    itineraries = Itinerary.objects.filter(user=request.user).order_by("-created_at")

    results = [
        {
            "id": itin.id,
            "title": itin.title,
            "stop_count": itin.stops.count(),
        }
        for itin in itineraries
    ]

    return JsonResponse({"itineraries": results})


@login_required
@require_POST
def api_add_to_itinerary(request):
    """API endpoint for adding a location to an itinerary"""
    try:
        location_id = request.POST.get("location_id")
        itinerary_id = request.POST.get("itinerary_id")
        new_itinerary_title = request.POST.get("new_itinerary_title")

        location = get_object_or_404(PublicArt, id=location_id)

        if new_itinerary_title:
            itinerary = Itinerary.objects.create(
                user=request.user, title=new_itinerary_title.strip()
            )
            order = 1
        elif itinerary_id:
            itinerary = get_object_or_404(Itinerary, id=itinerary_id, user=request.user)
            last_stop = itinerary.stops.order_by("-order").first()
            order = (last_stop.order + 1) if last_stop else 1
        else:
            return JsonResponse(
                {"success": False, "error": "No itinerary specified"}, status=400
            )

        if ItineraryStop.objects.filter(
            itinerary=itinerary, location=location
        ).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": (f"This location is already in {itinerary.title}"),
                },
                status=400,
            )

        ItineraryStop.objects.create(
            itinerary=itinerary, location=location, order=order
        )

        return JsonResponse(
            {
                "success": True,
                "message": f"Added to {itinerary.title}",
                "itinerary_id": itinerary.id,
                "itinerary_url": itinerary.get_absolute_url(),
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_POST
def favorite_itinerary(request, pk):
    """Add itinerary to user's favorites"""
    from .models import ItineraryFavorite

    itinerary = get_object_or_404(Itinerary, pk=pk)

    try:
        ItineraryFavorite.objects.get_or_create(itinerary=itinerary, user=request.user)
        messages.success(request, f'Added "{itinerary.title}" to favorites.')
    except Exception as e:
        messages.error(request, f"Failed to add to favorites: {str(e)}")

    return redirect(request.META.get("HTTP_REFERER", itinerary.get_absolute_url()))


@login_required
@require_POST
def unfavorite_itinerary(request, pk):
    """Remove itinerary from user's favorites"""
    from .models import ItineraryFavorite

    itinerary = get_object_or_404(Itinerary, pk=pk)

    try:
        deleted_count, _ = ItineraryFavorite.objects.filter(
            itinerary=itinerary, user=request.user
        ).delete()

        if deleted_count > 0:
            messages.success(request, f'Removed "{itinerary.title}" from favorites.')
        else:
            messages.info(request, "This itinerary was not in your favorites.")
    except Exception as e:
        messages.error(request, f"Failed to remove from favorites: {str(e)}")

    return redirect(request.META.get("HTTP_REFERER", itinerary.get_absolute_url()))


@login_required
def favorites(request):
    """Display user's favorite itineraries"""
    from .models import ItineraryFavorite

    favorites_qs = (
        ItineraryFavorite.objects.filter(user=request.user)
        .select_related("itinerary", "itinerary__user")
        .prefetch_related("itinerary__stops", "itinerary__stops__location")
        .order_by("-created_at")
    )

    favorites_list = []
    for fav in favorites_qs:
        fav.itinerary.favorited_at = fav.created_at
        favorites_list.append(fav.itinerary)

    context = {
        "itineraries": favorites_list,
        "is_favorites_view": True,
    }

    return render(request, "itineraries/favorites.html", context)


@login_required
def create_event_from_itinerary(request, pk):
    """Create an event from an existing itinerary"""
    from events.forms import EventForm, parse_locations, parse_invites
    from events.services import create_event
    from datetime import datetime, time
    from django.utils import timezone as django_timezone

    itinerary = get_object_or_404(
        Itinerary.objects.prefetch_related("stops", "stops__location"),
        pk=pk,
        user=request.user,
    )

    # Check if itinerary has any stops
    if not itinerary.stops.exists():
        messages.error(
            request,
            "Cannot create an event from an empty itinerary. "
            "Please add locations first.",
        )
        return redirect("itineraries:detail", pk=pk)

    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            try:
                # Get additional locations from the form
                locations = parse_locations(request)
                invites = parse_invites(request)

                # Create the event
                event = create_event(
                    host=request.user, form=form, locations=locations, invites=invites
                )

                messages.success(
                    request,
                    f'Event "{event.title}" created successfully '
                    f'from itinerary "{itinerary.title}"!',
                )
                return redirect(event.get_absolute_url())

            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
        
        # If form is invalid, we still need to set these for template rendering
        first_stop = itinerary.stops.first()
        first_location = first_stop.location if first_stop else None
        first_location_id = first_location.id if first_location else None
    else:
        # Pre-populate form with itinerary data
        initial_data = {
            "title": itinerary.title,
            "description": (
                itinerary.description if itinerary.description else ""
            ),
            "visibility": "PUBLIC_OPEN",  # Default to public
        }

        # Get first stop for location and time
        first_stop = itinerary.stops.first()
        first_location = first_stop.location if first_stop else None
        first_location_id = first_location.id if first_location else None
        
        if first_stop and first_stop.location:
            # Verify the location has valid coordinates
            if first_stop.location.latitude and first_stop.location.longitude:
                # Set the location ID for the form initial value
                initial_data["start_location"] = first_location_id
            
            # If itinerary has a date, convert it to datetime
            if itinerary.date:
                # Use visit_time from first stop if available, otherwise noon
                visit_time = first_stop.visit_time if first_stop.visit_time else time(12, 0)
                dt = datetime.combine(itinerary.date, visit_time)
                # Make it timezone-aware
                initial_data["start_time"] = django_timezone.make_aware(dt)

        form = EventForm(initial=initial_data)
        
        # Explicitly set the field value after form instantiation
        if first_location_id:
            form.fields["start_location"].initial = first_location_id

    # Get all locations for the dropdown (only those with valid coordinates)
    all_locations = PublicArt.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).order_by("title")
    
    # Ensure first_location is in the available locations
    # If the first stop's location doesn't have coordinates, find the first one that does
    if first_location and first_location_id:
        if not all_locations.filter(id=first_location_id).exists():
            # First location doesn't have coordinates, find first stop that does
            print(f"DEBUG: First location ID {first_location_id} ({first_location.title}) doesn't have valid coordinates")
            first_location = None
            first_location_id = None
            for stop in itinerary.stops.all():
                if stop.location.latitude and stop.location.longitude:
                    first_location = stop.location
                    first_location_id = stop.location.id
                    print(f"DEBUG: Using alternative first location: {first_location.title} (ID: {first_location_id})")
                    break

    # Get locations from itinerary (excluding the first one as it's the start)
    itinerary_locations = []
    for stop in itinerary.stops.all()[1:]:  # Skip first stop
        itinerary_locations.append(
            {"id": stop.location.id, "title": stop.location.title}
        )

    context = {
        "form": form,
        "locations": all_locations,
        "itinerary": itinerary,
        "itinerary_locations": itinerary_locations,
        "first_location": first_location,
        "first_location_id": first_location_id,
        "from_itinerary": True,
    }
    
    # DEBUG: Print what we're passing
    print(f"DEBUG: first_location = {first_location}")
    print(f"DEBUG: first_location_id = {first_location_id}")
    if first_location:
        print(f"DEBUG: first_location.id = {first_location.id}")
        print(f"DEBUG: first_location.title = {first_location.title}")

    return render(request, "itineraries/create_event_from_itinerary.html", context)
