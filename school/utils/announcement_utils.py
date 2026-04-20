

# school/utils/announcement_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for SchoolAnnouncement views (refactored for production).
#
# Fixes:
#   • _parse_datetime now uses field_key for errors dict → matches template checks (published_at / expires_at)
#   • All other logic unchanged and fully compatible with SchoolAnnouncement model
# ─────────────────────────────────────────────────────────────────────────────

from datetime import datetime
from django.db.models import Count, Q

from school.models import SchoolAnnouncement


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

VALID_AUDIENCES = {'all', 'teachers', 'parents', 'students'}
VALID_PRIORITIES = {'normal', 'urgent', 'critical'}

AUDIENCE_LABELS = {
    'all':      'Everyone',
    'teachers': 'Teachers & Staff',
    'parents':  'Parents & Guardians',
    'students': 'Students',
}

PRIORITY_LABELS = {
    'normal':   'Normal',
    'urgent':   'Urgent',
    'critical': 'Critical',
}

PRIORITY_ORDER = {'critical': 0, 'urgent': 1, 'normal': 2}


# ═══════════════════════════════════════════════════════════════════════════════
#  DATE PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_datetime(value: str, field_key: str, errors: dict):
    """
    Parse a datetime string from POST data.
    Accepts: 'YYYY-MM-DDTHH:MM' (HTML datetime-local input format)
    or       'YYYY-MM-DD HH:MM'
    Returns a timezone-naive datetime or None.
    Error key matches the field name used in templates (published_at / expires_at).
    """
    value = (value or '').strip()
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    errors[field_key] = f'{field_key.replace("_", " ").title()} is not a valid date/time (use YYYY-MM-DD HH:MM).'
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_announcement(
    post: dict,
    files: dict,
    instance: SchoolAnnouncement | None = None,
) -> tuple[dict, dict]:
    """
    Manually validate all SchoolAnnouncement POST fields.

    Returns:
        (cleaned_data, errors)

    cleaned_data — ready for setattr loop on the instance.
                   Attachment file is validated here but saved by the view.
    errors       — dict of field_name → error message.
                   Empty dict = validation passed.
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── title ─────────────────────────────────────────────────────────────────
    title = (post.get('title') or '').strip()
    if not title:
        errors['title'] = 'Announcement title is required.'
    elif len(title) > 200:
        errors['title'] = 'Title must not exceed 200 characters.'
    else:
        cleaned['title'] = title

    # ── content ───────────────────────────────────────────────────────────────
    content = (post.get('content') or '').strip()
    if not content:
        errors['content'] = 'Announcement content / body is required.'
    else:
        cleaned['content'] = content

    # ── audience ──────────────────────────────────────────────────────────────
    audience = (post.get('audience') or '').strip()
    if not audience:
        errors['audience'] = 'Target audience is required.'
    elif audience not in VALID_AUDIENCES:
        errors['audience'] = 'Invalid audience selected.'
    else:
        cleaned['audience'] = audience

    # ── priority ──────────────────────────────────────────────────────────────
    priority = (post.get('priority') or '').strip()
    if not priority:
        errors['priority'] = 'Priority level is required.'
    elif priority not in VALID_PRIORITIES:
        errors['priority'] = 'Invalid priority selected.'
    else:
        cleaned['priority'] = priority

    # ── school_class (optional FK — resolved in view) ─────────────────────────
    class_id = (post.get('school_class') or '').strip()
    if class_id:
        try:
            cleaned['school_class_id'] = int(class_id)
        except ValueError:
            errors['school_class'] = 'Invalid class selected.'
    else:
        cleaned['school_class_id'] = None

    # ── is_published ──────────────────────────────────────────────────────────
    cleaned['is_published'] = (
        str(post.get('is_published', '')).strip().lower() in ('1', 'true', 'on', 'yes')
    )

    # ── published_at ──────────────────────────────────────────────────────────
    published_at = _parse_datetime(post.get('published_at'), 'published_at', errors)
    cleaned['published_at'] = published_at

    # ── expires_at ────────────────────────────────────────────────────────────
    expires_at = _parse_datetime(post.get('expires_at'), 'expires_at', errors)
    cleaned['expires_at'] = expires_at

    # Cross-field: expiry must be after published_at if both set
    if published_at and expires_at and expires_at <= published_at:
        errors['expires_at'] = 'Expiry date/time must be after the publish date/time.'

    # ── attachment validation ──────────────────────────────────────────────────
    attachment = files.get('attachment')
    if attachment:
        import os
        allowed_ext = {'.pdf', '.jpg', '.jpeg', '.png', '.docx', '.xlsx'}
        ext = os.path.splitext(attachment.name)[1].lower()
        if ext not in allowed_ext:
            errors['attachment'] = (
                'Attachment must be a PDF, image (JPG/PNG), Word (.docx), '
                'or Excel (.xlsx) file.'
            )
        elif attachment.size > 5 * 1024 * 1024:
            errors['attachment'] = 'Attachment must not exceed 5 MB.'

    # ── clear_attachment flag (handled in view) ───────────────────────────────
    cleaned['clear_attachment'] = (
        str(post.get('clear_attachment', '')).strip().lower() in ('1', 'true', 'on', 'yes')
    )

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_announcement_list_stats() -> dict:
    """High-level statistics shown above the announcements list."""
    from django.utils import timezone
    now = timezone.now()

    qs = SchoolAnnouncement.objects.all()

    total       = qs.count()
    published   = qs.filter(is_published=True).count()
    draft       = qs.filter(is_published=False).count()
    active      = qs.filter(
        is_published=True
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).count()
    expired     = qs.filter(is_published=True, expires_at__lt=now).count()

    # Critical / urgent published right now
    critical = qs.filter(is_published=True, priority='critical').filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).count()
    urgent = qs.filter(is_published=True, priority='urgent').filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).count()

    by_audience = list(
        qs.filter(is_published=True)
        .values('audience')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    for row in by_audience:
        row['label'] = AUDIENCE_LABELS.get(row['audience'], row['audience'])

    by_priority = list(
        qs.values('priority')
        .annotate(total=Count('id'))
        .order_by('priority')
    )
    for row in by_priority:
        row['label'] = PRIORITY_LABELS.get(row['priority'], row['priority'])

    # 5 most recent published announcements for the sidebar/banner
    latest = qs.filter(
        is_published=True
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).order_by('-published_at')[:5]

    return {
        'total':        total,
        'published':    published,
        'draft':        draft,
        'active':       active,
        'expired':      expired,
        'critical':     critical,
        'urgent':       urgent,
        'by_audience':  by_audience,
        'by_priority':  by_priority,
        'latest':       latest,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_announcement_detail_stats(announcement: SchoolAnnouncement) -> dict:
    """
    Stats and context for the announcement detail page.
    Includes status flags and sibling navigation (prev / next).
    """
    from django.utils import timezone
    now = timezone.now()

    is_expired = (
        announcement.expires_at is not None and
        announcement.expires_at < now
    )
    is_active = announcement.is_published and not is_expired

    # Days until expiry / days since expiry
    days_until_expiry = None
    if announcement.expires_at:
        delta = (announcement.expires_at - now).days
        days_until_expiry = delta   # negative = already expired

    # Prev / next published announcements for navigation
    prev_announcement = (
        SchoolAnnouncement.objects
        .filter(is_published=True, published_at__lt=announcement.published_at)
        .exclude(pk=announcement.pk)
        .order_by('-published_at')
        .first()
    )
    next_announcement = (
        SchoolAnnouncement.objects
        .filter(is_published=True, published_at__gt=announcement.published_at)
        .exclude(pk=announcement.pk)
        .order_by('published_at')
        .first()
    )

    # Related announcements — same audience or same priority, excluding self
    related = (
        SchoolAnnouncement.objects
        .filter(is_published=True)
        .filter(
            Q(audience=announcement.audience) |
            Q(priority=announcement.priority)
        )
        .exclude(pk=announcement.pk)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by('-published_at')[:4]
    )

    return {
        'is_expired':         is_expired,
        'is_active':          is_active,
        'days_until_expiry':  days_until_expiry,
        'prev_announcement':  prev_announcement,
        'next_announcement':  next_announcement,
        'related':            related,
        'audience_label':     AUDIENCE_LABELS.get(announcement.audience, announcement.audience),
        'priority_label':     PRIORITY_LABELS.get(announcement.priority, announcement.priority),
        'priority_order':     PRIORITY_ORDER.get(announcement.priority, 99),
    }

