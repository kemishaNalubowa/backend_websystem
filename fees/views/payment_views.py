# fees/views/payment_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All FeesPayment views.
#
# Views:
#   payment_list    — list with full stats and filters
#   payment_add     — record a new payment (auto-generates receipt number)
#   payment_edit    — edit an existing payment record
#   payment_delete  — confirm + perform deletion
#   payment_detail  — full single payment page with receipt-style detail
#
# Rules:
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via payment_utils
#   - django.contrib.messages for all feedback
#   - login_required on every view
#   - transaction.atomic() on all saves
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import SchoolClass, Term
from fees.models import FeesPayment, SchoolFees
from fees.utils.fees_utils import FEES_TYPE_LABELS
from fees.utils.payment_utils import (
    generate_receipt_number,
    get_payment_detail_stats,
    get_payment_list_stats,
    validate_and_parse_payment,
)
from students.models import Student

_T = 'fees/payments/'

_CLASS_LEVEL_CHOICES = [
    ('baby', 'Baby Class'), ('middle', 'Middle Class'), ('top', 'Top Class'),
    ('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4'),
    ('p5', 'P5'), ('p6', 'P6'), ('p7', 'P7'),
]


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_form_lookups() -> dict:
    """Common querysets every payment form template needs."""
    return {
        'all_terms':   Term.objects.all().order_by('-start_date'),
        'all_classes': SchoolClass.objects.filter(
                           is_active=True
                       ).order_by('section', 'level', 'stream'),
        # Students and SchoolFees are filtered dynamically based on
        # selected class/term — passed separately or loaded via the
        # template using the available all_students / active_fees lists.
        'all_students': Student.objects.filter(
                            is_active=True
                        ).select_related('current_class').order_by(
                            'last_name', 'first_name'
                        ),
        'active_fees':  SchoolFees.objects.filter(
                            is_active=True
                        ).select_related('school_class', 'term').order_by(
                            '-term__start_date', 'school_class__level', 'fees_type'
                        ),
    }


