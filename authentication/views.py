import re
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash


from django.urls import reverse

from .models import CustomUser

from .utils import (

    # ===========================================================================
    # CONSTANTS
    # ===========================================================================
    COUNTRY_LIST,
    GENDER_CHOICES,

    # ===========================================================================
    # UTILITIES
    # ===========================================================================
    generate_otp,
    _obfuscate_email,
    _login_required,

    # ===========================================================================
    # EMAIL HELPERS
    # ===========================================================================
    # _send_mail_safe,
    send_otp_email,
    send_account_activated_email,
    _send_profile_updated_email,
    _send_password_changed_email,
    _send_email_change_otp,
    _send_email_change_notice_to_old,
    _send_email_change_success_old,
    _send_email_change_success_new,
    # _send_email_change_failure_email,
    _send_reset_otp_email,
    _send_recovery_failed_email,


    # ===========================================================================
    # VALIDATION HELPERS  (return error string or None)
    # ===========================================================================
    _validate_name,
    _validate_email,
    _validate_phone,
    _validate_country,
    _validate_gender,
    _validate_username,
    _validate_password,

    _finalize_email_change_failure,
    _dispatch_reset_otp,
    _handle_recovery_lockout,


)


 
# ===========================================================================
# REGISTRATION & ACTIVATION
# ===========================================================================

def create_account(request):
    if request.method == "GET":
        prefill = request.session.get("submitted_data", {})
        return render(request, "authentication/create_account.html", {
            "countries": COUNTRY_LIST,
            "genders":   GENDER_CHOICES,
            "prefill":   prefill,
        })

    first_name   = request.POST.get("first_name", "").strip()
    last_name    = request.POST.get("last_name", "").strip()
    email        = request.POST.get("email", "").strip()
    phone_number = request.POST.get("phone_number", "").strip()
    country      = request.POST.get("country", "").strip()
    gender       = request.POST.get("gender", "").strip()
    username     = request.POST.get("username", "").strip()

    request.session["submitted_data"] = {
        "first_name": first_name, "last_name": last_name, "email": email,
        "phone_number": phone_number, "country": country,
        "gender": gender, "username": username,
    }

    for validator, args in [
        (_validate_name,    (first_name, "First name")),
        (_validate_name,    (last_name,  "Last name")),
        (_validate_email,   (email,)),
        (_validate_phone,   (phone_number,)),
        (_validate_country, (country,)),
        (_validate_gender,  (gender,)),
        (_validate_username,(username,)),
    ]:
        err = validator(*args)
        if err:
            messages.error(request, err)
            return redirect(reverse("create_account"))

    normalised_phone = re.sub(r"[\s\-\(\)\+]", "", phone_number)

    if CustomUser.objects.filter(email__iexact=email).exists():
        messages.error(request, "An account with this email address already exists. Please use a different email or sign in.")
        return redirect(reverse("create_account"))

    if CustomUser.objects.filter(phone_number=normalised_phone).exists():
        messages.error(request, "This phone number is already associated with another account. Please use a different phone number.")
        return redirect(reverse("create_account"))

    if CustomUser.objects.filter(username__iexact=username).exists():
        messages.error(request, "This username is already taken. Please choose a different username.")
        return redirect(reverse("create_account"))

    user = CustomUser.objects.create_user(
        username=username, email=email, first_name=first_name,
        last_name=last_name, phone_number=normalised_phone,
        country=country, gender=gender,
    )
    user.is_active = False
    user.is_email_verified = False
    user.save()

    otp = generate_otp()
    request.session["otp_secret"]     = otp
    request.session["otp_first_name"] = first_name
    request.session["otp_last_name"]  = last_name
    request.session["otp_email"]      = email
    request.session.pop("submitted_data", None)

    send_otp_email(email, otp, first_name)

    messages.success(request, f"Account created! We sent a 6-digit OTP to {email}. Please enter it below to activate your account.")
    return redirect(reverse("activate_account"))






