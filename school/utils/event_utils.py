# school/utils/event_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for SchoolEvent views:
#   - Manual field validation
#   - POST data parsing
#   - List-level and detail statistics
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date, datetime
from django.db.models import Count, Q

from school.models import SchoolEvent


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

VALID_EVENT_TYPES = {
    'academic', 'exam', 'sports', 'cultural', 'religious',
    'holiday', 'meeting', 'trip', 'graduation', 'open_day', 'other',
}

EVENT_TYPE_LABELS = {
    'academic':   'Academic',
    'exam':       'Examination',
    'sports':     'Sports Day / Inter-House',
    'cultural':   'Cultural / Drama',
    'religious':  'Religious / Chapel',
    'holiday':    'Public Holiday',
    'meeting':    'Parents / Staff Meeting',
    'trip':       'School Trip / Excursion',
    'graduation': 'Graduation / Completion',
    'open_day':   'Open Day / Visiting Day',
    'other':      'Other',
}

# Status tags derived at runtime from dates
STATUS_UPCOMING  = 'upcoming'
STATUS_ACTIVE    = 'active'
STATUS_FINISHED  = 'finished'


# ═══════════════════════════════════════════════════════════════════════════════
#  DATE / TIME PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_date(value: str, field_label: str, errors: dict) -> date | None:
    value = (value or '').strip()
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    errors[field_label] = f'{field_label} is not a valid date (use YYYY-MM-DD).'
    return None


def _parse_time(value: str, field_label: str, errors: dict):
    """Parse HH:MM time string. Returns time object or None."""
    value = (value or '').strip()
    if not value:
        return None
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    errors[field_label] = f'{field_label} is not a valid time (use HH:MM).'
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  RUNTIME STATUS
# ═══════════════════════════════════════════════════════════════════════════════

def get_event_status(event: SchoolEvent, today: date | None = None) -> str:
    """
    Returns 'upcoming' | 'active' | 'finished' based on today's date.
    """
    today = today or date.today()
    if event.end_date < today:
        return STATUS_FINISHED
    if event.start_date <= today:
        return STATUS_ACTIVE
    return STATUS_UPCOMING


