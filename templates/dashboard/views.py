
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import ParentProfile
from assessments.models import AssessmentPerformance
from communication.models import ParentsRequest, ParentsRequestReply
from fees.models import (
    FeesPayment,
    SchoolFees,
    SchoolScholasticRequirements,
    ScholasticRequirementPayment,
)
from school.models import SchoolAnnouncement, SchoolEvent
from students.models import Student


# ═══════════════════════════════════════════════════════════════════════════════
#  PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_parent_profile(request):
    """Return the ParentProfile for the logged-in user or 404."""
    return get_object_or_404(ParentProfile, user=request.user, is_active=True)


def _get_owned_student(parent_profile, student_id):
    """
    Return the Student only if they are linked to this parent.
    Prevents parents from accessing other students' data by manipulating URLs.
    """
    return get_object_or_404(
        Student,
        pk=student_id,
        parent_relationships__parent=parent_profile,
    )


def _generate_reference_number():
    """Generate a unique reference number e.g. REQ20250001."""
    year  = datetime.date.today().year
    count = ParentsRequest.objects.filter(created_at__year=year).count() + 1
    return f"REQ{year}{count:04d}"


# REQUEST_TYPE_CHOICES mirrored here for template rendering
REQUEST_TYPE_CHOICES = [
    ('leave',       'Leave / Absence Request'),
    ('transfer',    'Transfer Request'),
    ('meeting',     'Meeting Request'),
    ('complaint',   'Complaint'),
    ('fee_query',   'Fees Enquiry'),
    ('performance', 'Academic Performance Enquiry'),
    ('health',      'Health / Medical Concern'),
    ('general',     'General Inquiry'),
    ('other',       'Other'),
]

VALID_REQUEST_TYPES = {k for k, _ in REQUEST_TYPE_CHOICES}


# ═══════════════════════════════════════════════════════════════════════════════
#  COVER / LANDING
# ═══════════════════════════════════════════════════════════════════════════════

def cover_page(request):
    return render(request, 'dashboard/cover.html')


