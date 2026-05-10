# fees/views/payment_add_views.py
# =============================================================================
# PAYMENT ADD WIZARD  —  4 Steps
# =============================================================================
# Step 1 — Student ID + payment type selection (checkboxes, multi-select)
# Step 2 — Show pending fees per selected type; handler picks which to work on
# Step 3 — Enter amounts / physical quantities for each selected fee
# Step 4 — Full summary + handler password confirmation → save
#
# URL names expected (add to fees/urls.py):
#   fees:payment_add_step1   /fees/payments/add/step1/
#   fees:payment_add_step2   /fees/payments/add/step2/
#   fees:payment_add_step3   /fees/payments/add/step3/
#   fees:payment_add_step4   /fees/payments/add/step4/
#   fees:payment_list        /fees/payments/
#
# SESSION KEY : 'payment_wizard'
# Sub-keys    : step1  step2  step3
# Rule        : ORM objects are NEVER stored in session — PKs only.
# =============================================================================

from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from fees.models import (
    AssessmentFees,
    FeesPayment,
    SchoolFees,
    SchoolScholasticRequirements,
    StudentFeesPaymentsStatus,
    StudentScholasticRequirementStatus,
)
from fees.utils.payment_utils import generate_receipt_number
from fees.utils.pending_fees_utils import (
    get_student_pending_fees,
    record_payment_status,
    record_scholastic_payment,
)
from students.models import Student
from permissions.decorators import has_permission


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

_SESSION_KEY = 'payment_wizard'
_T           = 'fees/payments/'

PAYMENT_TYPE_CHOICES = [
    ('school',     'School Fees'),
    ('assessment', 'Assessment Fees'),
    ('scholastic', 'Scholastic Requirements'),
]
_VALID_TYPES = {t for t, _ in PAYMENT_TYPE_CHOICES}


# ─────────────────────────────────────────────────────────────────────────────
# SESSION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_wizard(request):
    return request.session.get(_SESSION_KEY, {})


def _save_wizard(request, data):
    request.session[_SESSION_KEY] = data
    request.session.modified = True


def _clear_wizard(request):
    if _SESSION_KEY in request.session:
        del request.session[_SESSION_KEY]
    request.session.modified = True


def _cancel(request):
    _clear_wizard(request)
    messages.info(request, 'Payment entry cancelled.')
    return redirect('fees:payment_list')


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE — group pending fees by type for step 2 display
# ─────────────────────────────────────────────────────────────────────────────

def _group_fees(fees_list):
    groups = {
        'school':     {'label': 'School Fees',            'items': []},
        'assessment': {'label': 'Assessment Fees',         'items': []},
        'scholastic': {'label': 'Scholastic Requirements', 'items': []},
    }
    for f in fees_list:
        t = f['type']
        if t in groups:
            groups[t]['items'].append(f)
    return {k: v for k, v in groups.items() if v['items']}


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE — rebuild full fee details from DB for step 3 / step 4
# ─────────────────────────────────────────────────────────────────────────────

