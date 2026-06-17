from django.contrib import messages
import random
import string
from django.core.mail import send_mail
from django.conf import settings
import re
from django.shortcuts import redirect
from django.urls import reverse




# ===========================================================================
# CONSTANTS
# ===========================================================================

COUNTRY_LIST = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Argentina",
    "Armenia", "Australia", "Austria", "Azerbaijan", "Bahrain", "Bangladesh",
    "Belarus", "Belgium", "Belize", "Benin", "Bolivia", "Bosnia and Herzegovina",
    "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi",
    "Cambodia", "Cameroon", "Canada", "Chad", "Chile", "China", "Colombia",
    "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czech Republic", "Denmark",
    "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Estonia",
    "Ethiopia", "Finland", "France", "Georgia", "Germany", "Ghana", "Greece",
    "Guatemala", "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia",
    "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan",
    "Kazakhstan", "Kenya", "Kuwait", "Latvia", "Lebanon", "Libya", "Lithuania",
    "Luxembourg", "Malaysia", "Mali", "Malta", "Mexico", "Moldova", "Mongolia",
    "Morocco", "Mozambique", "Myanmar", "Namibia", "Nepal", "Netherlands",
    "New Zealand", "Nicaragua", "Nigeria", "North Korea", "Norway", "Oman",
    "Pakistan", "Panama", "Paraguay", "Peru", "Philippines", "Poland",
    "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saudi Arabia",
    "Senegal", "Serbia", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
    "Somalia", "South Africa", "South Korea", "Spain", "Sri Lanka", "Sudan",
    "Sweden", "Switzerland", "Syria", "Taiwan", "Tanzania", "Thailand",
    "Tunisia", "Turkey", "Uganda", "Ukraine", "United Arab Emirates",
    "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Venezuela",
    "Vietnam", "Yemen", "Zambia", "Zimbabwe",
]

GENDER_CHOICES = ["male", "female", "other", "prefer_not_to_say"]


# ===========================================================================
# UTILITIES
# ===========================================================================

def generate_otp(length=6):
    return "".join(random.choices(string.digits, k=length))


def _obfuscate_email(email):
    """john.doe@gmail.com  →  ********@gmail.com"""
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return f"{'*' * len(local)}@{domain}"


def _login_required(request):
    """Returns True if user is authenticated, otherwise redirects and returns False."""
    if not request.user.is_authenticated:
        messages.error(request, "Please log in to access this page.")
        return False
    return True


# ===========================================================================
# EMAIL HELPERS
# ===========================================================================

def _send_mail_safe(subject, body, recipient):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient])
    except Exception:
        pass


def send_otp_email(email, otp, first_name):
    _send_mail_safe(
        "Your Account Verification OTP",
        f"Hello {first_name},\n\n"
        f"Your One-Time Password (OTP) for account verification is:\n\n"
        f"    {otp}\n\n"
        f"This OTP is valid for 10 minutes. Do not share it with anyone.\n\n"
        f"Regards,\nThe Team",
        email,
    )


def send_account_activated_email(email, first_name):
    _send_mail_safe(
        "Account Activated Successfully",
        f"Hello {first_name},\n\n"
        f"Congratulations! Your account has been successfully activated.\n"
        f"You can now log in and start using our platform.\n\n"
        f"Regards,\nThe Team",
        email,
    )


def _send_profile_updated_email(email, first_name):
    _send_mail_safe(
        "Profile Updated Successfully",
        f"Hello {first_name},\n\n"
        f"Your profile information has been updated successfully.\n"
        f"If you did not make this change, please contact support immediately.\n\n"
        f"Regards,\nThe Team",
        email,
    )


def _send_password_changed_email(email, first_name):
    _send_mail_safe(
        "Password Changed Successfully",
        f"Hello {first_name},\n\n"
        f"Your account password has been changed successfully.\n"
        f"You have been logged out. Please log in with your new password.\n\n"
        f"If you did not make this change, please reset your password immediately.\n\n"
        f"Regards,\nThe Team",
        email,
    )


