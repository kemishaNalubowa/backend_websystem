from django.db import models



class TimeStampedModel(models.Model):
    """Abstract base model with created_at and updated_at timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


TEACHING_STAFF_ROLES = [
        'head_teacher',
        'deputy_head',
        'teacher',
        'lab_technician',
        'it_officer',
        'subject_teacher',
    ]