# ═══════════════════════════════════════════════════════════════════════════════
#  PARENT DASHBOARD — HOME
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def parent_dashboard(request):
    """
    Main parent portal home page.

    Displays:
        • Parent / guardian profile card
        • Cards for each linked student (click → student detail page)
        • Upcoming school events  (next 5)
        • Recent school announcements (latest 5)
        • Recent requests submitted by this parent (latest 5)
    """
    parent  = _get_parent_profile(request)
    students = parent.get_students()

    today = timezone.now().date()

    # Adjust queryset filters to match your SchoolEvent / SchoolAnnouncement
    # field names if they differ from 'event_date' / 'is_active'.
    events = SchoolEvent.objects.filter(
        event_date__gte=today
    ).order_by('event_date')[:5]

    announcements = SchoolAnnouncement.objects.filter(
        is_active=True
    ).order_by('-created_at')[:5]

    recent_requests = ParentsRequest.objects.filter(
        parent=request.user
    ).order_by('-created_at')[:5]

    return render(request, 'dashboard/parent_home.html', {
        'parent':           parent,
        'students':         students,
        'events':           events,
        'announcements':    announcements,
        'recent_requests':  recent_requests,
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def parent_dashboard_student(request, student_id):
    """
    Per-student detail page — tabbed layout.

    Tabs:
        1. Student Information
        2. Fees Structure       (SchoolFees for current class)
        3. Fees Payments        (FeesPayment history)
        4. Scholastic Items     (SchoolScholasticRequirements for class + term)
        5. Scholastic Payments  (ScholasticRequirementPayment history)
        6. Assessment Results   (AssessmentPerformance history)
    """
    parent  = _get_parent_profile(request)
    student = _get_owned_student(parent, student_id)

    current_class = student.current_class  # SchoolSupportedClasses instance

    # ── Fees structure ────────────────────────────────────────────────────────
    # SchoolFees reaches SchoolSupportedClasses via FeesClass junction.
    # Adjust 'fees_classes__supported_class' if your FeesClass field name differs.
    fees_structure = SchoolFees.objects.filter(
        fees_classes__supported_class=current_class
    ).distinct()

    # ── Fees payment history ──────────────────────────────────────────────────
    fees_payments = FeesPayment.objects.filter(
        student=student
    ).order_by('-payment_date')

    # ── Scholastic requirements ───────────────────────────────────────────────
    # Adjust 'supported_class' / 'term' field names to match your model.
    scholastic_items = SchoolScholasticRequirements.objects.filter(
        supported_class=current_class
    ).order_by('term', 'item_name')

    # ── Scholastic payment history ────────────────────────────────────────────
    scholastic_payments = ScholasticRequirementPayment.objects.filter(
        student=student
    ).order_by('-payment_date')

    # ── Assessment performance ────────────────────────────────────────────────
    performance = AssessmentPerformance.objects.filter(
        student=student
    ).order_by('-created_at')

    # ── Parent's requests for this specific student ───────────────────────────
    student_requests = ParentsRequest.objects.filter(
        parent=request.user,
        student=student,
    ).order_by('-created_at')

    return render(request, 'dashboard/parent_student.html', {
        'parent':              parent,
        'student':             student,
        'current_class':       current_class,
        'fees_structure':      fees_structure,
        'fees_payments':       fees_payments,
        'scholastic_items':    scholastic_items,
        'scholastic_payments': scholastic_payments,
        'performance':         performance,
        'student_requests':    student_requests,
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMUNICATION — REQUEST LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def parent_communication(request):
    """
    Full communication history page.

    Shows all requests submitted by this parent with status badges.
    Provides a "New Request" button that links to parent_new_request.
    """
    parent = _get_parent_profile(request)

    # Optional status filter via GET param  e.g. ?status=pending
    status_filter = request.GET.get('status', '').strip()

    qs = ParentsRequest.objects.filter(parent=request.user).order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)

    # Status choices for the filter dropdown
    status_choices = [
        ('',         'All Requests'),
        ('pending',  'Pending'),
        ('reviewed', 'Reviewed / In Progress'),
        ('resolved', 'Resolved'),
        ('closed',   'Closed'),
        ('rejected', 'Rejected'),
    ]

    return render(request, 'dashboard/parent_communication.html', {
        'parent':         parent,
        'requests':       qs,
        'status_filter':  status_filter,
        'status_choices': status_choices,
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMUNICATION — REQUEST DETAIL + REPLIES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def parent_request_detail(request, request_id):
    """
    View a single request with all parent-visible replies.
    Marks unread replies as read when the parent opens this page.
    """
    parent         = _get_parent_profile(request)
    parent_request = get_object_or_404(
        ParentsRequest,
        pk=request_id,
        parent=request.user,   # only this parent's requests
    )

    # Mark unread, parent-visible replies as read
    unread_replies = ParentsRequestReply.objects.filter(
        request=parent_request,
        is_internal=False,
        is_read_by_parent=False,
    )
    if unread_replies.exists():
        with transaction.atomic():
            unread_replies.update(
                is_read_by_parent=True,
                read_at=timezone.now(),
            )

    # Only show parent-visible replies (is_internal=False)
    replies = ParentsRequestReply.objects.filter(
        request=parent_request,
        is_internal=False,
    ).order_by('created_at')

    return render(request, 'dashboard/parent_request_detail.html', {
        'parent':         parent,
        'parent_request': parent_request,
        'replies':        replies,
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  COMMUNICATION — NEW REQUEST FORM  (GET + POST)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def parent_new_request(request, student_id=None):
    """
    GET  → Show the new-request form.
    POST → Validate, save, redirect.

    student_id (optional URL param): pre-selects which student the request
    is about. Parents can also pick from a dropdown on the form.
    """
    parent   = _get_parent_profile(request)
    students = parent.get_students()

    # Pre-select student if passed in URL
    preselected_student = None
    if student_id:
        preselected_student = _get_owned_student(parent, student_id)

    if request.method == 'GET':
        return render(request, 'dashboard/parent_new_request.html', {
            'parent':               parent,
            'students':             students,
            'preselected_student':  preselected_student,
            'request_type_choices': REQUEST_TYPE_CHOICES,
            'post':                 {},
            'errors':               {},
        })

    # ── POST ─────────────────────────────────────────────────────────────────
    post         = request.POST
    errors       = {}

    request_type = post.get('request_type', '').strip()
    subject      = post.get('subject', '').strip()
    message_text = post.get('message', '').strip()
    student_pk   = post.get('student_id', '').strip()
    is_urgent    = post.get('is_urgent') == 'on'

    # Validation
    if not request_type:
        errors['request_type'] = 'Please select a request type.'
    elif request_type not in VALID_REQUEST_TYPES:
        errors['request_type'] = 'Invalid request type selected.'

    if not subject:
        errors['subject'] = 'Subject is required.'
    elif len(subject) > 200:
        errors['subject'] = 'Subject must be 200 characters or fewer.'

    if not message_text:
        errors['message'] = 'Message body is required.'

    student_obj = None
    if student_pk:
        try:
            student_obj = _get_owned_student(parent, int(student_pk))
        except (ValueError, Exception):
            errors['student_id'] = 'Invalid student selection.'

    if errors:
        return render(request, 'dashboard/parent_new_request.html', {
            'parent':               parent,
            'students':             students,
            'preselected_student':  preselected_student,
            'request_type_choices': REQUEST_TYPE_CHOICES,
            'post':                 post,
            'errors':               errors,
        })

    # Save
    reference_number = _generate_reference_number()

    with transaction.atomic():
        new_request = ParentsRequest.objects.create(
            reference_number = reference_number,
            parent           = request.user,
            student          = student_obj,
            request_type     = request_type,
            subject          = subject,
            message          = message_text,
            is_urgent        = is_urgent,
            status           = 'pending',
        )

        # Handle optional file attachment
        if request.FILES.get('attachment'):
            new_request.attachment = request.FILES['attachment']
            new_request.save(update_fields=['attachment'])

    messages.success(
        request,
        f'Your request <strong>{reference_number}</strong> has been submitted successfully. '
        f'The school will respond shortly.',
    )
    return redirect('parent_communication')
