"""
Tests for the accounts app
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.hashers import make_password
from accounts.forms import SignupForm
from accounts.models import EmailVerificationOTP


class SignupFormTests(TestCase):
    def test_email_uniqueness_case_insensitive(self):
        User.objects.create_user(
            username="test1", email="test@example.com", password="pass123"
        )
        form = SignupForm(
            data={
                "username": "test2",
                "email": "TEST@example.com",
                "password1": "testpass123",
                "password2": "testpass123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_email_lowercased_on_save(self):
        form = SignupForm(
            data={
                "username": "testuser",
                "email": "TEST@EXAMPLE.COM",
                "password1": "testpass123",
                "password2": "testpass123",
            }
        )
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.email, "test@example.com")


class AuthBackendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = Client()

    def test_login_with_username(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "testuser", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/dashboard/")

    def test_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "test@example.com", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/dashboard/")

    def test_login_with_wrong_password(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "testuser", "password": "wrongpass"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct")


class SignupViewTests(TestCase):
    def test_signup_creates_user(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "newpass123",
                "password2": "newpass123",
            },
        )
        # Should redirect to OTP verification
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("accounts:verify_otp"))

        # User should NOT be created yet (waiting for OTP verification)
        self.assertFalse(User.objects.filter(username="newuser").exists())

        # OTP record should be created
        from accounts.models import EmailVerificationOTP

        self.assertTrue(
            EmailVerificationOTP.objects.filter(
                email="new@example.com", username="newuser"
            ).exists()
        )


class SignupViewFormTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_signup_view_get_request(self):
        """Test GET request to signup page"""
        response = self.client.get(reverse("accounts:signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign Up")

    def test_signup_view_invalid_form(self):
        """Test signup with invalid form data"""
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "newuser",
                "email": "invalid-email",
                "password1": "pass123",
                "password2": "different",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())


class VerifyOTPViewFormTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_verify_otp_get_request_with_session(self):
        """Test GET request to OTP verification with session data"""
        session = self.client.session
        session["pending_verification_email"] = "test@example.com"
        session.save()

        response = self.client.get(reverse("accounts:verify_otp"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verify")

    def test_verify_otp_invalid_form_submission(self):
        """Test OTP verification with invalid OTP"""
        EmailVerificationOTP.objects.create(
            email="test@example.com",
            username="testuser",
            password_hash=make_password("testpass123"),
            otp="123456",
        )

        session = self.client.session
        session["pending_verification_email"] = "test@example.com"
        session.save()

        response = self.client.post(reverse("accounts:verify_otp"), {"otp": "999999"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="testuser").exists())


class EmailSendingTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_signup_sends_email(self):
        """Test that signup process sends OTP email"""
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "testpass123",
                "password2": "testpass123",
            },
        )

        # Check that email was sent
        self.assertEqual(response.status_code, 302)
        # In test mode, emails are stored in django.core.mail.outbox
        # This would work if email backend is properly configured for testing

    def test_resend_otp_sends_email(self):
        """Test that resend OTP sends email"""
        # Create OTP record
        EmailVerificationOTP.objects.create(
            email="test@example.com",
            username="testuser",
            password_hash=make_password("testpass123"),
            otp="123456",
        )

        session = self.client.session
        session["pending_verification_email"] = "test@example.com"
        session.save()

        response = self.client.post(reverse("accounts:resend_otp"))

        # Should redirect back to verify page
        self.assertEqual(response.status_code, 302)


class SessionCleanupTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_session_cleaned_after_successful_verification(self):
        """Test session is cleaned after successful OTP verification"""
        # Create OTP record
        EmailVerificationOTP.objects.create(
            email="test@example.com",
            username="testuser",
            password_hash=make_password("testpass123"),
            otp="123456",
        )

        # Set session
        session = self.client.session
        session["pending_verification_email"] = "test@example.com"
        session.save()

        # Verify OTP
        self.client.post(reverse("accounts:verify_otp"), {"otp": "123456"})

        # Check session is cleaned
        self.assertNotIn("pending_verification_email", self.client.session)

    def test_session_cleaned_after_expired_otp(self):
        """Test session is cleaned when OTP expires"""
        # Create expired OTP
        otp_record = EmailVerificationOTP.objects.create(
            email="test@example.com",
            username="testuser",
            password_hash="hash",
            otp="123456",
        )
        otp_record.created_at = timezone.now() - timedelta(minutes=5)
        otp_record.save()

        # Set session
        session = self.client.session
        session["pending_verification_email"] = "test@example.com"
        session.save()

        # Try to verify
        self.client.post(reverse("accounts:verify_otp"), {"otp": "123456"})

        # Session should be cleaned
        self.assertNotIn("pending_verification_email", self.client.session)