def _apply_to_instance(instance: FeesPayment, cleaned: dict) -> None:
    """Write cleaned scalar and FK fields onto a FeesPayment instance."""
    scalar_fields = ('amount_paid', 'payment_date')
    for f in scalar_fields:
        if f in cleaned:
            setattr(instance, f, cleaned[f])

    if 'student_id'     in cleaned:
        instance.student_id      = cleaned['student_id']
    if 'term_id'        in cleaned:
        instance.term_id         = cleaned['term_id']
    if 'school_class_id' in cleaned:
        instance.school_class_id = cleaned['school_class_id']
    if 'school_fees_id' in cleaned:
        instance.school_fees_id  = cleaned['school_fees_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. PAYMENTS LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def payment_list(request):
    """
    All fee payment records with statistics and filters.

    Stats cards:
        total payments, total UGX collected,
        today's collection (count + amount),
        current-term totals, by-term, by-section, by-class,
        by-fee-type, 30-day daily trend, monthly totals,
        highest/lowest/average payment, 10 recent payments.

    Filters (GET — all stackable):
        ?q=         receipt number / student name / student ID search
        ?term=<id>  filter by term FK
        ?class=     filter by class level (e.g. p5)
        ?section=   nursery | primary
        ?fee_type=  fee type value
        ?date_from= YYYY-MM-DD  payment_date >=
        ?date_to=   YYYY-MM-DD  payment_date <=
        ?student=<id> filter by a specific student
    """
    today = date.today()
    qs    = FeesPayment.objects.select_related(
        'student', 'school_class', 'school_fees', 'term'
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    search          = request.GET.get('q', '').strip()
    term_filter     = request.GET.get('term', '').strip()
    class_filter    = request.GET.get('class', '').strip()
    section_filter  = request.GET.get('section', '').strip()
    fee_type_filter = request.GET.get('fee_type', '').strip()
    date_from_raw   = request.GET.get('date_from', '').strip()
    date_to_raw     = request.GET.get('date_to', '').strip()
    student_filter  = request.GET.get('student', '').strip()

    if search:
        qs = qs.filter(
            Q(receipt_number__icontains=search)          |
            Q(student__first_name__icontains=search)     |
            Q(student__last_name__icontains=search)      |
            Q(student__student_id__icontains=search)
        )

    if term_filter:
        qs = qs.filter(term__pk=term_filter)

    if class_filter:
        qs = qs.filter(school_class__level=class_filter)

    if section_filter:
        qs = qs.filter(school_class__section=section_filter)

    if fee_type_filter:
        qs = qs.filter(school_fees__fees_type=fee_type_filter)

    if date_from_raw:
        try:
            from datetime import datetime as dt
            df = dt.strptime(date_from_raw, '%Y-%m-%d').date()
            qs = qs.filter(payment_date__gte=df)
        except ValueError:
            messages.warning(request, 'Invalid "from" date — filter ignored.')

    if date_to_raw:
        try:
            from datetime import datetime as dt
            dt_ = dt.strptime(date_to_raw, '%Y-%m-%d').date()
            qs = qs.filter(payment_date__lte=dt_)
        except ValueError:
            messages.warning(request, 'Invalid "to" date — filter ignored.')

    if student_filter:
        qs = qs.filter(student__pk=student_filter)

    qs = qs.order_by('-payment_date', '-created_at')

    # ── Filtered total (shown above the table) ─────────────────────────────────
    filtered_total = qs.aggregate(s=Sum('amount_paid'))['s'] or 0

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # Annotate with fee type label
    items = list(page_obj.object_list)
    for item in items:
        ft = item.school_fees.fees_type if item.school_fees else ''
        item.fee_type_label = FEES_TYPE_LABELS.get(ft, ft)

    stats = get_payment_list_stats()

    context = {
        'payments':         items,
        'page_obj':         page_obj,
        'filtered_total':   filtered_total,
        # active filters
        'search':           search,
        'term_filter':      term_filter,
        'class_filter':     class_filter,
        'section_filter':   section_filter,
        'fee_type_filter':  fee_type_filter,
        'date_from_raw':    date_from_raw,
        'date_to_raw':      date_to_raw,
        'student_filter':   student_filter,
        # choice lists
        'fees_type_choices':   list(FEES_TYPE_LABELS.items()),
        'class_level_choices': _CLASS_LEVEL_CHOICES,
        'fees_type_labels':    FEES_TYPE_LABELS,
        'today':               today,
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD PAYMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def payment_add(request):
    """
    Record a new fee payment.

    GET  — blank form; payment_date pre-set to today;
           current term pre-selected if active.
    POST — validate all fields; auto-generate receipt_number inside
           transaction.atomic(); save; redirect to payment_detail.

    Receipt number is generated inside the atomic block to prevent
    race conditions with concurrent payments being recorded simultaneously.
    """
    lookups = _get_form_lookups()

    if request.method == 'GET':
        current_term = Term.objects.filter(is_current=True).first()
        return render(request, f'{_T}form.html', {
            'form_title':   'Record Payment',
            'action':       'add',
            'post':         {},
            'errors':       {},
            'today_str':    date.today().strftime('%Y-%m-%d'),
            'current_term': current_term,
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_payment(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': 'Record Payment',
            'action':     'add',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            payment = FeesPayment()
            _apply_to_instance(payment, cleaned)
            payment.receipt_number = generate_receipt_number()
            payment.save()
    except Exception as exc:
        messages.error(request, f'Could not save payment: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title': 'Record Payment',
            'action':     'add',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Payment recorded. Receipt number: {payment.receipt_number} — '
        f'UGX {payment.amount_paid:,.0f} for {payment.student}.'
    )
    return redirect('fees:payment_detail', pk=payment.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT PAYMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def payment_edit(request, pk):
    """
    Edit an existing payment record.

    Note: receipt_number is never changed on edit — it is a permanent
    record identifier. Only amount_paid, payment_date, student, term,
    school_class, and school_fees are editable.

    GET  — form pre-filled with current values.
    POST — validate; save; re-render with errors on failure.
    """
    payment = get_object_or_404(
        FeesPayment.objects.select_related(
            'student', 'school_class', 'school_fees', 'term'
        ),
        pk=pk
    )
    lookups = _get_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'payment':    payment,
            'form_title': f'Edit Payment — {payment.receipt_number}',
            'action':     'edit',
            'post':       {},
            'errors':     {},
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_payment(request.POST, instance=payment)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'payment':    payment,
            'form_title': f'Edit Payment — {payment.receipt_number}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            _apply_to_instance(payment, cleaned)
            payment.save()
    except Exception as exc:
        messages.error(request, f'Could not update payment: {exc}')
        return render(request, f'{_T}form.html', {
            'payment':    payment,
            'form_title': f'Edit Payment — {payment.receipt_number}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Payment {payment.receipt_number} has been updated successfully.'
    )
    return redirect('fees:payment_detail', pk=payment.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE PAYMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def payment_delete(request, pk):
    """
    Delete a payment record.

    GET  — confirmation page showing payment summary (receipt, student,
           amount, date, fee item) so the user knows exactly what
           will be removed.
    POST — delete the record and redirect to payments list.

    Note: deletion of a payment record affects the student's balance in
    AssessmentFees. A warning is shown on the confirmation page.
    """
    payment = get_object_or_404(
        FeesPayment.objects.select_related(
            'student', 'school_class', 'school_fees', 'term'
        ),
        pk=pk
    )

    if request.method == 'GET':
        ft = payment.school_fees.fees_type if payment.school_fees else ''
        return render(request, f'{_T}delete_confirm.html', {
            'payment':        payment,
            'fee_type_label': FEES_TYPE_LABELS.get(ft, ft),
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    receipt = payment.receipt_number
    student = str(payment.student)
    try:
        payment.delete()
        messages.success(
            request,
            f'Payment {receipt} ({student}) has been permanently deleted. '
            f'Please update the student\'s fee assessment if required.'
        )
    except Exception as exc:
        messages.error(request, f'Could not delete payment: {exc}')
        return redirect('fees:payment_detail', pk=pk)

    return redirect('fees:payment_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. PAYMENT DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def payment_detail(request, pk):
    """
    Full single payment detail page — receipt-style layout.

    Displays:
        - Receipt number, student name, class, term
        - Fee item (type + amount from SchoolFees)
        - Amount paid (UGX), payment date
        - Coverage %: how much of the fee does this single payment cover
        - Student totals for this fee across all payments (cleared / outstanding)
        - All other payments by this student for the same term (sidebar)
        - Student's total paid this term
        - Previous / Next payment navigation (by date)
    """
    payment = get_object_or_404(
        FeesPayment.objects.select_related(
            'student', 'student__current_class',
            'school_class', 'school_fees', 'term'
        ),
        pk=pk
    )
    stats = get_payment_detail_stats(payment)

    context = {
        'payment':    payment,
        'page_title': f'Receipt — {payment.receipt_number}',
        **stats,
    }
    return render(request, f'{_T}detail.html', context)
