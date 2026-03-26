# school/models.py
# ─────────────────────────────────────────────────────────────────────────────
# APP: school
# MODELS: SchoolSetting, SchoolRequirement, SchoolAnnouncement,
#         SchoolEvent, SchoolCalendar
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from academics.base import TimeStampedModel
from authentication.models import CustomUser


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

class SchoolRequirement(TimeStampedModel):
    """
    Items required of students for a given term/class.
    E.g. scholastic materials, uniform items, stationery lists.
    Published to parents at the start of each term.
    """
    CATEGORY_CHOICES = [
        ('stationery',  'Stationery'),
        ('uniform',     'School Uniform'),
        ('scholastic',  'Scholastic Materials / Books'),
        ('sports',      'Sports / P.E. Kit'),
        ('equipment',   'Equipment / Tools'),
        ('other',       'Other'),
    ]

    title         = models.CharField(max_length=200)
    description   = models.TextField()
    category      = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    school_class  = models.ForeignKey(
                        'academics.SchoolClass',
                        on_delete=models.CASCADE,
                        null=True, blank=True,
                        related_name='requirements',
                        help_text='Leave blank if this requirement applies to all classes'
                    )
    term          = models.ForeignKey(
                        'academics.Term',
                        on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='requirements'
                    )
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2,
                         null=True, blank=True,
                         help_text='Estimated cost in UGX (optional)')
    is_compulsory  = models.BooleanField(default=True)
    is_published   = models.BooleanField(default=False)
    created_by     = models.ForeignKey(
                         CustomUser,
                         on_delete=models.SET_NULL,
                         null=True,
                         related_name='requirements_created'
                     )

    class Meta:
        verbose_name        = 'School Requirement'
        verbose_name_plural = 'School Requirements'
        ordering            = ['term', 'school_class', 'category']

    def __str__(self):
        target = str(self.school_class) if self.school_class else 'All Classes'
        return f"{self.title} | {target} | {self.get_category_display()}"


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
                       'academics.SchoolClass',
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
                          'academics.SchoolClass',
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

class SchoolCalendar(TimeStampedModel):
    """
    Published academic calendar for a given term / academic year.
    Typically a school issues a calendar at the start of each term
    outlining term dates, exams, events, and holidays.
    """
    title         = models.CharField(max_length=200,
                        help_text='E.g. "Term 1 2026 Academic Calendar"')
    academic_year = models.CharField(max_length=9, help_text='E.g. 2025/2026')
    term          = models.ForeignKey(
                        'academics.Term',
                        on_delete=models.CASCADE,
                        related_name='calendar_entries'
                    )
    description   = models.TextField(blank=True)
    document      = models.FileField(upload_to='calendars/', blank=True, null=True,
                        help_text='Upload a PDF or image of the printed school calendar')
    is_active     = models.BooleanField(default=True)
    is_published  = models.BooleanField(default=False,
                        help_text='Visible to parents and staff on the portal')
    published_at  = models.DateTimeField(null=True, blank=True)
    created_by    = models.ForeignKey(
                        CustomUser,
                        on_delete=models.SET_NULL,
                        null=True,
                        related_name='calendars_created'
                    )

    class Meta:
        verbose_name        = 'School Calendar'
        verbose_name_plural = 'School Calendars'
        ordering            = ['-academic_year', 'term__name']

    def __str__(self):
        return f"{self.title} ({self.academic_year})"
