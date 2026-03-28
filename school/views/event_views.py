# school/views/event_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All SchoolEvent views.
#
# Views:
#   event_list             — list with full stats and filters
#   event_add              — add a new event
#   event_edit             — edit an existing event
#   event_delete           — confirm + perform deletion
#   event_detail           — full single event page with stats
#   event_toggle_published — POST-only quick publish/unpublish
#
# Rules (same as all previous views in this project):
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via event_utils
#   - django.contrib.messages for all feedback
#   - login_required on every view
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import SchoolClass
from authentication.models import CustomUser
from school.models import SchoolEvent
from school.utils.event_utils import (
    EVENT_TYPE_LABELS,
    annotate_events,
    get_event_detail_stats,
    get_event_list_stats,
    get_event_status,
    validate_and_parse_event,
)

_T = 'school/events/'

_EVENT_TYPE_CHOICES = list(EVENT_TYPE_LABELS.items())


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_form_lookups() -> dict:
    """Common querysets / choices every event form needs."""
    return {
        'all_classes':        SchoolClass.objects.filter(
                                  is_active=True
                              ).order_by('section', 'level', 'stream'),
        'all_staff':          CustomUser.objects.filter(
                                  user_type__in=('admin', 'head_teacher', 'teacher', 'staff')
                              ).order_by('last_name', 'first_name'),
        'event_type_choices': _EVENT_TYPE_CHOICES,
    }


