# school/views/event_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Rules: FBV only | no Forms | no CBVs | no JSON | manual validation |
#        messages for feedback | login_required | transaction.atomic on saves
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date, parse_time

from academics.models import SchoolSupportedClasses
from authentication.models import CustomUser
from school.models import SchoolEvent


from permissions.decorators import has_permission

_T = 'school/events/'

EVENT_TYPE_CHOICES = [
    ('academic',   'Academic'),
    ('exam',       'Examination'),
    ('sports',     'Sports Day / Inter-House'),
    ('cultural',   'Cultural / Drama'),
    ('religious',  'Religious / Chapel'),
    ('holiday',    'Public Holiday'),
    ('meeting',    'Parents / Staff Meeting'),
    ('trip',       'School Trip / Excursion'),
    ('graduation', 'Graduation / Completion'),
    ('open_day',   'Open Day / Visiting Day'),
    ('other',      'Other'),
]
_EVENT_TYPE_LABELS = dict(EVENT_TYPE_CHOICES)
_VALID_TYPES       = set(_EVENT_TYPE_LABELS.keys())


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_form_lookups():
    return {
        'all_classes': SchoolSupportedClasses.objects.select_related(
            'supported_class'
        ).order_by('supported_class__order'),
        'all_staff': CustomUser.objects.filter(
            is_active=True,
            user_type__in=('admin', 'head_teacher', 'teacher', 'staff'),
        ).order_by('last_name', 'first_name'),
        'event_type_choices': EVENT_TYPE_CHOICES,
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

    event_type = post.get('event_type', '').strip()
    if event_type not in _VALID_TYPES:
        errors['event_type'] = 'Select a valid event type.'
    else:
        cleaned['event_type'] = event_type

    start_date = parse_date(post.get('start_date', '').strip())
    end_date   = parse_date(post.get('end_date', '').strip())

    if not start_date:
        errors['start_date'] = 'A valid start date is required.'
    else:
        cleaned['start_date'] = start_date

    if not end_date:
        errors['end_date'] = 'A valid end date is required.'
    elif start_date and end_date < start_date:
        errors['end_date'] = 'End date must be on or after the start date.'
    else:
        cleaned['end_date'] = end_date

    for field in ('start_time', 'end_time'):
        raw = post.get(field, '').strip()
        cleaned[field] = parse_time(raw) if raw else None

    cleaned['venue']           = post.get('venue', '').strip()[:200]
    cleaned['description']     = post.get('description', '').strip()
    cleaned['is_whole_school'] = bool(post.get('is_whole_school'))
    cleaned['is_published']    = bool(post.get('is_published'))
    cleaned['clear_attachment']= bool(post.get('clear_attachment'))

    # Organiser FK
    org_pk = post.get('organized_by', '').strip()
    try:
        cleaned['organized_by_id'] = int(org_pk) if org_pk else None
    except ValueError:
        cleaned['organized_by_id'] = None

    # M2M classes (only used when not whole-school)
    cleaned['school_class_ids'] = []
    for pk_str in post.getlist('school_classes'):
        try:
            cleaned['school_class_ids'].append(int(pk_str))
        except ValueError:
            pass

    return cleaned, errors


def _apply(event, cleaned):
    """Write cleaned scalar / FK fields onto a SchoolEvent instance."""
    for field in (
        'title', 'description', 'event_type',
        'start_date', 'end_date', 'start_time', 'end_time',
        'venue', 'is_whole_school', 'is_published',
    ):
        if field in cleaned:
            setattr(event, field, cleaned[field])
    event.organized_by_id = cleaned.get('organized_by_id')


def _get_status(event, today):
    if event.start_date > today:
        return 'upcoming'
    if event.end_date < today:
        return 'finished'
    return 'active'


def _annotate(events, today):
    for e in events:
        e.status = _get_status(e, today)
    return events


# ═══════════════════════════════════════════════════════════════════════════════
#  1. LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('events_list', action='read')
def event_list(request):
    today = date.today()
    qs    = SchoolEvent.objects.select_related('organized_by').prefetch_related(
        'school_classes__supported_class'
    )

    search           = request.GET.get('q', '').strip()
    type_filter      = request.GET.get('type', '').strip()
    status_filter    = request.GET.get('status', '').strip()
    scope_filter     = request.GET.get('scope', '').strip()
    year_filter      = request.GET.get('year', '').strip()
    published_filter = request.GET.get('published', '').strip()

    if search:
        qs = qs.filter(
            Q(title__icontains=search)       |
            Q(description__icontains=search) |
            Q(venue__icontains=search)
        )
    if type_filter:
        qs = qs.filter(event_type=type_filter)
    if status_filter == 'upcoming':
        qs = qs.filter(start_date__gt=today)
    elif status_filter == 'active':
        qs = qs.filter(start_date__lte=today, end_date__gte=today)
    elif status_filter == 'finished':
        qs = qs.filter(end_date__lt=today)
    if published_filter == '1':
        qs = qs.filter(is_published=True)
    elif published_filter == '0':
        qs = qs.filter(is_published=False)
    if scope_filter == 'whole':
        qs = qs.filter(is_whole_school=True)
    elif scope_filter == 'class':
        qs = qs.filter(is_whole_school=False)
    if year_filter:
        try:
            qs = qs.filter(start_date__year=int(year_filter))
        except ValueError:
            pass

    qs = qs.order_by('start_date', 'start_time')

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    items     = _annotate(list(page_obj.object_list), today)

    years = sorted(
        set(SchoolEvent.objects.values_list('start_date__year', flat=True)),
        reverse=True,
    )

    context = {
        'events':            items,
        'page_obj':          page_obj,
        'search':            search,
        'type_filter':       type_filter,
        'status_filter':     status_filter,
        'scope_filter':      scope_filter,
        'year_filter':       year_filter,
        'published_filter':  published_filter,
        'event_type_choices': EVENT_TYPE_CHOICES,
        'years':             years,
        'today':             today,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('event', action='create')
def event_add(request):
    lookups = _get_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'form_title':         'Add School Event',
            'action':             'add',
            'post':               {},
            'errors':             {},
            'selected_class_ids': [],
            **lookups,
        })

    cleaned, errors = _validate(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title':         'Add School Event',
            'action':             'add',
            'post':               request.POST,
            'errors':             errors,
            'selected_class_ids': cleaned.get('school_class_ids', []),
            **lookups,
        })

    try:
        with transaction.atomic():
            event = SchoolEvent()
            _apply(event, cleaned)
            if request.FILES.get('attachment'):
                event.attachment = request.FILES['attachment']
            event.save()

            if not event.is_whole_school and cleaned['school_class_ids']:
                event.school_classes.set(cleaned['school_class_ids'])
            else:
                event.school_classes.clear()

    except Exception as exc:
        messages.error(request, f'Could not save event: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title':         'Add School Event',
            'action':             'add',
            'post':               request.POST,
            'errors':             {},
            'selected_class_ids': cleaned.get('school_class_ids', []),
            **lookups,
        })

    messages.success(
        request,
        f'Event "{event.title}" has been '
        f'{"published" if event.is_published else "saved as draft"} successfully.'
    )
    return redirect('school:event_detail', pk=event.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('event', action='edit')
def event_edit(request, pk):
    event   = get_object_or_404(
        SchoolEvent.objects.prefetch_related('school_classes'),
        pk=pk
    )
    lookups = _get_form_lookups()
    existing_class_ids = list(event.school_classes.values_list('id', flat=True))

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'event':              event,
            'form_title':         f'Edit — {event.title}',
            'action':             'edit',
            'post':               {},
            'errors':             {},
            'selected_class_ids': existing_class_ids,
            **lookups,
        })

    cleaned, errors = _validate(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'event':              event,
            'form_title':         f'Edit — {event.title}',
            'action':             'edit',
            'post':               request.POST,
            'errors':             errors,
            'selected_class_ids': cleaned.get('school_class_ids', existing_class_ids),
            **lookups,
        })

    try:
        with transaction.atomic():
            _apply(event, cleaned)

            if cleaned['clear_attachment']:
                if event.attachment:
                    event.attachment.delete(save=False)
                event.attachment = None
            elif request.FILES.get('attachment'):
                if event.attachment:
                    event.attachment.delete(save=False)
                event.attachment = request.FILES['attachment']

            event.save()

            if not event.is_whole_school and cleaned['school_class_ids']:
                event.school_classes.set(cleaned['school_class_ids'])
            else:
                event.school_classes.clear()

    except Exception as exc:
        messages.error(request, f'Could not update event: {exc}')
        return render(request, f'{_T}form.html', {
            'event':              event,
            'form_title':         f'Edit — {event.title}',
            'action':             'edit',
            'post':               request.POST,
            'errors':             {},
            'selected_class_ids': existing_class_ids,
            **lookups,
        })

    messages.success(request, f'Event "{event.title}" updated successfully.')
    return redirect('school:event_detail', pk=event.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('events_list', action='read')
def event_detail(request, pk):
    event = get_object_or_404(
        SchoolEvent.objects
        .select_related('organized_by')
        .prefetch_related('school_classes__supported_class'),
        pk=pk
    )
    today         = date.today()
    status        = _get_status(event, today)
    duration_days = (event.end_date - event.start_date).days + 1

    if status == 'upcoming':
        days_until_start = (event.start_date - today).days
    elif status == 'finished':
        days_until_start = -(today - event.end_date).days
    else:
        days_until_start = 0

    prev_event = (
        SchoolEvent.objects
        .filter(start_date__lt=event.start_date)
        .order_by('-start_date').first()
    )
    next_event = (
        SchoolEvent.objects
        .filter(start_date__gt=event.start_date)
        .order_by('start_date').first()
    )
    related_events = (
        SchoolEvent.objects
        .filter(event_type=event.event_type)
        .exclude(pk=event.pk)
        .order_by('start_date')[:4]
    )

    context = {
        'event':            event,
        'page_title':       event.title,
        'status':           status,
        'duration_days':    duration_days,
        'days_until_start': days_until_start,
        'type_label':       _EVENT_TYPE_LABELS.get(event.event_type, event.event_type),
        'prev_event':       prev_event,
        'next_event':       next_event,
        'related_events':   related_events,
        'today':            today,
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  5. DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('event', action='delete')
def event_delete(request, pk):
    event = get_object_or_404(
        SchoolEvent.objects.prefetch_related('school_classes'),
        pk=pk
    )

    if request.method == 'GET':
        today = date.today()
        return render(request, f'{_T}delete_confirm.html', {
            'event':       event,
            'status':      _get_status(event, today),
            'type_label':  _EVENT_TYPE_LABELS.get(event.event_type, event.event_type),
            'class_count': event.school_classes.count(),
        })

    title = event.title
    try:
        if event.attachment:
            event.attachment.delete(save=False)
        event.delete()
        messages.success(request, f'Event "{title}" permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete event: {exc}')
        return redirect('school:event_detail', pk=pk)

    return redirect('school:event_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  6. TOGGLE PUBLISHED
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('event', action='toggle')
def event_toggle_published(request, pk):
    if request.method != 'POST':
        return redirect('school:event_list')

    event = get_object_or_404(SchoolEvent, pk=pk)
    event.is_published = not event.is_published
    event.save(update_fields=['is_published'])

    state = 'published' if event.is_published else 'saved as draft'
    messages.success(request, f'"{event.title}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('school:event_detail', pk=event.pk)
