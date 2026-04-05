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
from fees.models import FeesPayment, SchoolFees,AssessmentFees
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


PAYMENT_TYPE_CHOICES = [
    ("assessment", "Assessment Fees Payment"),
    ("school", "School Fees Payment"),
]

@login_required
def add_payment(request):
    """
    Multi-step Add Payment View — Part 1 implemented.

    Session keys created:
        payment_part1_done
        payment_type
        student_id
        student_mini
        class_id
        fees_list
    """

    # ------------------------------------------------------------------
    # Reset flow (optional safety)
    # ------------------------------------------------------------------
    if request.GET.get("reset") == "1":
        for key in [
            "payment_part1_done",
            "payment_type",
            "student_id",
            "student_mini",
            "class_id",
            "fees_list",
        ]:
            request.session.pop(key, None)

        messages.info(request, "Payment process reset.")
        return redirect("fees:add_payment")

    # ------------------------------------------------------------------
    # POST — PART 1 SUBMISSION
    # ------------------------------------------------------------------
    if request.method == "POST" and not request.session.get(
        "payment_part1_done"
    ):

        student_id = request.POST.get("student")
        payment_type = request.POST.get("payment_type")

        errors = {}

        # ------------------------------
        # Validate student
        # ------------------------------
        if not student_id:
            errors["student"] = "Student is required."
        else:
            try:
                student = (
                    Student.objects.select_related("current_class")
                    .filter(pk=student_id, is_active=True)
                    .first()
                )

                if not student:
                    errors["student"] = "Invalid student selected."

            except Exception:
                errors["student"] = "Student lookup failed."

        # ------------------------------
        # Validate payment type
        # ------------------------------
        if payment_type not in ["assessment", "school"]:
            errors["payment_type"] = "Select a valid payment type."

        # ------------------------------
        # Stop if errors
        # ------------------------------
        if errors:
            context = {
                "errors": errors,
                "payment_type_choices": PAYMENT_TYPE_CHOICES,
                "students": Student.objects.filter(is_active=True),
            }
            return render(request, f'{_T}form.html', context)

        # ------------------------------------------------------------------
        # Fetch student mini info
        # ------------------------------------------------------------------
        current_class = student.current_class

        if not current_class:
            messages.error(request, "Student has no current class assigned.")
            return redirect("fees:add_payment")

        student_mini = {
            "id": student.pk,
            "student_id": student.student_id,
            "name": student.full_name,
            "class": current_class.display_name,
        }

        # ------------------------------------------------------------------
        # Fetch fees based on payment type
        # ------------------------------------------------------------------
        fees_list = []

        # ==============================
        # ASSESSMENT FEES
        # ==============================
        if payment_type == "assessment":

            assessments = (
                AssessmentFees.objects.filter(
                    school_class=current_class,
                    is_active=True,
                )
                .order_by("name")
            )

            fees_list = [
                {
                    "id": a.pk,
                    "name": a.name,
                    "amount": float(a.amount),
                }
                for a in assessments
            ]

        # ==============================
        # SCHOOL FEES
        # ==============================
        elif payment_type == "school":

            school_fees = (
                SchoolFees.objects.filter(
                    school_class=current_class,
                    is_active=True,
                )
                .select_related("term")
                .order_by("term__start_date")
            )

            fees_list = [
                {
                    "id": f.pk,
                    "type": f.get_fees_type_display(),
                    "term": f.term.name,
                    "amount": float(f.amount),
                }
                for f in school_fees
            ]

        # ------------------------------------------------------------------
        # Store everything in session
        # ------------------------------------------------------------------
        request.session["payment_part1_done"] = True
        request.session["payment_type"] = payment_type
        request.session["student_id"] = student.pk
        request.session["class_id"] = current_class.pk
        request.session["student_mini"] = student_mini
        request.session["fees_list"] = fees_list

        request.session.modified = True

        messages.success(request, "Step 1 completed successfully.")

        # Redirect to same page (multi-step pattern)
        return redirect("fees:add_payment")

    # ------------------------------------------------------------------
    # GET — Render page based on session flag
    # ------------------------------------------------------------------
    context = {
        "payment_part1_done": request.session.get(
            "payment_part1_done", False
        ),
        "payment_type_choices": PAYMENT_TYPE_CHOICES,
        "students": Student.objects.filter(is_active=True),
        "student_mini": request.session.get("student_mini"),
        "fees_list": request.session.get("fees_list", []),
        "payment_type": request.session.get("payment_type"),
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
