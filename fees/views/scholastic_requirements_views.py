from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction

from fees.models import (
    SchoolScholasticRequirements,
    ScholasticRequirementClass,
)
from academics.models import Term
from academics.utils.subject_utils import get_sch_supported_classes


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _validate_requirement(post, supported_classes):
    """
    Validate POST data for SchoolScholasticRequirements.
    Returns (cleaned_data dict, errors dict).
    cleaned_data is only meaningful when errors is empty.
    """
    errors = {}
    data   = {}

    # term
    term_id = (post.get('term') or '').strip()
    if not term_id:
        errors['term'] = 'Term is required.'
    else:
        try:
            data['term'] = Term.objects.get(pk=term_id)
        except Term.DoesNotExist:
            errors['term'] = 'Selected term does not exist.'

    # item_name
    item_name = (post.get('item_name') or '').strip()
    if not item_name:
        errors['item_name'] = 'Item name is required.'
    elif len(item_name) > 150:
        errors['item_name'] = 'Item name must not exceed 150 characters.'
    else:
        data['item_name'] = item_name

    # quantity
    qty_str = (post.get('quantity') or '').strip()
    if not qty_str:
        errors['quantity'] = 'Quantity is required.'
    else:
        try:
            qty = int(qty_str)
            if qty < 1:
                errors['quantity'] = 'Quantity must be at least 1.'
            else:
                data['quantity'] = qty
        except ValueError:
            errors['quantity'] = 'Quantity must be a whole number.'

    # unit
    valid_units = [u[0] for u in SchoolScholasticRequirements.UNIT_CHOICES]
    unit = (post.get('unit') or '').strip()
    if not unit:
        errors['unit'] = 'Unit is required.'
    elif unit not in valid_units:
        errors['unit'] = 'Select a valid unit.'
    else:
        data['unit'] = unit

    # monetary_value
    val_str = (post.get('monetary_value') or '').strip()
    if not val_str:
        errors['monetary_value'] = 'Monetary value is required.'
    else:
        try:
            val = float(val_str)
            if val < 0:
                errors['monetary_value'] = 'Monetary value cannot be negative.'
            else:
                data['monetary_value'] = val
        except ValueError:
            errors['monetary_value'] = 'Enter a valid amount (numbers only).'

    # description — optional
    data['description'] = (post.get('description') or '').strip()

    # classes — at least one must be ticked
    chosen_pks = []
    for cls in supported_classes:
        key = f"class_{cls.supported_class.key.lower()}"
        if (post.get(key) or '').strip():
            chosen_pks.append(cls.pk)

    if not chosen_pks:
        errors['classes'] = 'Select at least one class.'
    else:
        data['chosen_pks'] = chosen_pks

    return data, errors


def _checked_pks_from_post(post, supported_classes):
    """Return a set of SchoolSupportedClasses PKs that are ticked in POST."""
    checked = set()
    for cls in supported_classes:
        key = f"class_{cls.supported_class.key.lower()}"
        if (post.get(key) or '').strip():
            checked.add(cls.pk)
    return checked


# ─────────────────────────────────────────────────────────────────────────────
# VIEWS
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def scholastic_requirements_list(request):
    term_id  = request.GET.get('term', '').strip()
    terms    = Term.objects.all().order_by('-name')

    qs = (
        SchoolScholasticRequirements.objects
        .select_related('term')
        .prefetch_related('assigned_classes__school_class__supported_class')
        .order_by('-term__name', 'item_name')
    )
    if term_id:
        qs = qs.filter(term_id=term_id)

    return render(request, 'fees/scholastic_requirements/list.html', {
        'requirements': qs,
        'terms':        terms,
        'term_id':      term_id,
    })


