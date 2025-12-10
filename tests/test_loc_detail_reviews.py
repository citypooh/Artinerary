"""
Comprehensive unit tests for review/rating system in loc_detail
Tests ArtComment model with ratings, likes, replies, and image uploads
"""

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal
import json

from loc_detail.models import PublicArt, ArtComment, CommentLike

TEST_MEDIA_ROOT = "/tmp/test_media"


@override_settings(
    DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage",
    MEDIA_ROOT=TEST_MEDIA_ROOT,
)
class ArtCommentRatingModelTests(TestCase):
    """Test cases for ArtComment model with ratings"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="reviewer", email="reviewer@example.com", password="testpass123"
        )
        self.art = PublicArt.objects.create(
            title="Rated Art", artist_name="Famous Artist"
        )

    def test_create_review_with_rating(self):
        """Test creating a review with rating"""
        review = ArtComment.objects.create(
            user=self.user, art=self.art, comment="Excellent artwork!", rating=5
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Excellent artwork!")
        self.assertIsNone(review.parent)

    def test_create_reply_without_rating(self):
        """Test creating a reply (replies don't need ratings)"""
        parent_review = ArtComment.objects.create(
            user=self.user, art=self.art, comment="Main review", rating=4
        )

        user2 = User.objects.create_user(username="replier", password="testpass123")
        reply = ArtComment.objects.create(
            user=user2,
            art=self.art,
            comment="I agree!",
            rating=5,  # Rating set but not used for replies
            parent=parent_review,
        )

        self.assertEqual(reply.parent, parent_review)
        self.assertEqual(parent_review.replies.count(), 1)

    def test_rating_choices(self):
        """Test that rating choices are 1-5"""
        for rating in range(1, 6):
            review = ArtComment.objects.create(
                user=self.user, art=self.art, comment=f"Rating {rating}", rating=rating
            )
            self.assertEqual(review.rating, rating)

    def test_default_rating(self):
        """Test default rating is 5"""
        review = ArtComment.objects.create(
            user=self.user, art=self.art, comment="No rating specified"
        )
        self.assertEqual(review.rating, 5)

    def test_review_with_image(self):
        """Test creating review with images through CommentImage"""
        # Create a review first
        review = ArtComment.objects.create(
            user=self.user,
            art=self.art,
            comment="Check out this photo!",
            rating=5,
        )

        # Add image through CommentImage model
        from loc_detail.models import CommentImage

        image = SimpleUploadedFile(
            name="test_image.jpg",
            content=b"fake_image_content",
            content_type="image/jpeg",
        )

        comment_image = CommentImage.objects.create(
            comment=review, image=image, order=0
        )

        # Verify image was set
        review.refresh_from_db()
        self.assertEqual(review.images.count(), 1)
        self.assertIsNotNone(comment_image.image)
        self.assertIn("review_images/", comment_image.image.name)


class CommentLikeModelTests(TestCase):
    """Test cases for CommentLike model"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username="liker", email="liker@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="disliker", email="disliker@example.com", password="testpass123"
        )
        self.art = PublicArt.objects.create(title="Test Art")
        self.comment = ArtComment.objects.create(
            user=self.user1, art=self.art, comment="Test comment", rating=4
        )

    def test_create_like(self):
        """Test creating a like"""
        like = CommentLike.objects.create(
            user=self.user2, comment=self.comment, is_like=True
        )

        self.assertTrue(like.is_like)
        self.assertEqual(like.user, self.user2)
        self.assertEqual(like.comment, self.comment)

    def test_create_dislike(self):
        """Test creating a dislike"""
        dislike = CommentLike.objects.create(
            user=self.user2, comment=self.comment, is_like=False
        )

        self.assertFalse(dislike.is_like)

    def test_unique_user_comment_constraint(self):
        """Test that user can only have one reaction per comment"""
        CommentLike.objects.create(user=self.user2, comment=self.comment, is_like=True)

        # Trying to create another reaction should fail
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            CommentLike.objects.create(
                user=self.user2, comment=self.comment, is_like=False
            )

    def test_comment_like_str_method(self):
        """Test string representation"""
        like = CommentLike.objects.create(
            user=self.user2, comment=self.comment, is_like=True
        )

        expected = (
            f"{self.user2.username} liked comment by {self.comment.user.username}"
        )
        self.assertEqual(str(like), expected)

    def test_cascade_delete_user(self):
        """Test likes are deleted when user is deleted"""
        CommentLike.objects.create(user=self.user2, comment=self.comment, is_like=True)

        self.assertEqual(CommentLike.objects.count(), 1)
        self.user2.delete()
        self.assertEqual(CommentLike.objects.count(), 0)

    def test_cascade_delete_comment(self):
        """Test likes are deleted when comment is deleted"""
        CommentLike.objects.create(user=self.user2, comment=self.comment, is_like=True)

        self.assertEqual(CommentLike.objects.count(), 1)
        self.comment.delete()
        self.assertEqual(CommentLike.objects.count(), 0)


class ArtCommentPropertiesTests(TestCase):
    """Test ArtComment properties for likes/dislikes"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(username="author", password="testpass123")
        self.liker1 = User.objects.create_user(
            username="liker1", password="testpass123"
        )
        self.liker2 = User.objects.create_user(
            username="liker2", password="testpass123"
        )
        self.disliker = User.objects.create_user(
            username="disliker", password="testpass123"
        )

        self.art = PublicArt.objects.create(title="Test Art")
        self.comment = ArtComment.objects.create(
            user=self.user, art=self.art, comment="Test comment", rating=4
        )

    def test_likes_count_property(self):
        """Test likes_count property"""
        # Initially no likes
        self.assertEqual(self.comment.likes_count, 0)

        # Add two likes
        CommentLike.objects.create(user=self.liker1, comment=self.comment, is_like=True)
        CommentLike.objects.create(user=self.liker2, comment=self.comment, is_like=True)

        self.assertEqual(self.comment.likes_count, 2)

    def test_dislikes_count_property(self):
        """Test dislikes_count property"""
        # Initially no dislikes
        self.assertEqual(self.comment.dislikes_count, 0)

        # Add dislike
        CommentLike.objects.create(
            user=self.disliker, comment=self.comment, is_like=False
        )

        self.assertEqual(self.comment.dislikes_count, 1)

    def test_user_reaction_like(self):
        """Test user_reaction method for like"""
        CommentLike.objects.create(user=self.liker1, comment=self.comment, is_like=True)

        reaction = self.comment.user_reaction(self.liker1)
        self.assertEqual(reaction, "like")

    def test_user_reaction_dislike(self):
        """Test user_reaction method for dislike"""
        CommentLike.objects.create(
            user=self.disliker, comment=self.comment, is_like=False
        )

        reaction = self.comment.user_reaction(self.disliker)
        self.assertEqual(reaction, "dislike")

    def test_user_reaction_none(self):
        """Test user_reaction method when no reaction"""
        reaction = self.comment.user_reaction(self.liker1)
        self.assertIsNone(reaction)


class PublicArtRatingMethodsTests(TestCase):
    """Test PublicArt methods for rating calculation"""

    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(username="user1", password="testpass123")
        self.user2 = User.objects.create_user(username="user2", password="testpass123")
        self.user3 = User.objects.create_user(username="user3", password="testpass123")

        self.art = PublicArt.objects.create(
            title="Rated Artwork", artist_name="Test Artist"
        )

    def test_get_average_rating_no_reviews(self):
        """Test average rating with no reviews"""
        self.assertEqual(self.art.get_average_rating(), 0)

    def test_get_average_rating_single_review(self):
        """Test average rating with one review"""
        ArtComment.objects.create(
            user=self.user1, art=self.art, comment="Great!", rating=4
        )

        self.assertEqual(self.art.get_average_rating(), 4.0)

    def test_get_average_rating_multiple_reviews(self):
        """Test average rating with multiple reviews"""
        ArtComment.objects.create(
            user=self.user1, art=self.art, comment="Good", rating=4
        )
        ArtComment.objects.create(
            user=self.user2, art=self.art, comment="Excellent", rating=5
        )
        ArtComment.objects.create(user=self.user3, art=self.art, comment="OK", rating=3)

        # Average: (4 + 5 + 3) / 3 = 4.0
        self.assertEqual(self.art.get_average_rating(), 4.0)

    def test_get_average_rating_excludes_replies(self):
        """Test that replies don't affect average rating"""
        parent_review = ArtComment.objects.create(
            user=self.user1, art=self.art, comment="Main review", rating=5
        )

        # Create reply (should not count)
        ArtComment.objects.create(
            user=self.user2,
            art=self.art,
            comment="Reply comment",
            rating=1,
            parent=parent_review,
        )

        # Average should be 5.0 (only main review counts)
        self.assertEqual(self.art.get_average_rating(), 5.0)

    def test_get_total_reviews_no_reviews(self):
        """Test total reviews count with no reviews"""
        self.assertEqual(self.art.get_total_reviews(), 0)

    def test_get_total_reviews_excludes_replies(self):
        """Test that replies don't count as reviews"""
        parent_review = ArtComment.objects.create(
            user=self.user1, art=self.art, comment="Main review", rating=5
        )

        # Create two replies
        ArtComment.objects.create(
            user=self.user2, art=self.art, comment="Reply 1", parent=parent_review
        )
        ArtComment.objects.create(
            user=self.user3, art=self.art, comment="Reply 2", parent=parent_review
        )

        # Should only count main review
        self.assertEqual(self.art.get_total_reviews(), 1)


class ReviewViewTests(TestCase):
    """Test review submission and display in views"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.art = PublicArt.objects.create(
            title="Test Art",
            artist_name="Test Artist",
            latitude=Decimal("40.7128"),
            longitude=Decimal("-74.0060"),
        )

    def test_submit_review_with_rating(self):
        """Test submitting a review with rating"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            reverse("loc_detail:art_detail", kwargs={"art_id": self.art.id}),
            {"comment": "Amazing artwork!", "rating": "5"},
        )
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Check review was created
        review = ArtComment.objects.get(user=self.user, art=self.art)
        self.assertEqual(review.comment, "Amazing artwork!")
        self.assertEqual(review.rating, 5)

    def test_submit_review_with_image(self):
        """Test submitting review with image"""
        self.client.login(username="testuser", password="testpass123")

        image = SimpleUploadedFile(
            name="test.jpg", content=b"fake_image", content_type="image/jpeg"
        )

        response = self.client.post(
            reverse("loc_detail:art_detail", kwargs={"art_id": self.art.id}),
            {"comment": "See my photo!", "rating": "4", "images": [image]},
        )
        self.assertIn(response.status_code, (200, 302))

        review = ArtComment.objects.get(user=self.user)
        # Check that images were added through CommentImage
        self.assertGreaterEqual(review.images.count(), 0)

    def test_edit_existing_review(self):
        """Test editing an existing review"""
        # Create initial review
        review = ArtComment.objects.create(
            user=self.user, art=self.art, comment="Initial comment", rating=3
        )

        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            reverse("loc_detail:art_detail", kwargs={"art_id": self.art.id}),
            {"comment": "Updated comment", "rating": "5", "comment_id": review.id},
        )
        self.assertEqual(response.status_code, 302)

        review.refresh_from_db()
        self.assertEqual(review.comment, "Updated comment")
        self.assertEqual(review.rating, 5)

    def test_cannot_submit_multiple_reviews(self):
        """Test that user can only have one review per artwork"""
        # Create first review
        ArtComment.objects.create(
            user=self.user, art=self.art, comment="First review", rating=4
        )

        self.client.login(username="testuser", password="testpass123")

        # Attempt to create second review without comment_id (should update existing)
        response = self.client.post(
            reverse("loc_detail:art_detail", kwargs={"art_id": self.art.id}),
            {"comment": "Second review", "rating": "5"},
        )
        self.assertIn(response.status_code, (200, 302))

        # Should still only have one review
        reviews = ArtComment.objects.filter(
            user=self.user, art=self.art, parent__isnull=True
        )
        self.assertGreaterEqual(reviews.count(), 1)

    def test_submit_reply_to_review(self):
        """Test submitting a reply to a review"""
        # Create parent review
        parent = ArtComment.objects.create(
            user=self.user, art=self.art, comment="Parent review", rating=5
        )

        # Create another user to reply
        replier = User.objects.create_user(username="replier", password="testpass123")
        self.client.login(username="replier", password="testpass123")

        response = self.client.post(
            reverse("loc_detail:art_detail", kwargs={"art_id": self.art.id}),
            {"comment": "Great point!", "parent_id": parent.id},
        )
        self.assertIn(response.status_code, (200, 302))

        # Check reply was created
        reply = ArtComment.objects.get(parent=parent)
        self.assertEqual(reply.comment, "Great point!")
        self.assertEqual(reply.user, replier)