def activate_account(request):
    if not request.session.get("otp_email"):
        messages.error(request, "No pending account activation found. Please register first.")
        return redirect(reverse("create_account"))

    email      = request.session["otp_email"]
    first_name = request.session.get("otp_first_name", "")

    if request.method == "GET":
        return render(request, "authentication/activate_account.html", {"email": email, "first_name": first_name})

    action = request.POST.get("action", "verify")

    if action == "resend":
        new_otp = generate_otp()
        request.session["otp_secret"] = new_otp
        send_otp_email(email, new_otp, first_name)
        messages.info(request, "A new OTP has been sent to your email address.")
        return redirect(reverse("activate_account"))


    entered_otp = request.POST.get("otp", "").strip()

    if not entered_otp:
        messages.error(request, "Please enter the OTP.")
        return redirect(reverse("activate_account"))
    
    if not entered_otp.isdigit() or len(entered_otp) != 6:
        messages.error(request, "OTP must be a 6-digit number.")
        return redirect(reverse("activate_account"))
    
    if entered_otp != request.session.get("otp_secret", ""):
        messages.error(request, "Invalid OTP. Please try again or request a new one.")
        return redirect(reverse("activate_account"))
    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        messages.error(request, "User account not found. Please register again.")
        return redirect(reverse("create_account"))


    # OTP correct — mark active AND email verified
    user.is_active = True
    user.is_email_verified = True
    user.save()

    request.session["activating_user_id"] = user.pk
    for key in ("otp_secret", "otp_first_name", "otp_last_name"):
        request.session.pop(key, None)

    messages.success(request, "OTP verified successfully! Please set a password for your account.")
    return redirect(reverse("add_password"))

def add_password(request):
    user_id = request.session.get("activating_user_id")
    if not user_id:
        messages.error(request, "Session expired or invalid. Please start again.")
        return redirect(reverse("create_account"))


    try:
        user = CustomUser.objects.get(pk=user_id, is_active=True)
    except CustomUser.DoesNotExist:
        messages.error(request, "User account not found or not activated.")
        return redirect(reverse("create_account"))


    if request.method == "GET":
        return render(request, "authentication/add_password.html", {"first_name": user.first_name})

    error = _validate_password(request.POST.get("password", ""), request.POST.get("confirm_password", ""))
    if error:
        messages.error(request, error)
        return redirect(reverse("add_password"))

    user.set_password(request.POST.get("password"))
    user.save()

    request.session.pop("activating_user_id", None)
    request.session.pop("otp_email", None)

    send_account_activated_email(user.email, user.first_name)

    messages.success(request, "Your account has been fully activated! A confirmation email has been sent. You can now log in.")
    return redirect(reverse("login"))



# ===========================================================================
# AUTH
# ===========================================================================

def user_login(request):
    if request.user.is_authenticated is True:
        return redirect(reverse("dashboard"))

    if request.method == "GET":
        return render(request, "authentication/login.html")

    username = request.POST.get("username", "").strip()
    password          = request.POST.get("password", "").strip()

    if not username:
        messages.error(request, "Username or Password Is required.")
        return redirect(reverse("login"))

    if not password:
        messages.error(request, "Password is required.")
        return redirect(reverse("login"))

    user = None
    
    user = authenticate(request, username=username, password=password)

    if user is None:
        messages.error(request, "Invalid credentials. Please check your username and password.")
        return redirect(reverse("login"))

    if not user.is_active:
        messages.error(request, "Your account is not active. Please complete the activation process.")
        return redirect(reverse("login"))

    login(request, user)
    messages.success(request, f"Welcome back, {user.first_name}!")

    next_url = request.POST.get('next') or request.GET.get('next')
    return redirect(next_url if next_url else reverse("dashboard"))












def user_logout(request):
    logout(request)
    messages.success(request, "You have been signed out successfully.")
    return redirect(reverse("login"))

def dashboard(request):
    if not _login_required(request):
        return redirect(reverse("login"))
    return render(request, "authentication/dashboard.html", {"user": request.user})


# ===========================================================================
# PROFILE
# ===========================================================================

def profile(request):
    """View-only profile page."""
    if not _login_required(request):
        return redirect(reverse("login"))
    return render(request, "authentication/profile.html", {"user": request.user})