@login_required
def add_scholastic_requirements(request, pk=None):
    """Handles both add (pk=None) and edit (pk provided)."""

    supported_classes = get_sch_supported_classes()
    terms             = Term.objects.all().order_by('-name')
    requirement       = None
    checked_pks       = set()   # SchoolSupportedClasses PKs that should be ticked

    if pk:
        requirement = get_object_or_404(
            SchoolScholasticRequirements.objects.prefetch_related('assigned_classes'),
            pk=pk,
        )
        checked_pks = set(
            requirement.assigned_classes.values_list('school_class_id', flat=True)
        )

    if request.method == 'POST':
        data, errors = _validate_requirement(request.POST, supported_classes)

        if errors:
            # Re-render with validation errors — preserve what the user ticked
            return render(request, 'fees/scholastic_requirements/add_edit.html', {
                'supported_classes': supported_classes,
                'terms':             terms,
                'unit_choices':      SchoolScholasticRequirements.UNIT_CHOICES,
                'requirement':       requirement,
                'checked_pks':       _checked_pks_from_post(request.POST, supported_classes),
                'errors':            errors,
                'post':              request.POST,
            })

        with transaction.atomic():
            if requirement:
                requirement.term           = data['term']
                requirement.item_name      = data['item_name']
                requirement.quantity       = data['quantity']
                requirement.unit           = data['unit']
                requirement.monetary_value = data['monetary_value']
                requirement.description    = data['description']
                requirement.save()
                requirement.assigned_classes.all().delete()   # rebuild bridges
            else:
                requirement = SchoolScholasticRequirements.objects.create(
                    term           = data['term'],
                    item_name      = data['item_name'],
                    quantity       = data['quantity'],
                    unit           = data['unit'],
                    monetary_value = data['monetary_value'],
                    description    = data['description'],
                )

            for cls_pk in data['chosen_pks']:
                ScholasticRequirementClass.objects.create(
                    requirement  = requirement,
                    school_class_id = cls_pk,
                )

        verb = 'updated' if pk else 'added'
        messages.success(request, f'"{requirement.item_name}" {verb} successfully.')
        return redirect('fees:scholastic_requirements_list')

    # GET
    return render(request, 'fees/scholastic_requirements/add_edit.html', {
        'supported_classes': supported_classes,
        'terms':             terms,
        'unit_choices':      SchoolScholasticRequirements.UNIT_CHOICES,
        'requirement':       requirement,
        'checked_pks':       checked_pks,
        'errors':            {},
        'post':              None,
    })


@login_required
def scholastic_requirements_detail(request, pk):
    requirement = get_object_or_404(
        SchoolScholasticRequirements.objects
        .select_related('term')
        .prefetch_related('assigned_classes__school_class__supported_class'),
        pk=pk,
    )
    return render(request, 'fees/scholastic_requirements/detail.html', {
        'requirement':      requirement,
        'assigned_classes': requirement.assigned_classes.select_related('school_class__supported_class'),
    })


@login_required
def delete_scholastic_requirement(request, pk):
    requirement = get_object_or_404(SchoolScholasticRequirements, pk=pk)

    if request.method == 'POST':
        item_name = requirement.item_name
        requirement.delete()
        messages.success(request, f'"{item_name}" has been deleted.')
        return redirect('fees:scholastic_requirements_list')

    return render(request, 'fees/scholastic_requirements/confirm_delete.html', {
        'requirement': requirement,
    })


@login_required
def toggle_scholastic_requirement(request, pk):
    requirement = get_object_or_404(SchoolScholasticRequirements, pk=pk)

    if request.method == 'POST':
        requirement.is_active = not requirement.is_active
        requirement.save()
        state = 'activated' if requirement.is_active else 'deactivated'
        messages.success(request, f'"{requirement.item_name}" has been {state}.')

    return redirect('fees:scholastic_requirements_detail', pk=pk)




# fees/views/scholastic_payment_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Views for ScholasticRequirementPayment transactions.
#
# Views:
#   scholastic_payment_list   — paginated list with filters + stats
#   scholastic_payment_detail — full single-transaction receipt page
#   scholastic_payment_delete — confirm + perform deletion
#
# Rules (same as all fees views):
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
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

from academics.models import Term
from fees.models import (
    ScholasticRequirementPayment,
    SchoolScholasticRequirements,
    StudentScholasticRequirementStatus,
)
from students.models import Student


_T = 'fees/scholastic_payments/'