def _build_fee_details(student, selected):
    """
    Re-fetches full fee detail dicts from DB for a list of
    {'type': ..., 'fee_id': ...} dicts (from session['step2']['selected']).

    Common keys (all types):
        type  fee_id  label  term_label
        amount_required  amount_paid  amount_balance

    Scholastic-only extras:
        quantity_required  quantity_brought_already  quantity_remaining
        unit  unit_price  monetary_value
    """
    school_ids     = [s['fee_id'] for s in selected if s['type'] == 'school']
    assessment_ids = [s['fee_id'] for s in selected if s['type'] == 'assessment']
    scholastic_ids = [s['fee_id'] for s in selected if s['type'] == 'scholastic']

    school_map = {
        f.pk: f for f in SchoolFees.objects.filter(
            pk__in=school_ids).select_related('term')
    }
    assessment_map = {
        f.pk: f for f in AssessmentFees.objects.filter(
            pk__in=assessment_ids).select_related('term', 'assessment')
    }
    scholastic_map = {
        r.pk: r for r in SchoolScholasticRequirements.objects.filter(
            pk__in=scholastic_ids).select_related('term')
    }

    school_status_map = {
        s.school_fees_id: s
        for s in StudentFeesPaymentsStatus.objects.filter(
            student=student, school_fees_id__in=school_ids)
    }
    assessment_status_map = {
        s.assessment_fees_id: s
        for s in StudentFeesPaymentsStatus.objects.filter(
            student=student, assessment_fees_id__in=assessment_ids)
    }
    scholastic_status_map = {
        s.requirement_id: s
        for s in StudentScholasticRequirementStatus.objects.filter(
            student=student, requirement_id__in=scholastic_ids)
    }

    details = []

    for item in selected:
        ftype  = item['type']
        fee_id = item['fee_id']

        if ftype == 'school':
            fee = school_map.get(fee_id)
            if not fee:
                continue
            status = school_status_map.get(fee_id)
            details.append({
                'type':            'school',
                'fee_id':          fee_id,
                'label':           fee.title or fee.get_fees_type_display(),
                'term_label':      str(fee.term),
                'amount_required': fee.amount,
                'amount_paid':     status.amount_paid    if status else Decimal('0'),
                'amount_balance':  status.amount_balance if status else fee.amount,
            })

        elif ftype == 'assessment':
            fee = assessment_map.get(fee_id)
            if not fee:
                continue
            status     = assessment_status_map.get(fee_id)
            fee_amount = fee.amount or Decimal('0')
            label      = str(fee.assessment) if fee.assessment else str(fee)
            details.append({
                'type':            'assessment',
                'fee_id':          fee_id,
                'label':           label,
                'term_label':      str(fee.term),
                'amount_required': fee_amount,
                'amount_paid':     status.amount_paid    if status else Decimal('0'),
                'amount_balance':  status.amount_balance if status else fee_amount,
            })

        elif ftype == 'scholastic':
            req = scholastic_map.get(fee_id)
            if not req:
                continue
            status        = scholastic_status_map.get(fee_id)
            qty_already   = status.quantity_brought if status else 0
            qty_remaining = req.quantity - qty_already
            details.append({
                'type':                     'scholastic',
                'fee_id':                   fee_id,
                'label':                    req.item_name,
                'term_label':               str(req.term),
                'amount_required':          req.monetary_value,
                'amount_paid':              status.amount_paid_ugx    if status else Decimal('0'),
                'amount_balance':           status.amount_balance_ugx if status else req.monetary_value,
                'quantity_required':        req.quantity,
                'quantity_brought_already': qty_already,
                'quantity_remaining':       qty_remaining,
                'unit':                     req.get_unit_display(),
                'unit_price':               req.unit_price,
                'monetary_value':           req.monetary_value,
            })

    return details


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE — build step 4 display summary
# ─────────────────────────────────────────────────────────────────────────────

def _build_summary(fee_details, entries):
    """
    Merges fee_details (DB data) with handler-entered amounts (from session)
    to produce a display-ready summary for step 4.
    """
    entry_map = {(e['type'], e['fee_id']): e for e in entries}
    summary   = []

    for detail in fee_details:
        key   = (detail['type'], detail['fee_id'])
        entry = entry_map.get(key)
        if not entry:
            continue

        ftype = detail['type']

        if ftype in ('school', 'assessment'):
            amount      = Decimal(entry['amount'])
            new_balance = max(Decimal('0'), detail['amount_balance'] - amount)
            summary.append({
                'type':               ftype,
                'label':              detail['label'],
                'term_label':         detail['term_label'],
                'amount_required':    detail['amount_required'],
                'amount_paid_so_far': detail['amount_paid'],
                'amount_paying':      amount,
                'new_balance':        new_balance,
                'will_clear':         new_balance == Decimal('0'),
            })

        elif ftype == 'scholastic':
            qty_now   = int(entry['quantity_brought'])
            cash_now  = Decimal(entry['cash_paid'])
            new_qty   = detail['quantity_brought_already'] + qty_now
            phys_credit = Decimal(str(new_qty)) * detail['unit_price']
            total_cash  = detail['amount_paid'] + cash_now
            new_balance = max(Decimal('0'), detail['monetary_value'] - phys_credit - total_cash)
            summary.append({
                'type':              'scholastic',
                'label':             detail['label'],
                'term_label':        detail['term_label'],
                'amount_required':   detail['amount_required'],
                'quantity_required': detail['quantity_required'],
                'unit':              detail['unit'],
                'quantity_bringing': qty_now,
                'new_total_qty':     new_qty,
                'cash_paying':       cash_now,
                'total_cash_paid':   total_cash,
                'new_balance':       new_balance,
                'will_clear':        new_balance == Decimal('0'),
            })

    return summary


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE — simulate remaining fees after save (step 4 preview)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_remaining(student, entries):
    """
    Simulates what will still be pending AFTER saving all entries.
    Read-only — no DB writes.
    """
    all_pending = get_student_pending_fees(student)
    entry_map   = {(e['type'], e['fee_id']): e for e in entries}
    remaining   = []

    for pending in all_pending:
        key   = (pending['type'], pending['fee_id'])
        entry = entry_map.get(key)

        if not entry:
            remaining.append(pending)
            continue

        ftype = pending['type']

        if ftype in ('school', 'assessment'):
            amount      = Decimal(entry['amount'])
            new_balance = pending['amount_balance'] - amount
            if new_balance > Decimal('0'):
                updated                   = dict(pending)
                updated['amount_balance'] = new_balance
                updated['amount_paid']    = pending['amount_paid'] + amount
                remaining.append(updated)

        elif ftype == 'scholastic':
            qty_now     = int(entry['quantity_brought'])
            cash_now    = Decimal(entry['cash_paid'])
            new_qty     = pending.get('quantity_brought', 0) + qty_now
            phys_credit = Decimal(str(new_qty)) * pending.get('unit_price', Decimal('0'))
            new_cash    = pending.get('amount_paid', Decimal('0')) + cash_now
            new_balance = max(
                Decimal('0'),
                pending['amount_required'] - phys_credit - new_cash,
            )
            if new_balance > Decimal('0'):
                updated                   = dict(pending)
                updated['amount_balance'] = new_balance
                remaining.append(updated)

    return remaining