def _send_email_change_otp(new_email, otp, first_name):
    _send_mail_safe(
        "Verify Your New Email Address",
        f"Hello {first_name},\n\n"
        f"You requested to change your account email to this address.\n\n"
        f"Your verification OTP is:\n\n"
        f"    {otp}\n\n"
        f"This OTP is valid for 10 minutes. Do not share it with anyone.\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"Regards,\nThe Team",
        new_email,
    )


def _send_email_change_notice_to_old(old_email, new_email, first_name):
    _send_mail_safe(
        "Email Address Change Requested",
        f"Hello {first_name},\n\n"
        f"A request to change the email address on your account to:\n\n"
        f"    {new_email}\n\n"
        f"has been initiated. An OTP has been sent to the new email for verification.\n"
        f"If you did not request this, please contact support immediately.\n\n"
        f"Regards,\nThe Team",
        old_email,
    )


def _send_email_change_success_old(old_email, new_email, first_name):
    _send_mail_safe(
        "Email Address Changed Successfully",
        f"Hello {first_name},\n\n"
        f"Your account email address has been successfully changed from:\n\n"
        f"    {old_email}\n\n"
        f"to:\n\n"
        f"    {new_email}\n\n"
        f"This email address is no longer associated with your account.\n"
        f"If you did not make this change, please contact support immediately.\n\n"
        f"Regards,\nThe Team",
        old_email,
    )


def _send_email_change_success_new(new_email, first_name):
    _send_mail_safe(
        "Welcome – Your Email is Now Active",
        f"Hello {first_name},\n\n"
        f"Your email address has been successfully verified and set as your account email.\n"
        f"You can now use this email address to log in.\n\n"
        f"Regards,\nThe Team",
        new_email,
    )


def _send_email_change_failure_email(old_email, new_email, first_name):
    body = (
        f"Hello {first_name},\n\n"
        f"The attempt to change your account email to:\n\n"
        f"    {new_email}\n\n"
        f"has failed because the verification OTP was not validated successfully.\n"
        f"Your account email remains unchanged.\n\n"
        f"If you did not initiate this request, please contact support.\n\n"
        f"Regards,\nThe Team"
    )
    _send_mail_safe("Email Change Failed", body, old_email)
    _send_mail_safe("Email Change Verification Failed", body, new_email)


def _send_reset_otp_email(email, otp, first_name):
    _send_mail_safe(
        "Password Reset OTP",
        f"Hello {first_name},\n\n"
        f"You requested a password reset for your account.\n\n"
        f"Your One-Time Password (OTP) is:\n\n"
        f"    {otp}\n\n"
        f"This OTP is valid for 10 minutes. Do not share it with anyone.\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"Regards,\nThe Team",
        email,
    )


def _send_recovery_failed_email(email, first_name):
    _send_mail_safe(
        "Security Alert – Account Recovery Failed",
        f"Hello {first_name},\n\n"
        f"We noticed multiple failed attempts to recover your account.\n"
        f"After exhausting all verification options, the recovery process\n"
        f"has been blocked for your protection.\n\n"
        f"If this was not you, your account is safe — no changes were made.\n"
        f"If you believe your account is at risk, please contact support.\n\n"
        f"Regards,\nThe Team",
        email,
    )


# ===========================================================================
# VALIDATION HELPERS  (return error string or None)
# ===========================================================================

def _validate_name(value, label):
    if not value or not value.strip():
        return f"{label} is required."
    if not re.match(r"^[A-Za-z\s\-']+$", value.strip()):
        return f"{label} must contain letters only."
    if len(value.strip()) < 2:
        return f"{label} must be at least 2 characters."
    return None


