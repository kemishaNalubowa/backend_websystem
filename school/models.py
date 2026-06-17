# school/models.py
# ─────────────────────────────────────────────────────────────────────────────
# APP: school
# MODELS: SchoolSetting, SchoolRequirement, SchoolAnnouncement,
#         SchoolEvent, SchoolCalendar
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from academics.base import TimeStampedModel
from authentication.models import CustomUser
from academics.models import SchoolStream,SchoolSupportedClasses

class SchoolSetting(models.Model):
    """
    Core school profile and configuration.
    Designed as a singleton — only one record should exist.
    Follows Uganda's Ministry of Education and Sports (MoES) registration fields.
    """
    SCHOOL_TYPE_CHOICES = [
        ('day',      'Day School'),
        ('boarding', 'Boarding School'),
        ('mixed',    'Day & Boarding'),
    ]
    OWNERSHIP_CHOICES = [
        ('government',   'Government'),
        ('private',      'Private'),
        ('community',    'Community'),
        ('faith_based',  'Faith-Based / Mission'),
    ]
    REGION_CHOICES = [
        ('central',  'Central Region'),
        ('eastern',  'Eastern Region'),
        ('northern', 'Northern Region'),
        ('western',  'Western Region'),
    ]
    CURRICULUM_CHOICES = [
        ('uganda',   'Uganda National Curriculum (MoES)'),
        ('ib',       'International Baccalaureate (IB)'),
        ('british',  'British Curriculum'),
        ('mixed',    'Mixed / Custom'),
    ]

    # ── Identity ──────────────────────────────────────────────────────────────
    school_name          = models.CharField(max_length=200)
    school_motto         = models.CharField(max_length=200, blank=True)
    school_logo          = models.ImageField(upload_to='school/', blank=True, null=True)
    school_stamp         = models.ImageField(upload_to='school/', blank=True, null=True,
                               help_text='Official school stamp image for reports and letters')
    head_teacher_signature = models.ImageField(upload_to='school/signatures/', blank=True, null=True)

    # ── Official registration ─────────────────────────────────────────────────
    registration_number  = models.CharField(max_length=50, blank=True,
                               verbose_name='MoES Registration Number')
    establishment_year   = models.PositiveIntegerField(null=True, blank=True)
    ownership            = models.CharField(max_length=20, choices=OWNERSHIP_CHOICES,
                               default='private')
    school_type          = models.CharField(max_length=10, choices=SCHOOL_TYPE_CHOICES,
                               default='day')
    curriculum           = models.CharField(max_length=20, choices=CURRICULUM_CHOICES,
                               default='uganda')

    # ── Location ──────────────────────────────────────────────────────────────
    address              = models.TextField()
    district             = models.CharField(max_length=100)
    region               = models.CharField(max_length=20, choices=REGION_CHOICES)
    county               = models.CharField(max_length=100, blank=True)
    sub_county           = models.CharField(max_length=100, blank=True)
    village              = models.CharField(max_length=100, blank=True)
    po_box               = models.CharField(max_length=50, blank=True,
                               verbose_name='P.O. Box')

    # ── Contact ───────────────────────────────────────────────────────────────
    phone                = models.CharField(max_length=15)
    alt_phone            = models.CharField(max_length=15, blank=True)
    email                = models.EmailField(blank=True)
    website              = models.URLField(blank=True)

    # ── Academic config ───────────────────────────────────────────────────────
    has_nursery           = models.BooleanField(default=True)
    has_primary           = models.BooleanField(default=True)
    # Report card configuration
    report_footer_text    = models.TextField(blank=True,
                                help_text='Text printed at the bottom of report cards')

    class Meta:
        verbose_name        = 'School Setting'
        verbose_name_plural = 'School Settings'

    def __str__(self):
        return self.school_name


# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────

class SchoolAnnouncement(TimeStampedModel):
    """
    Notices and announcements sent from the school administration
    to staff, parents, or students.
    """
    AUDIENCE_CHOICES = [
        ('all',      'Everyone'),
        ('teachers', 'Teachers & Staff'),
        ('parents',  'Parents & Guardians'),
        ('students', 'Students'),
    ]
    PRIORITY_CHOICES = [
        ('normal',  'Normal'),
        ('urgent',  'Urgent'),
        ('critical','Critical'),
    ]

    title        = models.CharField(max_length=200)
    content      = models.TextField()
    audience     = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='all')
    priority     = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at   = models.DateTimeField(null=True, blank=True,
                       help_text='Date/time after which this announcement is no longer shown')
    attachment   = models.FileField(upload_to='announcements/', blank=True, null=True)
    # Target a specific class (optional — leave blank for school-wide)
    school_class = models.ForeignKey(
                       SchoolSupportedClasses,
                       on_delete=models.SET_NULL,
                       null=True, blank=True,
                       related_name='announcements'
                   )
    posted_by    = models.ForeignKey(
                       CustomUser,
                       on_delete=models.SET_NULL,
                       null=True,
                       related_name='announcements_posted'
                   )

    class Meta:
        verbose_name        = 'Announcement'
        verbose_name_plural = 'Announcements'
        ordering            = ['-published_at', '-created_at']

    def __str__(self):
        status = 'Published' if self.is_published else 'Draft'
        return f"[{status}] {self.title} → {self.get_audience_display()}"