# =============================================================================
# STEP 1 — Student ID + Payment Types
# =============================================================================

@login_required
@has_permission('fee_payment', action='read')
def payment_add_step1(request):
    if request.method == 'POST':

        if request.POST.get('action') == 'cancel':
            return _cancel(request)

        errors         = {}
        student_id_raw = request.POST.get('student_id', '').strip()
        payment_types  = request.POST.getlist('payment_types')

        student = None
        if not student_id_raw:
            errors['student_id'] = 'Student ID is required.'
        else:
            try:
                student = Student.objects.select_related('current_class').get(
                    student_id=student_id_raw, is_active=True,
                )
            except Student.DoesNotExist:
                errors['student_id'] = (
                    f'No active student found with ID "{student_id_raw}".'
                )

        valid_types = [t for t in payment_types if t in _VALID_TYPES]
        if not valid_types:
            errors['payment_types'] = 'Select at least one payment type.'

        if errors:
            return render(request, f'{_T}add_step1.html', {
                'errors':               errors,
                'post':                 request.POST,
                'payment_type_choices': PAYMENT_TYPE_CHOICES,
            })

        wizard = _get_wizard(request)
        wizard['step1'] = {
            'student_pk':    student.pk,
            'student_id':    student.student_id,
            'student_name':  student.full_name,
            'student_class': str(student.current_class) if student.current_class else 'N/A',
            'payment_types': valid_types,
        }
        wizard.pop('step2', None)
        wizard.pop('step3', None)
        _save_wizard(request, wizard)
        return redirect('fees:payment_add_step2')

    # GET — pre-populate if coming back from step 2
    wizard   = _get_wizard(request)
    existing = wizard.get('step1', {})
    return render(request, f'{_T}add_step1.html', {
        'errors':               {},
        'post':                 {},
        'existing':             existing,
        'payment_type_choices': PAYMENT_TYPE_CHOICES,
    })


# =============================================================================
# STEP 2 — Select which pending fees to process
# =============================================================================

@login_required
@has_permission('fee_payment', action='read')
def payment_add_step2(request):
    wizard = _get_wizard(request)
    step1  = wizard.get('step1')

    if not step1:
        messages.warning(request, 'Please start from Step 1.')
        return redirect('fees:payment_add_step1')

    student = get_object_or_404(Student, pk=step1['student_pk'], is_active=True)

    if request.method == 'POST':

        if request.POST.get('action') == 'cancel':
            return _cancel(request)

        if request.POST.get('action') == 'back':
            return redirect('fees:payment_add_step1')

        selected = []
        for key in request.POST:
            if not key.startswith('select_'):
                continue
            parts = key.split('_', 2)   # ['select', 'school', '5']
            if len(parts) != 3:
                continue
            _, fee_type, fee_id_str = parts
            if fee_type not in _VALID_TYPES:
                continue
            try:
                fee_id = int(fee_id_str)
            except ValueError:
                continue
            selected.append({'type': fee_type, 'fee_id': fee_id})

        if not selected:
            pending      = get_student_pending_fees(student)
            filtered     = [f for f in pending if f['type'] in step1['payment_types']]
            grouped_fees = _group_fees(filtered)
            return render(request, f'{_T}add_step2.html', {
                'step1':                step1,
                'grouped_fees':         grouped_fees,
                'payment_type_choices': PAYMENT_TYPE_CHOICES,
                'prev_selected':        set(),
                'error':                'Select at least one fee to continue.',
            })

        wizard['step2'] = {'selected': selected}
        wizard.pop('step3', None)
        _save_wizard(request, wizard)
        return redirect('fees:payment_add_step3')

    # GET
    pending      = get_student_pending_fees(student)
    filtered     = [f for f in pending if f['type'] in step1['payment_types']]
    grouped_fees = _group_fees(filtered)

    prev_selected = {
        f"{s['type']}_{s['fee_id']}"
        for s in wizard.get('step2', {}).get('selected', [])
    }

    return render(request, f'{_T}add_step2.html', {
        'step1':                step1,
        'grouped_fees':         grouped_fees,
        'prev_selected':        prev_selected,
        'payment_type_choices': PAYMENT_TYPE_CHOICES,
        'error':                None,
    })


