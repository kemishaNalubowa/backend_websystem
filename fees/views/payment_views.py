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
from fees.models import FeesPayment, SchoolFees,AssessmentFees,FeesClass
from fees.utils.fees_utils import FEES_TYPE_LABELS
from fees.utils.payment_utils import (
    generate_receipt_number,
    get_payment_detail_stats,
    get_payment_list_stats,
    validate_and_parse_payment,
)
from students.models import Student




# from django.shortcuts import render, redirect
# from django.contrib import messages

# from students.models import Student
# from academics.models import SchoolSupportedClasses
# from fees.models import SchoolFees
# from assessments.models import AssessmentFees  # adjust if your app name differs



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
    # filtered_total = qs.aggregate(s=Sum('amount_paid'))['s'] or 0

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # Annotate with fee type label
    items = list(page_obj.object_list)
    for item in items:
        ft = item.school_fees.fees_type if item.school_fees else ''
        item.fee_type_label = FEES_TYPE_LABELS.get(ft, ft)

    # stats = get_payment_list_stats()

    context = {
        'payments':         items,
        'page_obj':         page_obj,
        # 'filtered_total':   filtered_total,
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
        # **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD PAYMENT
# ═══════════════════════════════════════════════════════════════════════════════

# fees/views/payment_views.py

# ============================================================================
# ADD PAYMENT — PART 1
# ----------------------------------------------------------------------------
# Flow:
# 1) User selects:
#       - student_id
#       - payment_type (assessment | school)
# 2) System fetches:
#       - student mini info
#       - current class
# 3) Based on payment type:
#       - Fetch relevant fee structures
#       - Convert to lightweight list (mini info)
#       - Store in session
# 4) Set session flag: payment_part1_done = True
# 5) Redirect back to same view
# 6) Template renders next section based on flag
# ============================================================================


# fees/views/add_payment_view.py
# Multi-step Add Payment — school / assessment / scholastic
# Rules: FBV only, no forms.py, no CBV, no JSON, messages for feedback,
#        login_required on every view, transaction.atomic on all saves.

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from fees.models import (
    AssessmentFees, FeesClass, FeesPayment, SchoolFees,
    SchoolScholasticRequirements, ScholasticRequirementClass,
    StudentFeesPaymentsStatus, StudentScholasticRequirementStatus,ScholasticRequirementPayment
)
from fees.utils.payment_utils import generate_receipt_number,generate_receipt_number_scholastic
from students.models import Student

_T = 'fees/payments/'

PAYMENT_TYPE_CHOICES = [
    ("school",     "School Fees Payment"),
    ("assessment", "Assessment Fees Payment"),
    ("scholastic", "Scholastic Requirements"),
]

_ALL_KEYS = [
    "payment_part1_done", "payment_part2_done",
    "payment_part3_done", "payment_part4_done",
    "payment_type", "student_id", "student_mini", "class_id",
    "fees_list", "payment_amounts", "selected_fees",
    "selected_fee_ids", "skipped_fees",
]


def _clear_session(request):
    for key in _ALL_KEYS:
        request.session.pop(key, None)
    request.session.modified = True


def _get_old_payments_details(student, payment_type, payment_type_obj):
    """
    payment_type_obj is:
      - a FeesClass instance           (for 'school' and 'assessment')
      - a ScholasticRequirementClass   (for 'scholastic')
    """

    payments_list  = []
    payment_status = {}

    # ── School fees ───────────────────────────────────────────────────────
    if payment_type == "school":
        fee_obj = payment_type_obj.fees

        status   = StudentFeesPaymentsStatus.objects.filter(student=student, school_fees=fee_obj).first()
        payments = FeesPayment.objects.filter(student=student, school_fees=fee_obj)

        if status:
            payment_status = {
                "amount_paid":    round(float(status.amount_paid or 0), 2),
                "amount_balance": round(float(status.amount_balance or 0), 2),
            }
        for p in payments:
            payments_list.append({
                "id":     p.receipt_number,
                "date":   f'{p.payment_date}',
                "amount": round(float(p.amount or 0), 2),
            })

    # ── Assessment fees ───────────────────────────────────────────────────
    elif payment_type == "assessment":
        fee_obj = payment_type_obj.assessment_fee

        status   = StudentFeesPaymentsStatus.objects.filter(student=student, assessment_fees=fee_obj).first()
        payments = FeesPayment.objects.filter(student=student, assessment_fees=fee_obj)

        if status:
            payment_status = {
                "amount_paid":    round(float(status.amount_paid or 0), 2),
                "amount_balance": round(float(status.amount_balance or 0), 2),
            }
        for p in payments:
            payments_list.append({
                "id":     p.receipt_number,
                "date":   f'{p.payment_date}',
                "amount": round(float(p.amount or 0), 2),
            })

    # ── Scholastic requirements ───────────────────────────────────────────
    elif payment_type == "scholastic":
        req_obj = payment_type_obj.requirement

        status   = StudentScholasticRequirementStatus.objects.filter(student=student, requirement=req_obj).first()
        payments = ScholasticRequirementPayment.objects.filter(student=student, requirement=req_obj)

        if status:
            payment_status = {
                "quantity_brought":   status.quantity_brought,
                "amount_paid_ugx":    round(float(status.amount_paid_ugx or 0), 2),
                "amount_balance_ugx": round(float(status.amount_balance_ugx or 0), 2),
                "last_brought_on":    f'{status.last_brought_on}',
                "last_paid_on":       f'{status.last_paid_on}',
            }
        for p in payments:
            payments_list.append({
                "receipt_number":  p.receipt_number,
                "date":            f'{p.payment_date}',
                "brought_item":    p.brought_item,
                "items_brought":   p.items_brought,
                "brought_cash":    p.brought_cash,
                "amount_paid_ugx": round(float(p.amount_paid_ugx or 0), 2),
            })

    return {
        "status":   payment_status,
        "payments": payments_list,
    }





@login_required
def add_payment(request):

    # ── RESET ─────────────────────────────────────────────────────────────
    if request.GET.get("reset") == "1":
        _clear_session(request)
        messages.info(request, "Payment process reset.")
        return redirect("fees:add_payment")

    # ── CANCEL ────────────────────────────────────────────────────────────
    if request.method == "POST" and request.POST.get("action") == "cancel_payment":
        _clear_session(request)
        messages.info(request, "Payment process cancelled.")
        return redirect("fees:add_payment")

    # =========================================================================
    # PART 1 — Student + payment type
    # =========================================================================
    if request.method == "POST" and not request.session.get("payment_part1_done"):
        student_id   = request.POST.get("student", "").strip()
        payment_type = request.POST.get("payment_type", "").strip()
        errors = {}

        if not student_id:
            errors["student"] = "Student is required."
        else:
            try:
                student = (
                    Student.objects.select_related("current_class")
                    .filter(student_id=student_id, is_active=True).first()
                )
                if not student:
                    errors["student"] = "No active student found with that ID."
            except Exception:
                errors["student"] = "Student lookup failed."

        if payment_type not in [t[0] for t in PAYMENT_TYPE_CHOICES]:
            errors["payment_type"] = "Select a valid payment type."

        if errors:
            return render(request, f'{_T}form.html', {
                "errors": errors,
                "payment_type_choices": PAYMENT_TYPE_CHOICES,
                "students": Student.objects.filter(is_active=True),
            })

        current_class = student.current_class
        if not current_class:
            messages.error(request, "This student has no class assigned.")
            return redirect("fees:add_payment")

        student_mini = {
            "id":         student.pk,
            "student_id": student.student_id,
            "name":       student.full_name,
            "class":      current_class.supported_class.name,
        }

        fees_list = []

        if payment_type == "school":
            qs = FeesClass.objects.filter(
                school_class=current_class,
                fees__isnull=False,
                fees__is_active=True,
            ).select_related("fees", "fees__term")
            for fc in qs:
                fee_type = (
                    fc.fees.get_fees_type_display()
                    if fc.fees.fees_type != "other"
                    else (fc.fees.title or fc.fees.get_fees_type_display())
                )

                payment_ = _get_old_payments_details(
                    student=student,
                    payment_type=payment_type,
                    payment_type_obj=fc
                )

                fees_list.append({
                    "id":     fc.fees.pk,
                    "type":   fee_type,
                    "term":   fc.fees.term.name,
                    "amount": float(fc.fees.amount),
                    **payment_
                })



                


        elif payment_type == "assessment":
            qs = FeesClass.objects.filter(
                school_class=current_class,
                assessment_fee__isnull=False,
            ).select_related("assessment_fee", "assessment_fee__assessment", "assessment_fee__term")
            for fc in qs:
                if fc.assessment_fee.amount is not None:
                    payment_ = _get_old_payments_details(
                        student=student,
                        payment_type=payment_type,
                        payment_type_obj=fc
                    )
                    fees_list.append(
                        {
                            "id":     fc.assessment_fee.pk,
                            "name":   fc.assessment_fee.assessment.title,
                            "term":   fc.assessment_fee.term.name,
                            "amount": float(fc.assessment_fee.amount),
                            **payment_
                        }
                        
                    )

        elif payment_type == "scholastic":
            qs = ScholasticRequirementClass.objects.filter(
                school_class=current_class,
                requirement__is_active=True,
            ).select_related("requirement", "requirement__term")

            for rc in qs:
                payment_= _get_old_payments_details(
                    student=student,
                    payment_type=payment_type,
                    payment_type_obj=rc
                )
                fees_list.append({
                        "id":              rc.requirement.pk,
                        "name":            rc.requirement.item_name,
                        "term":            rc.requirement.term.name,
                        "quantity_needed": rc.requirement.quantity,
                        "unit":            rc.requirement.get_unit_display(),
                        "monetary_value":  float(rc.requirement.monetary_value),
                        "unit_price":      float(rc.requirement.unit_price),
                        **payment_
                    })

        request.session["payment_part1_done"] = True
        request.session["payment_type"]       = payment_type
        request.session["student_id"]         = student.pk
        request.session["class_id"]           = current_class.pk
        request.session["student_mini"]       = student_mini
        request.session["fees_list"]          = fees_list
        request.session.modified = True

        messages.success(request, "Step 1 complete.")
        return redirect("fees:add_payment")

    # =========================================================================
    # PART 2 — Select fees / requirements
    # =========================================================================
    if request.method == "POST" and request.POST.get("step") == "part2":
        if not request.session.get("payment_part1_done"):
            messages.error(request, "Complete Step 1 first.")
            return redirect("fees:add_payment")

        selected_ids = [
            request.POST[key] for key in request.POST if key.startswith("fee_")
        ]
        if not selected_ids:
            messages.error(request, "Select at least one item to continue.")
            return redirect("fees:add_payment")

        fees_list     = request.session.get("fees_list", [])
        selected_fees = [f for f in fees_list if str(f.get("id")) in selected_ids]
        skipped_fees  = [f for f in fees_list if str(f.get("id")) not in selected_ids]

        if not selected_fees:
            messages.error(request, "Invalid selection.")
            return redirect("fees:add_payment")

        request.session["payment_part2_done"] = True
        request.session["selected_fee_ids"]   = selected_ids
        request.session["selected_fees"]      = selected_fees
        request.session["skipped_fees"]       = skipped_fees
        request.session.modified = True

        messages.success(request, "Selection saved.")
        return redirect("fees:add_payment")

    # =========================================================================
    # PART 3 — Collect amounts / quantities
    # =========================================================================
    if request.method == "POST" and request.POST.get("step") == "part3":
        if not request.session.get("payment_part2_done"):
            messages.error(request, "Complete Step 2 first.")
            return redirect("fees:add_payment")

        selected_fees   = request.session.get("selected_fees", [])
        payment_type    = request.session.get("payment_type")
        payment_amounts = {}
        errors          = []

        if payment_type == "scholastic":
            for item in selected_fees:
                req_id        = item.get("id")
                item_name     = item.get("name", "")
                unit_price    = float(item.get("unit_price", 0))
                status_data   = item.get("status", {})

                # ── Use status if exists, else use defaults ──────────────────────
                if status_data and status_data.get("amount_balance_ugx") is not None:
                    monetary_value   = float(status_data.get("amount_balance_ugx", 0))
                    qty_already_have = int(status_data.get("quantity_brought", 0))
                    quantity_needed  = max(0, int(item.get("quantity_needed", 0)) - qty_already_have)
                else:
                    monetary_value  = float(item.get("monetary_value", 0))
                    quantity_needed = int(item.get("quantity_needed", 0))

                raw_qty  = request.POST.get(f"qty_brought_{req_id}", "").strip()
                raw_cash = request.POST.get(f"cash_amount_{req_id}", "").strip()

                qty_brought = 0
                cash_amount = 0.0

                if raw_qty:
                    try:
                        qty_brought = int(raw_qty)
                        if qty_brought < 0:
                            errors.append(f"Quantity cannot be negative for {item_name}.")
                            continue
                        qty_brought = min(qty_brought, quantity_needed)  # cap at remaining
                    except (ValueError, TypeError):
                        errors.append(f"Invalid quantity for {item_name}.")
                        continue

                if raw_cash:
                    try:
                        cash_amount = float(raw_cash)
                        if cash_amount < 0:
                            errors.append(f"Cash amount cannot be negative for {item_name}.")
                            continue
                    except (ValueError, TypeError):
                        errors.append(f"Invalid cash amount for {item_name}.")
                        continue

                if qty_brought == 0 and cash_amount == 0:
                    errors.append(f"Enter a quantity or cash amount for {item_name}.")
                    continue

                physical_credit  = qty_brought * unit_price
                remaining_after_items = max(0.0, monetary_value - physical_credit)

                # cap cash to what's still owed after items
                cash_amount = min(cash_amount, remaining_after_items)

                balance = max(0.0, remaining_after_items - cash_amount)
                status  = "Fully Met" if balance == 0 else "Partially Met"

                payment_amounts[str(req_id)] = {
                    "name":            item_name,
                    "term":            item.get("term"),
                    "unit":            item.get("unit"),
                    "quantity_needed": quantity_needed,
                    "qty_brought":     qty_brought,
                    "monetary_value":  monetary_value,
                    "cash_amount":     cash_amount,
                    "balance":         balance,
                    "status":          status,
                }
        else:
            for fee in selected_fees:
                fee_id     = fee.get("id")


                status_data = fee.get("status", {})
                if status_data and status_data.get("amount_balance") is not None:
                    fee_amount = float(status_data.get("amount_balance", 0))
                else:
                    fee_amount = float(fee.get("amount", 0))

                label      = fee.get("name") or fee.get("type") or "Fee"
                raw_amount = request.POST.get(f"amount_{fee_id}", "").strip()

                if not raw_amount:
                    errors.append(f"Amount required for {label}.")
                    continue
                try:
                    amount = float(raw_amount)
                    if amount <= 0:
                        errors.append(f"Amount must be > 0 for {label}.")
                        continue
                except (ValueError, TypeError):
                    errors.append(f"Invalid amount for {label}.")
                    continue

                if amount >= fee_amount:
                    balance = 0.0
                    status  = "Fully Paid"
                else:
                    balance = round(fee_amount - amount, 2)
                    status  = "Partially Paid"

                payment_amounts[str(fee_id)] = {
                    "type":    fee.get("type") or fee.get("name"),
                    "term":    fee.get("term"),
                    "amount":  amount,
                    "balance": balance,
                    "status":  status,
                }

        if errors:
            for err in errors:
                messages.error(request, err)
            return redirect("fees:add_payment")

        request.session["payment_amounts"]    = payment_amounts
        request.session["payment_part3_done"] = True
        request.session.modified = True

        messages.success(request, "Amounts captured.")
        return redirect("fees:add_payment")

    # =========================================================================
    # PART 4 — Verify password, save to DB, clear session
    # =========================================================================
    if request.method == "POST" and request.POST.get("step") == "part4":
        if not request.session.get("payment_part3_done"):
            messages.error(request, "Complete Step 3 first.")
            return redirect("fees:add_payment")

        handler_password = request.POST.get("handler_password", "")
        if not handler_password or not request.user.check_password(handler_password):
            messages.error(request, "Incorrect password. Payment was not recorded.")
            return redirect("fees:add_payment")

        student_id      = request.session.get("student_id")
        payment_type    = request.session.get("payment_type")
        payment_amounts = request.session.get("payment_amounts", {})
        today           = date.today()

        try:
            student       = Student.objects.get(pk=student_id)
            current_class = student.current_class
        except Student.DoesNotExist:
            messages.error(request, "Student not found. Please start again.")
            _clear_session(request)
            return redirect("fees:add_payment")

        try:
            with transaction.atomic():

                # ── Scholastic ────────────────────────────────────────────
                if payment_type == "scholastic":
                    for req_id_str, data in payment_amounts.items():
                        req_obj = SchoolScholasticRequirements.objects.get(pk=int(req_id_str))

                        from django.utils.timezone import now
                        

                        sr_p = ScholasticRequirementPayment.objects.create(
                            student         = student,
                            receipt_number  = generate_receipt_number_scholastic(),
                            requirement     = req_obj,
                            school_class    = current_class,
                            payment_date  = now().date()
                        )



                        status_row, _ = StudentScholasticRequirementStatus.objects.get_or_create(
                            student     = student,
                            requirement = req_obj,
                            defaults={
                                "school_class":       current_class,
                                "quantity_brought":   0,
                                "amount_paid_ugx":    0,
                                "amount_balance_ugx": req_obj.monetary_value,
                                "fully_met":          False,
                            }
                        )

                        qty_brought = int(data.get("qty_brought", 0))
                        cash_amount = float(data.get("cash_amount", 0))

                        status_row.quantity_brought += qty_brought
                        status_row.amount_paid_ugx   = float(status_row.amount_paid_ugx) + cash_amount

                        physical_credit = status_row.quantity_brought * float(req_obj.unit_price)
                        new_balance = max(
                            0.0,
                            float(req_obj.monetary_value)
                            - physical_credit
                            - float(status_row.amount_paid_ugx)
                        )
                        status_row.amount_balance_ugx = new_balance
                        status_row.fully_met          = new_balance <= 0

                        if qty_brought > 0:
                            sr_p.brought_item = True
                            sr_p.items_brought = qty_brought

                            status_row.last_brought_on = today
                        if cash_amount > 0:
                            sr_p.brought_cash =True
                            sr_p.amount_paid_ugx = float(cash_amount)

                            status_row.last_paid_on = today
                        if status_row.fully_met and not status_row.fully_met_on:
                            sr_p.paid_fully =True

                            status_row.fully_met_on = today


                        

                        status_row.recorded_by = request.user
                        sr_p.handled_by = request.user

                        sr_p.save()
                        status_row.save()


                         

                # ── School Fees ───────────────────────────────────────────
                elif payment_type == "school":
                    for fee_id_str, data in payment_amounts.items():
                        fee_obj = SchoolFees.objects.get(pk=int(fee_id_str))
                        amount  = float(data.get("amount", 0))

                        FeesPayment.objects.create(
                            receipt_number = generate_receipt_number(),
                            student        = student,
                            term           = fee_obj.term,
                            school_fees    = fee_obj,
                            school_class   = current_class,
                            amount         = amount,
                            payment_date   = today,
                            handled_by     = request.user,
                        )

                        status_row, _ = StudentFeesPaymentsStatus.objects.get_or_create(
                            student     = student,
                            school_fees = fee_obj,
                            defaults={
                                "payment_type":   "school",
                                "school_class":   current_class,
                                "amount_paid":    0,
                                "amount_balance": fee_obj.amount,
                            }
                        )
                        status_row.amount_paid    = float(status_row.amount_paid) + amount
                        new_balance               = float(status_row.amount_balance) - amount
                        status_row.amount_balance = max(0.0, new_balance)
                        status_row.fully_paid     = status_row.amount_balance <= 0
                        if status_row.fully_paid and not status_row.fully_paid_on:
                            status_row.fully_paid_on = today
                        status_row.save()

                # ── Assessment Fees ───────────────────────────────────────
                elif payment_type == "assessment":
                    for fee_id_str, data in payment_amounts.items():
                        fee_obj = AssessmentFees.objects.get(pk=int(fee_id_str))
                        amount  = float(data.get("amount", 0))

                        FeesPayment.objects.create(
                            receipt_number  = generate_receipt_number(),
                            student         = student,
                            term            = fee_obj.term,
                            assessment_fees = fee_obj,
                            school_class    = current_class,
                            amount          = amount,
                            payment_date    = today,
                            handled_by      = request.user,
                        )

                        status_row, _ = StudentFeesPaymentsStatus.objects.get_or_create(
                            student         = student,
                            assessment_fees = fee_obj,
                            defaults={
                                "payment_type":   "assessment",
                                "school_class":   current_class,
                                "amount_paid":    0,
                                "amount_balance": fee_obj.amount,
                            }
                        )
                        status_row.amount_paid    = float(status_row.amount_paid) + amount
                        new_balance               = float(status_row.amount_balance) - amount
                        status_row.amount_balance = max(0.0, new_balance)
                        status_row.fully_paid     = status_row.amount_balance <= 0
                        if status_row.fully_paid and not status_row.fully_paid_on:
                            status_row.fully_paid_on = today
                        status_row.save()

        except Exception as exc:
            messages.error(request, f"Payment failed: {exc}")
            return redirect("fees:add_payment")

        _clear_session(request)
        messages.success(request, "Payment recorded successfully.")
        return redirect("fees:payment_list")

    # =========================================================================
    # GET — render based on session state
    # =========================================================================
    steps = {
        "payment_part1_done": request.session.get("payment_part1_done", False),
        "payment_part2_done": request.session.get("payment_part2_done", False),
        "payment_part3_done": request.session.get("payment_part3_done", False),
        "payment_part4_done": request.session.get("payment_part4_done", False),
    }

    context = {
        "payment_type_choices": PAYMENT_TYPE_CHOICES,
        "students":             Student.objects.filter(is_active=True),
        "student_mini":         request.session.get("student_mini"),
        "fees_list":            request.session.get("fees_list", []),
        "selected_fees":        request.session.get("selected_fees", []),
        "payment_amounts":      request.session.get("payment_amounts", {}),
        "payment_type":         request.session.get("payment_type"),
        "today_str":            date.today().strftime("%d %b %Y"),
        **steps,
    }

    return render(request, f'{_T}form.html', context)








# def payment_add(request):
#     """
#     PART 1 ONLY (Wizard Step 1)
#     - Choose payment type (School Fees / Assessment Fees)
#     - Enter Student ID
#     - Validate → load student + current class + available fees
#     - Store everything in session
#     """
#     lookups = _get_form_lookups()

#     if request.method == 'GET':
#         # Always show clean Part 1 form on GET
#         # (we keep session data if user already completed Part 1)
#         context = {
#             'form_title': 'Record Payment — Step 1 of 2',
#             'action': 'add',
#             'step': 1,
#             'payment_form_data': request.session.get('payment_form_data', {}),
#             'is_part1_done': request.session.get('is_part1_done', False),
#             **lookups,
#         }
#         return render(request, f'{_T}form.html', context)

#     # ── POST (Part 1) ───────────────────────────────────────────────────────
#     payment_type = (request.POST.get('payment_type') or '').strip()
#     student_id_input = (request.POST.get('student_id') or '').strip().upper()

#     errors: dict = {}
#     post_data = request.POST  # for re-rendering errors

#     # 1. Validate payment type
#     if payment_type not in ['school_fees', 'assessment_fees']:
#         errors['payment_type'] = 'Please select School Fees or Assessment Fees.'

#     # 2. Validate student ID
#     if not student_id_input:
#         errors['student_id'] = 'Student ID is required.'
#     else:
#         try:
#             student = Student.objects.get(
#                 student_id=student_id_input,
#                 is_active=True
#             )
#         except Student.DoesNotExist:
#             errors['student_id'] = f'No active student found with ID "{student_id_input}".'
#         except Student.MultipleObjectsReturned:
#             errors['student_id'] = 'Multiple students found with this ID. Please contact admin.'

#     if errors:
#         for msg in errors.values():
#             messages.error(request, msg)
#         return render(request, f'{_T}form.html', {
#             'form_title': 'Record Payment — Step 1 of 2',
#             'action': 'add',
#             'step': 1,
#             'post': post_data,
#             'errors': errors,
#             'payment_form_data': request.session.get('payment_form_data', {}),
#             'is_part1_done': False,
#             **lookups,
#         })

#     # ── Success: build data and save to session ─────────────────────────────
#     current_class = student.current_class
#     mini_info = {
#         'pk': student.pk,
#         'student_id': student.student_id,
#         'full_name': student.full_name,
#         'current_class_pk': current_class.pk if current_class else None,
#         'current_class_name': current_class.name if current_class else 'No class assigned',
#     }

#     # Current term (used to filter fees)
#     current_term = Term.objects.filter(is_current=True).first()

#     # Get available fees based on payment type + class context
#     if payment_type == 'school_fees':
#         qs = SchoolFees.objects.filter(is_active=True)
#         if current_term:
#             qs = qs.filter(term=current_term)
#         available_fees = qs.order_by('fees_type', 'title')
#     else:  # assessment_fees
#         qs = AssessmentFees.objects.all()
#         if current_term:
#             qs = qs.filter(term=current_term)
#         available_fees = qs.order_by('assessment__title' if hasattr(AssessmentFees, 'assessment') else 'pk')

#     # Prepare serializable list for session
#     fees_data = []
#     for fee in available_fees:
#         if payment_type == 'school_fees':
#             display = f"{fee.get_fees_type_display()} — {fee.title or ''} (UGX {fee.amount:,.0f})"
#             amount = float(fee.amount)
#         else:
#             display = f"Assessment Fee — {getattr(fee, 'assessment', fee)} (UGX {getattr(fee, 'amount', 0):,.0f})"
#             amount = float(getattr(fee, 'amount', 0))

#         fees_data.append({
#             'pk': fee.pk,
#             'display': display,
#             'amount': amount,
#             'fee_type': payment_type,
#         })

#     # Save to session
#     request.session['payment_form_data'] = {
#         'payment_type': payment_type,
#         'payment_type_label': 'School Fees' if payment_type == 'school_fees' else 'Assessment Fees',
#         'student': mini_info,
#         'available_fees': fees_data,
#         'current_term_pk': current_term.pk if current_term else None,
#     }
#     request.session['is_part1_done'] = True
#     request.session.modified = True

#     messages.success(
#         request,
#         f"✅ Student {student.full_name} ({student.student_id}) validated. "
#         f"Loaded {len(fees_data)} fee item(s)."
#     )

#     # Re-render same template (now showing Part 1 summary)
#     context = {
#         'form_title': 'Record Payment — Step 1 Complete',
#         'action': 'add',
#         'step': 1,
#         'payment_form_data': request.session['payment_form_data'],
#         'is_part1_done': True,
#         **lookups,
#     }
#     return render(request, f'{_T}form.html', context)

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

from decimal import Decimal
from django.db.models import Q, Sum
from fees.models import StudentFeesPaymentsStatus


@login_required
def payment_detail(request, pk):
    """
    Production-ready single-payment receipt detail view.
    - Handles BOTH SchoolFees and AssessmentFees uniformly
    - Fixes amount_paid → amount (model field)
    - Computes coverage, student totals, outstanding, term summary
    - Robust prev/next navigation (chronological across all payments)
    - Minimal queries, no N+1, clean fallback logic
    - Matches exactly what the add_payment flow creates
    """
    payment = get_object_or_404(
        FeesPayment.objects.select_related(
            'student',
            'term',
            'school_class',
            'school_fees',
            'assessment_fees',
            'assessment_fees__assessment',
        ),
        pk=pk,
    )

    # ── Fee details (school or assessment) ─────────────────────────────────
    if payment.school_fees:
        fee = payment.school_fees
        fee_type_label = fee.title or fee.get_fees_type_display()
        fee_amount = fee.amount
    elif payment.assessment_fees:
        fee = payment.assessment_fees
        fee_type_label = (
            f"{fee.assessment.title} (Assessment Fee)"
            if fee.assessment else "Assessment Fee"
        )
        fee_amount = fee.amount or Decimal('0')
    else:
        # Should never happen (model clean() enforces exactly one)
        fee = None
        fee_type_label = "Unknown Fee"
        fee_amount = Decimal('0')

    # ── Coverage % of THIS specific payment ───────────────────────────────
    coverage = (
        round((float(payment.amount) / float(fee_amount)) * 100)
        if fee_amount and fee_amount > 0
        else 0
    )

    # ── Student’s running status for this exact fee line ───────────────────
    if payment.school_fees:
        status = StudentFeesPaymentsStatus.objects.filter(
            student=payment.student,
            school_fees=payment.school_fees,
        ).first()
    else:
        status = StudentFeesPaymentsStatus.objects.filter(
            student=payment.student,
            assessment_fees=payment.assessment_fees,
        ).first()

    if status:
        student_total_for_fee = status.amount_paid
        is_cleared = status.fully_paid
        outstanding = status.amount_balance if not is_cleared else Decimal('0')
    else:
        # Rare fallback (first payment before status row was created)
        student_total_for_fee = payment.amount
        is_cleared = (fee_amount and payment.amount >= fee_amount)
        outstanding = max(Decimal('0'), (fee_amount or Decimal('0')) - payment.amount)

    # ── Other payments this term (exclude current) ─────────────────────────
    student_term_payments = FeesPayment.objects.filter(
        student=payment.student,
        term=payment.term,
    ).exclude(pk=payment.pk).select_related(
        'school_fees',
        'assessment_fees',
        'assessment_fees__assessment',
    ).order_by('payment_date', 'created_at')

    # ── Full term total (including current payment) ────────────────────────
    student_term_total = FeesPayment.objects.filter(
        student=payment.student,
        term=payment.term,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # ── Prev / Next navigation (chronological) ─────────────────────────────
    prev_payment = FeesPayment.objects.filter(
        Q(payment_date__lt=payment.payment_date) |
        Q(payment_date=payment.payment_date, pk__lt=payment.pk)
    ).only('pk', 'receipt_number').order_by('payment_date', 'pk').last()

    next_payment = FeesPayment.objects.filter(
        Q(payment_date__gt=payment.payment_date) |
        Q(payment_date=payment.payment_date, pk__gt=payment.pk)
    ).only('pk', 'receipt_number').order_by('payment_date', 'pk').first()

    context = {
        'payment': payment,
        'page_title': f'Receipt — {payment.receipt_number}',
        'fee_type_label': fee_type_label,
        'fee': fee,                    # used in template for {% if fee %} and fee.amount
        'fee_amount': fee_amount,
        'coverage': coverage,
        'is_cleared': is_cleared,
        'outstanding': outstanding,
        'student_total_for_fee': student_total_for_fee,
        'student_term_payments': student_term_payments,
        'student_term_total': student_term_total,
        'prev_payment': prev_payment,
        'next_payment': next_payment,
    }

    return render(request, f'{_T}detail.html', context)






