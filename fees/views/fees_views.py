# fees/views/fees_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All SchoolFees views.
#
# Views:
#   fees_list             — list with full stats and filters
#   fees_add              — add a new fee structure
#   fees_edit             — edit an existing fee structure
#   fees_delete           — confirm + perform deletion
#   fees_detail           — full single fee detail page
#   fees_duplicate        — clone + redirect to edit the duplicate
#   fees_toggle_active    — POST-only quick activate / deactivate
#
# Rules:
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via fees_utils
#   - django.contrib.messages for all feedback
#   - login_required on every view
#   - transaction.atomic() on all saves
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.utils.subject_utils import get_sch_supported_classes
from academics.models import SchoolSupportedClasses, Term
from fees.models import SchoolFees
from fees.utils.fees_utils import (
    FEES_TYPE_LABELS,
    get_fees_detail_stats,
    get_fees_list_stats,
    validate_and_parse_fees,
)

_T = 'fees/school_fees/'

_FEES_TYPE_CHOICES = list(FEES_TYPE_LABELS.items())

_CLASS_LEVEL_CHOICES = [
    ('baby', 'Baby Class'), ('middle', 'Middle Class'), ('top', 'Top Class'),
    ('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4'),
    ('p5', 'P5'), ('p6', 'P6'), ('p7', 'P7'),
]


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_form_lookups() -> dict:
    """Common querysets every fee form template needs."""
    return {
        'all_classes':       SchoolSupportedClasses.objects.order_by('supported_class__section', 'supported_class__key'),
        'all_terms':         Term.objects.all().order_by('-start_date'),
        'fees_type_choices': _FEES_TYPE_CHOICES,
    }