# =============================================================================
# STEP 3 — Enter amounts / quantities
# =============================================================================

@login_required
@has_permission('fee_payment', action='read')
def payment_add_step3(request):
    wizard = _get_wizard(request)
    step1  = wizard.get('step1')
    step2  = wizard.get('step2')

    if not step1 or not step2:
        messages.warning(request, 'Please start from Step 1.')
        return redirect('fees:payment_add_step1')

    student  = get_object_or_404(Student, pk=step1['student_pk'], is_active=True)
    selected = step2['selected']

    if request.method == 'POST':

        if request.POST.get('action') == 'cancel':
            return _cancel(request)

        if request.POST.get('action') == 'back':
            return redirect('fees:payment_add_step2')

        fee_details = _build_fee_details(student, selected)
        errors  = {}
        entries = []

        for detail in fee_details:
            ftype  = detail['type']
            fee_id = detail['fee_id']

            if ftype in ('school', 'assessment'):
                raw       = request.POST.get(f'amount_{ftype}_{fee_id}', '').strip()
                field_key = f'amount_{ftype}_{fee_id}'

                if not raw:
                    errors[field_key] = 'Amount is required.'
                    continue
                try:
                    amount = Decimal(raw)
                except Exception:
                    errors[field_key] = 'Enter a valid numeric amount.'
                    continue
                if amount <= Decimal('0'):
                    errors[field_key] = 'Amount must be greater than zero.'
                    continue
                if amount > detail['amount_balance']:
                    errors[field_key] = (
                        f'Amount exceeds balance of UGX {detail["amount_balance"]:,.0f}.'
                    )
                    continue

                entries.append({'type': ftype, 'fee_id': fee_id, 'amount': str(amount)})

            elif ftype == 'scholastic':
                raw_qty   = request.POST.get(f'qty_{fee_id}',  '0').strip() or '0'
                raw_cash  = request.POST.get(f'cash_{fee_id}', '0').strip() or '0'
                field_key = f'scholastic_{fee_id}'

                try:
                    qty  = int(raw_qty)
                    cash = Decimal(raw_cash)
                except Exception:
                    errors[field_key] = 'Enter a valid quantity and/or cash amount.'
                    continue

                if qty < 0:
                    errors[field_key] = 'Quantity cannot be negative.'
                    continue
                if cash < Decimal('0'):
                    errors[field_key] = 'Cash amount cannot be negative.'
                    continue
                if qty == 0 and cash == Decimal('0'):
                    errors[field_key] = (
                        'Enter at least one unit brought or a cash amount.'
                    )
                    continue
                if qty > detail['quantity_remaining']:
                    errors[field_key] = (
                        f'Cannot bring more than {detail["quantity_remaining"]} '
                        f'{detail["unit"]}(s) — '
                        f'{detail["quantity_brought_already"]} already recorded.'
                    )
                    continue

                phys_credit = Decimal(str(qty)) * detail['unit_price']
                if phys_credit + cash > detail['amount_balance']:
                    errors[field_key] = (
                        f'Combined contribution (UGX {phys_credit + cash:,.0f}) '
                        f'exceeds remaining balance (UGX {detail["amount_balance"]:,.0f}).'
                    )
                    continue

                entries.append({
                    'type':             'scholastic',
                    'fee_id':           fee_id,
                    'quantity_brought': qty,
                    'cash_paid':        str(cash),
                })

        if errors:
            return render(request, f'{_T}add_step3.html', {
                'step1':       step1,
                'fee_details': fee_details,
                'errors':      errors,
                'post':        request.POST,
            })

        wizard['step3'] = {'entries': entries}
        _save_wizard(request, wizard)
        return redirect('fees:payment_add_step4')

    # GET
    fee_details = _build_fee_details(student, selected)
    return render(request, f'{_T}add_step3.html', {
        'step1':       step1,
        'fee_details': fee_details,
        'errors':      {},
        'post':        {},
    })