# ═══════════════════════════════════════════════════════════════════════════════
#  1. LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def scholastic_payment_list(request):
    """
    All ScholasticRequirementPayment records with filters and stats.

    Filters (GET — all stackable):
        ?q=           receipt number / student name / student ID
        ?term=<id>    filter by requirement term FK
        ?student=<id> filter by student PK
        ?date_from=   YYYY-MM-DD
        ?date_to=     YYYY-MM-DD
        ?type=        items | cash | mixed
    """
    today = date.today()

    qs = ScholasticRequirementPayment.objects.select_related(
        'student', 'requirement', 'requirement__term', 'school_class',
        'school_class__supported_class',
    ).order_by('-payment_date', '-created_at')

    # ── Filters ──────────────────────────────────────────────────────────────
    search        = request.GET.get('q', '').strip()
    term_filter   = request.GET.get('term', '').strip()
    student_filter= request.GET.get('student', '').strip()
    date_from_raw = request.GET.get('date_from', '').strip()
    date_to_raw   = request.GET.get('date_to', '').strip()
    type_filter   = request.GET.get('type', '').strip()   # items | cash | mixed

    if search:
        qs = qs.filter(
            Q(receipt_number__icontains=search)      |
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search)  |
            Q(student__student_id__icontains=search) |
            Q(requirement__item_name__icontains=search)
        )

    if term_filter:
        qs = qs.filter(requirement__term__pk=term_filter)

    if student_filter:
        qs = qs.filter(student__pk=student_filter)

    if date_from_raw:
        try:
            from datetime import datetime as _dt
            qs = qs.filter(payment_date__gte=_dt.strptime(date_from_raw, '%Y-%m-%d').date())
        except ValueError:
            messages.warning(request, 'Invalid "from" date — filter ignored.')

    if date_to_raw:
        try:
            from datetime import datetime as _dt
            qs = qs.filter(payment_date__lte=_dt.strptime(date_to_raw, '%Y-%m-%d').date())
        except ValueError:
            messages.warning(request, 'Invalid "to" date — filter ignored.')

    if type_filter == 'items':
        qs = qs.filter(brought_item=True, brought_cash=False)
    elif type_filter == 'cash':
        qs = qs.filter(brought_cash=True, brought_item=False)
    elif type_filter == 'mixed':
        qs = qs.filter(brought_item=True, brought_cash=True)

    # ── Stats (over full unfiltered set) ─────────────────────────────────────
    all_qs          = ScholasticRequirementPayment.objects.all()
    total           = all_qs.count()
    total_cash      = all_qs.aggregate(s=Sum('amount_paid_ugx'))['s'] or 0
    today_qs        = all_qs.filter(payment_date=today)
    today_count     = today_qs.count()
    today_cash      = today_qs.aggregate(s=Sum('amount_paid_ugx'))['s'] or 0

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    context = {
        'payments':       page_obj.object_list,
        'page_obj':       page_obj,
        # stats
        'total':          total,
        'total_cash':     total_cash,
        'today_count':    today_count,
        'today_cash':     today_cash,
        'today':          today,
        # active filters
        'search':         search,
        'term_filter':    term_filter,
        'student_filter': student_filter,
        'date_from_raw':  date_from_raw,
        'date_to_raw':    date_to_raw,
        'type_filter':    type_filter,
        # dropdowns
        'terms':          Term.objects.all().order_by('-name'),
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def scholastic_payment_detail(request, pk):
    """
    Full receipt detail for a single ScholasticRequirementPayment.
    Shows:
      - transaction breakdown (items + cash)
      - student's running status for this requirement
      - all other transactions for this student × requirement
      - prev / next navigation
    """
    payment = get_object_or_404(
        ScholasticRequirementPayment.objects.select_related(
            'student',
            'requirement',
            'requirement__term',
            'school_class',
            'school_class__supported_class',
            'handled_by',
        ),
        pk=pk,
    )

    req = payment.requirement

    # ── Student's running status for this requirement ─────────────────────────
    status = StudentScholasticRequirementStatus.objects.filter(
        student=payment.student,
        requirement=req,
    ).first()

    # ── Physical credit for this specific transaction ─────────────────────────
    physical_credit_this = float(payment.items_brought) * float(req.unit_price)

    # ── All other transactions for this student × requirement ─────────────────
    other_payments = ScholasticRequirementPayment.objects.filter(
        student=payment.student,
        requirement=req,
    ).exclude(pk=payment.pk).order_by('payment_date', 'created_at')

    # ── Prev / Next navigation ────────────────────────────────────────────────
    prev_payment = ScholasticRequirementPayment.objects.filter(
        Q(payment_date__lt=payment.payment_date) |
        Q(payment_date=payment.payment_date, pk__lt=payment.pk)
    ).only('pk', 'receipt_number').order_by('payment_date', 'pk').last()

    next_payment = ScholasticRequirementPayment.objects.filter(
        Q(payment_date__gt=payment.payment_date) |
        Q(payment_date=payment.payment_date, pk__gt=payment.pk)
    ).only('pk', 'receipt_number').order_by('payment_date', 'pk').first()

    context = {
        'payment':              payment,
        'req':                  req,
        'status':               status,
        'physical_credit_this': physical_credit_this,
        'other_payments':       other_payments,
        'prev_payment':         prev_payment,
        'next_payment':         next_payment,
        'page_title':           f'Receipt — {payment.receipt_number}',
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def scholastic_payment_delete(request, pk):
    """
    Delete a ScholasticRequirementPayment record.

    GET  — confirmation page with full transaction summary.
    POST — delete the record; does NOT auto-recalculate the status row
           (warn the user to manually review the student's requirement status).
    """
    payment = get_object_or_404(
        ScholasticRequirementPayment.objects.select_related(
            'student', 'requirement', 'requirement__term',
            'school_class', 'school_class__supported_class',
        ),
        pk=pk,
    )

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {
            'payment': payment,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    receipt  = payment.receipt_number
    student  = str(payment.student)
    req_name = payment.requirement.item_name

    try:
        with transaction.atomic():
            payment.delete()
        messages.success(
            request,
            f'Transaction {receipt} ({student} — {req_name}) permanently deleted. '
            f'Review the student\'s requirement status to verify the balance.'
        )
    except Exception as exc:
        messages.error(request, f'Could not delete transaction: {exc}')
        return redirect('fees:scholastic_payment_detail', pk=pk)

    return redirect('fees:scholastic_payment_list')