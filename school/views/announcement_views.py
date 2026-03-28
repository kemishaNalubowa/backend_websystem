# school/views/announcement_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All SchoolAnnouncement views.
#
# Views:
#   announcement_list    — list with full stats and filters
#   announcement_add     — add a new announcement
#   announcement_edit    — edit an existing announcement
#   announcement_delete  — confirm + perform deletion
#   announcement_detail  — full single announcement page with stats
#   announcement_toggle_published — POST-only quick publish/unpublish
#
# Rules (same as all previous views in this project):
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via announcement_utils
#   - django.contrib.messages for all feedback
#   - login_required on every view
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academics.models import SchoolClass
from school.models import SchoolAnnouncement
from school.utils.announcement_utils import (
    AUDIENCE_LABELS,
    PRIORITY_LABELS,
    PRIORITY_ORDER,
    get_announcement_detail_stats,
    get_announcement_list_stats,
    validate_and_parse_announcement,
)

_T = 'school/announcements/'

_AUDIENCE_CHOICES  = list(AUDIENCE_LABELS.items())
_PRIORITY_CHOICES  = list(PRIORITY_LABELS.items())


# ── Private helper ─────────────────────────────────────────────────────────────

def _get_form_lookups() -> dict:
    """Querysets every form template needs."""
    return {
        'all_classes':      SchoolClass.objects.filter(
                                is_active=True
                            ).order_by('section', 'level', 'stream'),
        'audience_choices': _AUDIENCE_CHOICES,
        'priority_choices': _PRIORITY_CHOICES,
    }


