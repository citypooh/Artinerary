from django.contrib import messages
from django.contrib.auth import logout, login
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.conf import settings
from .forms import SignupForm, EmailOrUsernameAuthenticationForm, OTPVerificationForm
from .models import EmailVerificationOTP


class SignupView(FormView):
    template_name = "accounts/signup.html"
    form_class = SignupForm
    success_url = reverse_lazy("accounts:verify_otp")

    def form_valid(self, form):
        # Don't create the user yet, store data in session and send OTP
        email = form.cleaned_data["email"]
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password1"]

        # Delete any existing unverified OTP for this email
        EmailVerificationOTP.objects.filter(email=email, is_verified=False).delete()

        # Create OTP record
        otp_record = EmailVerificationOTP.objects.create(
            email=email,
            username=username,
            password_hash=make_password(password),
        )

        # Send OTP via email
        self.send_otp_email(email, otp_record.otp)

        # Store email in session for OTP verification
        self.request.session["pending_verification_email"] = email

        messages.success(
            self.request,
            f"A verification code has been sent to {email}. "
            "Please verify within 3 minutes.",
        )
        return super().form_valid(form)

    def send_otp_email(self, email, otp):
        """Send OTP to user's email"""
        subject = "Verify Your Artinerary Account"
        message = f"""
        Welcome to Artinerary!

        Your verification code is: {otp}

        This code will expire in 3 minutes.

        If you didn't create an account with Artinerary, please ignore this email.
        """
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as e:
            # Log the error but don't fail the signup
            print(f"Error sending OTP email: {e}")


def verify_otp_view(request):
    """View to verify OTP"""
    email = request.session.get("pending_verification_email")

    if not email:
        messages.error(request, "No pending verification found. Please sign up again.")
        return redirect("accounts:signup")

    if request.method == "POST":
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data["otp"]

            try:
                otp_record = EmailVerificationOTP.objects.get(
                    email=email, otp=entered_otp, is_verified=False
                )

                if otp_record.is_expired():
                    messages.error(
                        request,
                        "OTP has expired. Please sign up again to receive a new code.",
                    )
                    otp_record.delete()
                    del request.session["pending_verification_email"]
                    return redirect("accounts:signup")

                # OTP is valid, create the user
                user = User.objects.create(
                    username=otp_record.username,
                    email=otp_record.email,
                    password=otp_record.password_hash,
                )

                # Mark OTP as verified
                otp_record.is_verified = True
                otp_record.save()

                # Log the user in
                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )

                # Clean up session
                del request.session["pending_verification_email"]

                messages.success(
                    request, "Email verified successfully! Welcome to Artinerary."
                )
                return redirect(settings.LOGIN_REDIRECT_URL)

            except EmailVerificationOTP.DoesNotExist:
                messages.error(request, "Invalid OTP. Please try again.")

    else:
        form = OTPVerificationForm()

    return render(request, "accounts/verify_otp.html", {"form": form, "email": email})


def resend_otp_view(request):
    """Resend OTP to user's email"""
    email = request.session.get("pending_verification_email")

    if not email:
        messages.error(request, "No pending verification found. Please sign up again.")
        return redirect("accounts:signup")

    # Get the latest unverified OTP record
    try:
        otp_record = EmailVerificationOTP.objects.filter(
            email=email, is_verified=False
        ).latest("created_at")

        # Generate new OTP
        otp_record.otp = EmailVerificationOTP.generate_otp()
        otp_record.save(update_fields=["otp"])

        # Send new OTP
        SignupView().send_otp_email(email, otp_record.otp)

        messages.success(
            request, "A new verification code has been sent to your email."
        )
    except EmailVerificationOTP.DoesNotExist:
        messages.error(request, "Verification session expired. Please sign up again.")
        return redirect("accounts:signup")

    return redirect("accounts:verify_otp")


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    form_class = EmailOrUsernameAuthenticationForm
    redirect_authenticated_user = True


def logout_view(request):
    """Handle both GET and POST logout"""
    # Set user as offline before logging out
    if request.user.is_authenticated:
        try:
            from messages.models import UserOnlineStatus

            status = UserOnlineStatus.objects.filter(user=request.user).first()
            if status:
                status.set_offline()
        except Exception:
            pass  # Don't fail logout if status update fails

    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("landing_page")
