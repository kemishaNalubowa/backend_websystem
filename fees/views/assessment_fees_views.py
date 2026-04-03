# fees/views/assessment_fees_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All AssessmentFees views.
#
# Views:
#   assessment_fees_list          — list with full stats and filters
#   assessment_fees_add           — add a single assessment record
#   assessment_fees_edit          — edit (discount, notes, total_required)
#   assessment_fees_delete        — confirm + perform deletion
#   assessment_fees_detail        — full single record page
#   assessment_fees_recalculate   — POST: re-sync total_paid from payments
#   assessment_fees_bulk_generate — POST: generate for all students in a class+term
#
# Rules:
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via assessment_fees_utils
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

from academics.models import SchoolClass, Term
from fees.models import AssessmentFees
from fees.utils.assessment_fees_utils import (
    bulk_generate_for_class,
    get_assessment_fees_detail_stats,
    get_assessment_fees_list_stats,
    recalculate_from_payments,
    validate_and_parse_assessment_fees,
)
from students.models import Student

_T = 'fees/assessment_fees/'

_CLASS_LEVEL_CHOICES = [
    ('baby', 'Baby Class'), ('middle', 'Middle Class'), ('top', 'Top Class'),
    ('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4'),
    ('p5', 'P5'), ('p6', 'P6'), ('p7', 'P7'),
]


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_form_lookups() -> dict:
    """Common querysets every assessment fees form template needs."""
    return {
        'all_terms':    Term.objects.all().order_by('-start_date'),
        'all_students': Student.objects.filter(
                            is_active=True
                        ).select_related('current_class').order_by(
                            'last_name', 'first_name'
                        ),
    }