def _validate_email(value):
    if not value or not value.strip():
        return "Email address is required."
    if not re.match(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$", value.strip()):
        return "Enter a valid email address."
    return None


def _validate_phone(value):
    if not value or not value.strip():
        return "Phone number is required."
    cleaned = re.sub(r"[\s\-\(\)\+]", "", value.strip())
    if not cleaned.isdigit():
        return "Phone number must contain digits only."
    if len(cleaned) < 7 or len(cleaned) > 15:
        return "Phone number must be between 7 and 15 digits."
    return None


def _validate_country(value):
    if not value or not value.strip():
        return "Country is required."
    if value.strip() not in COUNTRY_LIST:
        return "Please select a valid country."
    return None


def _validate_gender(value):
    if not value or not value.strip():
        return "Gender is required."
    if value.strip() not in GENDER_CHOICES:
        return "Please select a valid gender."
    return None


def _validate_username(value):
    if not value or not value.strip():
        return "Username is required."
    if len(value.strip()) < 3:
        return "Username must be at least 3 characters."
    if len(value.strip()) > 150:
        return "Username must be at most 150 characters."
    if not re.match(r"^[\w.@+-]+$", value.strip()):
        return "Username may only contain letters, digits, and @/./+/-/_ characters."
    return None


def _validate_password(value, confirm):
    if not value:
        return "Password is required."
    if len(value) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", value):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", value):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"\d", value):
        return "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
        return "Password must contain at least one special character."
    if not confirm:
        return "Please confirm your password."
    if value != confirm:
        return "Passwords do not match."
    return None


# ===========================================================================
# CUSTOM AUTHENTICATION BACKEND (for phone-based login)
# ===========================================================================

class PhoneOrUsernameBackend:
    """
    Custom authentication backend that allows login via:
    - username (for staff/teachers/admins)
    - phone number (for parents/staff/teachers - not admins)

    For non-admin users, first looks up by phone_number, then by username.
    For admin users, only username is allowed.
    """

    def authenticate(self, request, username=None, password=None, phone=None, **kwargs):
        """
        Authenticate using username/phone + password.
        Returns CustomUser if authentication succeeds, None otherwise.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = None

        target = phone or username or ""
        cleaned_digits = re.sub(r"\D", "", target)
        phone_variations = [target]
        if cleaned_digits:
            phone_variations.append(cleaned_digits)
            if len(cleaned_digits) == 9:
                phone_variations.extend(["0" + cleaned_digits, "256" + cleaned_digits])
            elif len(cleaned_digits) == 10 and cleaned_digits.startswith("0"):
                phone_variations.extend([cleaned_digits[1:], "256" + cleaned_digits[1:]])
            elif len(cleaned_digits) == 12 and cleaned_digits.startswith("256"):
                phone_variations.extend([cleaned_digits[3:], "0" + cleaned_digits[3:]])
        phone_variations = list(set(phone_variations))

        # If a dedicated phone kwarg was passed, search by phone_number only
        if phone:
            user = User.objects.filter(
                phone__in=phone_variations,
                user_type__in=['parent', 'teacher', 'staff']
            ).first()

        elif username:
            # Try phone_number first (parents / staff / teachers)
            user = User.objects.filter(
                phone__in=phone_variations,
                user_type__in=['parent', 'teacher', 'staff']
            ).first()

            # Fall back to username lookup (covers admins too)
            if not user:
                user = User.objects.filter(username__iexact=username).first()

        # Verify password and active status
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None

    def user_can_authenticate(self, user):
        """Check if user can authenticate (must be active)."""
        return getattr(user, 'is_active', True)

    def get_user(self, user_id):
        """Retrieve a user by ID."""
        from .models import CustomUser
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None


# ===========================================================================
# FLOW HELPERS
# ===========================================================================

def _finalize_email_change_failure(request, user, old_email, new_email):
    """Send failure emails to both, reset is_email_verified, clear session."""
    _send_email_change_failure_email(old_email, new_email, user.first_name)
    user.is_email_verified = True
    user.save()
    for key in ("ce_new_email", "ce_old_email", "ce_otp", "ce_resend_count"):
        request.session.pop(key, None)


def _dispatch_reset_otp(request, email, username, first_name):
    otp = generate_otp()
    request.session["fp_otp"] = otp
    _send_reset_otp_email(email, otp, first_name)
    messages.success(request, "A 6-digit password reset OTP has been sent to your registered email. Please check your inbox.")
    return redirect(reverse("fp_enter_otp"))


def _handle_recovery_lockout(request, email, first_name):
    _send_recovery_failed_email(email, first_name)
    for key in ("fp_email", "fp_username", "fp_first_name", "fp_email_tries", "fp_user_tries", "fp_mode", "fp_otp"):
        request.session.pop(key, None)