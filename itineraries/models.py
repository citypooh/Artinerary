"""
Models for the itineraries app
"""

from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from loc_detail.models import PublicArt


class Itinerary(models.Model):
    """Model representing a user's itinerary"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="itineraries")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    date = models.DateField(
        blank=True, null=True, help_text="Planned date for this itinerary"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Itineraries"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "title"], name="unique_user_itinerary_title"
            )
        ]

    def __str__(self):
        return f"{self.title} by {self.user.username}"

    def get_absolute_url(self):
        return reverse("itineraries:detail", kwargs={"pk": self.pk})


class ItineraryStop(models.Model):
    """Model representing a stop in an itinerary"""

    itinerary = models.ForeignKey(
        Itinerary, on_delete=models.CASCADE, related_name="stops"
    )
    location = models.ForeignKey(
        PublicArt, on_delete=models.CASCADE, related_name="itinerary_stops"
    )
    order = models.PositiveIntegerField(default=0)
    visit_time = models.TimeField(
        blank=True, null=True, help_text="Planned visit time for this location"
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["order"]
        unique_together = ["itinerary", "order"]

    def __str__(self):
        return f"{self.itinerary.title} - Stop {self.order}: {self.location.title}"


class ItineraryFavorite(models.Model):
    """Tracks user's favorited itineraries"""

    itinerary = models.ForeignKey(
        Itinerary, on_delete=models.CASCADE, related_name="favorited_by"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="favorite_itineraries"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["itinerary", "user"], name="uniq_itinerary_favorite"
            )
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["itinerary"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} favorited {self.itinerary.title}"
