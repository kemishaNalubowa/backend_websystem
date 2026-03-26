# communication/models.py
# ─────────────────────────────────────────────────────────────────────────────
# APP: communication
# MODELS: ParentsRequest, ParentsRequestReply
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from academics.base import TimeStampedModel
from authentication.models import CustomUser


class ParentsRequest(TimeStampedModel):
    """
    A formal request or inquiry submitted by a parent/guardian to the school.
    Covers leave requests, complaints, meeting requests, fee queries, etc.
    Replies are tracked via the ParentsRequestReply model.
    """
    REQUEST_TYPE_CHOICES = [
        ('leave',       'Leave / Absence Request'),
        ('transfer',    'Transfer Request'),
        ('meeting',     'Meeting Request'),
        ('complaint',   'Complaint'),
        ('fee_query',   'Fees Enquiry'),
        ('performance', 'Academic Performance Enquiry'),
        ('health',      'Health / Medical Concern'),
        ('general',     'General Inquiry'),
        ('other',       'Other'),
    ]
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('reviewed',  'Reviewed / In Progress'),
        ('resolved',  'Resolved'),
        ('closed',    'Closed'),
        ('rejected',  'Rejected'),
    ]

    # ── Request metadata ──────────────────────────────────────────────────────
    reference_number = models.CharField(max_length=20, unique=True,
                           help_text='Auto-generated e.g. REQ2025001')
    parent           = models.ForeignKey(
                           CustomUser,
                           on_delete=models.CASCADE,
                           related_name='requests'
                       )
    # Optionally linked to a specific child
    student          = models.ForeignKey(
                           'students.Student',
                           on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='parent_requests',
                           help_text='The student this request concerns (if applicable)'
                       )
    request_type     = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    subject          = models.CharField(max_length=200)
    message          = models.TextField()
    is_urgent        = models.BooleanField(default=False)
    attachment       = models.FileField(upload_to='requests/', blank=True, null=True,
                           help_text='Supporting document e.g. medical certificate')

    # ── Status & handling ─────────────────────────────────────────────────────
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES,
                           default='pending')
    assigned_to      = models.ForeignKey(
                           CustomUser,
                           on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='assigned_requests',
                           help_text='Staff member handling this request'
                       )
    resolved_at      = models.DateTimeField(null=True, blank=True)
    internal_notes   = models.TextField(blank=True,
                           help_text='Internal notes (not visible to parent)')

    class Meta:
        verbose_name        = 'Parent Request'
        verbose_name_plural = 'Parents Requests'
        ordering            = ['-created_at']

    def __str__(self):
        return (
            f"{self.reference_number} | {self.parent.user.get_full_name()} | "
            f"{self.get_request_type_display()} | {self.get_status_display()}"
        )


# ─────────────────────────────────────────────────────────────────────────────

class ParentsRequestReply(TimeStampedModel):
    """
    A reply to a parent's request, written by a school staff member.
    Supports threaded replies (multiple replies per request).
    Replies can be marked internal (visible to staff only) or
    parent-facing (visible on the parent portal).
    """
    request     = models.ForeignKey(
                      ParentsRequest,
                      on_delete=models.CASCADE,
                      related_name='replies'
                  )
    replied_by  = models.ForeignKey(
                      CustomUser,
                      on_delete=models.CASCADE,
                      related_name='request_replies'
                  )
    message     = models.TextField()
    attachment  = models.FileField(upload_to='request_replies/', blank=True, null=True)
    is_internal = models.BooleanField(default=False,
                      help_text='If True, this reply is only visible to staff, not the parent')
    is_read_by_parent = models.BooleanField(default=False,
                            help_text='Marked True when the parent views this reply')
    read_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Request Reply'
        verbose_name_plural = 'Request Replies'
        ordering            = ['created_at']

    def __str__(self):
        visibility = 'Internal' if self.is_internal else 'Parent-visible'
        return (
            f"Reply to {self.request.reference_number} | "
            f"{self.replied_by.get_full_name()} | {visibility}"
        )