def _apply_to_instance(instance: SchoolEvent, cleaned: dict) -> None:
    """
    Write all cleaned scalar and FK fields onto a SchoolEvent instance.
    M2M (school_classes) is handled separately in the view after save().
    """
    scalar_fields = (
        'title', 'description', 'event_type',
        'start_date', 'end_date', 'start_time', 'end_time',
        'venue', 'is_whole_school', 'is_published',
    )
    for f in scalar_fields:
        if f in cleaned:
            setattr(instance, f, cleaned[f])

    if 'organized_by_id' in cleaned:
        instance.organized_by_id = cleaned['organized_by_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. EVENTS LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def event_list(request):
    """
    All school events with full statistics and filters.

    Stats cards:
        total, published, draft,
        upcoming (published, start_date > today),
        active   (published, start_date <= today <= end_date),
        finished (published, end_date < today).
        By-type breakdown, whole-school vs class-specific,
        next 5 upcoming, currently active events, monthly distribution.

    Filters (GET params — all stackable):
        ?q=           title / description / venue search
        ?type=        event_type value
        ?status=      upcoming | active | finished
        ?published=   1 | 0
        ?scope=       whole | class
        ?class=<pk>   filter by a specific class (M2M)
        ?year=        filter by start_date year
        ?month=       filter by start_date month (1–12)
    """
    today = date.today()
    qs = SchoolEvent.objects.select_related(
        'organized_by'
    ).prefetch_related('school_classes')

    # ── Filters ───────────────────────────────────────────────────────────────
    search          = request.GET.get('q', '').strip()
    type_filter     = request.GET.get('type', '').strip()
    status_filter   = request.GET.get('status', '').strip()
    published_filter= request.GET.get('published', '').strip()
    scope_filter    = request.GET.get('scope', '').strip()
    class_filter    = request.GET.get('class', '').strip()
    year_filter     = request.GET.get('year', '').strip()
    month_filter    = request.GET.get('month', '').strip()

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

    if class_filter:
        qs = qs.filter(school_classes__pk=class_filter).distinct()

    if year_filter:
        try:
            qs = qs.filter(start_date__year=int(year_filter))
        except ValueError:
            pass

    if month_filter:
        try:
            qs = qs.filter(start_date__month=int(month_filter))
        except ValueError:
            pass

    # Default order: upcoming first, then active, then finished; drafts last
    qs = qs.order_by('start_date', 'start_time')

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # Annotate items with runtime status
    items = annotate_events(list(page_obj.object_list), today)

    # Years available for filter dropdown
    years = (
        SchoolEvent.objects
        .dates('start_date', 'year', order='DESC')
        .values_list('start_date__year', flat=True)
        .distinct()
    )

    stats = get_event_list_stats()

    context = {
        'events':           items,
        'page_obj':         page_obj,
        # active filters
        'search':           search,
        'type_filter':      type_filter,
        'status_filter':    status_filter,
        'published_filter': published_filter,
        'scope_filter':     scope_filter,
        'class_filter':     class_filter,
        'year_filter':      year_filter,
        'month_filter':     month_filter,
        # choice lists for filter controls
        'event_type_choices': _EVENT_TYPE_CHOICES,
        'all_classes':      SchoolClass.objects.filter(
                                is_active=True
                            ).order_by('section', 'level', 'stream'),
        'years':            years,
        'months': [
            (1,'January'),(2,'February'),(3,'March'),(4,'April'),
            (5,'May'),(6,'June'),(7,'July'),(8,'August'),
            (9,'September'),(10,'October'),(11,'November'),(12,'December'),
        ],
        'today': today,
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD EVENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def event_add(request):
    """
    Add a new school event.
    GET  — blank form with class, staff, and type dropdowns.
    POST — validate; save on success; re-render with per-field errors on failure.

    M2M school_classes:
        Received as a list via POST['school_classes'] (multi-select).
        Set via .set() after the instance is saved.
        Only applied when is_whole_school=False.
    """
    lookups = _get_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'form_title':        'Add School Event',
            'action':            'add',
            'post':              {},
            'errors':            {},
            'selected_class_ids': [],
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_event(request.POST, request.FILES)

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
            _apply_to_instance(event, cleaned)

            # Attachment
            if request.FILES.get('attachment'):
                event.attachment = request.FILES['attachment']

            event.save()

            # M2M — only relevant when not a whole-school event
            if not event.is_whole_school and cleaned.get('school_class_ids'):
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
#  3. EDIT EVENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def event_edit(request, pk):
    """
    Edit an existing school event.
    GET  — form pre-filled with current values; selected_class_ids pre-checked.
    POST — validate; save; handle M2M and attachment changes.
    """
    event   = get_object_or_404(
        SchoolEvent.objects.prefetch_related('school_classes'),
        pk=pk
    )
    lookups = _get_form_lookups()
    selected_class_ids = list(event.school_classes.values_list('id', flat=True))

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'event':              event,
            'form_title':         f'Edit — {event.title}',
            'action':             'edit',
            'post':               {},
            'errors':             {},
            'selected_class_ids': selected_class_ids,
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_event(request.POST, request.FILES, instance=event)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'event':              event,
            'form_title':         f'Edit — {event.title}',
            'action':             'edit',
            'post':               request.POST,
            'errors':             errors,
            'selected_class_ids': cleaned.get('school_class_ids', selected_class_ids),
            **lookups,
        })

    try:
        with transaction.atomic():
            _apply_to_instance(event, cleaned)

            # Attachment handling
            if cleaned.get('clear_attachment'):
                if event.attachment:
                    event.attachment.delete(save=False)
                event.attachment = None
            elif request.FILES.get('attachment'):
                if event.attachment:
                    event.attachment.delete(save=False)
                event.attachment = request.FILES['attachment']

            event.save()

            # M2M update
            if not event.is_whole_school and cleaned.get('school_class_ids'):
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
            'selected_class_ids': selected_class_ids,
            **lookups,
        })

    messages.success(request, f'Event "{event.title}" has been updated successfully.')
    return redirect('school:event_detail', pk=event.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE EVENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def event_delete(request, pk):
    """
    Delete a school event.
    GET  — confirmation page showing event summary and class count.
    POST — delete the record (and attachment from disk), redirect to list.
    """
    event = get_object_or_404(
        SchoolEvent.objects.prefetch_related('school_classes'),
        pk=pk
    )

    if request.method == 'GET':
        today = date.today()
        return render(request, f'{_T}delete_confirm.html', {
            'event':       event,
            'status':      get_event_status(event, today),
            'type_label':  EVENT_TYPE_LABELS.get(event.event_type, event.event_type),
            'class_count': event.school_classes.count(),
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    title = event.title
    try:
        if event.attachment:
            event.attachment.delete(save=False)
        event.delete()
        messages.success(request, f'Event "{title}" has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete event: {exc}')
        return redirect('school:event_detail', pk=pk)

    return redirect('school:event_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. EVENT DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def event_detail(request, pk):
    """
    Full single event page.

    Displays:
        - Title, type, dates, times, venue, description
        - Status badge: Upcoming / Active / Finished + Published / Draft
        - Days until start (or days since it ended)
        - Duration in days
        - Organiser details
        - Whole-school flag — or list of targeted classes
        - Attachment download link (if any)
        - Prev / Next published events for navigation
        - Related events (same type or overlapping dates)
    """
    event = get_object_or_404(
        SchoolEvent.objects
        .select_related('organized_by')
        .prefetch_related('school_classes'),
        pk=pk
    )
    stats = get_event_detail_stats(event)

    context = {
        'event':      event,
        'page_title': event.title,
        'today':      date.today(),
        **stats,
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. TOGGLE PUBLISHED  (POST-only quick action)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def event_toggle_published(request, pk):
    """
    Quick POST-only toggle for is_published.
    Flips the published state without opening the full edit form.
    Respects ?next= or HTTP_REFERER for redirect destination.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('school:event_list')

    event = get_object_or_404(SchoolEvent, pk=pk)
    event.is_published = not event.is_published
    event.save(update_fields=['is_published'])

    state = 'published' if event.is_published else 'unpublished (draft)'
    messages.success(request, f'"{event.title}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('school:event_detail', pk=event.pk)
