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
