# school/views/image_views.py
# ─────────────────────────────────────────────────────────────────────────────
# DynamicImage management — allows admins to upload/manage images
# for the frontend (hero banners, team photos, event images, etc.)
# ─────────────────────────────────────────────────────────────────────────────

import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.conf import settings

from school.models import DynamicImage

_T = 'school/images/'

IMAGE_CATEGORIES = [
    ('hero',  'Hero / Banner Image'),
    ('team',  'Team Member Photo'),
    ('event', 'Event Image'),
    ('other', 'Other'),
]

VALID_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.svg', '.gif']

from permissions.decorators import has_permission


@login_required
@has_permission('school_images', action='read')
def image_list(request):
    """List all DynamicImage records."""
    qs = DynamicImage.objects.all().order_by('category', 'key')

    category_filter = request.GET.get('category', '').strip()
    if category_filter:
        qs = qs.filter(category=category_filter)

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(key__icontains=search) | qs.filter(label__icontains=search)

    context = {
        'images':      qs,
        'categories':  IMAGE_CATEGORIES,
        'cat_filter':  category_filter,
        'search':      search,
        'page_title':  'Manage Images',
    }
    return render(request, f'{_T}list.html', context)


@login_required
@has_permission('school_images', action='create')
def image_add(request):
    """Upload a new DynamicImage."""
    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'form_title': 'Upload New Image',
            'action':     'add',
            'post':       {},
            'errors':     {},
            'categories': IMAGE_CATEGORIES,
        })

    errors = {}
    post_data = request.POST
    files_data = request.FILES

    key = post_data.get('key', '').strip()
    if not key:
        errors['key'] = 'Image key is required (e.g. about_hero).'
    elif not key.replace('_', '').replace('-', '').isalnum():
        errors['key'] = 'Key must contain only letters, numbers, underscores and hyphens.'
    elif DynamicImage.objects.filter(key=key).exists():
        errors['key'] = f'Key "{key}" is already in use.'

    label = post_data.get('label', '').strip()
    if not label:
        errors['label'] = 'Label is required.'

    category = post_data.get('category', '').strip()
    if category not in dict(IMAGE_CATEGORIES):
        errors['category'] = 'Invalid category selected.'

    image_file = files_data.get('image')
    if not image_file:
        errors['image'] = 'Please select an image file to upload.'
    else:
        ext = os.path.splitext(image_file.name)[1].lower()
        if ext not in VALID_EXTENSIONS:
            errors['image'] = f'Unsupported file type "{ext}". Allowed: {", ".join(VALID_EXTENSIONS)}.'
        if image_file.size > 10 * 1024 * 1024:
            errors['image'] = 'Image size must be less than 10MB.'

    description = post_data.get('description', '').strip()

    is_active = post_data.get('is_active') == '1'

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': 'Upload New Image',
            'action':     'add',
            'post':       post_data,
            'errors':     errors,
            'categories': IMAGE_CATEGORIES,
        })

    try:
        img = DynamicImage(
            key=key,
            label=label,
            category=category,
            image=image_file,
            description=description,
            is_active=is_active,
        )
        img.save()
        messages.success(request, f'Image "{label}" uploaded successfully.')
        return redirect('school:image_list')
    except Exception as e:
        messages.error(request, f'Could not save image: {e}')
        return render(request, f'{_T}form.html', {
            'form_title': 'Upload New Image',
            'action':     'add',
            'post':       post_data,
            'errors':     {'general': str(e)},
            'categories': IMAGE_CATEGORIES,
        })


@login_required
@has_permission('school_images', action='edit')
def image_edit(request, pk):
    """Edit an existing DynamicImage."""
    image = get_object_or_404(DynamicImage, pk=pk)

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'form_title': f'Edit Image: {image.label}',
            'action':     'edit',
            'post': {
                'key':         image.key,
                'label':       image.label,
                'category':    image.category,
                'description': image.description,
                'is_active':   image.is_active,
                'current_image': image.image.url if image.image else None,
            },
            'errors':     {},
            'image_obj':  image,
            'categories': IMAGE_CATEGORIES,
        })

    errors = {}
    post_data = request.POST
    files_data = request.FILES

    key = post_data.get('key', '').strip()
    if not key:
        errors['key'] = 'Image key is required.'
    elif not key.replace('_', '').replace('-', '').isalnum():
        errors['key'] = 'Key must contain only letters, numbers, underscores and hyphens.'
    elif DynamicImage.objects.filter(key=key).exclude(pk=pk).exists():
        errors['key'] = f'Key "{key}" is already in use.'

    label = post_data.get('label', '').strip()
    if not label:
        errors['label'] = 'Label is required.'

    category = post_data.get('category', '').strip()
    if category not in dict(IMAGE_CATEGORIES):
        errors['category'] = 'Invalid category selected.'

    image_file = files_data.get('image')
    if image_file:
        ext = os.path.splitext(image_file.name)[1].lower()
        if ext not in VALID_EXTENSIONS:
            errors['image'] = f'Unsupported file type "{ext}".'
        if image_file.size > 10 * 1024 * 1024:
            errors['image'] = 'Image size must be less than 10MB.'

    description = post_data.get('description', '').strip()
    is_active = post_data.get('is_active') == '1'
    clear_image = post_data.get('clear_image') == '1'

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': f'Edit Image: {image.label}',
            'action':     'edit',
            'post':       post_data,
            'errors':     errors,
            'image_obj':  image,
            'categories': IMAGE_CATEGORIES,
        })

    try:
        image.key = key
        image.label = label
        image.category = category
        image.description = description
        image.is_active = is_active

        if clear_image and image.image:
            image.image.delete(save=False)
            image.image = None
        elif image_file:
            # Delete old file if replacing
            if image.image:
                image.image.delete(save=False)
            image.image = image_file

        image.save()
        messages.success(request, f'Image "{label}" updated successfully.')
        return redirect('school:image_list')
    except Exception as e:
        messages.error(request, f'Could not update image: {e}')
        return render(request, f'{_T}form.html', {
            'form_title': f'Edit Image: {image.label}',
            'action':     'edit',
            'post':       post_data,
            'errors':     {'general': str(e)},
            'image_obj':  image,
            'categories': IMAGE_CATEGORIES,
        })


@login_required
@has_permission('school_images', action='delete')
def image_delete(request, pk):
    """Delete a DynamicImage."""
    image = get_object_or_404(DynamicImage, pk=pk)

    if request.method == 'POST':
        try:
            if image.image:
                image.image.delete(save=False)
            image.delete()
            messages.success(request, f'Image "{image.label}" deleted successfully.')
        except Exception as e:
            messages.error(request, f'Could not delete image: {e}')
        return redirect('school:image_list')

    return render(request, f'{_T}delete_confirm.html', {
        'image': image,
    })


@login_required
@has_permission('school_images', action='toggle')
def image_toggle_active(request, pk):
    """POST-only: toggle is_active on a DynamicImage."""
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('school:image_list')

    image = get_object_or_404(DynamicImage, pk=pk)
    image.is_active = not image.is_active
    image.save(update_fields=['is_active', 'updated_at'])

    state = 'activated' if image.is_active else 'deactivated'
    messages.success(request, f'Image "{image.label}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    return redirect(next_url or 'school:image_list')
