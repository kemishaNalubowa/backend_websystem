# school/views/announcement_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Rules: FBV only | no Forms | no CBVs | no JSON | manual validation |
#        messages for feedback | login_required | transaction.atomic on saves
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from academics.models import SchoolSupportedClasses
from school.models import SchoolAnnouncement
from permissions.decorators import has_permission

_T = 'school/announcements/'

AUDIENCE_CHOICES = [
    ('all',      'Everyone'),
    ('teachers', 'Teachers & Staff'),
    ('parents',  'Parents & Guardians'),
    ('students', 'Students'),
]
PRIORITY_CHOICES = [
    ('normal',   'Normal'),
    ('urgent',   'Urgent'),
    ('critical', 'Critical'),
]
_VALID_AUDIENCES  = {k for k, _ in AUDIENCE_CHOICES}
_VALID_PRIORITIES = {k for k, _ in PRIORITY_CHOICES}


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_lookups():
    return {
        'audience_choices': AUDIENCE_CHOICES,
        'priority_choices': PRIORITY_CHOICES,
        'all_classes': SchoolSupportedClasses.objects.select_related(
            'supported_class'
        ).order_by('supported_class__order'),
    }


def _validate(post):
    """Manual field-by-field validation. Returns (cleaned, errors)."""
    errors  = {}
    cleaned = {}

    title = post.get('title', '').strip()
    if not title:
        errors['title'] = 'Title is required.'
    elif len(title) > 200:
        errors['title'] = 'Title must be 200 characters or fewer.'
    else:
        cleaned['title'] = title

    content = post.get('content', '').strip()
    if not content:
        errors['content'] = 'Message body is required.'
    else:
        cleaned['content'] = content

    audience = post.get('audience', '').strip()
    if audience not in _VALID_AUDIENCES:
        errors['audience'] = 'Select a valid audience.'
    else:
        cleaned['audience'] = audience

    priority = post.get('priority', '').strip()
    if priority not in _VALID_PRIORITIES:
        errors['priority'] = 'Select a valid priority.'
    else:
        cleaned['priority'] = priority

    class_pk = post.get('school_class', '').strip()
    if class_pk:
        try:
            cleaned['school_class_id'] = int(class_pk)
        except ValueError:
            errors['school_class'] = 'Invalid class selection.'
    else:
        cleaned['school_class_id'] = None

    for field in ('published_at', 'expires_at'):
        raw = post.get(field, '').strip()
        if raw:
            dt = parse_datetime(raw)
            if dt is None:
                errors[field] = f'Invalid date/time.'
            else:
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                cleaned[field] = dt
        else:
            cleaned[field] = None

    cleaned['is_published']     = bool(post.get('is_published'))
    cleaned['clear_attachment'] = bool(post.get('clear_attachment'))

    return cleaned, errors


def _apply(ann, cleaned, is_new=False):
    """Write cleaned data onto a SchoolAnnouncement instance."""
    ann.title           = cleaned['title']
    ann.content         = cleaned['content']
    ann.audience        = cleaned['audience']
    ann.priority        = cleaned['priority']
    ann.school_class_id = cleaned['school_class_id']
    ann.expires_at      = cleaned['expires_at']

    was_draft = not ann.is_published
    ann.is_published = cleaned['is_published']

    # Auto-set published_at when first publishing
    if ann.is_published and (was_draft or is_new) and not cleaned.get('published_at'):
        ann.published_at = timezone.now()
    elif cleaned.get('published_at'):
        ann.published_at = cleaned['published_at']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('announcements_list', action='read')