def profile_edit(request):
    """Edit profile (no email field)."""
    if not _login_required(request):
        return redirect(reverse("login"))

    user = request.user

    if request.method == "GET":
        return render(request, "authentication/profile_edit.html", {
            "user":      user,
            "countries": COUNTRY_LIST,
            "genders":   GENDER_CHOICES,
        })

    first_name   = request.POST.get("first_name", "").strip()
    last_name    = request.POST.get("last_name", "").strip()
    phone_number = request.POST.get("phone_number", "").strip()
    country      = request.POST.get("country", "").strip()
    gender       = request.POST.get("gender", "").strip()
    username     = request.POST.get("username", "").strip()

    # Validate each field
    for validator, args in [
        (_validate_name,    (first_name, "First name")),
        (_validate_name,    (last_name,  "Last name")),
        (_validate_phone,   (phone_number,)),
        (_validate_country, (country,)),
        (_validate_gender,  (gender,)),
        (_validate_username,(username,)),
    ]:
        err = validator(*args)
        if err:
            messages.error(request, err)
            return redirect(reverse("profile_edit"))
            

    normalised_phone = re.sub(r"[\s\-\(\)\+]", "", phone_number)

    # Uniqueness checks — exclude self
    if CustomUser.objects.filter(phone_number=normalised_phone).exclude(pk=user.pk).exists():
        messages.error(request, "This phone number is already associated with another account.")
        return redirect(reverse("profile_edit"))

    if CustomUser.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
        messages.error(request, "This username is already taken. Please choose a different username.")
        return redirect(reverse("profile_edit"))

    user.first_name   = first_name
    user.last_name    = last_name
    user.phone_number = normalised_phone
    user.country      = country
    user.gender       = gender
    user.username     = username
    user.save()

    _send_profile_updated_email(user.email, user.first_name)

    messages.success(request, "Your profile has been updated successfully! A confirmation email has been sent.")
    return redirect(reverse("profile_updated"))

def profile_updated(request):
    if not _login_required(request):
        return redirect(reverse("login"))
    return render(request, "authentication/profile_updated.html", {"user": request.user})


# ===========================================================================
# CHANGE PASSWORD  (authenticated user)
# ===========================================================================

def change_password(request):
    if not _login_required(request):
        return redirect(reverse("login"))

    user = request.user

    if request.method == "GET":
        return render(request, "authentication/change_password.html")

    old_password     = request.POST.get("old_password", "")
    new_password     = request.POST.get("new_password", "")
    confirm_password = request.POST.get("confirm_password", "")

    if not old_password:
        messages.error(request, "Current password is required.")
        return redirect(reverse("change_password"))

    if not user.check_password(old_password):
        messages.error(request, "The current password you entered is incorrect.")
        return redirect(reverse("change_password"))

    if new_password == old_password:
        messages.error(request, "New password must be different from your current password.")
        return redirect(reverse("change_password"))

    err = _validate_password(new_password, confirm_password)
    if err:
        messages.error(request, err)
        return redirect(reverse("change_password"))

    # Save the new password — keep session alive just long enough to show success
    user.set_password(new_password)
    user.save()

    # Notify user via email
    _send_password_changed_email(user.email, user.first_name)

    # Log the user out for security
    logout(request)

    messages.success(request, "Your password has been changed successfully. Please log in with your new password.")
    return redirect(reverse("login"))


# ===========================================================================
# CHANGE EMAIL FLOW
# ===========================================================================
#
# Session keys used in this flow
# --------------------------------
# ce_new_email      – the new email the user wants to switch to
# ce_old_email      – the current email in DB at the time of request
# ce_otp            – the OTP secret sent to new email
# ce_resend_count   – how many times the OTP has been resent (max 2 extra = 3 total)
# ===========================================================================

def change_email(request):
    """Step 1 – enter the new email address."""
    if not _login_required(request):
        return redirect(reverse("login"))

    user = request.user

    if request.method == "GET":
        return render(request, "authentication/change_email.html", {"current_email": user.email})

    new_email = request.POST.get("new_email", "").strip()

    # Format validation
    err = _validate_email(new_email)
    if err:
        messages.error(request, err)
        return redirect(reverse("change_email"))
        

    # Cannot be the same as the current email
    if new_email.lower() == user.email.lower():
        messages.error(request, "The new email address cannot be the same as your current email.")
        return redirect(reverse("change_email"))

    # Cannot already belong to another account
    if CustomUser.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
        messages.error(request, "This email address is already associated with another account.")
        return redirect(reverse("change_email"))

    # Generate OTP and session everything
    otp = generate_otp()
    request.session["ce_new_email"]    = new_email
    request.session["ce_old_email"]    = user.email
    request.session["ce_otp"]          = otp
    request.session["ce_resend_count"] = 0

    # Mark email as unverified while change is in progress
    user.is_email_verified = False
    user.save()

    # Send OTP to new email + notice to old email
    _send_email_change_otp(new_email, otp, user.first_name)
    _send_email_change_notice_to_old(user.email, new_email, user.first_name)

    messages.success(request,
        f"A verification OTP has been sent to {new_email}. "
        "A notice has also been sent to your current email."
    )
    return redirect(reverse("verify_change_email_otp"))