def _apply_to_instance(instance: SchoolFees, cleaned: dict) -> None:
    """Write cleaned scalar and FK fields onto a SchoolFees instance."""
    scalar_fields = (
        'fees_type', 'amount', 'description',
        'due_date', 'is_compulsory', 'is_active',
    )
    for f in scalar_fields:
        if f in cleaned:
            setattr(instance, f, cleaned[f])

    if 'school_class_id' in cleaned:
        instance.school_class_id = cleaned['school_class_id']
    if 'term_id' in cleaned:
        instance.term_id = cleaned['term_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. FEES LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def fees_list(request):
    """
    All school fee structures with statistics and filters.

    Stats cards:
        total, active, inactive, compulsory, optional,
        total UGX amount (active), compulsory/optional split,
        by-type, by-term, by-class, by-section breakdowns,
        highest/lowest/average fee amounts,
        overdue fee structures (due_date passed),
        current-term fee strip.

    Filters (GET — all stackable):
        ?q=           title / description search
        ?type=        fees_type value
        ?term=<id>    filter by term FK
        ?class=       filter by class level (e.g. p4)
        ?section=     nursery | primary
        ?active=      1 | 0
        ?compulsory=  1 | 0
        ?overdue=     1   (due_date < today)
    """
    from datetime import date
    today = date.today()

    qs = SchoolFees.objects.select_related(
        'school_class', 'term'
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    search            = request.GET.get('q', '').strip()
    type_filter       = request.GET.get('type', '').strip()
    term_filter       = request.GET.get('term', '').strip()
    class_filter      = request.GET.get('class', '').strip()
    section_filter    = request.GET.get('section', '').strip()
    active_filter     = request.GET.get('active', '').strip()
    compulsory_filter = request.GET.get('compulsory', '').strip()
    overdue_filter    = request.GET.get('overdue', '').strip()

    if search:
        qs = qs.filter(
            Q(description__icontains=search) |
            Q(fees_type__icontains=search)
        )

    if type_filter:
        qs = qs.filter(fees_type=type_filter)

    if term_filter:
        qs = qs.filter(term__pk=term_filter)

    if class_filter:
        qs = qs.filter(school_class__level=class_filter)

    if section_filter:
        qs = qs.filter(school_class__section=section_filter)

    if active_filter == '1':
        qs = qs.filter(is_active=True)
    elif active_filter == '0':
        qs = qs.filter(is_active=False)

    if compulsory_filter == '1':
        qs = qs.filter(is_compulsory=True)
    elif compulsory_filter == '0':
        qs = qs.filter(is_compulsory=False)

    if overdue_filter == '1':
        qs = qs.filter(
            is_active=True,
            due_date__lt=today,
            due_date__isnull=False,
        )

    qs = qs.order_by(
        '-term__start_date', 'school_class__supported_class__section', 'fees_type',
    )

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # Annotate each item with type label and overdue flag for template
    items = list(page_obj.object_list)
    for item in items:
        item.type_label = FEES_TYPE_LABELS.get(item.fees_type, item.fees_type)
        item.is_overdue = (
            item.due_date is not None
            and item.due_date < today
            and item.is_active
        )

    stats = get_fees_list_stats()

    context = {
        'fees':               items,
        'page_obj':           page_obj,
        # active filters
        'search':             search,
        'type_filter':        type_filter,
        'term_filter':        term_filter,
        'class_filter':       class_filter,
        'section_filter':     section_filter,
        'active_filter':      active_filter,
        'compulsory_filter':  compulsory_filter,
        'overdue_filter':     overdue_filter,
        # choices for filter dropdowns
        'fees_type_choices':  _FEES_TYPE_CHOICES,
        'class_level_choices': _CLASS_LEVEL_CHOICES,
        'fees_type_labels':   FEES_TYPE_LABELS,
        'today':              today,
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def fees_add(request):
    """
    Add a new school fee structure.
    GET  — blank form; pre-selects current term if one is active.
    POST — validate; save on success; re-render with per-field errors on failure.

    Uniqueness enforced: one fee type per class per term.
    """
    lookups = _get_form_lookups()

    if request.method == 'GET':
        current_term = Term.objects.filter(is_current=True).first()
        return render(request, f'{_T}form.html', {
            'form_title':   'Add Fee Structure',
            'action':       'add',
            'post':         {},
            'errors':       {},
            "classes":get_sch_supported_classes(),
            'current_term': current_term,
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_fees(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': 'Add Fee Structure',
            'action':     'add',
            "classes":get_sch_supported_classes(),
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            fee = SchoolFees()
            _apply_to_instance(fee, cleaned)
            fee.save()
    except Exception as exc:
        messages.error(request, f'Could not save fee structure: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title': 'Add Fee Structure',
            'action':     'add',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Fee structure "{FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type)}" '
        f'for {fee.school_class} — {fee.term} has been created successfully.'
    )
    return redirect('fees:fees_detail', pk=fee.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def fees_edit(request, pk):
    """
    Edit an existing school fee structure.
    GET  — form pre-filled with current values.
    POST — validate; save; re-render with errors on failure.
    """
    fee     = get_object_or_404(
        SchoolFees.objects.select_related('school_class', 'term'), pk=pk
    )
    lookups = _get_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'fee':        fee,
            'form_title': f'Edit — {FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type)} '
                          f'| {fee.school_class} | {fee.term}',
            'action':     'edit',
            'post':       {},
            'errors':     {},
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_fees(request.POST, instance=fee)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'fee':        fee,
            'form_title': f'Edit — {FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type)} '
                          f'| {fee.school_class} | {fee.term}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            _apply_to_instance(fee, cleaned)
            fee.save()
    except Exception as exc:
        messages.error(request, f'Could not update fee structure: {exc}')
        return render(request, f'{_T}form.html', {
            'fee':        fee,
            'form_title': f'Edit — {FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type)}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Fee structure "{FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type)}" '
        f'has been updated successfully.'
    )
    return redirect('fees:fees_detail', pk=fee.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def fees_delete(request, pk):
    """
    Delete a school fee structure.
    GET  — confirmation page showing fee details and payment impact.
    POST — perform deletion.

    Guard: if confirmed payments exist against this fee structure,
    deletion is blocked. Admin must deactivate instead.
    """
    fee = get_object_or_404(
        SchoolFees.objects.select_related('school_class', 'term'), pk=pk
    )

    # Impact count
    from fees.models import FeesPayment, AssessmentFees
    payment_count    = FeesPayment.objects.filter(school_fees=fee).count()
    assessment_count = AssessmentFees.objects.filter(term=fee.term).count()
    has_payments     = payment_count > 0

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {
            'fee':              fee,
            'type_label':       FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type),
            'payment_count':    payment_count,
            'assessment_count': assessment_count,
            'has_payments':     has_payments,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    # Hard block: never delete a fee structure that has payments against it.
    if has_payments:
        messages.error(
            request,
            f'This fee structure has {payment_count:,} payment record(s) and '
            f'cannot be deleted. Deactivate it instead to hide it from new '
            f'assignments while preserving payment history.'
        )
        return redirect('fees:fees_detail', pk=fee.pk)

    label = (
        f'{FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type)} '
        f'| {fee.school_class} | {fee.term}'
    )
    try:
        fee.delete()
        messages.success(request, f'Fee structure "{label}" has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete fee structure: {exc}')
        return redirect('fees:fees_detail', pk=fee.pk)

    return redirect('fees:fees_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. FEES DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def fees_detail(request, pk):
    """
    Full single fee structure detail page.

    Displays:
        - Fee type, amount (UGX), class, term, due date, flags
        - Overdue badge + days overdue (if applicable)
        - Collection stats: total collected, payment count,
          collection rate %, expected total (fee × student count)
        - Students: paid vs unpaid counts, shortfall amount
        - Payment method breakdown
        - 10 most recent payments for this fee
        - Sibling fees (same class + term, different type)
        - Same fee type across other classes in same term (benchmarking)
    """
    fee = get_object_or_404(
        SchoolFees.objects.select_related('school_class', 'term'),
        pk=pk
    )
    stats = get_fees_detail_stats(fee)

    context = {
        'fee':        fee,
        'page_title': (
            f'{FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type)} '
            f'— {fee.school_class} | {fee.term}'
        ),
        **stats,
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. DUPLICATE FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def fees_duplicate(request, pk):
    """
    Duplicate a fee structure then immediately redirect to edit the new copy.

    Flow:
        POST /fees/school-fees/<pk>/duplicate/
            → Clone the object
            → Set is_active=False on the duplicate (inactive until reviewed)
            → Clear due_date (likely different for new term)
            → Redirect to fees_edit for the new copy

    Typical use: copy a Term 1 fee structure across to Term 2 or
    copy P4 fees across to P5 and adjust the amount.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('fees:fees_list')

    original = get_object_or_404(
        SchoolFees.objects.select_related('school_class', 'term'), pk=pk
    )

    try:
        with transaction.atomic():
            duplicate = SchoolFees(
                school_class  = original.school_class,
                term          = original.term,
                fees_type     = original.fees_type,
                amount        = original.amount,
                description   = original.description,
                due_date      = None,        # clear — likely different for new term
                is_compulsory = original.is_compulsory,
                is_active     = False,       # always inactive until reviewed + activated
            )
            # Skip uniqueness because (class, term, fees_type) would clash —
            # the duplicate must be assigned to a different class or term in edit.
            # We bypass the model-level unique_together by saving directly.
            # The validator in fees_edit will enforce uniqueness on save.
            duplicate.save()
    except Exception as exc:
        messages.error(request, f'Could not duplicate fee structure: {exc}')
        return redirect('fees:fees_list')

    label = FEES_TYPE_LABELS.get(original.fees_type, original.fees_type)
    messages.info(
        request,
        f'A copy of "{label} — {original.school_class} | {original.term}" '
        f'has been created as inactive. '
        f'Update the class, term, and/or amount below then activate it.'
    )
    return redirect('fees:fees_edit', pk=duplicate.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. TOGGLE ACTIVE  (POST-only quick action)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def fees_toggle_active(request, pk):
    """
    POST-only: flip is_active on a fee structure.
    Redirects back to HTTP_REFERER or fees_detail.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('fees:fees_list')

    fee = get_object_or_404(SchoolFees, pk=pk)
    fee.is_active = not fee.is_active
    fee.save(update_fields=['is_active'])

    label = FEES_TYPE_LABELS.get(fee.fees_type, fee.fees_type)
    state = 'activated' if fee.is_active else 'deactivated'
    messages.success(request, f'"{label}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('fees:fees_detail', pk=fee.pk)