def _apply_to_instance(instance: AssessmentFees, cleaned: dict) -> None:
    """Write cleaned scalar and FK fields onto an AssessmentFees instance."""
    scalar_fields = (
        'total_required', 'total_paid', 'discount_amount',
        'discount_reason', 'notes',
    )
    for f in scalar_fields:
        if f in cleaned:
            setattr(instance, f, cleaned[f])

    if 'student_id' in cleaned:
        instance.student_id = cleaned['student_id']
    if 'term_id' in cleaned:
        instance.term_id = cleaned['term_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. ASSESSMENT FEES LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_list(request):
    """
    All assessment fee statements with statistics and filters.

    Stats cards:
        total, cleared, outstanding, cleared %, discounted,
        total required / paid / balance / discount (UGX),
        overall collection rate,
        by-term and by-class breakdowns,
        top 10 defaulters,
        current-term summary.

    Filters (GET — all stackable):
        ?q=           student name / student ID search
        ?term=<id>    filter by term FK
        ?class=       filter by class level (e.g. p6)
        ?section=     nursery | primary
        ?cleared=1|0  cleared or outstanding
        ?discount=1   has a discount
    """
    qs = AssessmentFees.objects.select_related(
        'student', 'student__current_class', 'term', 'generated_by'
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    search          = request.GET.get('q', '').strip()
    term_filter     = request.GET.get('term', '').strip()
    class_filter    = request.GET.get('class', '').strip()
    section_filter  = request.GET.get('section', '').strip()
    cleared_filter  = request.GET.get('cleared', '').strip()
    discount_filter = request.GET.get('discount', '').strip()

    if search:
        qs = qs.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search)  |
            Q(student__student_id__icontains=search)
        )

    if term_filter:
        qs = qs.filter(term__pk=term_filter)

    if class_filter:
        qs = qs.filter(student__current_class__level=class_filter)

    if section_filter:
        qs = qs.filter(student__current_class__section=section_filter)

    if cleared_filter == '1':
        qs = qs.filter(is_cleared=True)
    elif cleared_filter == '0':
        qs = qs.filter(is_cleared=False)

    if discount_filter == '1':
        qs = qs.filter(discount_amount__gt=0)

    qs = qs.order_by('-term__start_date', 'term__name', '-balance')

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    stats = get_assessment_fees_list_stats()

    context = {
        'assessments':      page_obj.object_list,
        'page_obj':         page_obj,
        # active filters
        'search':           search,
        'term_filter':      term_filter,
        'class_filter':     class_filter,
        'section_filter':   section_filter,
        'cleared_filter':   cleared_filter,
        'discount_filter':  discount_filter,
        # choice lists
        'class_level_choices': _CLASS_LEVEL_CHOICES,
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD ASSESSMENT FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_add(request):
    """
    Add a single assessment fees record for one student.

    GET  — blank form; current term pre-selected if active.
           total_required is informational — admin should enter the
           sum of compulsory fees for that student's class + term.
    POST — validate; save (model.save() auto-computes balance + is_cleared).

    For adding records in bulk for a whole class, use assessment_fees_bulk_generate.
    """
    lookups = _get_form_lookups()

    if request.method == 'GET':
        current_term = Term.objects.filter(is_current=True).first()
        return render(request, f'{_T}form.html', {
            'form_title':   'Add Fees Assessment',
            'action':       'add',
            'post':         {},
            'errors':       {},
            'current_term': current_term,
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────

    






    cleaned, errors = validate_and_parse_assessment_fees(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': 'Add Fees Assessment',
            'action':     'add',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            af = AssessmentFees()
            _apply_to_instance(af, cleaned)
            af.generated_by = request.user
            af.save()   # auto-computes balance + is_cleared
    except Exception as exc:
        messages.error(request, f'Could not save fees assessment: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title': 'Add Fees Assessment',
            'action':     'add',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Fees assessment created for {af.student} — {af.term}. '
        f'Balance: UGX {af.balance:,.0f}.'
    )
    return redirect('fees:assessment_fees_detail', pk=af.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT ASSESSMENT FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_edit(request, pk):
    """
    Edit an existing assessment fees record.

    The main editable fields are:
        - total_required   (in case fee structure changed after generation)
        - discount_amount  (staff child, scholarship, waiver)
        - discount_reason  (required when discount > 0)
        - notes

    total_paid is also editable here but should normally be synced
    via assessment_fees_recalculate instead of being typed manually.

    model.save() auto-recomputes balance and is_cleared after any edit.
    """
    af      = get_object_or_404(
        AssessmentFees.objects.select_related('student', 'term', 'generated_by'),
        pk=pk
    )
    lookups = _get_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'assessment': af,
            'form_title': f'Edit Assessment — {af.student} | {af.term}',
            'action':     'edit',
            'post':       {},
            'errors':     {},
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_assessment_fees(request.POST, instance=af)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'assessment': af,
            'form_title': f'Edit Assessment — {af.student} | {af.term}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            _apply_to_instance(af, cleaned)
            af.save()   # auto-recomputes balance + is_cleared
    except Exception as exc:
        messages.error(request, f'Could not update fees assessment: {exc}')
        return render(request, f'{_T}form.html', {
            'assessment': af,
            'form_title': f'Edit Assessment — {af.student} | {af.term}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    status = 'CLEARED' if af.is_cleared else f'Balance UGX {af.balance:,.0f}'
    messages.success(
        request,
        f'Assessment for {af.student} | {af.term} updated. {status}.'
    )
    return redirect('fees:assessment_fees_detail', pk=af.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE ASSESSMENT FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_delete(request, pk):
    """
    Delete an assessment fees record.

    GET  — confirmation page showing the record summary.
    POST — perform deletion.

    Note: deleting an assessment does NOT delete the underlying
    FeesPayment records — those remain on file. A warning is shown.
    """
    af = get_object_or_404(
        AssessmentFees.objects.select_related('student', 'term'),
        pk=pk
    )

    if request.method == 'GET':
        from fees.models import FeesPayment
        payment_count = FeesPayment.objects.filter(
            student=af.student, term=af.term
        ).count()
        return render(request, f'{_T}delete_confirm.html', {
            'assessment':   af,
            'payment_count': payment_count,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    label = f'{af.student} | {af.term}'
    try:
        af.delete()
        messages.success(
            request,
            f'Fees assessment for "{label}" has been deleted. '
            f'Payment records are preserved.'
        )
    except Exception as exc:
        messages.error(request, f'Could not delete assessment: {exc}')
        return redirect('fees:assessment_fees_detail', pk=pk)

    return redirect('fees:assessment_fees_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. ASSESSMENT FEES DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_detail(request, pk):
    """
    Full single assessment fees detail page.

    Displays:
        - Student details, class, term
        - Total required / paid / balance / discount (UGX)
        - Cleared badge or outstanding balance
        - Discount details (amount + reason) if applicable
        - Per-fee-type breakdown: required vs paid vs balance for each fee item
        - All actual payment records for this student + term
        - Payment breakdown by fee type
        - Class peers stats (cleared count, average balance)
        - Prev / Next assessments for the same student (other terms)
        - Notes
    """
    af = get_object_or_404(
        AssessmentFees.objects.select_related(
            'student', 'student__current_class', 'term', 'generated_by'
        ),
        pk=pk
    )
    stats = get_assessment_fees_detail_stats(af)

    context = {
        'assessment': af,
        'page_title': f'{af.student} — Fees Assessment | {af.term}',
        **stats,
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. RECALCULATE FROM PAYMENTS  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_recalculate(request, pk):
    """
    POST-only: re-sync total_paid from actual FeesPayment records.

    Use this whenever payments are added/edited/deleted outside the
    normal flow, or to correct a drifted total_paid value.

    Updates: total_paid, last_payment_date, balance, is_cleared.
    Does NOT touch total_required or discount_amount.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('fees:assessment_fees_list')

    af = get_object_or_404(
        AssessmentFees.objects.select_related('student', 'term'), pk=pk
    )

    try:
        with transaction.atomic():
            result = recalculate_from_payments(af)
    except Exception as exc:
        messages.error(request, f'Recalculation failed: {exc}')
        return redirect('fees:assessment_fees_detail', pk=af.pk)

    if result['changed']:
        messages.success(
            request,
            f'Recalculated for {af.student} | {af.term}. '
            f'Total paid updated from UGX {result["old_paid"]:,.0f} '
            f'to UGX {result["new_paid"]:,.0f}. '
            f'New balance: UGX {af.balance:,.0f}.'
        )
    else:
        messages.info(
            request,
            f'No change — total paid is already correct '
            f'(UGX {result["new_paid"]:,.0f}).'
        )

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('fees:assessment_fees_detail', pk=af.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. BULK GENERATE  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_bulk_generate(request):
    """
    POST-only: generate AssessmentFees records for ALL active students
    in a selected class + term combination.

    POST params:
        school_class  — SchoolClass pk
        term          — Term pk
        overwrite     — '1' to update existing records, '0' to skip them

    total_required per student = sum of all active compulsory SchoolFees
    for that class + term.

    total_paid is synced from existing FeesPayment records.

    Redirects to assessment_fees_list filtered by the selected term.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('fees:assessment_fees_list')

    # ── Validate inputs ───────────────────────────────────────────────────────
    errors = {}

    class_id = (request.POST.get('school_class') or '').strip()
    term_id  = (request.POST.get('term') or '').strip()

    if not class_id:
        errors['school_class'] = 'Class is required.'
    if not term_id:
        errors['term'] = 'Term is required.'

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return redirect('fees:assessment_fees_list')

    try:
        school_class = SchoolClass.objects.get(pk=int(class_id))
        term         = Term.objects.get(pk=int(term_id))
    except (SchoolClass.DoesNotExist, Term.DoesNotExist, ValueError):
        messages.error(request, 'Invalid class or term selected.')
        return redirect('fees:assessment_fees_list')

    overwrite = request.POST.get('overwrite', '0') == '1'

    # ── Run bulk generation ───────────────────────────────────────────────────
    try:
        with transaction.atomic():
            result = bulk_generate_for_class(
                school_class=school_class,
                term=term,
                generated_by=request.user,
                overwrite=overwrite,
            )
    except Exception as exc:
        messages.error(request, f'Bulk generation failed: {exc}')
        return redirect('fees:assessment_fees_list')

    # ── Feedback message ──────────────────────────────────────────────────────
    parts = []
    if result['created']:
        parts.append(f'{result["created"]} created')
    if result['updated']:
        parts.append(f'{result["updated"]} updated')
    if result['skipped']:
        parts.append(f'{result["skipped"]} skipped (already exist)')

    summary = ', '.join(parts) if parts else 'No records processed'
    messages.success(
        request,
        f'Bulk generation for {school_class} | {term} complete — {summary}.'
    )

    if result['errors']:
        for err in result['errors']:
            messages.warning(request, f'Error: {err}')

    from django.urls import reverse
    return redirect(f"{reverse('fees:assessment_fees_list')}?term={term.pk}")