def verify_change_email_otp(request):
    """Step 2 – enter the OTP sent to the new email; support resend (max 2 extra)."""
    if not _login_required(request):
        return redirect(reverse("login"))

    new_email    = request.session.get("ce_new_email")
    old_email    = request.session.get("ce_old_email")
    resend_count = request.session.get("ce_resend_count", 0)

    if not new_email:
        messages.error(request, "Email change session not found. Please start again.")
        return redirect(reverse("change_email"))

    obfuscated = _obfuscate_email(new_email)
    user       = request.user

    if request.method == "GET":
        return render(request, "authentication/verify_change_email_otp.html", {
            "obfuscated":   obfuscated,
            "resend_count": resend_count,
        })

    action = request.POST.get("action", "verify")

    # ---- Resend OTP ----
    if action == "resend":
        if resend_count >= 2:
            # 3 total sends exhausted — fail the whole flow
            _finalize_email_change_failure(request, user, old_email, new_email)
            return redirect(reverse("email_change_failed"))
            

        new_otp = generate_otp()
        request.session["ce_otp"]          = new_otp
        request.session["ce_resend_count"] = resend_count + 1

        _send_email_change_otp(new_email, new_otp, user.first_name)

        remaining_resends = 2 - (resend_count + 1)
        messages.info(request,
            f"A new OTP has been sent to {obfuscated}. "
            f"You have {remaining_resends} resend(s) remaining."
        )
        return redirect(reverse("verify_change_email_otp"))

    # ---- Verify OTP ----
    entered_otp = request.POST.get("otp", "").strip()

    if not entered_otp:
        messages.error(request, "Please enter the OTP.")
        return redirect(reverse("verify_change_email_otp"))

    if not entered_otp.isdigit() or len(entered_otp) != 6:
        messages.error(request, "OTP must be exactly 6 digits.")
        return redirect(reverse("verify_change_email_otp"))

    if entered_otp != request.session.get("ce_otp", ""):
        messages.error(request, "Invalid OTP. Please try again or use the resend button.")
        return redirect(reverse("verify_change_email_otp"))

    # ---- OTP correct — commit the new email ----
    old_email_db = user.email  # what is currently in DB
    user.email            = new_email
    user.is_email_verified = True
    user.save()

    # Send success notices to both addresses
    _send_email_change_success_old(old_email_db, new_email, user.first_name)
    _send_email_change_success_new(new_email, user.first_name)

    # Clear session
    for key in ("ce_new_email", "ce_old_email", "ce_otp", "ce_resend_count"):
        request.session.pop(key, None)

    messages.success(request, "Your email address has been changed successfully!")
    return redirect(reverse("email_change_success"))


def email_change_success(request):
    if not _login_required(request):
        return redirect(reverse("login"))
    return render(request, "authentication/email_change_success.html", {"user": request.user})


def email_change_failed(request):
    if not _login_required(request):
        return redirect(reverse("login"))
    return render(request, "authentication/email_change_failed.html", {"user": request.user})


# ===========================================================================
# FORGOT PASSWORD FLOW
# ===========================================================================

def forgot_password(request):
    if request.method == "GET":
        return render(request, "authentication/forgot_password.html")

    phone_raw = request.POST.get("phone_number", "").strip()
    err = _validate_phone(phone_raw)
    if err:
        messages.error(request, err)
        return redirect(reverse("forgot_password"))
        
        
    

    normalised = re.sub(r"[\s\-\(\)\+]", "", phone_raw)

    try:
        user = CustomUser.objects.get(phone_number=normalised)
    except CustomUser.DoesNotExist:
        messages.error(request, "No account was found with that phone number. Please check the number and try again.")
        return redirect(reverse("forgot_password"))

    request.session["fp_email"]       = user.email
    request.session["fp_username"]    = user.username
    request.session["fp_first_name"]  = user.first_name
    request.session["fp_email_tries"] = 0
    request.session["fp_user_tries"]  = 0
    request.session["fp_mode"]        = "email"

    return redirect(reverse("fp_verify_identity"))


