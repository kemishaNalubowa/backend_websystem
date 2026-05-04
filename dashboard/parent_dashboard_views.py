from decimal import Decimal
from django.shortcuts import get_object_or_404
from academics.models import Term, SchoolSupportedClasses
from fees.models import (
    SchoolFees, FeesPayment, StudentFeesPaymentsStatus,
    SchoolScholasticRequirements, StudentScholasticRequirementStatus,
    ScholasticRequirementPayment,
)
from django.contrib.auth.decorators import login_required
from assessments.models import AssessmentPerformance
from students.models import StudentClassPromotion


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

# At the top of the file, add these imports:
from decimal import Decimal
from fees.models import StudentFeesPaymentsStatus   # adjust app name if different








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


def _get_student_classes(student):
    """
    Walks StudentClassPromotion to collect every class the student
    has ever been in, ordered oldest first.
    Falls back to student.current_class if no promotion records exist.
    """
    promotions = StudentClassPromotion.objects.filter(
        student=student,
    ).select_related(
        'previous_class', 'current_class', 'upcoming_class', 'academic_year'
    ).order_by('academic_year')

    seen_ids = set()
    classes  = []

    for p in promotions:
        for cls in [p.previous_class, p.current_class, p.upcoming_class]:
            if cls is not None and cls.pk not in seen_ids:
                seen_ids.add(cls.pk)
                classes.append(cls)

    # If no promotion records at all, fall back to current_class
    if not classes and student.current_class:
        classes.append(student.current_class)

    return classes

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

    events = SchoolEvent.objects.filter(
        start_date__gte=today,
        is_published=True,
    ).order_by('start_date')[:5]

    announcements = SchoolAnnouncement.objects.filter(
        is_published=True
    ).order_by('-created_at')[:5]

    recent_requests = ParentsRequest.objects.filter(
        parent=request.user
    ).order_by('-created_at')[:5]

    return render(request, 'dashboard/parent/parent_home.html', {
        'parent':           parent,
        'students':         students,
        'events':           events,
        'announcements':    announcements,
        'recent_requests':  recent_requests,
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

    return render(request,  'dashboard/parent/parent_communication.html', {
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
    Parent can also submit a reply via POST.
    """
    parent         = _get_parent_profile(request)
    parent_request = get_object_or_404(
        ParentsRequest,
        pk=request_id,
        parent=request.user,   # only this parent's requests
    )

    # ── POST: parent submitting a reply ──────────────────────────────────────
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()

        errors = {}
        if not body:
            errors['body'] = 'Reply cannot be empty.'

        if errors:
            # Re-fetch replies so the page still renders correctly
            replies = ParentsRequestReply.objects.filter(
                request=parent_request,
                is_internal=False,
            ).order_by('created_at')

            return render(request,  'dashboard/parent/parent_request_detail.html', {
                'parent':         parent,
                'parent_request': parent_request,
                'replies':        replies,
                'errors':         errors,
                'post':           request.POST,
            })

        with transaction.atomic():
            ParentsRequestReply.objects.create(
                request          = parent_request,
                replied_by       = request.user,
                message             = body,
                is_internal      = False,        # parent replies are never internal
                is_read_by_parent= True,         # parent wrote it, already "read"
                read_at          = timezone.now(),
            )

            # Optional: re-open the request if it was marked closed/resolved
            if parent_request.status in ('resolved', 'closed'):
                parent_request.status = 'open'
                parent_request.save(update_fields=['status'])

        messages.success(request, 'Your reply has been sent.')
        return redirect('parent_request_detail', request_id=request_id)

    # ── GET: mark unread staff replies as read ────────────────────────────────
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

    replies = ParentsRequestReply.objects.filter(
        request=parent_request,
        is_internal=False,
    ).order_by('created_at')

    return render(request,  'dashboard/parent/parent_request_detail.html', {
        'parent':         parent,
        'parent_request': parent_request,
        'replies':        replies,
        'errors':         {},
        'post':           {},
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
        return render(request,  'dashboard/parent/parent_new_request.html', {
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
        return render(request,  'dashboard/parent/parent_new_request.html', {
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
















# ── 1. Student overview ────────────────────────────────────────────────────
@login_required
def parent_student_overview(request, student_id):
    parent  = _get_parent_profile(request)
    student = _get_owned_student(parent, student_id)

    class_list    = _get_student_classes(student)
    current_class = student.current_class

    return render(request,  'dashboard/parent/parent_student.html', {
        'parent':        parent,
        'student':       student,
        'current_class': current_class,
        'class_list':    class_list,
    })


# ── 2. Class page — list terms ─────────────────────────────────────────────
@login_required
def parent_student_class(request, student_id, class_id):
    parent       = _get_parent_profile(request)
    student      = _get_owned_student(parent, student_id)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)

    # Collect all term IDs that have data for this class
    fees_term_ids = SchoolFees.objects.filter(
        affected_school_class__school_class=school_class,
        is_active=True,
    ).values_list('term_id', flat=True).distinct()

    scholastic_term_ids = SchoolScholasticRequirements.objects.filter(
        assigned_classes__school_class=school_class,
        is_active=True,
    ).values_list('term_id', flat=True).distinct()

    all_term_ids = set(list(fees_term_ids) + list(scholastic_term_ids))
    # NEW
    terms = Term.objects.filter(
        pk__in=all_term_ids,
    ).order_by('-is_active', '-start_date')

    terms_data = []
    for term in terms:
        fees_qs = SchoolFees.objects.filter(
            affected_school_class__school_class=school_class,
            term=term,
            is_active=True,
        ).distinct()

        statuses = StudentFeesPaymentsStatus.objects.filter(
            student=student,
            school_fees__in=fees_qs,
        )

        total_fees    = sum(f.amount for f in fees_qs)
        total_paid    = sum(s.amount_paid for s in statuses)
        total_balance = total_fees - total_paid
        paid_count    = statuses.filter(fully_paid=True).count()

        scholastic_total = SchoolScholasticRequirements.objects.filter(
            assigned_classes__school_class=school_class,
            term=term,
            is_active=True,
        ).distinct().count()

        scholastic_met = StudentScholasticRequirementStatus.objects.filter(
            student=student,
            requirement__assigned_classes__school_class=school_class,
            requirement__term=term,
            fully_met=True,
        ).count()

        terms_data.append({
            'term':             term,
            'total_fees':       total_fees,
            'total_paid':       total_paid,
            'total_balance':    total_balance,
            'fees_items':       fees_qs.count(),
            'paid_count':       paid_count,
            'scholastic_total': scholastic_total,
            'scholastic_met':   scholastic_met,
        })

    return render(request,  'dashboard/parent/parent_student_class.html', {
        'parent':        parent,
        'student':       student,
        'school_class':  school_class,
        'current_class': student.current_class,
        'terms_data':    terms_data,
    })


# ── 3. Term overview — section mini cards ─────────────────────────────────
@login_required
def parent_student_class_term(request, student_id, class_id, term_id):
    parent       = _get_parent_profile(request)
    student      = _get_owned_student(parent, student_id)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)
    term         = get_object_or_404(Term, pk=term_id)

    # ── Fees summary ───────────────────────────────────────────────────────
    fees_qs = SchoolFees.objects.filter(
        affected_school_class__school_class=school_class,
        term=term,
        is_active=True,
    ).distinct()

    statuses   = StudentFeesPaymentsStatus.objects.filter(
        student=student, school_fees__in=fees_qs,
    )
    total_fees    = sum(f.amount for f in fees_qs)
    total_paid    = sum(s.amount_paid for s in statuses)
    total_balance = total_fees - total_paid
    fully_paid_count = statuses.filter(fully_paid=True).count()

    fees_summary = {
        'total_fees':        total_fees,
        'total_paid':        total_paid,
        'total_balance':     total_balance,
        'fully_paid_count':  fully_paid_count,
        'total_items':       fees_qs.count(),
    }

    # ── Scholastic summary ─────────────────────────────────────────────────
    scholastic_qs = SchoolScholasticRequirements.objects.filter(
        assigned_classes__school_class=school_class,
        term=term,
        is_active=True,
    ).distinct()

    scholastic_met = StudentScholasticRequirementStatus.objects.filter(
        student=student,
        requirement__in=scholastic_qs,
        fully_met=True,
    ).count()

    scholastic_summary = {
        'total': scholastic_qs.count(),
        'met':   scholastic_met,
    }

    # ── Performance summary ────────────────────────────────────────────────
    performance_qs = AssessmentPerformance.objects.filter(
    student=student,
    assessment__term=term,
    )
    performance_count = performance_qs.count()

    return render(request,  'dashboard/parent/parent_student_class_term.html', {
        'parent':              parent,
        'student':             student,
        'school_class':        school_class,
        'current_class':       student.current_class,
        'term':                term,
        'fees_summary':        fees_summary,
        'scholastic_summary':  scholastic_summary,
        'performance_count':   performance_count,
    })


# ── 4. Fees structure page ─────────────────────────────────────────────────
@login_required
def parent_student_class_term_fees(request, student_id, class_id, term_id):
    parent       = _get_parent_profile(request)
    student      = _get_owned_student(parent, student_id)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)
    term         = get_object_or_404(Term, pk=term_id)

    fees_qs = SchoolFees.objects.filter(
        affected_school_class__school_class=school_class,
        term=term,
        is_active=True,
    ).select_related('term').distinct().order_by('fees_type')

    total_fees_amount = Decimal('0')
    total_paid        = Decimal('0')
    total_balance     = Decimal('0')
    fully_paid_count  = 0
    fees_structure_data = []

    for fee in fees_qs:
        status = StudentFeesPaymentsStatus.objects.filter(
            student=student,
            school_fees=fee,
        ).first()

        raw_txns = FeesPayment.objects.filter(
            student=student,
            school_fees=fee,
        ).order_by('payment_date', 'created_at')

        running       = fee.amount
        enriched_txns = []
        for txn in raw_txns:
            prev_bal = running
            running  = running - txn.amount
            enriched_txns.append({
                'txn':             txn,
                'prev_balance':    prev_bal,
                'current_balance': max(running, Decimal('0')),
            })

        fees_structure_data.append({
            'fee':          fee,
            'status':       status,
            'transactions': enriched_txns,
        })

        total_fees_amount += fee.amount
        if status:
            total_paid    += status.amount_paid
            total_balance += status.amount_balance
            if status.fully_paid:
                fully_paid_count += 1
        else:
            total_balance += fee.amount

    fees_stats = {
        'total_fees':       total_fees_amount,
        'total_paid':       total_paid,
        'total_balance':    total_balance,
        'fully_paid_count': fully_paid_count,
        'total_items':      len(fees_structure_data),
    }

    return render(request,  'dashboard/parent/parent_student_class_term_fees.html', {
        'parent':               parent,
        'student':              student,
        'school_class':         school_class,
        'current_class':        student.current_class,
        'term':                 term,
        'fees_structure_data':  fees_structure_data,
        'fees_stats':           fees_stats,
    })


# ── 5. Scholastic requirements page ───────────────────────────────────────
@login_required
def parent_student_class_term_scholastic(request, student_id, class_id, term_id):
    parent       = _get_parent_profile(request)
    student      = _get_owned_student(parent, student_id)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)
    term         = get_object_or_404(Term, pk=term_id)

    scholastic_qs = SchoolScholasticRequirements.objects.filter(
        assigned_classes__school_class=school_class,
        term=term,
        is_active=True,
    ).distinct().order_by('item_name')

    total_items      = 0
    fully_met_count  = 0
    total_cash_value = Decimal('0')
    total_cash_paid  = Decimal('0')
    scholastic_data  = []

    for req in scholastic_qs:
        status = StudentScholasticRequirementStatus.objects.filter(
            student=student,
            requirement=req,
        ).first()

        transactions = ScholasticRequirementPayment.objects.filter(
            student=student,
            requirement=req,
        ).order_by('payment_date', 'created_at')

        enriched_txns = []
        for txn in transactions:
            if txn.brought_item and txn.brought_cash:
                txn_type = 'Mixed'
            elif txn.brought_item:
                txn_type = 'Items'
            else:
                txn_type = 'Cash'
            enriched_txns.append({
                'txn':      txn,
                'txn_type': txn_type,
            })

        scholastic_data.append({
            'req':          req,
            'status':       status,
            'transactions': enriched_txns,
        })

        # Stats
        total_items      += 1
        total_cash_value += req.monetary_value
        if status:
            total_cash_paid += status.amount_paid_ugx
            if status.fully_met:
                fully_met_count += 1

    scholastic_stats = {
        'total_items':      total_items,
        'fully_met_count':  fully_met_count,
        'total_cash_value': total_cash_value,
        'total_cash_paid':  total_cash_paid,
    }

    return render(request, 'dashboard/parent/parent_student_class_term_scholastic.html', {
        'parent':            parent,
        'student':           student,
        'school_class':      school_class,
        'current_class':     student.current_class,
        'term':              term,
        'scholastic_data':   scholastic_data,
        'scholastic_stats':  scholastic_stats,
    })

















# ── 6. Performance page ────────────────────────────────────────────────────
@login_required
def parent_student_class_term_scholastic_performance(request, student_id, class_id, term_id):
    parent       = _get_parent_profile(request)
    student      = _get_owned_student(parent, student_id)
    school_class = get_object_or_404(SchoolSupportedClasses, pk=class_id)
    term         = get_object_or_404(Term, pk=term_id)

    from assessments.models import AssessmentSubject, AssessmentTotalMark

    performance_qs = AssessmentPerformance.objects.filter(
        student=student,
        assessment__term=term,
        school_class=school_class,
    ).select_related(
        'assessment',
        'assessment__term',
        'subject',          # direct FK on AssessmentPerformance
    ).order_by('subject__name', 'assessment__date_given')

    total_assessments    = performance_qs.count()
    performance_data     = []

    for perf in performance_qs:
        # Get the passmark from AssessmentSubject for this assessment + subject + class
        assessment_subject = AssessmentSubject.objects.filter(
            assessment=perf.assessment,
            subject=perf.subject,
            assessment_class=school_class,
        ).first()
        pass_mark = assessment_subject.passmark if assessment_subject else None

        # Get total mark from AssessmentTotalMark
        total_mark_obj = AssessmentTotalMark.objects.filter(
            assessment=perf.assessment,
            subject=assessment_subject,
        ).first() if assessment_subject else None
        total_mark = total_mark_obj.total_mark if total_mark_obj else None

        # Determine pass/fail
        if pass_mark is not None and perf.marks_obtained is not None:
            passed = perf.marks_obtained >= pass_mark
        else:
            passed = None

        # Percentage
        if total_mark and total_mark > 0:
            percentage = round((perf.marks_obtained / total_mark) * 100, 1)
        else:
            percentage = None

        performance_data.append({
            'perf':       perf,
            'assessment': perf.assessment,
            'subject':    perf.subject,
            'obtained':   perf.marks_obtained,
            'total':      total_mark,
            'pass_mark':  pass_mark,
            'passed':     passed,
            'percentage': percentage,
            'comment':    perf.comment,
        })

    # Summary stats
    scored = [r for r in performance_data if r['percentage'] is not None]
    average_percentage = (
        round(sum(r['percentage'] for r in scored) / len(scored), 1)
        if scored else 0
    )
    passed_count = sum(1 for r in performance_data if r['passed'] is True)

    performance_stats = {
        'total_assessments':  total_assessments,
        'average_percentage': average_percentage,
        'passed_count':       passed_count,
    }

    return render(request, 'dashboard/parent/parent_student_class_term_performance.html', {
        'parent':             parent,
        'student':            student,
        'school_class':       school_class,
        'current_class':      student.current_class,
        'term':               term,
        'performance_data':   performance_data,
        'performance_stats':  performance_stats,
    })