def annotate_events(events, today: date | None = None) -> list:
    """
    Attach runtime status, type label, and days-away to a list of events.
    Called by list and detail views so templates don't repeat this logic.
    """
    today = today or date.today()
    result = []
    for ev in events:
        ev.status      = get_event_status(ev, today)
        ev.type_label  = EVENT_TYPE_LABELS.get(ev.event_type, ev.event_type)
        ev.days_away   = (ev.start_date - today).days   # negative = in the past
        ev.duration    = (ev.end_date - ev.start_date).days + 1
        result.append(ev)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_event(
    post: dict,
    files: dict,
    instance: SchoolEvent | None = None,
) -> tuple[dict, dict]:
    """
    Manually validate all SchoolEvent POST fields.

    Returns:
        (cleaned_data, errors)

    cleaned_data  — scalars ready for setattr loop; school_classes handled
                    separately by the view (M2M).
    errors        — dict of field_name → error string.
                    Empty = passed.
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── title ─────────────────────────────────────────────────────────────────
    title = (post.get('title') or '').strip()
    if not title:
        errors['title'] = 'Event title is required.'
    elif len(title) > 200:
        errors['title'] = 'Event title must not exceed 200 characters.'
    else:
        cleaned['title'] = title

    # ── description ───────────────────────────────────────────────────────────
    cleaned['description'] = (post.get('description') or '').strip()

    # ── event_type ────────────────────────────────────────────────────────────
    event_type = (post.get('event_type') or '').strip()
    if not event_type:
        errors['event_type'] = 'Event type is required.'
    elif event_type not in VALID_EVENT_TYPES:
        errors['event_type'] = 'Invalid event type selected.'
    else:
        cleaned['event_type'] = event_type

    # ── dates ─────────────────────────────────────────────────────────────────
    start_date = _parse_date(post.get('start_date'), 'Start date', errors)
    end_date   = _parse_date(post.get('end_date'),   'End date',   errors)

    if not start_date:
        errors.setdefault('start_date', 'Start date is required.')
    if not end_date:
        errors.setdefault('end_date', 'End date is required.')

    if start_date and end_date:
        if end_date < start_date:
            errors['end_date'] = 'End date must be on or after start date.'
        else:
            cleaned['start_date'] = start_date
            cleaned['end_date']   = end_date

    # ── times (optional) ──────────────────────────────────────────────────────
    start_time = _parse_time(post.get('start_time'), 'Start time', errors)
    end_time   = _parse_time(post.get('end_time'),   'End time',   errors)

    # Cross-check: on a single-day event end_time must be after start_time
    if (start_time and end_time and start_date and end_date
            and start_date == end_date and end_time <= start_time):
        errors['end_time'] = 'End time must be after start time for a single-day event.'

    cleaned['start_time'] = start_time
    cleaned['end_time']   = end_time

    # ── venue ─────────────────────────────────────────────────────────────────
    venue = (post.get('venue') or '').strip()
    if len(venue) > 200:
        errors['venue'] = 'Venue must not exceed 200 characters.'
    else:
        cleaned['venue'] = venue

    # ── is_whole_school ───────────────────────────────────────────────────────
    is_whole_school = (
        str(post.get('is_whole_school', '')).strip().lower()
        in ('1', 'true', 'on', 'yes')
    )
    cleaned['is_whole_school'] = is_whole_school

    # school_classes M2M — validated as int list in view, stored here as raw IDs
    class_ids_raw = post.getlist('school_classes') if hasattr(post, 'getlist') else []
    valid_class_ids = []
    for cid in class_ids_raw:
        try:
            valid_class_ids.append(int(cid))
        except (ValueError, TypeError):
            errors['school_classes'] = 'One or more selected classes are invalid.'
            break
    cleaned['school_class_ids'] = valid_class_ids

    # ── is_published ──────────────────────────────────────────────────────────
    cleaned['is_published'] = (
        str(post.get('is_published', '')).strip().lower()
        in ('1', 'true', 'on', 'yes')
    )

    # ── organized_by FK (optional — resolved in view) ─────────────────────────
    organized_by_id = (post.get('organized_by') or '').strip()
    if organized_by_id:
        try:
            cleaned['organized_by_id'] = int(organized_by_id)
        except ValueError:
            errors['organized_by'] = 'Invalid organiser selected.'
    else:
        cleaned['organized_by_id'] = None

    # ── attachment validation ──────────────────────────────────────────────────
    attachment = files.get('attachment')
    if attachment:
        import os
        allowed_ext = {'.pdf', '.jpg', '.jpeg', '.png', '.docx'}
        ext = os.path.splitext(attachment.name)[1].lower()
        if ext not in allowed_ext:
            errors['attachment'] = (
                'Attachment must be a PDF, image (JPG/PNG), or Word (.docx) file.'
            )
        elif attachment.size > 5 * 1024 * 1024:
            errors['attachment'] = 'Attachment must not exceed 5 MB.'

    cleaned['clear_attachment'] = (
        str(post.get('clear_attachment', '')).strip().lower()
        in ('1', 'true', 'on', 'yes')
    )

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_event_list_stats() -> dict:
    """High-level statistics shown above the events list page."""
    today = date.today()
    qs    = SchoolEvent.objects.all()

    total      = qs.count()
    published  = qs.filter(is_published=True).count()
    draft      = qs.filter(is_published=False).count()

    # Status-based counts (published events only)
    upcoming = qs.filter(is_published=True, start_date__gt=today).count()
    active   = qs.filter(
        is_published=True,
        start_date__lte=today,
        end_date__gte=today,
    ).count()
    finished = qs.filter(is_published=True, end_date__lt=today).count()

    # By type
    by_type = list(
        qs.values('event_type')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    for row in by_type:
        row['label'] = EVENT_TYPE_LABELS.get(row['event_type'], row['event_type'])

    # Whole-school vs class-specific
    whole_school    = qs.filter(is_whole_school=True).count()
    class_specific  = qs.filter(is_whole_school=False).count()

    # Next 5 upcoming published events
    next_events = list(
        annotate_events(
            qs.filter(is_published=True, start_date__gte=today)
            .select_related('organized_by')
            .order_by('start_date')[:5],
            today,
        )
    )

    # Currently active events
    active_events = list(
        annotate_events(
            qs.filter(
                is_published=True,
                start_date__lte=today,
                end_date__gte=today,
            ).select_related('organized_by').order_by('start_date'),
            today,
        )
    )

    # Monthly distribution (published) for the current year
    from django.db.models.functions import ExtractMonth
    monthly = list(
        qs.filter(is_published=True, start_date__year=today.year)
        .annotate(month=ExtractMonth('start_date'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month')
    )

    return {
        'total':          total,
        'published':      published,
        'draft':          draft,
        'upcoming':       upcoming,
        'active':         active,
        'finished':       finished,
        'whole_school':   whole_school,
        'class_specific': class_specific,
        'by_type':        by_type,
        'next_events':    next_events,
        'active_events':  active_events,
        'monthly':        monthly,
        'today':          today,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_event_detail_stats(event: SchoolEvent) -> dict:
    """Stats and context for the single event detail page."""
    today  = date.today()
    status = get_event_status(event, today)

    days_away  = (event.start_date - today).days   # negative if past
    duration   = (event.end_date - event.start_date).days + 1
    type_label = EVENT_TYPE_LABELS.get(event.event_type, event.event_type)

    # Sibling navigation — prev / next published events by start_date
    prev_event = (
        SchoolEvent.objects
        .filter(is_published=True, start_date__lt=event.start_date)
        .exclude(pk=event.pk)
        .order_by('-start_date')
        .first()
    )
    next_event = (
        SchoolEvent.objects
        .filter(is_published=True, start_date__gt=event.start_date)
        .exclude(pk=event.pk)
        .order_by('start_date')
        .first()
    )

    # Related: same event type or overlapping dates, excluding self
    related = list(
        annotate_events(
            SchoolEvent.objects
            .filter(is_published=True)
            .filter(
                Q(event_type=event.event_type) |
                Q(start_date__lte=event.end_date, end_date__gte=event.start_date)
            )
            .exclude(pk=event.pk)
            .order_by('start_date')[:4],
            today,
        )
    )

    # Classes involved
    classes = event.school_classes.all().order_by(
        'section', 'level', 'stream'
    ) if not event.is_whole_school else []

    return {
        'status':      status,
        'days_away':   days_away,
        'duration':    duration,
        'type_label':  type_label,
        'prev_event':  prev_event,
        'next_event':  next_event,
        'related':     related,
        'classes':     classes,
        'today':       today,
    }