def fp_verify_identity(request):
    if not request.session.get("fp_email"):
        messages.error(request, "Recovery session expired. Please start again.")
        return redirect(reverse("forgot_password"))

    real_email    = request.session["fp_email"]
    real_username = request.session["fp_username"]
    first_name    = request.session.get("fp_first_name", "")
    mode          = request.session.get("fp_mode", "email")
    email_tries   = request.session.get("fp_email_tries", 0)
    user_tries    = request.session.get("fp_user_tries", 0)
    obfuscated    = _obfuscate_email(real_email)

    if request.method == "GET":
        return render(request, "authentication/fp_verify_identity.html", {
            "mode": mode, "obfuscated": obfuscated,
            "email_tries": email_tries, "user_tries": user_tries,
        })

    action = request.POST.get("action", "submit")

    if action == "switch_to_username":
        request.session["fp_mode"] = "username"
        return redirect(reverse("fp_verify_identity"))

    if mode == "email":
        entered_email = request.POST.get("email", "").strip()
        if not entered_email:
            messages.error(request, "Please enter your email address.")
            return redirect(reverse("fp_verify_identity"))

        if entered_email.lower() != real_email.lower():
            email_tries += 1
            request.session["fp_email_tries"] = email_tries
            if email_tries >= 2:
                request.session["fp_mode"] = "username"
                messages.warning(request, "The email you entered does not match our records. You have used all email attempts. Please verify using your username instead.")
            else:
                messages.error(request, f"The email address you entered does not match our records. You have {2 - email_tries} attempt(s) remaining.")
            return redirect(reverse("fp_verify_identity"))

        return _dispatch_reset_otp(request, real_email, real_username, first_name)

    if mode == "username":
        entered_username = request.POST.get("username", "").strip()
        if not entered_username:
            messages.error(request, "Please enter your username.")
            return redirect(reverse("fp_verify_identity"))

        if entered_username.lower() != real_username.lower():
            user_tries += 1
            request.session["fp_user_tries"] = user_tries
            if user_tries >= 2:
                _handle_recovery_lockout(request, real_email, first_name)
                return redirect(reverse("fp_recovery_failed"))
            messages.error(request, f"The username you entered does not match our records. You have {2 - user_tries} attempt(s) remaining.")
            return redirect(reverse("fp_verify_identity"))

        return _dispatch_reset_otp(request, real_email, real_username, first_name)

    return redirect(reverse("forgot_password"))


def fp_enter_otp(request):
    if not request.session.get("fp_otp"):
        messages.error(request, "Recovery session expired. Please start again.")
        return redirect(reverse("forgot_password"))

    real_email = request.session.get("fp_email", "")
    first_name = request.session.get("fp_first_name", "")
    obfuscated = _obfuscate_email(real_email)

    if request.method == "GET":
        return render(request, "authentication/fp_enter_otp.html", {"obfuscated": obfuscated})

    action = request.POST.get("action", "verify")

    if action == "resend":
        new_otp = generate_otp()
        request.session["fp_otp"] = new_otp
        _send_reset_otp_email(real_email, new_otp, first_name)
        messages.info(request, "A new OTP has been sent to your registered email.")
        return redirect(reverse("fp_enter_otp"))

    entered_otp = request.POST.get("otp", "").strip()
    if not entered_otp:
        messages.error(request, "Please enter the OTP.")
        return redirect(reverse("fp_enter_otp"))
    if not entered_otp.isdigit() or len(entered_otp) != 6:
        messages.error(request, "OTP must be exactly 6 digits.")
        return redirect(reverse("fp_enter_otp"))
    if entered_otp != request.session.get("fp_otp", ""):
        messages.error(request, "Invalid OTP. Please try again or request a new one.")
        return redirect(reverse("fp_enter_otp"))

    request.session.pop("fp_otp", None)
    messages.success(request, "OTP verified! Please set your new password.")
    return redirect(reverse("fp_reset_password"))


