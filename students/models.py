# students/models.py
# ─────────────────────────────────────────────────────────────────────────────
# APP: students
# MODELS: Student, Admission
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from academics.base import TimeStampedModel
from authentication.models import CustomUser


class Student(TimeStampedModel):
    """
    A learner enrolled in the school (Nursery or Primary).
    Linked to a parent/guardian and a current class.
    """
    GENDER_CHOICES = [
        ('male',   'Male'),
        ('female', 'Female'),
    ]
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+','AB+'), ('AB-','AB-'),
    ]
    RELIGION_CHOICES = [
        ('catholic',    'Roman Catholic'),
        ('protestant',  'Protestant / Anglican'),
        ('muslim',      'Muslim'),
        ('sda',         'Seventh Day Adventist'),
        ('pentecostal', 'Pentecostal / Born Again'),
        ('other',       'Other'),
    ]

    # ── Identity ──────────────────────────────────────────────────────────────
    student_id          = models.CharField(max_length=20, unique=True,
                              help_text='Auto-generated student number e.g. STD2025001')
    first_name          = models.CharField(max_length=50)
    last_name           = models.CharField(max_length=50)
    other_names         = models.CharField(max_length=50, blank=True)
    date_of_birth       = models.DateField()
    gender              = models.CharField(max_length=10, choices=GENDER_CHOICES)
    profile_photo       = models.ImageField(upload_to='students/', blank=True, null=True)
    nationality         = models.CharField(max_length=50, default='Ugandan')
    district_of_origin  = models.CharField(max_length=100, blank=True,
                              help_text='District of origin in Uganda')
    village             = models.CharField(max_length=100, blank=True)
    religion            = models.CharField(max_length=20, choices=RELIGION_CHOICES, blank=True)
    # Uganda-specific identity documents
    birth_certificate_no = models.CharField(max_length=50, blank=True,
                               verbose_name='Birth Certificate Number')

    # ── Academic placement ────────────────────────────────────────────────────
    current_class       = models.ForeignKey(
                              'academics.SchoolClass',
                              on_delete=models.SET_NULL,
                              null=True,
                              related_name='students'
                          )
    date_enrolled       = models.DateField()
    academic_year       = models.CharField(max_length=9,
                              help_text='Enrolment year e.g. 2025/2026')
    previous_school     = models.CharField(max_length=200, blank=True)
    previous_class      = models.CharField(max_length=50, blank=True,
                              help_text='Class attended at previous school')
    is_active           = models.BooleanField(default=True)

    # ── Parent / Guardian ─────────────────────────────────────────────────────
    parent              = models.ForeignKey(
                              CustomUser,
                              on_delete=models.SET_NULL,
                              null=True, blank=True,
                              related_name='children'
                          )
    # Secondary / emergency guardian (in case parent is unavailable)
    secondary_guardian_name  = models.CharField(max_length=100, blank=True)
    secondary_guardian_phone = models.CharField(max_length=15, blank=True)
    secondary_guardian_relationship = models.CharField(max_length=50, blank=True)

    # ── Health ────────────────────────────────────────────────────────────────
    blood_group         = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True)
    medical_notes       = models.TextField(blank=True,
                              help_text='Allergies, chronic conditions, special needs, etc.')
    is_special_needs    = models.BooleanField(default=False)
    special_needs_notes = models.TextField(blank=True)

    # ── Departure ─────────────────────────────────────────────────────────────
    date_left           = models.DateField(null=True, blank=True)
    left_reason         = models.CharField(max_length=200, blank=True,
                              help_text='E.g. Transfer, Completed P7, Withdrew')

    class Meta:
        verbose_name        = 'Student'
        verbose_name_plural = 'Students'
        ordering            = ['last_name', 'first_name']

    @property
    def full_name(self):
        parts = [self.first_name, self.other_names, self.last_name]
        return ' '.join(p for p in parts if p)

    def __str__(self):
        return f"{self.student_id} — {self.full_name}"


# ─────────────────────────────────────────────────────────────────────────────

class Admission(TimeStampedModel):
    """
    Admission application before a student is formally enrolled.
    Tracks the full application lifecycle: Pending → Approved → Student created.
    """
    STATUS_CHOICES = [
        ('pending',    'Pending Review'),
        ('shortlisted','Shortlisted'),
        ('approved',   'Approved'),
        ('rejected',   'Rejected'),
        ('waitlisted', 'Waitlisted'),
        ('enrolled',   'Enrolled'),   # Student record has been created
    ]
    GENDER_CHOICES = [
        ('male',   'Male'),
        ('female', 'Female'),
    ]

    # ── Application reference ─────────────────────────────────────────────────
    admission_number    = models.CharField(max_length=20, unique=True,
                              help_text='Auto-generated e.g. ADM2025001')
    academic_year       = models.CharField(max_length=9,
                              help_text='Intended year of entry e.g. 2026/2027')
    applied_class       = models.ForeignKey(
                              'academics.SchoolClass',
                              on_delete=models.SET_NULL,
                              null=True,
                              related_name='admission_applications',
                              help_text='Class the child is applying to join'
                          )

    # ── Applicant details ─────────────────────────────────────────────────────
    first_name          = models.CharField(max_length=50)
    last_name           = models.CharField(max_length=50)
    other_names         = models.CharField(max_length=50, blank=True)
    date_of_birth       = models.DateField()
    gender              = models.CharField(max_length=10, choices=GENDER_CHOICES)
    nationality         = models.CharField(max_length=50, default='Ugandan')
    district_of_origin  = models.CharField(max_length=100, blank=True)
    religion            = models.CharField(max_length=50, blank=True)
    birth_certificate_no = models.CharField(max_length=50, blank=True)

    # ── Previous schooling ────────────────────────────────────────────────────
    previous_school     = models.CharField(max_length=200, blank=True)
    previous_class      = models.CharField(max_length=50, blank=True)
    last_result         = models.CharField(max_length=100, blank=True,
                              help_text='E.g. Promoted with 85%, Division 2')

    # ── Parent / Guardian (at time of application) ────────────────────────────
    parent_full_name    = models.CharField(max_length=100)
    parent_relationship = models.CharField(max_length=50,
                              help_text='E.g. Father, Mother, Guardian')
    parent_phone        = models.CharField(max_length=15)
    parent_email        = models.EmailField(blank=True)
    parent_occupation   = models.CharField(max_length=100, blank=True)
    parent_address      = models.TextField()


    # ── Application status ────────────────────────────────────────────────────
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='pending')
    application_date    = models.DateField(auto_now_add=True)
    admission_date      = models.DateField(null=True, blank=True,
                              help_text='Date officially admitted / approved')
    rejection_reason    = models.TextField(blank=True)
    interview_date      = models.DateField(null=True, blank=True)
    interview_notes     = models.TextField(blank=True)
    reviewed_by         = models.ForeignKey(
                              CustomUser,
                              on_delete=models.SET_NULL,
                              null=True, blank=True,
                              related_name='admissions_reviewed'
                          )
    notes               = models.TextField(blank=True)
    # Link to created Student record once approved & enrolled
    student             = models.OneToOneField(
                              Student,
                              on_delete=models.SET_NULL,
                              null=True, blank=True,
                              related_name='admission_record'
                          )

    class Meta:
        verbose_name        = 'Admission'
        verbose_name_plural = 'Admissions'
        ordering            = ['-application_date']

    def __str__(self):
        return f"{self.admission_number} — {self.first_name} {self.last_name} ({self.academic_year})"
