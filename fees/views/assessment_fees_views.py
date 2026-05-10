# fees/views/assessment_fees_views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import SchoolClass, Term
from fees.models import AssessmentFees
from fees.utils.assessment_fees_utils import (
    validate_and_parse_assessment_fees,
)
from assessments.models import Assessment
from permissions.decorators import has_permission

_T = 'fees/assessment_fees/'


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_form_lookups() -> dict:
    """Common querysets every assessment fees form template needs."""
    return {
        'all_terms':   Term.objects.all().order_by('-start_date'),
        'assessments': Assessment.objects.select_related('term').order_by('-term__start_date', 'title'),
    }


def _apply_to_instance(instance: AssessmentFees, cleaned: dict) -> None:
    """Write cleaned scalar and FK fields onto an AssessmentFees instance."""
    for f in ('amount', 'due_date'):
        if f in cleaned:
            setattr(instance, f, cleaned[f])
    if 'assessment_id' in cleaned:
        instance.assessment_id = cleaned['assessment_id']
    if 'term_id' in cleaned:
        instance.term_id = cleaned['term_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('assessment_fee', action='read')
def assessment_fees_list(request):
    qs = AssessmentFees.objects.select_related('term', 'generated_by', 'assessment__term')

    term_filter = request.GET.get('term', '').strip()
    search      = request.GET.get('q', '').strip()

    if term_filter:
        qs = qs.filter(term__pk=term_filter)
    if search:
        qs = qs.filter(assessment__title__icontains=search)

    qs = qs.order_by('-term__start_date', 'assessment__title')

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    terms        = Term.objects.all().order_by('-start_date')
    current_term = Term.objects.filter(is_active=True).first()
    school_classes = SchoolClass.objects.all().order_by('name')

    return render(request, f'{_T}list.html', {
        'fee_assessments': page_obj.object_list,
        'page_obj':        page_obj,
        'search':          search,
        'term_filter':     term_filter,
        'terms':           terms,
        'current_term':    current_term,
        'school_classes':  school_classes,
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('assessment_fee', action='create')
def assessment_fees_add(request):
    lookups      = _get_form_lookups()
    current_term = Term.objects.filter(is_active=True).first()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'form_title':   'Add Fees Assessment',
            'action':       'add',
            'post':         {},
            'errors':       {},
            'current_term': current_term,
            **lookups,
        })

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
#  3. EDIT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('assessment_fee', action='edit')
def assessment_fees_edit(request, pk):
    af = get_object_or_404(
        AssessmentFees.objects.select_related('assessment', 'term', 'generated_by'),
        pk=pk
    )
    lookups      = _get_form_lookups()
    current_term = Term.objects.filter(is_active=True).first()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'fee':          af,
            'form_title':   f'Edit — {af.assessment.title} | {af.term}',
            'action':       'edit',
            'post':         {},
            'errors':       {},
            'current_term': current_term,
            **lookups,
        })

    cleaned, errors = validate_and_parse_assessment_fees(request.POST, instance=af)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'fee':          af,
            'form_title':   f'Edit — {af.assessment.title} | {af.term}',
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
            'form_title':   f'Edit — {af.assessment.title} | {af.term}',
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
#  4. DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('assessment_fee', action='delete')
def assessment_fees_delete(request, pk):
    af = get_object_or_404(
        AssessmentFees.objects.select_related('assessment', 'term'),
        pk=pk
    )

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {'fee': af})

    label = f'{af.assessment.title} | {af.term}'
    try:
        af.delete()
        messages.success(request, f'Fees assessment for "{label}" has been deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete: {exc}')
        return redirect('fees:assessment_fees_detail', pk=pk)

    return redirect('fees:assessment_fees_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission('assessment_fee', action='read')
def assessment_fees_detail(request, pk):
    af = get_object_or_404(
        AssessmentFees.objects.select_related(
            'assessment__term', 'term', 'generated_by'
        ),
        pk=pk
    )
    return render(request, f'{_T}detail.html', {
        'fee':        af,
        'page_title': f'{af.assessment.title} — Fee Assessment | {af.term}',
    })