def fp_reset_password(request):
    if not request.session.get("fp_email"):
        messages.error(request, "Recovery session expired. Please start again.")
        return redirect(reverse("forgot_password"))

    real_email = request.session["fp_email"]
    first_name = request.session.get("fp_first_name", "")

    if request.method == "GET":
        return render(request, "authentication/fp_reset_password.html", {"first_name": first_name})

    err = _validate_password(request.POST.get("password", ""), request.POST.get("confirm_password", ""))
    if err:
        messages.error(request, err)
        return redirect(reverse("fp_reset_password"))

    try:
        user = CustomUser.objects.get(email=real_email)
    except CustomUser.DoesNotExist:
        messages.error(request, "Account not found. Please start again.")
        return redirect(reverse("forgot_password"))

    user.set_password(request.POST.get("password"))
    user.save()

    for key in ("fp_email", "fp_username", "fp_first_name", "fp_email_tries", "fp_user_tries", "fp_mode", "fp_otp"):
        request.session.pop(key, None)

    messages.success(request, "Your password has been reset successfully. You can now log in.")
    return redirect(reverse("login"))


def fp_recovery_failed(request):
    return render(request, "authentication/fp_recovery_failed.html")


# ===========================================================================
# HOME
# ===========================================================================

def home(request):
    return render(request, "authentication/home.html")




# ===========================================================================
# SETUP KEY FLOW  (staff account activation)
# ===========================================================================
#
# Session keys used in this flow
# ──────────────────────────────
# sk_email       – staff member's email address
# sk_first_name  – staff member's first name
# sk_username    – staff member's username
# sk_otp         – OTP sent to staff email for verification
# ===========================================================================

def verify_setup_key(request):
    """
    Step 1 – Staff enters their username + setup key.
    If valid: send OTP to their email, store session data, redirect to OTP page.
    """
    if request.method == "GET":
        return render(request, "authentication/verify_setup_key.html")

    username  = request.POST.get("username",  "").strip()
    setupkey  = request.POST.get("setupkey",  "").strip()

    if not username:
        messages.error(request, "Username is required.")
        return redirect(reverse("verify_setup_key"))

    if not setupkey:
        messages.error(request, "Setup key is required.")
        return redirect(reverse("verify_setup_key"))

    # Look up user by username; must have a setupkey on record
    try:
        user = CustomUser.objects.get(username__iexact=username)
    except CustomUser.DoesNotExist:
        messages.error(request, "No account found with that username.")
        return redirect(reverse("verify_setup_key"))

    if not user.setupkey:
        messages.error(request, "This account does not have a pending setup key. Please contact your administrator.")
        return redirect(reverse("verify_setup_key"))

    if not verify_setupkey(setupkey, user.setupkey):
        messages.error(request, "Invalid setup key. Please check the key in your email and try again.")
        return redirect(reverse("verify_setup_key"))

    # Credentials verified — send OTP
    otp = generate_otp()
    request.session["sk_email"]      = user.email
    request.session["sk_first_name"] = user.first_name
    request.session["sk_username"]   = user.username
    request.session["sk_otp"]        = otp

    _send_reset_otp_email(user.email, otp, user.first_name)

    obfuscated = _obfuscate_email(user.email)
    messages.success(request, f"Setup key verified! A 6-digit OTP has been sent to {obfuscated}. Please enter it to continue.")
    return redirect(reverse("verify_setupkey_otp"))