def _apply_to_instance(instance: SchoolAnnouncement, cleaned: dict) -> None:
    """Write all cleaned scalar and FK fields onto an instance."""
    scalar_fields = (
        'title', 'content', 'audience', 'priority',
        'is_published', 'published_at', 'expires_at',
    )
    for f in scalar_fields:
        if f in cleaned:
            setattr(instance, f, cleaned[f])

    if 'school_class_id' in cleaned:
        instance.school_class_id = cleaned['school_class_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. ANNOUNCEMENTS LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def announcement_list(request):
    """
    All announcements with statistics and filters.

    Stats cards:
        total, published, draft, active (published + not expired),
        expired, critical (active), urgent (active).
        By-audience and by-priority breakdowns.

    Filters (GET params — all stackable):
        ?q=             full-text search in title + content
        ?audience=      all | teachers | parents | students
        ?priority=      normal | urgent | critical
        ?published=1|0  published or draft
        ?status=active|expired|draft
        ?class=<id>     filter by target class FK
    """
    now = timezone.now()
    qs  = SchoolAnnouncement.objects.select_related(
        'school_class', 'posted_by'
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    search           = request.GET.get('q', '').strip()
    audience_filter  = request.GET.get('audience', '').strip()
    priority_filter  = request.GET.get('priority', '').strip()
    published_filter = request.GET.get('published', '').strip()
    status_filter    = request.GET.get('status', '').strip()
    class_filter     = request.GET.get('class', '').strip()

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(content__icontains=search)
        )

    if audience_filter:
        qs = qs.filter(audience=audience_filter)

    if priority_filter:
        qs = qs.filter(priority=priority_filter)

    if published_filter == '1':
        qs = qs.filter(is_published=True)
    elif published_filter == '0':
        qs = qs.filter(is_published=False)

    if status_filter == 'active':
        qs = qs.filter(is_published=True).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )
    elif status_filter == 'expired':
        qs = qs.filter(is_published=True, expires_at__lt=now)
    elif status_filter == 'draft':
        qs = qs.filter(is_published=False)

    if class_filter:
        qs = qs.filter(school_class__pk=class_filter)

    # Default sort: critical first → urgent → normal, then newest
    qs = qs.order_by(
        '-is_published',
        '-created_at',
    )

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # Annotate each page item with live status for the template
    items = list(page_obj.object_list)
    for item in items:
        item._is_expired = (
            item.expires_at is not None and item.expires_at < now
        )
        item.is_active = item.is_published and not item._is_expired
        item.priority_order = PRIORITY_ORDER.get(item.priority, 99)
        item.audience_label = AUDIENCE_LABELS.get(item.audience, item.audience)
        item.priority_label = PRIORITY_LABELS.get(item.priority, item.priority)

    stats = get_announcement_list_stats()

    context = {
        'announcements':    items,
        'page_obj':         page_obj,
        # active filters
        'search':           search,
        'audience_filter':  audience_filter,
        'priority_filter':  priority_filter,
        'published_filter': published_filter,
        'status_filter':    status_filter,
        'class_filter':     class_filter,
        # choice lists for filter controls
        'audience_choices': _AUDIENCE_CHOICES,
        'priority_choices': _PRIORITY_CHOICES,
        'all_classes':      SchoolClass.objects.filter(
                                is_active=True
                            ).order_by('section', 'level', 'stream'),
        'now':              now,
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD ANNOUNCEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def announcement_add(request):
    """
    Add a new announcement.
    GET  — blank form; published_at pre-set to now for convenience.
    POST — validate; save on success; re-render with per-field errors on failure.
    """
    lookups = _get_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'form_title': 'New Announcement',
            'action':     'add',
            'post':       {},
            'errors':     {},
            'now_str':    timezone.now().strftime('%Y-%m-%dT%H:%M'),
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_announcement(request.POST, request.FILES)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': 'New Announcement',
            'action':     'add',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            ann = SchoolAnnouncement()
            _apply_to_instance(ann, cleaned)
            ann.posted_by = request.user

            # Auto-set published_at to now if being published without a set date
            if ann.is_published and not ann.published_at:
                ann.published_at = timezone.now()

            # Handle attachment upload
            if not cleaned.get('clear_attachment') and request.FILES.get('attachment'):
                ann.attachment = request.FILES['attachment']

            ann.save()
    except Exception as exc:
        messages.error(request, f'Could not save announcement: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title': 'New Announcement',
            'action':     'add',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Announcement "{ann.title}" has been '
        f'{"published" if ann.is_published else "saved as draft"} successfully.'
    )
    return redirect('school:announcement_detail', pk=ann.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT ANNOUNCEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def announcement_edit(request, pk):
    """
    Edit an existing announcement.
    GET  — form pre-filled with current values.
    POST — validate; save; re-render with errors on failure.

    Attachment handling:
        - 'clear_attachment' checkbox in POST removes the existing file.
        - Uploading a new file replaces the existing one.
        - Submitting without touching the file field leaves it unchanged.
    """
    ann     = get_object_or_404(SchoolAnnouncement, pk=pk)
    lookups = _get_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'announcement': ann,
            'form_title':   f'Edit — {ann.title}',
            'action':       'edit',
            'post':         {},
            'errors':       {},
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_announcement(
        request.POST, request.FILES, instance=ann
    )

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'announcement': ann,
            'form_title':   f'Edit — {ann.title}',
            'action':       'edit',
            'post':         request.POST,
            'errors':       errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            was_draft = not ann.is_published
            _apply_to_instance(ann, cleaned)

            # Auto-set published_at when transitioning from draft → published
            if ann.is_published and was_draft and not ann.published_at:
                ann.published_at = timezone.now()

            # Attachment handling
            if cleaned.get('clear_attachment'):
                if ann.attachment:
                    ann.attachment.delete(save=False)
                ann.attachment = None
            elif request.FILES.get('attachment'):
                if ann.attachment:
                    ann.attachment.delete(save=False)
                ann.attachment = request.FILES['attachment']

            ann.save()
    except Exception as exc:
        messages.error(request, f'Could not update announcement: {exc}')
        return render(request, f'{_T}form.html', {
            'announcement': ann,
            'form_title':   f'Edit — {ann.title}',
            'action':       'edit',
            'post':         request.POST,
            'errors':       {},
            **lookups,
        })

    messages.success(request, f'Announcement "{ann.title}" has been updated.')
    return redirect('school:announcement_detail', pk=ann.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE ANNOUNCEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def announcement_delete(request, pk):
    """
    Delete an announcement.
    GET  — confirmation page showing the announcement summary.
    POST — delete the record and its attachment file, redirect to list.
    """
    ann = get_object_or_404(SchoolAnnouncement, pk=pk)

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {
            'announcement':   ann,
            'audience_label': AUDIENCE_LABELS.get(ann.audience, ann.audience),
            'priority_label': PRIORITY_LABELS.get(ann.priority, ann.priority),
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    title = ann.title
    try:
        # Delete the attachment from disk before removing the record
        if ann.attachment:
            ann.attachment.delete(save=False)
        ann.delete()
        messages.success(request, f'Announcement "{title}" has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete announcement: {exc}')

    return redirect('school:announcement_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. ANNOUNCEMENT DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def announcement_detail(request, pk):
    """
    Full single announcement page.

    Displays:
        - Full title, content, audience, priority, posted_by, dates
        - Attachment download link (if any)
        - Target class (if class-specific)
        - Status badge: Active / Draft / Expired
        - Days until expiry (or days since expiry)
        - Prev / Next published announcement navigation
        - Related announcements (same audience or same priority)
    """
    ann   = get_object_or_404(
        SchoolAnnouncement.objects.select_related('school_class', 'posted_by'),
        pk=pk
    )
    stats = get_announcement_detail_stats(ann)

    context = {
        'announcement': ann,
        'now':          timezone.now(),
        'page_title':   ann.title,
        **stats,
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. TOGGLE PUBLISHED  (POST-only quick action)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def announcement_toggle_published(request, pk):
    """
    Quick POST-only toggle for is_published.
    When publishing: auto-sets published_at to now if not already set.
    When unpublishing: clears published_at so it can be reset on next publish.
    Redirects back to HTTP_REFERER or to the announcement detail page.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('school:announcement_list')

    ann = get_object_or_404(SchoolAnnouncement, pk=pk)
    ann.is_published = not ann.is_published

    if ann.is_published and not ann.published_at:
        ann.published_at = timezone.now()

    ann.save(update_fields=['is_published', 'published_at'])

    state = 'published' if ann.is_published else 'unpublished (saved as draft)'
    messages.success(request, f'"{ann.title}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('school:announcement_detail', pk=ann.pk)