# ─────────────────────────────────────────────────────────────────────────────

class SchoolEvent(TimeStampedModel):
    """
    Events on the school calendar.
    Includes academic, sports, cultural, religious, and public holiday events.
    Uganda observes national holidays and faith-based events are common
    in mission/faith-based schools.
    """
    EVENT_TYPE_CHOICES = [
        ('academic',   'Academic'),
        ('exam',       'Examination'),
        ('sports',     'Sports Day / Inter-House'),
        ('cultural',   'Cultural / Drama'),
        ('religious',  'Religious / Chapel'),
        ('holiday',    'Public Holiday'),
        ('meeting',    'Parents / Staff Meeting'),
        ('trip',       'School Trip / Excursion'),
        ('graduation', 'Graduation / Completion'),
        ('open_day',   'Open Day / Visiting Day'),
        ('other',      'Other'),
    ]

    title         = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    event_type    = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    start_date    = models.DateField()
    end_date      = models.DateField()
    start_time    = models.TimeField(null=True, blank=True)
    end_time      = models.TimeField(null=True, blank=True)
    venue         = models.CharField(max_length=200, blank=True,
                        help_text='Location e.g. School Playground, Assembly Hall, Kololo Grounds')
    is_whole_school = models.BooleanField(default=True,
                          help_text='Does this event involve the whole school?')
    school_classes  = models.ManyToManyField(
                          SchoolSupportedClasses,
                          blank=True,
                          related_name='events',
                          help_text='Specific classes involved (if not whole-school)'
                      )


    is_published    = models.BooleanField(default=False)
    attachment      = models.FileField(upload_to='events/', blank=True, null=True,
                          help_text='Event notice, invitation, or programme')
    organized_by    = models.ForeignKey(
                          CustomUser,
                          on_delete=models.SET_NULL,
                          null=True,
                          related_name='events_organized'
                      )

    class Meta:
        verbose_name        = 'School Event'
        verbose_name_plural = 'School Events'
        ordering            = ['start_date']

    def __str__(self):
        return f"{self.title} | {self.start_date} — {self.get_event_type_display()}"


# ─────────────────────────────────────────────────────────────────────────────

class DynamicImage(TimeStampedModel):
    """
    Admin-managed image assets for the public-facing website.
    Each image has a unique `key` (e.g. 'about_hero', 'events_hero',
    'team_director') that the frontend references by name.
    The API returns each key with a cache-busting ?v= query string
    derived from the file's last-modified timestamp so browsers always
    fetch the latest version after an upload.
    """

    CATEGORY_CHOICES = [
        ('hero',  'Hero / Banner Image'),
        ('team',  'Team Member Photo'),
        ('event', 'Event Image'),
        ('other', 'Other'),
    ]

    key         = models.SlugField(
                      max_length=80, unique=True,
                      help_text=(
                          'Machine-readable identifier used by the frontend. '
                          'Examples: about_hero, events_hero, team_director'
                      )
                  )
    label       = models.CharField(
                      max_length=150,
                      help_text='Human-readable label shown in admin (e.g. "About Us Hero Image")'
                  )
    category    = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='other')
    image       = models.ImageField(
                      upload_to='dynamic_images/',
                      help_text='Upload the image file. Replaces any previous version.'
                  )
    description = models.TextField(blank=True, help_text='Optional notes for admin reference')
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Dynamic Image'
        verbose_name_plural = 'Dynamic Images'
        ordering            = ['category', 'key']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.label} ({self.key})"

# ─────────────────────────────────────────────────────────────────────────────
# Fee Management Models

class FeeCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Fee Category"
        verbose_name_plural = "Fee Categories"

    def __str__(self):
        return self.name

class FeeStructure(models.Model):
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, related_name='structures')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    academic_year = models.CharField(max_length=9)  # e.g., "2025-2026"
    grade_level = models.CharField(max_length=50)  # e.g., "Grade 10"

    class Meta:
        verbose_name = "Fee Structure"
        verbose_name_plural = "Fee Structures"
        unique_together = ('fee_category', 'academic_year', 'grade_level')

    def __str__(self):
        return f"{self.fee_category.name} - {self.grade_level} ({self.academic_year})"

class StudentFee(models.Model):
    student = models.ForeignKey('authentication.CustomUser', on_delete=models.CASCADE, related_name='student_fees')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, related_name='student_fees')
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Student Fee"
        verbose_name_plural = "Student Fees"

    def __str__(self):
        return f"{self.student.username} - {self.fee_structure}"

class Payment(models.Model):
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    transaction_id = models.CharField(max_length=100, unique=True)
    payment_method = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"{self.transaction_id} - {self.amount_paid}"