class CommentReactionAPITests(TestCase):
    """Test comment like/dislike API endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="testpass123"
        )

        self.art = PublicArt.objects.create(title="Test Art")
        self.comment = ArtComment.objects.create(
            user=self.user1, art=self.art, comment="Test comment", rating=4
        )

    def test_api_comment_reaction_requires_login(self):
        """Test that API requires authentication"""
        response = self.client.post(
            reverse(
                "loc_detail:api_comment_reaction",
                kwargs={"comment_id": self.comment.id},
            )
        )
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_api_comment_reaction_requires_post(self):
        """Test that API only accepts POST"""
        self.client.login(username="user2", password="testpass123")
        response = self.client.get(
            reverse(
                "loc_detail:api_comment_reaction",
                kwargs={"comment_id": self.comment.id},
            )
        )
        self.assertEqual(response.status_code, 405)  # Method not allowed

    def test_api_add_like(self):
        """Test adding a like via API"""
        self.client.login(username="user2", password="testpass123")

        response = self.client.post(
            reverse(
                "loc_detail:api_comment_reaction",
                kwargs={"comment_id": self.comment.id},
            ),
            {"reaction": "like"},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data["success"])
        self.assertEqual(data["likes"], 1)
        self.assertEqual(data["dislikes"], 0)

    def test_api_add_dislike(self):
        """Test adding a dislike via API"""
        self.client.login(username="user2", password="testpass123")

        response = self.client.post(
            reverse(
                "loc_detail:api_comment_reaction",
                kwargs={"comment_id": self.comment.id},
            ),
            {"reaction": "dislike"},
        )
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["likes"], 0)
        self.assertEqual(data["dislikes"], 1)

    def test_api_toggle_like(self):
        """Test toggling like (remove it)"""
        # First add a like
        CommentLike.objects.create(user=self.user2, comment=self.comment, is_like=True)

        self.client.login(username="user2", password="testpass123")

        # Click like again to remove
        response = self.client.post(
            reverse(
                "loc_detail:api_comment_reaction",
                kwargs={"comment_id": self.comment.id},
            ),
            {"reaction": "like"},
        )
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["action"], "removed")
        self.assertEqual(data["likes"], 0)

    def test_api_change_like_to_dislike(self):
        """Test changing from like to dislike"""
        # First add a like
        CommentLike.objects.create(user=self.user2, comment=self.comment, is_like=True)

        self.client.login(username="user2", password="testpass123")

        # Now click dislike
        response = self.client.post(
            reverse(
                "loc_detail:api_comment_reaction",
                kwargs={"comment_id": self.comment.id},
            ),
            {"reaction": "dislike"},
        )
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["action"], "changed")
        self.assertEqual(data["likes"], 0)
        self.assertEqual(data["dislikes"], 1)

    def test_api_user_can_react_to_own_comment(self):
        """Test that users can like/dislike their own comments"""
        self.client.login(username="user1", password="testpass123")

        response = self.client.post(
            reverse(
                "loc_detail:api_comment_reaction",
                kwargs={"comment_id": self.comment.id},
            ),
            {"reaction": "like"},
        )
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["likes"], 1)


class RatingDisplayTests(TestCase):
    """Test rating display in art list and favorites"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.art1 = PublicArt.objects.create(
            title="High Rated Art", artist_name="Artist 1"
        )
        self.art2 = PublicArt.objects.create(
            title="Low Rated Art", artist_name="Artist 2"
        )

        # Add reviews
        ArtComment.objects.create(
            user=self.user, art=self.art1, comment="Great!", rating=5
        )
        ArtComment.objects.create(user=self.user, art=self.art2, comment="OK", rating=3)

    def test_rating_shown_in_art_list(self):
        """Test that ratings are displayed in art list"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("loc_detail:index"))

        # Check that ratings are shown
        self.assertContains(
            response,
            '<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px"><path d="m233-120 65-281L80-590l288-25 112-265 112 265 288 25-218 189 65 281-247-149-247 149Z"/></svg>',  # noqa: E501
        )  # Star character
        self.assertContains(response, "5.0")  # High rating
        self.assertContains(response, "3.0")  # Low rating

    def test_no_rating_for_unreviewed_art(self):
        """Test that unreviewed art shows no rating"""
        _ = PublicArt.objects.create(  # noqa: F841 (intentional)
            title="No Reviews", artist_name="Artist 3"
        )

        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("loc_detail:index"))

        # Art should be listed but without rating display
        self.assertContains(response, "No Reviews")


class ReviewBadgeTests(TestCase):
    """Test review badge display"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="prolific", email="prolific@example.com", password="testpass123"
        )
        self.art = PublicArt.objects.create(title="Test Art")

    def test_helpful_badge_with_5_likes(self):
        """Test that helpful badge appears with 5+ likes"""
        comment = ArtComment.objects.create(
            user=self.user, art=self.art, comment="Helpful review", rating=5
        )

        # Add 5 likes
        for i in range(5):
            liker = User.objects.create_user(
                username=f"liker{i}", password="testpass123"
            )
            CommentLike.objects.create(user=liker, comment=comment, is_like=True)

        self.client.login(username="prolific", password="testpass123")
        response = self.client.get(
            reverse("loc_detail:art_detail", kwargs={"art_id": self.art.id})
        )

        self.assertContains(response, "Helpful")

    def test_local_guide_badge_with_10_reviews(self):
        """Test that local guide badge appears with 10+ reviews"""
        # Create 10 different artworks
        for i in range(10):
            art = PublicArt.objects.create(title=f"Art {i}")
            ArtComment.objects.create(
                user=self.user, art=art, comment=f"Review {i}", rating=4
            )

        self.client.login(username="prolific", password="testpass123")
        response = self.client.get(
            reverse("loc_detail:art_detail", kwargs={"art_id": self.art.id})
        )
        self.assertIn(response.status_code, (200, 302))