# =============================================================================
# STEP 4 — Summary + password confirmation + save
# =============================================================================

@login_required
@has_permission('fee_payment', action='read')
def payment_add_step4(request):
    wizard     = _get_wizard(request)
    step1      = wizard.get('step1')
    step2      = wizard.get('step2')
    step3_data = wizard.get('step3')

    if not step1 or not step2 or not step3_data:
        messages.warning(request, 'Please start from Step 1.')
        return redirect('fees:payment_add_step1')

    student  = get_object_or_404(Student, pk=step1['student_pk'], is_active=True)
    entries  = step3_data['entries']
    selected = step2['selected']

    fee_details = _build_fee_details(student, selected)
    summary     = _build_summary(fee_details, entries)
    remaining   = _compute_remaining(student, entries)

    if request.method == 'POST':

        if request.POST.get('action') == 'cancel':
            return _cancel(request)

        if request.POST.get('action') == 'back':
            return redirect('fees:payment_add_step3')

        password = request.POST.get('confirm_password', '').strip()

        if not password:
            return render(request, f'{_T}add_step4.html', {
                'step1': step1, 'summary': summary, 'remaining': remaining,
                'pw_error': 'Your password is required to confirm this payment.',
            })

        confirmed_user = authenticate(
            request, username=request.user.username, password=password,
        )
        if not confirmed_user:
            return render(request, f'{_T}add_step4.html', {
                'step1': step1, 'summary': summary, 'remaining': remaining,
                'pw_error': 'Incorrect password. Please try again.',
            })

        today        = date.today()
        school_class = student.current_class

        try:
            with transaction.atomic():
                for entry in entries:
                    ftype  = entry['type']
                    fee_id = entry['fee_id']

                    if ftype == 'school':
                        fee    = SchoolFees.objects.get(pk=fee_id)
                        amount = Decimal(entry['amount'])
                        FeesPayment.objects.create(
                            receipt_number=generate_receipt_number(),
                            student=student, term=fee.term,
                            school_fees=fee, assessment_fees=None,
                            school_class=school_class, amount=amount,
                            payment_date=today, handled_by=request.user,
                        )
                        record_payment_status(
                            student=student, payment_type='school',
                            fee_pk=fee_id, amount_paid=amount,
                            school_class=school_class, term=fee.term,
                            handled_by=request.user, payment_date=today,
                        )

                    elif ftype == 'assessment':
                        fee    = AssessmentFees.objects.get(pk=fee_id)
                        amount = Decimal(entry['amount'])
                        FeesPayment.objects.create(
                            receipt_number=generate_receipt_number(),
                            student=student, term=fee.term,
                            school_fees=None, assessment_fees=fee,
                            school_class=school_class, amount=amount,
                            payment_date=today, handled_by=request.user,
                        )
                        record_payment_status(
                            student=student, payment_type='assessment',
                            fee_pk=fee_id, amount_paid=amount,
                            school_class=school_class, term=fee.term,
                            handled_by=request.user, payment_date=today,
                        )

                    elif ftype == 'scholastic':
                        record_scholastic_payment(
                            student=student,
                            requirement_pk=fee_id,
                            quantity_brought=int(entry['quantity_brought']),
                            cash_paid=Decimal(entry['cash_paid']),
                            school_class=school_class,
                            recorded_by=request.user,
                            event_date=today,
                        )

            _clear_wizard(request)
            messages.success(
                request,
                f'Payment recorded for {student.full_name} '
                f'({student.student_id}). {len(entries)} item(s) processed.',
            )
            return redirect('fees:payment_list')

        except ValueError as exc:
            return render(request, f'{_T}add_step4.html', {
                'step1': step1, 'summary': summary, 'remaining': remaining,
                'pw_error': str(exc),
            })
        except Exception as exc:
            return render(request, f'{_T}add_step4.html', {
                'step1': step1, 'summary': summary, 'remaining': remaining,
                'pw_error': f'Unexpected error — {exc}. Nothing was saved.',
            })

    # GET
    return render(request, f'{_T}add_step4.html', {
        'step1': step1, 'summary': summary, 'remaining': remaining,
        'pw_error': None,
    })