def announcement_list(request):
    now = timezone.now()
    qs  = SchoolAnnouncement.objects.select_related(
        'school_class__supported_class', 'posted_by'
    )

    search          = request.GET.get('q', '').strip()
    audience_filter = request.GET.get('audience', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    status_filter   = request.GET.get('status', '').strip()
    class_filter    = request.GET.get('class', '').strip()

    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(content__icontains=search))
    if audience_filter:
        qs = qs.filter(audience=audience_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)
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

    qs = qs.order_by('-is_published', '-created_at')

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # Annotate runtime flags
    items = []
    for ann in page_obj.object_list:
        ann.is_expired = ann.expires_at is not None and ann.expires_at < now
        ann.is_active  = ann.is_published and not ann.is_expired
        items.append(ann)

    context = {
        'announcements':    items,
        'page_obj':         page_obj,
        'search':           search,
        'audience_filter':  audience_filter,
        'priority_filter':  priority_filter,
        'status_filter':    status_filter,
        'class_filter':     class_filter,
        'now':              now,
        **_get_lookups(),
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('announcement', action='read')
def announcement_add(request):
    lookups = _get_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'form_title': 'New Announcement',
            'action':     'add',
            'post':       {},
            'errors':     {},
            'now_str':    timezone.now().strftime('%Y-%m-%dT%H:%M'),
            **lookups,
        })

    cleaned, errors = _validate(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': 'New Announcement',
            'action':     'add',
            'post':       request.POST,
            'errors':     errors,
            'now_str':    timezone.now().strftime('%Y-%m-%dT%H:%M'),
            **lookups,
        })

    try:
        with transaction.atomic():
            ann = SchoolAnnouncement()
            _apply(ann, cleaned, is_new=True)
            ann.posted_by = request.user
            if request.FILES.get('attachment'):
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
#  3. EDIT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('announcement', action='edit')
def announcement_edit(request, pk):
    ann     = get_object_or_404(
        SchoolAnnouncement.objects.select_related('school_class__supported_class'),
        pk=pk
    )
    lookups = _get_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'announcement': ann,
            'form_title':   f'Edit — {ann.title}',
            'action':       'edit',
            'post':         {},
            'errors':       {},
            **lookups,
        })

    cleaned, errors = _validate(request.POST)

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
            _apply(ann, cleaned)

            if cleaned['clear_attachment']:
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

    messages.success(request, f'Announcement "{ann.title}" updated successfully.')
    return redirect('school:announcement_detail', pk=ann.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('announcement_list', action='read')
def announcement_detail(request, pk):
    ann = get_object_or_404(
        SchoolAnnouncement.objects.select_related('school_class__supported_class', 'posted_by'),
        pk=pk
    )
    now        = timezone.now()
    is_expired = ann.expires_at is not None and ann.expires_at < now

    days_until_expiry = None
    if ann.expires_at:
        days_until_expiry = (ann.expires_at - now).days

    prev_ann = (
        SchoolAnnouncement.objects
        .filter(created_at__lt=ann.created_at)
        .order_by('-created_at')
        .first()
    )
    next_ann = (
        SchoolAnnouncement.objects
        .filter(created_at__gt=ann.created_at)
        .order_by('created_at')
        .first()
    )
    related = (
        SchoolAnnouncement.objects
        .filter(audience=ann.audience, is_published=True)
        .exclude(pk=ann.pk)
        .order_by('-created_at')[:4]
    )

    context = {
        'announcement':      ann,
        'now':               now,
        'is_expired':        is_expired,
        'days_until_expiry': days_until_expiry,
        'prev_announcement': prev_ann,
        'next_announcement': next_ann,
        'related':           related,
        'page_title':        ann.title,
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  5. DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('announcement', action='delete')
def announcement_delete(request, pk):
    ann = get_object_or_404(SchoolAnnouncement, pk=pk)

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {
            'announcement':   ann,
            'audience_label': dict(AUDIENCE_CHOICES).get(ann.audience, ann.audience),
            'priority_label': dict(PRIORITY_CHOICES).get(ann.priority, ann.priority),
        })

    title = ann.title
    try:
        if ann.attachment:
            ann.attachment.delete(save=False)
        ann.delete()
        messages.success(request, f'Announcement "{title}" permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete announcement: {exc}')
        return redirect('school:announcement_detail', pk=pk)

    return redirect('school:announcement_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  6. TOGGLE PUBLISHED
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('publish_announcement', action='toggle')
def announcement_toggle_published(request, pk):
    if request.method != 'POST':
        return redirect('school:announcement_list')

    ann = get_object_or_404(SchoolAnnouncement, pk=pk)
    ann.is_published = not ann.is_published
    if ann.is_published and not ann.published_at:
        ann.published_at = timezone.now()
    ann.save(update_fields=['is_published', 'published_at'])

    state = 'published' if ann.is_published else 'saved as draft'
    messages.success(request, f'"{ann.title}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('school:announcement_detail', pk=ann.pk)