def verify_setupkey_otp(request):
    """
    Step 2 – Staff enters the OTP sent to their email.
    On success: activate account, clear setupkey, session fp_* data, redirect to set password.
    """
    if not request.session.get("sk_otp"):
        messages.error(request, "Setup session expired. Please start again.")
        return redirect(reverse("verify_setup_key"))

    email      = request.session.get("sk_email", "")
    first_name = request.session.get("sk_first_name", "")
    obfuscated = _obfuscate_email(email)

    if request.method == "GET":
        return render(request, "authentication/verify_setupkey_otp.html", {
            "obfuscated": obfuscated,
            "first_name": first_name,
        })

    action = request.POST.get("action", "verify")

    # ── Resend OTP ─────────────────────────────────────────────────────────
    if action == "resend":
        # Clear all sk_* session data and send back to setup key entry
        for key in ("sk_email", "sk_first_name", "sk_username", "sk_otp"):
            request.session.pop(key, None)
        messages.info(request, "Please re-enter your username and setup key to receive a new OTP.")
        return redirect(reverse("verify_setup_key"))

    # ── Verify OTP ─────────────────────────────────────────────────────────
    entered_otp = request.POST.get("otp", "").strip()

    if not entered_otp:
        messages.error(request, "Please enter the OTP.")
        return redirect(reverse("verify_setupkey_otp"))

    if not entered_otp.isdigit() or len(entered_otp) != 6:
        messages.error(request, "OTP must be exactly 6 digits.")
        return redirect(reverse("verify_setupkey_otp"))

    if entered_otp != request.session.get("sk_otp", ""):
        messages.error(request, "Invalid OTP. Please try again or tap \"Request New OTP\" to restart.")
        return redirect(reverse("verify_setupkey_otp"))

    # ── OTP correct — activate account ─────────────────────────────────────
    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        messages.error(request, "Account not found. Please contact your administrator.")
        for key in ("sk_email", "sk_first_name", "sk_username", "sk_otp"):
            request.session.pop(key, None)
        return redirect(reverse("verify_setup_key"))

    user.is_active         = True
    user.is_email_verified = True
    user.setupkey          = None          # invalidate setup key
    user.password_changed_on_temp_key_access = False
    user.save()

    send_staff_account_live_email(user.email, user.first_name)

    # Clear sk_* session keys
    for key in ("sk_email", "sk_first_name", "sk_username", "sk_otp"):
        request.session.pop(key, None)

    # Seed fp_* session so fp_reset_password works as-is
    request.session["fp_email"]      = user.email
    request.session["fp_first_name"] = user.first_name

    messages.success(request, "Identity verified! Please now set a permanent password for your account.")
    return redirect(reverse("fp_reset_password"))


# ===========================================================================
# STAFF MANAGEMENT
# ===========================================================================

def staff_add(request):
    if not _staff_required(request):
        return redirect(reverse("login"))

    if request.method == "GET":
        return render(request, "authentication/staff_add.html", {
            "countries": COUNTRY_LIST,
            "genders":   GENDER_CHOICES,
        })

    first_name   = request.POST.get("first_name",   "").strip()
    last_name    = request.POST.get("last_name",    "").strip()
    email        = request.POST.get("email",        "").strip()
    phone_number = request.POST.get("phone_number", "").strip()
    country      = request.POST.get("country",      "").strip()
    gender       = request.POST.get("gender",       "").strip()

    for validator, args in [
        (_validate_name,  (first_name, "First name")),
        (_validate_name,  (last_name,  "Last name")),
        (_validate_email, (email,)),
        (_validate_phone, (phone_number,)),
        (_validate_country,(country,)),
        (_validate_gender, (gender,)),
    ]:
        err = validator(*args)
        if err:
            messages.error(request, err)
            return redirect(reverse("staff_add"))

    normalised_phone = re.sub(r"[\s\-\(\)\+]", "", phone_number)

    if CustomUser.objects.filter(email__iexact=email).exists():
        messages.error(request, "An account with this email already exists.")
        return redirect(reverse("staff_add"))

    if CustomUser.objects.filter(phone_number=normalised_phone).exists():
        messages.error(request, "This phone number is already in use.")
        return redirect(reverse("staff_add"))

    # ── Generate unique username from first name ───────────────────────────
    username = make_unique_username(
        first_name,
        lambda u: CustomUser.objects.filter(username__iexact=u).exists(),
    )

    # ── Generate & hash setup key ──────────────────────────────────────────
    plain_key   = generate_setupkey()
    hashed_key  = hash_setupkey(plain_key)

    # ── Create user (inactive until setup completes) ───────────────────────
    user = CustomUser.objects.create_user(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone_number=normalised_phone,
        country=country,
        gender=gender,
    )
    user.is_active         = False
    user.is_email_verified = False
    user.is_staff          = True
    user.is_superuser      = False
    user.user_type         = "staff"
    user.setupkey          = hashed_key
    user.password_changed_on_temp_key_access = True
    user.save()

    # ── Send setup credentials email ──────────────────────────────────────
    login_url = request.build_absolute_uri(reverse("login"))
    send_staff_setup_email(email, first_name, username, plain_key, login_url)

    messages.success(
        request,
        f"Staff account for '{first_name} {last_name}' created. "
        f"Setup credentials have been sent to {email}."
    )
    return redirect(reverse("dashboard"))



# ==========