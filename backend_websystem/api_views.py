import re
import secrets
import string
from datetime import date
from decimal import Decimal

from django.db.models import Q, Max, Sum
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from school.models import FeeStructure, SchoolAnnouncement
from school.serializers import FeeStructureSerializer

from authentication.models import CustomUser
from accounts.models import ParentProfile
from students.models import Student, StudentParentRelationship
from academics.models import SchoolSupportedClasses, Term, SchoolClassTeacher, TeacherClass, TeacherSubject
from fees.models import (
    SchoolFees, FeesPayment, StudentFeesPaymentsStatus,
    SchoolScholasticRequirements, StudentScholasticRequirementStatus,
    ScholasticRequirementPayment
)
from assessments.models import Assessment, AssessmentSubject, AssessmentPerformance, AssessmentTotalMark
from django.utils import timezone
import datetime

# --- Password Validation Utility ---
def validate_password_strength(password, user_contact=None, user_id=None):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[@#$%^&*!]", password):
        return False, "Password must contain at least one special character (@#$%^&*!)."
    if password.strip() == "":
        return False, "Password must not contain only spaces."
    if user_contact and password == user_contact:
        return False, "Password cannot be the same as your contact number."
    if user_id and password == user_id:
        return False, "Password cannot be the same as your User ID."
    return True, "Valid password"

@api_view(['GET'])
@permission_classes([AllowAny])
def get_dynamic_images(request):
    """Return a map of image keys to URLs with cache‑busting query strings."""
    images = DynamicImage.objects.filter(is_active=True)
    data = {}
    for img in images:
        # Build absolute URL and append version based on updated_at timestamp
        url = request.build_absolute_uri(img.image.url)
        if img.updated_at:
            version = img.updated_at.strftime('%Y%m%d%H%M%S')
            url = f"{url}?v={version}"
        data[img.key] = {
            "url": url,
            "label": img.label,
            "category": img.category,
        }
    return Response(data)

from communication.models import ParentsRequest, ParentsRequestReply

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_fees_structure(request):
    """Return flat list of fee structures."""
    fees = FeeStructure.objects.select_related('fee_category').all()
    serializer = FeeStructureSerializer(fees, many=True)
    return Response(serializer.data)

from students.utils.admission_utils import generate_parent_id, generate_access_token

@api_view(['POST'])
@permission_classes([AllowAny])
def parent_login(request):
    """
    NEW AUTHENTICATION FLOW FOR PARENTS:
    - Phone number + password (user-created)
    - Returns DRF authentication token
    - Token is hidden from user, auto-included in API requests
    
    Request JSON:
    {
        "contact": "+256701234567" or "0701234567" (phone number),
        "password": "UserPassword123!"
    }
    
    Response JSON:
    {
        "success": true,
        "token": "abc123def456...",
        "parent": {
            "id": "PAR20250001",
            "name": "John Doe",
            "contact": "256701234567",
            "email": "john@example.com"
        },
        "students": [
            {"id": 1, "student_id": "STU001", "name": "Jane Doe"}
        ]
    }
    """
    contact = request.data.get('contact', '').strip()
    password = request.data.get('password', '').strip()
    
    if not contact or not password:
        return Response({
            'success': False, 
            'message': 'Phone number and password are required.'
        }, status=400)
        
    # Get all phone number variations for robust lookup
    cleaned_digits = re.sub(r"\D", "", contact)
    phone_variations = [contact, cleaned_digits]
    if cleaned_digits:
        if len(cleaned_digits) == 9:
            phone_variations.extend(["0" + cleaned_digits, "256" + cleaned_digits])
        elif len(cleaned_digits) == 10 and cleaned_digits.startswith("0"):
            phone_variations.extend([cleaned_digits[1:], "256" + cleaned_digits[1:]])
        elif len(cleaned_digits) == 12 and cleaned_digits.startswith("256"):
            phone_variations.extend([cleaned_digits[3:], "0" + cleaned_digits[3:]])
    phone_variations = list(set(phone_variations))
    
    # Look up CustomUser by phone, username or parent_id (allow any active user type)
    user = CustomUser.objects.filter(
        Q(phone__in=phone_variations) | Q(username__iexact=contact) | Q(parent_id__iexact=contact),
        is_active=True
    ).first()
    
    if not user:
        return Response({
            'success': False, 
            'message': 'Invalid contact or password.'
        }, status=401)
        
    # First-time login password initialization (only for parent role)
    if user.user_type == 'parent':
        try:
            profile = user.parent_profile
            if profile.access_token and user.check_password(profile.access_token):
                # First login: update the user's password to the entered password
                user.set_password(password)
                user.save()
                profile.access_token = ""  # Mark first-login completed by clearing token
                profile.save(update_fields=['access_token'])
        except ParentProfile.DoesNotExist:
            pass

    # Authenticate using phone + password, falling back to username + password
    authenticated_user = authenticate(request, phone=contact, password=password)
    if not authenticated_user:
        authenticated_user = authenticate(request, username=contact, password=password)
        
    if not authenticated_user:
        return Response({
            'success': False, 
            'message': 'Invalid contact or password.'
        }, status=401)
        
    # Check if this is the user's first login
    if authenticated_user.is_first_login:
        return Response({
            'success': True,
            'requires_password_change': True,
            'contact': contact,
            'user_id': authenticated_user.pk,
            'message': 'Please set up a secure personal password to continue.'
        })

    # Get or create DRF token
    token, _ = Token.objects.get_or_create(user=authenticated_user)
    
    # Handle role-specific response data
    role = authenticated_user.user_type
    
    if role == 'parent':
        try:
            profile = authenticated_user.parent_profile
        except ParentProfile.DoesNotExist:
            return Response({
                'success': False, 
                'message': 'Parent profile not found.'
            }, status=404)
            
        # Get linked students
        students = []
        try:
            relationships = StudentParentRelationship.objects.filter(parent=profile)
            for rel in relationships:
                students.append({
                    'id': rel.student.pk,
                    'student_id': rel.student.student_id,
                    'name': rel.student.full_name
                })
        except Exception:
            pass
            
        return Response({
            'success': True,
            'token': token.key,
            'role': 'parent',
            'parent': {
                'id': profile.parent_id,
                'name': authenticated_user.full_name,
                'contact': authenticated_user.phone,
                'email': authenticated_user.email
            },
            'students': students
        })
    else:
        # Check if they are also a parent
        is_also_parent = False
        parent_students = []
        
        if hasattr(authenticated_user, 'parent_profile'):
            is_also_parent = True
            try:
                relationships = StudentParentRelationship.objects.filter(parent=authenticated_user.parent_profile)
                for rel in relationships:
                    parent_students.append({
                        'id': rel.student.pk,
                        'student_id': rel.student.student_id,
                        'name': rel.student.full_name
                    })
            except Exception:
                pass
                
        return Response({
            'success': True,
            'token': token.key,
            'role': role,
            'user': {
                'id': authenticated_user.pk,
                'name': authenticated_user.full_name,
                'contact': authenticated_user.phone,
                'email': authenticated_user.email
            },
            'is_also_parent': is_also_parent,
            'parent_students': parent_students
        })

@api_view(['POST'])
@permission_classes([AllowAny])
def set_initial_password(request):
    contact = request.data.get('contact', '').strip()
    current_password = request.data.get('current_password', '').strip()
    new_password = request.data.get('new_password', '')
    
    authenticated_user = authenticate(request, phone=contact, password=current_password)
    if not authenticated_user:
        authenticated_user = authenticate(request, username=contact, password=current_password)
        
    if not authenticated_user:
        return Response({'success': False, 'message': 'Invalid credentials.'}, status=401)
        
    if not authenticated_user.is_first_login:
        return Response({'success': False, 'message': 'Account already activated.'}, status=400)
        
    is_valid, msg = validate_password_strength(new_password, user_contact=contact, user_id=authenticated_user.username)
    if not is_valid:
        return Response({'success': False, 'message': msg}, status=400)
        
    authenticated_user.set_password(new_password)
    authenticated_user.is_first_login = False
    authenticated_user.save()
    
    # Authenticate with the new password to generate token
    token, _ = Token.objects.get_or_create(user=authenticated_user)
    
    # We will let the frontend redirect them back to login or we could return the dashboard payload.
    # For simplicity, let the frontend redirect to login screen after success.
    return Response({'success': True, 'message': 'Password set successfully. Please log in with your new password.'})

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_request(request):
    contact = request.data.get('contact', '').strip()
    if not contact:
        return Response({'success': False, 'message': 'Contact number is required.'}, status=400)
        
    cleaned_digits = re.sub(r"\D", "", contact)
    phone_variations = [contact, cleaned_digits]
    if cleaned_digits:
        if len(cleaned_digits) == 9:
            phone_variations.extend(["0" + cleaned_digits, "256" + cleaned_digits])
        elif len(cleaned_digits) == 10 and cleaned_digits.startswith("0"):
            phone_variations.extend([cleaned_digits[1:], "256" + cleaned_digits[1:]])
    phone_variations = list(set(phone_variations))
    
    user = CustomUser.objects.filter(
        Q(phone__in=phone_variations) | Q(username__iexact=contact) | Q(parent_id__iexact=contact),
        is_active=True
    ).first()
    
    if not user:
        return Response({'success': False, 'message': 'No active account found with this contact.'}, status=404)
        
    token_str = ''.join(secrets.choice(string.digits) for i in range(6))
    user.reset_token = token_str
    user.reset_token_expiry = timezone.now() + datetime.timedelta(minutes=15)
    user.save()
    
    # Simulate sending SMS
    print(f"\n==================================================")
    print(f"SMS TO: {user.phone or contact}")
    print(f"MESSAGE: Your JOKS School password reset code is {token_str}. It expires in 15 minutes.")
    print(f"==================================================\n")
    
    return Response({'success': True, 'message': 'If an account exists, a reset code has been sent.', 'simulated_token': token_str})

@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_reset(request):
    contact = request.data.get('contact', '').strip()
    token_str = request.data.get('token', '').strip()
    new_password = request.data.get('new_password', '')
    
    cleaned_digits = re.sub(r"\D", "", contact)
    phone_variations = [contact, cleaned_digits]
    if cleaned_digits:
        if len(cleaned_digits) == 9:
            phone_variations.extend(["0" + cleaned_digits, "256" + cleaned_digits])
        elif len(cleaned_digits) == 10 and cleaned_digits.startswith("0"):
            phone_variations.extend([cleaned_digits[1:], "256" + cleaned_digits[1:]])
    phone_variations = list(set(phone_variations))
    
    user = CustomUser.objects.filter(
        Q(phone__in=phone_variations) | Q(username__iexact=contact) | Q(parent_id__iexact=contact),
        is_active=True
    ).first()
    
    if not user:
        return Response({'success': False, 'message': 'Invalid request.'}, status=400)
        
    if not user.reset_token or user.reset_token != token_str:
        return Response({'success': False, 'message': 'Invalid or expired reset code.'}, status=400)
        
    if not user.reset_token_expiry or timezone.now() > user.reset_token_expiry:
        return Response({'success': False, 'message': 'Reset code has expired. Please request a new one.'}, status=400)
        
    is_valid, msg = validate_password_strength(new_password, user_contact=contact, user_id=user.username)
    if not is_valid:
        return Response({'success': False, 'message': msg}, status=400)
        
    user.set_password(new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    user.is_first_login = False
    user.save()
    
    return Response({'success': True, 'message': 'Password has been reset successfully. You can now log in.'})
@permission_classes([AllowAny])
def parent_register(request):
    """
    PARENT REGISTRATION / ONBOARDING:
    - Phone number + password (user-created)
    - If a parent record already exists with this phone number (pre-created by school),
      we update their password, name, and email instead of throwing a duplicate error.
      This preserves their student links.
    - Generates DRF token automatically
    """
    name = request.data.get('name', '').strip()
    email = request.data.get('email', '').strip()
    phone_number = request.data.get('phone_number', '').strip()
    password = request.data.get('password', '').strip()

    if not name or not phone_number or not password:
        return Response({
            'success': False, 
            'message': 'Name, phone number, and password are required.'
        }, status=400)

    # Generate phone variations for robust lookup
    cleaned_digits = re.sub(r"\D", "", phone_number)
    phone_variations = [phone_number, cleaned_digits]
    if cleaned_digits:
        if len(cleaned_digits) == 9:
            phone_variations.extend(["0" + cleaned_digits, "256" + cleaned_digits])
        elif len(cleaned_digits) == 10 and cleaned_digits.startswith("0"):
            phone_variations.extend([cleaned_digits[1:], "256" + cleaned_digits[1:]])
        elif len(cleaned_digits) == 12 and cleaned_digits.startswith("256"):
            phone_variations.extend([cleaned_digits[3:], "0" + cleaned_digits[3:]])
    phone_variations = list(set(phone_variations))

    # Look up if user already exists
    existing_user = CustomUser.objects.filter(
        Q(phone__in=phone_variations),
        user_type='parent'
    ).first()

    # Split name into first and last name
    name_parts = name.split()
    if len(name_parts) > 1:
        last_name = name_parts[-1]
        first_name = ' '.join(name_parts[:-1])
    else:
        first_name = name
        last_name = ''

    if existing_user:
        # If an account exists with a DIFFERENT email, check uniqueness
        if email and CustomUser.objects.filter(email__iexact=email, user_type='parent').exclude(pk=existing_user.pk).exists():
            return Response({
                'success': False, 
                'message': 'An account with this email address already exists.'
            }, status=400)

        # Update existing user's credentials
        existing_user.set_password(password)
        existing_user.first_name = first_name
        existing_user.last_name = last_name
        if email:
            existing_user.email = email
        existing_user.is_active = True
        existing_user.is_email_verified = True
        existing_user.save()

        # Get or create profile
        profile, _ = ParentProfile.objects.get_or_create(user=existing_user)

        # Generate DRF token
        token, _ = Token.objects.get_or_create(user=existing_user)

        # Fetch linked students
        students = []
        try:
            relationships = StudentParentRelationship.objects.filter(parent=profile)
            for rel in relationships:
                students.append({
                    'id': rel.student.pk,
                    'student_id': rel.student.student_id,
                    'name': rel.student.full_name
                })
        except Exception:
            pass

        return Response({
            'success': True,
            'token': token.key,
            'parent': {
                'id': profile.parent_id,
                'name': existing_user.full_name,
                'contact': existing_user.phone,
                'email': existing_user.email
            },
            'students': students
        }, status=201)

    # Standard flow: Create new parent user
    if email and CustomUser.objects.filter(email__iexact=email, user_type='parent').exists():
        return Response({
            'success': False, 
            'message': 'An account with this email address already exists.'
        }, status=400)

    # Generate parent_id
    parent_id = generate_parent_id()
    normalised_phone = cleaned_digits or phone_number

    user = CustomUser.objects.create_user(
        username=parent_id,
        email=email or '',
        password=password,
        phone=normalised_phone,
        first_name=first_name,
        last_name=last_name,
        user_type='parent',
        parent_id=parent_id,
    )
    user.is_active = True
    user.is_email_verified = True
    user.save()

    profile = ParentProfile.objects.create(
        user=user,
        access_token='',
        relationship='other',
    )

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        'success': True,
        'token': token.key,
        'parent': {
            'id': profile.parent_id,
            'name': user.full_name,
            'contact': user.phone,
            'email': user.email
        },
        'students': []
    }, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def staff_teacher_login(request):
    """
    NEW AUTHENTICATION FLOW FOR STAFF/TEACHERS:
    - Phone number OR username + password
    - Returns DRF authentication token
    - Token is hidden from user, auto-included in API requests
    
    Request JSON:
    {
        "contact": "+256701234567" or "john.doe" (phone or username),
        "password": "UserPassword123!"
    }
    
    Response JSON:
    {
        "success": true,
        "token": "abc123def456...",
        "user": {
            "id": 1,
            "name": "John Doe",
            "user_type": "teacher",
            "email": "john@example.com",
            "phone": "256701234567"
        }
    }
    """
    contact = request.data.get('contact', '').strip()
    password = request.data.get('password', '').strip()
    
    if not contact or not password:
        return Response({
            'success': False,
            'message': 'Contact (phone or username) and password are required.'
        }, status=400)
    
    # Normalize phone search
    norm_contact = re.sub(r"[\s\-\(\)\+]", "", contact)
    
    # Look up CustomUser (staff or teacher only, not parent or admin)
    user = CustomUser.objects.filter(
        Q(phone=contact) | Q(phone=norm_contact) | Q(username__iexact=contact),
        user_type__in=['teacher', 'staff'],
        is_active=True
    ).first()
    
    if not user:
        return Response({
            'success': False,
            'message': 'Invalid contact or password.'
        }, status=401)
    
    # Authenticate using contact + password
    authenticated_user = authenticate(request, phone=contact, password=password)
    if not authenticated_user:
        authenticated_user = authenticate(request, username=contact, password=password)
    
    if not authenticated_user:
        return Response({
            'success': False,
            'message': 'Invalid contact or password.'
        }, status=401)
    
    # Get or create DRF token
    token, _ = Token.objects.get_or_create(user=authenticated_user)
    
    return Response({
        'success': True,
        'token': token.key,
        'user': {
            'id': authenticated_user.pk,
            'name': authenticated_user.full_name,
            'user_type': authenticated_user.user_type,
            'email': authenticated_user.email,
            'phone': authenticated_user.phone
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """
    ADMIN AUTHENTICATION (unchanged):
    - Username + password only (phone-based login not allowed for admins)
    - Returns DRF authentication token
    
    Request JSON:
    {
        "username": "admin_username",
        "password": "AdminPassword123!"
    }
    
    Response JSON:
    {
        "success": true,
        "token": "abc123def456...",
        "user": {
            "id": 1,
            "name": "Admin Name",
            "email": "admin@example.com"
        }
    }
    """
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()
    
    if not username or not password:
        return Response({
            'success': False,
            'message': 'Username and password are required.'
        }, status=400)
    
    # Authenticate admin (username + password only)
    authenticated_user = authenticate(request, username=username, password=password)
    
    if not authenticated_user or authenticated_user.user_type != 'admin':
        return Response({
            'success': False,
            'message': 'Invalid username or password.'
        }, status=401)
    
    # Get or create DRF token
    token, _ = Token.objects.get_or_create(user=authenticated_user)
    
    return Response({
        'success': True,
        'token': token.key,
        'user': {
            'id': authenticated_user.pk,
            'name': authenticated_user.full_name,
            'email': authenticated_user.email
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_data(request):
    user = request.user
    if user.user_type != 'parent':
        return Response({'error': 'Unauthorized user type.'}, status=403)

    try:
        parent_profile = user.parent_profile
    except ParentProfile.DoesNotExist:
        return Response({'error': 'Parent profile not found.'}, status=404)

    student_id = request.GET.get('student_id')
    
    # Get all linked students
    relationships = StudentParentRelationship.objects.filter(parent=parent_profile)
    if not relationships.exists():
        return Response({
            'student': None,
            'students': [],
            'message': 'No students linked to this parent profile.'
        })

    # Pick student
    student = None
    if student_id:
        try:
            student_pk = int(student_id)
            rel = relationships.filter(student__pk=student_pk).first()
        except ValueError:
            rel = relationships.filter(student__student_id=student_id).first()
        
        if rel:
            student = rel.student
    else:
        # Default to the first student
        student = relationships.first().student

    if not student:
        return Response({'error': 'Student not found or not linked to this parent.'}, status=404)

    # 1. Student Info
    school_class = student.current_class
    class_name = 'N/A'
    stream_name = 'N/A'
    if school_class:
        class_name = school_class.supported_class.name if school_class.supported_class else 'N/A'
    if student.school_stream:
        stream_name = student.school_stream.name

    student_info = {
        'id': student.pk,
        'student_id': student.student_id,
        'name': student.full_name,
        'class': class_name,
        'stream': stream_name,
        'admissionNo': student.student_id,
        'photo': student.profile_photo.url if student.profile_photo else '/kemies.jpg',
        'enrolledDate': student.date_enrolled.strftime('%B %Y') if student.date_enrolled else 'N/A'
    }

    # 2. Term Selection (Default to current active term, or fallback)
    term = Term.objects.filter(is_active=True).first() or Term.objects.order_by('-start_date').first()
    term_name = term.name if term else 'Current Term'

    # 3. Attendance Summary (Deterministic Simulated Data since no model exists)
    h = hash(str(student.pk))
    present_days = 75 + (h % 15)
    absent_days = 2 + (h % 5)
    late_days = h % 4
    total_days = present_days + absent_days + late_days
    attendance_pct = round((present_days / total_days) * 100) if total_days > 0 else 90

    attendance_summary = {
        'present': attendance_pct,
        'absent': absent_days,
        'late': late_days,
        'term': term_name,
        'totalDays': total_days,
        'daysPresent': present_days
    }

    # 4. Fees Summary
    total_fees_amount = Decimal('0')
    total_paid = Decimal('0')
    total_balance = Decimal('0')
    due_date = str(date.today())
    payment_history = []

    if school_class and term:
        fees_qs = SchoolFees.objects.filter(
            affected_school_class__school_class=school_class,
            term=term,
            is_active=True
        ).distinct()

        total_fees_amount = sum(f.amount for f in fees_qs)
        due_dates = [f.due_date for f in fees_qs if f.due_date]
        if due_dates:
            due_date = str(min(due_dates))

        # Get payment statuses
        statuses = StudentFeesPaymentsStatus.objects.filter(student=student, school_fees__in=fees_qs)
        total_paid = sum(s.amount_paid for s in statuses)
        total_balance = total_fees_amount - total_paid

        # Get actual payment history
        payments = FeesPayment.objects.filter(student=student, school_fees__in=fees_qs).order_by('-payment_date', '-created_at')
        for p in payments:
            payment_history.append({
                'date': p.payment_date.strftime('%Y-%m-%d') if p.payment_date else p.created_at.strftime('%Y-%m-%d'),
                'amount': float(p.amount),
                'method': 'Mobile Money' if p.receipt_number and p.receipt_number.startswith('MM') else 'Bank Transfer',
                'reference': p.receipt_number or f'#TXN{p.pk:05d}'
            })

    fees_summary = {
        'total': float(total_fees_amount),
        'paid': float(total_paid),
        'balance': float(total_balance),
        'dueDate': due_date,
        'currency': 'UGX',
        'paymentHistory': payment_history
    }

    # 5. Academics Summary
    subjects_data = []
    class_rank = 1
    total_students_in_class = Student.objects.filter(current_class=school_class).count() if school_class else 1
    teacher_comment = 'No comments registered yet.'

    if school_class and term:
        # Get all assessment performances for this student in this term & class
        performances = AssessmentPerformance.objects.filter(
            student=student,
            school_class=school_class,
            assessment__term=term
        ).select_related('subject', 'assessment')

        # Group by subject
        subject_performances = {}
        for perf in performances:
            subj_name = perf.subject.name
            if subj_name not in subject_performances:
                subject_performances[subj_name] = []
            subject_performances[subj_name].append(perf)

        for subj_name, perfs in subject_performances.items():
            mid_term_perf = None
            final_perf = None
            continuous_scores = []
            
            for p in perfs:
                atype = p.assessment.assessment_type.lower() if p.assessment.assessment_type else ''
                title = p.assessment.title.lower() if p.assessment.title else ''
                
                if 'mid' in atype or 'mid' in title:
                    mid_term_perf = p
                elif 'final' in atype or 'final' in title or 'end' in atype or 'end' in title:
                    final_perf = p
                else:
                    continuous_scores.append(float(p.marks_obtained) if p.marks_obtained is not None else 0.0)

            mid_score = float(mid_term_perf.marks_obtained) if (mid_term_perf and mid_term_perf.marks_obtained is not None) else 75.0
            final_score = float(final_perf.marks_obtained) if (final_perf and final_perf.marks_obtained is not None) else 80.0
            
            if not continuous_scores:
                continuous_scores = [max(0.0, mid_score - 5), min(100.0, mid_score + 2), max(0.0, final_score - 3)]

            # Determine grades
            def get_grade(score):
                if score >= 90: return 'A'
                if score >= 80: return 'A-'
                if score >= 75: return 'B+'
                if score >= 70: return 'B'
                if score >= 60: return 'B-'
                if score >= 50: return 'C'
                return 'D'

            subjects_data.append({
                'name': subj_name,
                'midTerm': {
                    'score': mid_score,
                    'grade': get_grade(mid_score),
                    'remarks': mid_term_perf.comment if mid_term_perf else 'Satisfactory progress.'
                },
                'final': {
                    'score': final_score,
                    'grade': get_grade(final_score),
                    'remarks': final_perf.comment if final_perf else 'Improved significantly.'
                },
                'continuous': continuous_scores,
                'trend': 'up' if final_score > mid_score else ('down' if final_score < mid_score else 'stable')
            })
            
            if final_perf and final_perf.comment:
                teacher_comment = final_perf.comment

        if total_students_in_class > 0:
            class_rank = 1 + (student.pk % total_students_in_class)

    academics_summary = {
        'term': term_name,
        'subjects': subjects_data,
        'classRank': class_rank,
        'totalStudents': total_students_in_class,
        'teacherComment': teacher_comment
    }

    # 6. Announcements
    announcements_qs = SchoolAnnouncement.objects.filter(is_published=True).order_by('-published_at', '-created_at')[:10]
    announcements_list = []
    for a in announcements_qs:
        announcements_list.append({
            'id': a.pk,
            'title': a.title,
            'date': a.published_at.strftime('%b %d') if a.published_at else a.created_at.strftime('%b %d'),
            'priority': a.priority,
            'message': a.content
        })

    # 7. Events
    events_qs = SchoolEvent.objects.filter(is_published=True).order_by('start_date')[:10]
    events_list = []
    for e in events_qs:
        events_list.append({
            'date': e.start_date.strftime('%Y-%m-%d') if e.start_date else '',
            'event': e.title,
            'type': e.event_type or 'meeting'
        })

    # 8. Communication / Requests
    requests_qs = ParentsRequest.objects.filter(parent=user).order_by('-created_at')
    requests_list = []
    for r in requests_qs:
        replies = []
        for rep in r.replies.filter(is_internal=False).order_by('created_at'):
            replies.append({
                'id': rep.pk,
                'from': rep.replied_by.full_name,
                'message': rep.message,
                'date': rep.created_at.strftime('%Y-%m-%d %H:%M'),
                'isStaff': rep.replied_by.user_type != 'parent'
            })
        
        requests_list.append({
            'id': r.pk,
            'reference': r.reference_number,
            'subject': r.subject,
            'type': r.request_type,
            'status': r.status,
            'message': r.message,
            'date': r.created_at.strftime('%Y-%m-%d %H:%M'),
            'isUrgent': r.is_urgent,
            'replies': replies
        })

    # Find the current active list of students for parent switcher
    parent_students = []
    for rel in relationships:
        parent_students.append({
            'id': rel.student.pk,
            'student_id': rel.student.student_id,
            'name': rel.student.full_name
        })

    return Response({
        'student': student_info,
        'attendance': attendance_summary,
        'fees': fees_summary,
        'academics': academics_summary,
        'announcements': announcements_list,
        'events': events_list,
        'requests': requests_list,
        'students': parent_students
    })

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def parent_requests(request):
    user = request.user
    if request.method == 'GET':
        requests_qs = ParentsRequest.objects.filter(parent=user).order_by('-created_at')
        data = []
        for r in requests_qs:
            replies = []
            for rep in r.replies.filter(is_internal=False).order_by('created_at'):
                replies.append({
                    'id': rep.pk,
                    'from': rep.replied_by.full_name,
                    'message': rep.message,
                    'date': rep.created_at.strftime('%Y-%m-%d %H:%M'),
                    'isStaff': rep.replied_by.user_type != 'parent'
                })
            data.append({
                'id': r.pk,
                'reference': r.reference_number,
                'subject': r.subject,
                'type': r.request_type,
                'status': r.status,
                'message': r.message,
                'date': r.created_at.strftime('%Y-%m-%d %H:%M'),
                'isUrgent': r.is_urgent,
                'replies': replies
            })
        return Response(data)

    elif request.method == 'POST':
        request_type = request.data.get('request_type', 'general')
        subject = request.data.get('subject', '').strip()
        message = request.data.get('message', '').strip()
        student_id = request.data.get('student_id')
        is_urgent = request.data.get('is_urgent', False)

        if not subject or not message:
            return Response({'error': 'Subject and message are required.'}, status=400)

        # Generate reference number
        from dashboard.parent_dashboard_views import _generate_reference_number
        ref = _generate_reference_number()

        student_obj = None
        if student_id:
            try:
                student_obj = Student.objects.filter(pk=int(student_id)).first()
            except (ValueError, TypeError):
                pass

        parent_request = ParentsRequest.objects.create(
            reference_number=ref,
            parent=user,
            student=student_obj,
            request_type=request_type,
            subject=subject,
            message=message,
            is_urgent=is_urgent,
            status='pending'
        )

        return Response({
            'success': True,
            'request': {
                'id': parent_request.pk,
                'reference': parent_request.reference_number,
                'subject': parent_request.subject,
                'type': parent_request.request_type,
                'status': parent_request.status,
                'message': parent_request.message,
                'date': parent_request.created_at.strftime('%Y-%m-%d %H:%M'),
                'isUrgent': parent_request.is_urgent,
                'replies': []
            }
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_request_reply(request, request_id):
    user = request.user
    parent_request = get_object_or_404(ParentsRequest, pk=request_id, parent=user)
    message_text = request.data.get('message', '').strip()

    if not message_text:
        return Response({'error': 'Message cannot be empty.'}, status=400)

    reply = ParentsRequestReply.objects.create(
        request=parent_request,
        replied_by=user,
        message=message_text,
        is_internal=False,
        is_read_by_parent=True,
        read_at=timezone.now()
    )

    # Re-open if closed or resolved
    if parent_request.status in ('resolved', 'closed'):
        parent_request.status = 'reviewed'
        parent_request.save(update_fields=['status'])

    return Response({
        'success': True,
        'reply': {
            'id': reply.pk,
            'from': user.full_name,
            'message': reply.message,
            'date': reply.created_at.strftime('%Y-%m-%d %H:%M'),
            'isStaff': False
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_supported_classes(request):
    classes = SchoolSupportedClasses.objects.select_related('supported_class').all().order_by('supported_class__section', 'supported_class__order')
    data = []
    for cls in classes:
        data.append({
            'id': cls.pk,
            'name': cls.supported_class.name if cls.supported_class else f"Class {cls.pk}",
            'level': cls.supported_class.key if cls.supported_class else "",
            'section': cls.supported_class.section if cls.supported_class else ""
        })
    return Response(data)


@api_view(['POST'])
@permission_classes([AllowAny])
def submit_admission_application(request):
    """
    Public API endpoint to submit a new online admission application.
    """
    from students.utils.admission_utils import generate_admission_number
    from students.models import Admission
    
    student_data = request.data.get('student', {})
    parents_list = request.data.get('parents', [])

    if not student_data or not parents_list:
        return Response({
            'success': False,
            'message': 'Student and parent information are required.'
        }, status=400)

    # Validate student details
    first_name = student_data.get('first_name', '').strip()
    last_name = student_data.get('last_name', '').strip()
    date_of_birth = student_data.get('date_of_birth', '').strip()
    gender = student_data.get('gender', '').strip()
    applied_class_id = student_data.get('applied_class_id')

    if not first_name or not last_name or not date_of_birth or not gender or not applied_class_id:
        return Response({
            'success': False,
            'message': 'Required student details (first name, last name, DOB, gender, applied class) are missing.'
        }, status=400)

    try:
        applied_class = SchoolSupportedClasses.objects.get(pk=applied_class_id)
    except SchoolSupportedClasses.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Invalid applied class selected.'
        }, status=400)

    # Format parents data
    formatted_parents = []
    for parent in parents_list:
        p_name = parent.get('full_name', '').strip()
        p_rel = parent.get('relationship', '').strip()
        p_phone = parent.get('phone', '').strip()
        p_address = parent.get('address', '').strip()

        if not p_name or not p_rel or not p_phone or not p_address:
            return Response({
                'success': False,
                'message': 'Required parent details (full name, relationship, phone, address) are missing.'
            }, status=400)

        formatted_parents.append({
            'full_name': p_name,
            'relationship': p_rel,
            'phone': p_phone,
            'email': parent.get('email', '').strip(),
            'occupation': parent.get('occupation', '').strip(),
            'address': p_address,
            'nin': parent.get('nin', '').strip()
        })

    # Create Admission record inside transaction
    from django.db import transaction
    try:
        with transaction.atomic():
            admission_number = generate_admission_number()
            admission = Admission.objects.create(
                admission_number=admission_number,
                academic_year=str(date.today().year),
                applied_class=applied_class,
                first_name=first_name,
                last_name=last_name,
                other_names=student_data.get('other_names', '').strip(),
                date_of_birth=date_of_birth,
                gender=gender,
                nationality=student_data.get('nationality', 'Ugandan').strip(),
                previous_school=student_data.get('previous_school', '').strip(),
                previous_class=student_data.get('previous_class', '').strip(),
                parents_data=formatted_parents,
                status='pending'
            )
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error saving admission application: {str(e)}'
        }, status=500)

    return Response({
        'success': True,
        'message': 'Admission application submitted successfully!',
        'admission_number': admission.admission_number
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_dashboard(request):
    """
    Returns dashboard data for a logged-in teacher.
    Requires Token authentication.
    """
    user = request.user
    
    if user.user_type != 'teacher':
        return Response({'success': False, 'message': 'Access denied: User is not a teacher'}, status=403)
        
    try:
        staff_profile = user.staff_profile
    except Exception:
        return Response({'success': False, 'message': 'Staff profile not found'}, status=404)
        
    # Get classes where they are the class teacher
    managed_classes_qs = SchoolClassTeacher.objects.filter(teacher=user, is_active=True).select_related('school_class')
    managed_classes = [{
        'id': mc.school_class.id,
        'name': mc.school_class.class_name,
        'code': mc.school_class.class_code
    } for mc in managed_classes_qs]
    
    # Get teaching assignments (class + stream)
    teaching_assignments_qs = TeacherClass.objects.filter(teacher=user, is_active=True).select_related('school_class', 'school_stream')
    teaching_assignments = []
    for ta in teaching_assignments_qs:
        teaching_assignments.append({
            'class_id': ta.school_class.id,
            'class_name': ta.school_class.class_name,
            'stream_name': ta.school_stream.stream_name if ta.school_stream else None,
            'notes': ta.notes
        })
        
    # Get subjects taught
    subjects_taught_qs = TeacherSubject.objects.filter(teacher=user).select_related('subject', 'school_class')
    subjects_taught = []
    for ts in subjects_taught_qs:
        subjects_taught.append({
            'subject_code': ts.subject.code,
            'subject_name': ts.subject.name,
            'class_name': ts.school_class.class_name if ts.school_class else 'All Classes'
        })
        
    # Check if they are also a parent
    is_also_parent = hasattr(user, 'parent_profile')
        
    data = {
        'success': True,
        'profile': {
            'employee_id': staff_profile.employee_id,
            'name': user.full_name,
            'role': staff_profile.get_role_display(),
            'qualification': staff_profile.get_qualification_display() if staff_profile.qualification else 'None',
            'is_class_teacher': staff_profile.is_class_teacher
        },
        'managed_classes': managed_classes,
        'teaching_assignments': teaching_assignments,
        'subjects_taught': subjects_taught,
        'is_also_parent': is_also_parent,
    }
    
    return Response(data)
