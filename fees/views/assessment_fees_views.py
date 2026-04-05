# fees/views/assessment_fees_views.py

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
from assessments.models import Assessment

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
        'assessments':  Assessment.objects.filter(
                            term__is_current=True
                        ).select_related('term').order_by('title'),
    }


def _apply_to_instance(instance: AssessmentFees, cleaned: dict) -> None:
    """Write cleaned scalar and FK fields onto an AssessmentFees instance."""
    # Scalar fields that actually exist on the current AssessmentFees model
    scalar_fields = ('amount', 'due_date')
    for f in scalar_fields:
        if f in cleaned:
            setattr(instance, f, cleaned[f])

    if 'assessment_id' in cleaned:
        instance.assessment_id = cleaned['assessment_id']
    if 'term_id' in cleaned:
        instance.term_id = cleaned['term_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. ASSESSMENT FEES LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_list(request):
    qs = AssessmentFees.objects.select_related('term', 'generated_by', 'assessment')

    term_filter = request.GET.get('term', '').strip()
    search      = request.GET.get('q', '').strip()

    if term_filter:
        qs = qs.filter(term__pk=term_filter)

    qs = qs.order_by('-term__start_date', 'term__name')

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    stats = get_assessment_fees_list_stats()

    return render(request, f'{_T}list.html', {
        'assessments':         page_obj.object_list,
        'page_obj':            page_obj,
        'search':              search,
        'term_filter':         term_filter,
        'class_level_choices': _CLASS_LEVEL_CHOICES,
        **stats,
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD ASSESSMENT FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_add(request):
    """
    Add a single assessment fees record.
    GET  — blank form; current term pre-selected.
    POST — validate; save; redirect to detail.
    """
    lookups      = _get_form_lookups()
    current_term = Term.objects.filter(is_current=True).first()

    if request.method == 'GET':
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
            'form_title':   'Add Fees Assessment',
            'action':       'add',
            'post':         request.POST,
            'errors':       errors,
            'current_term': current_term,
            **lookups,
        })

    try:
        with transaction.atomic():
            af = AssessmentFees()
            _apply_to_instance(af, cleaned)
            af.generated_by = request.user
            af.save()
    except Exception as exc:
        messages.error(request, f'Could not save fees assessment: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title':   'Add Fees Assessment',
            'action':       'add',
            'post':         request.POST,
            'errors':       {},
            'current_term': current_term,
            **lookups,
        })

    messages.success(
        request,
        f'Fees assessment created for "{af.assessment.title}" — {af.term}.'
    )
    return redirect('fees:assessment_fees_detail', pk=af.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT ASSESSMENT FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_edit(request, pk):
    """
    Edit an existing assessment fees record.
    Editable fields: assessment, term, amount, due_date.
    GET  — form pre-filled with current values.
    POST — validate; save; redirect to detail.
    """
    af      = get_object_or_404(
        AssessmentFees.objects.select_related('assessment', 'term', 'generated_by'),
        pk=pk
    )
    lookups      = _get_form_lookups()
    current_term = Term.objects.filter(is_current=True).first()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'fee':          af,                   # instance exposed as 'fee' so template logic is consistent
            'form_title':   f'Edit Assessment — {af.assessment.title} | {af.term}',
            'action':       'edit',
            'post':         {},
            'errors':       {},
            'current_term': current_term,
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_assessment_fees(request.POST, instance=af)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'fee':          af,
            'form_title':   f'Edit Assessment — {af.assessment.title} | {af.term}',
            'action':       'edit',
            'post':         request.POST,
            'errors':       errors,
            'current_term': current_term,
            **lookups,
        })

    try:
        with transaction.atomic():
            _apply_to_instance(af, cleaned)
            af.save()
    except Exception as exc:
        messages.error(request, f'Could not update fees assessment: {exc}')
        return render(request, f'{_T}form.html', {
            'fee':          af,
            'form_title':   f'Edit Assessment — {af.assessment.title} | {af.term}',
            'action':       'edit',
            'post':         request.POST,
            'errors':       {},
            'current_term': current_term,
            **lookups,
        })

    messages.success(
        request,
        f'Assessment "{af.assessment.title}" | {af.term} updated successfully.'
    )
    return redirect('fees:assessment_fees_detail', pk=af.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE ASSESSMENT FEES
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_delete(request, pk):
    af = get_object_or_404(
        AssessmentFees.objects.select_related('assessment', 'term'),
        pk=pk
    )

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {'assessment': af})

    label = f'{af.assessment.title} | {af.term}'
    try:
        af.delete()
        messages.success(request, f'Fees assessment for "{label}" has been deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete assessment: {exc}')
        return redirect('fees:assessment_fees_detail', pk=pk)

    return redirect('fees:assessment_fees_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_detail(request, pk):
    af = get_object_or_404(
        AssessmentFees.objects.select_related(
            'assessment', 'term', 'generated_by'
        ),
        pk=pk
    )
    stats = get_assessment_fees_detail_stats(af)

    return render(request, f'{_T}detail.html', {
        'assessment': af,
        'page_title': f'{af.assessment.title} — Fees Assessment | {af.term}',
        **stats,
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  6. RECALCULATE (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_recalculate(request, pk):
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('fees:assessment_fees_list')

    af = get_object_or_404(
        AssessmentFees.objects.select_related('assessment', 'term'), pk=pk
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
            f'Recalculated for {af.assessment.title} | {af.term}. '
            f'Total paid updated from UGX {result["old_paid"]:,.0f} '
            f'to UGX {result["new_paid"]:,.0f}.'
        )
    else:
        messages.info(request, f'No change — already correct (UGX {result["new_paid"]:,.0f}).')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    return redirect(next_url if next_url else 'fees:assessment_fees_detail', pk=af.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. BULK GENERATE (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def assessment_fees_bulk_generate(request):
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('fees:assessment_fees_list')

    errors   = {}
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

    parts = []
    if result['created']:  parts.append(f'{result["created"]} created')
    if result['updated']:  parts.append(f'{result["updated"]} updated')
    if result['skipped']:  parts.append(f'{result["skipped"]} skipped')

    messages.success(
        request,
        f'Bulk generation for {school_class} | {term} — '
        f'{", ".join(parts) if parts else "No records processed"}.'
    )

    for err in result.get('errors', []):
        messages.warning(request, f'Error: {err}')

    from django.urls import reverse
    return redirect(f"{reverse('fees:assessment_fees_list')}?term={term.pk}")
