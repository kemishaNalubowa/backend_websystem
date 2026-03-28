from django.shortcuts         import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib           import messages
from django.db                import transaction
from django.utils             import timezone

from .models  import ParentsRequest, ParentsRequestReply
from .utils   import (
    generate_reference_number,
    validate_parent_request,
    validate_request_reply,
    is_staff_user,
    get_parent_profile,
    user_can_access_request,
    VALID_REQUEST_TYPES,
    VALID_STATUSES,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Add Parent Request
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def add_parent_request(request):
    """
    Both parents and staff can open a new request.
    - Parents: the request is automatically linked to their Parent profile.
    - Staff: must select a parent from a dropdown (parent_id POST field).
    """
    user         = request.user
    staff        = is_staff_user(user)
    parent_obj   = get_parent_profile(user)

    # A non-staff user with no parent profile has no business here
    if not staff and not parent_obj:
        messages.error(request, 'Your account is not linked to a parent profile.')
        return redirect('dashboard')

    if request.method == 'POST':
        errors, cleaned = validate_parent_request(request.POST, request.FILES)

        # ── Resolve which parent this request belongs to ───────────────────
        if staff:
            from accounts.models import Parent          # local import to avoid circulars
            parent_id = request.POST.get('parent_id', '').strip()
            if not parent_id:
                errors['parent_id'] = 'Please select a parent.'
            else:
                try:
                    target_parent = Parent.objects.get(pk=parent_id)
                    cleaned['parent'] = target_parent
                except Parent.DoesNotExist:
                    errors['parent_id'] = 'Selected parent does not exist.'
        else:
            cleaned['parent'] = parent_obj

        # ── Optionally link to a student ───────────────────────────────────
        student_id = request.POST.get('student_id', '').strip()
        if student_id:
            from students.models import Student
            try:
                student = Student.objects.get(pk=student_id)
                cleaned['student'] = student
            except Student.DoesNotExist:
                errors['student_id'] = 'Selected student does not exist.'

        if errors:
            messages.error(request, 'Please correct the errors below.')
            return render(request, 'requests/add_parent_request.html', {
                'errors':        errors,
                'post':          request.POST,
                'request_types': ParentsRequest.REQUEST_TYPE_CHOICES,
                'is_staff':      staff,
            })

        with transaction.atomic():
            pr = ParentsRequest.objects.create(
                reference_number = generate_reference_number(),
                parent           = cleaned['parent'],
                student          = cleaned.get('student'),
                request_type     = cleaned['request_type'],
                subject          = cleaned['subject'],
                message          = cleaned['message'],
                is_urgent        = cleaned['is_urgent'],
                attachment       = cleaned.get('attachment'),
                status           = 'pending',
            )

        messages.success(
            request,
            f'Request "{pr.reference_number}" submitted successfully. '
            f'We will respond as soon as possible.'
        )
        return redirect('requests:detail', ref=pr.reference_number)

    # GET
    return render(request, 'communication/add_parent_request.html', {
        'errors':        {},
        'post':          {},
        'request_types': ParentsRequest.REQUEST_TYPE_CHOICES,
        'is_staff':      staff,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 2. Parent Requests List
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def parent_requests_list(request):
    """
    - Staff see all requests, with optional filters.
    - Parents see only their own requests.
    """
    user       = request.user
    staff      = is_staff_user(user)
    parent_obj = get_parent_profile(user)

    if not staff and not parent_obj:
        messages.error(request, 'Your account is not linked to a parent profile.')
        return redirect('dashboard')

    qs = ParentsRequest.objects.select_related('parent', 'student', 'assigned_to')

    if not staff:
        qs = qs.filter(parent=parent_obj)

    # ── Filters (available to both, but staff get more) ────────────────────
    status_filter = request.GET.get('status', '').strip()
    type_filter   = request.GET.get('request_type', '').strip()
    urgent_filter = request.GET.get('urgent', '').strip()
    search        = request.GET.get('q', '').strip()

    if status_filter and status_filter in dict(ParentsRequest.STATUS_CHOICES):
        qs = qs.filter(status=status_filter)

    if type_filter and type_filter in dict(ParentsRequest.REQUEST_TYPE_CHOICES):
        qs = qs.filter(request_type=type_filter)

    if urgent_filter == '1':
        qs = qs.filter(is_urgent=True)

    if search:
        qs = qs.filter(
            reference_number__icontains=search
        ) | qs.filter(
            subject__icontains=search
        )

    # ── Summary counts (for the stats bar) ────────────────────────────────
    base_qs    = ParentsRequest.objects.all() if staff else ParentsRequest.objects.filter(parent=parent_obj)
    total      = base_qs.count()
    pending    = base_qs.filter(status='pending').count()
    resolved   = base_qs.filter(status='resolved').count()
    urgent     = base_qs.filter(is_urgent=True).count()

    return render(request, 'communication/parent_requests_list.html', {
        'requests':       qs,
        'is_staff':       staff,
        'status_choices': ParentsRequest.STATUS_CHOICES,
        'type_choices':   ParentsRequest.REQUEST_TYPE_CHOICES,
        # active filters (to keep form state)
        'filter_status':  status_filter,
        'filter_type':    type_filter,
        'filter_urgent':  urgent_filter,
        'search':         search,
        # summary
        'total':          total,
        'pending':        pending,
        'resolved':       resolved,
        'urgent':         urgent,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 3. Parent Request Detail
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def parent_request_detail(request, ref):
    """
    Shows the full request thread with all replies.
    Parents see only parent-visible replies; staff see all.
    Marks unread staff replies as read when a parent views them.
    """
    user  = request.user
    staff = is_staff_user(user)

    parent_request = get_object_or_404(ParentsRequest, reference_number=ref)

    if not user_can_access_request(user, parent_request):
        messages.error(request, 'You do not have permission to view this request.')
        return redirect('requests:list')

    # ── Mark replies as read when parent opens the detail page ────────────
    if not staff:
        unread_replies = parent_request.replies.filter(
            is_internal=False,
            is_read_by_parent=False
        )
        if unread_replies.exists():
            unread_replies.update(
                is_read_by_parent=True,
                read_at=timezone.now()
            )

    # ── Fetch replies ──────────────────────────────────────────────────────
    replies_qs = parent_request.replies.select_related('replied_by')
    if not staff:
        replies_qs = replies_qs.filter(is_internal=False)

    return render(request, 'communication/parent_request_detail.html', {
        'parent_request':  parent_request,
        'replies':         replies_qs,
        'is_staff':        staff,
        'status_choices':  ParentsRequest.STATUS_CHOICES,
        # pass empty dicts so the template reply form has defaults
        'reply_errors':    {},
        'reply_post':      {},
    })


# ─────────────────────────────────────────────────────────────────────────────
# 4. Add Parent Request Reply
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def add_parent_request_reply(request, ref):
    """
    POST-only view. Both parents and staff can reply.
    Staff additionally can:
      - mark the reply as internal (hidden from parent)
      - change the request status in the same submission
    On validation failure, re-renders the detail page with errors inlined.
    """
    if request.method != 'POST':
        return redirect('requests:detail', ref=ref)

    user  = request.user
    staff = is_staff_user(user)

    parent_request = get_object_or_404(ParentsRequest, reference_number=ref)

    if not user_can_access_request(user, parent_request):
        messages.error(request, 'You do not have permission to reply to this request.')
        return redirect('requests:list')

    # ── Guard: don't allow replies on closed/rejected requests (parents only)
    if not staff and parent_request.status in ('closed', 'rejected'):
        messages.error(request, 'This request is closed and no longer accepts replies.')
        return redirect('requests:detail', ref=ref)

    errors, cleaned = validate_request_reply(request.POST, request.FILES, is_staff=staff)

    if errors:
        messages.error(request, 'Please fix the errors in your reply.')

        # Re-render the detail page with reply errors shown inline
        replies_qs = parent_request.replies.select_related('replied_by')
        if not staff:
            replies_qs = replies_qs.filter(is_internal=False)

        return render(request, 'communication/parent_request_detail.html', {
            'parent_request': parent_request,
            'replies':        replies_qs,
            'is_staff':       staff,
            'status_choices': ParentsRequest.STATUS_CHOICES,
            'reply_errors':   errors,
            'reply_post':     request.POST,
        })

    with transaction.atomic():
        # ── Create the reply ───────────────────────────────────────────────
        reply_kwargs = dict(
            request    = parent_request,
            replied_by = user,
            message    = cleaned['message'],
            is_internal= cleaned['is_internal'],
        )
        if 'attachment' in cleaned:
            reply_kwargs['attachment'] = cleaned['attachment']

        ParentsRequestReply.objects.create(**reply_kwargs)

        # ── Update request status if staff changed it ──────────────────────
        if staff and 'new_status' in cleaned:
            new_status = cleaned['new_status']
            parent_request.status = new_status
            if new_status == 'resolved':
                parent_request.resolved_at = timezone.now()
            parent_request.save(update_fields=['status', 'resolved_at'])

    messages.success(request, 'Your reply has been posted successfully.')
    return redirect('requests:detail', ref=ref)
