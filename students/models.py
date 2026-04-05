# students/models.py
# ─────────────────────────────────────────────────────────────────────────────
# APP: students
# MODELS:
#   Student                   — enrolled learner
#   Admission                 — application before enrolment (multi-parent JSON)
#   StudentParentRelationship — links each parent to a student + holds shared token
# ─────────────────────────────────────────────────────────────────────────────

import json

from django.db import models

from academics.base import TimeStampedModel
from authentication.models import CustomUser
from academics.models import SchoolStream


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT
# ═══════════════════════════════════════════════════════════════════════════════

class Student(TimeStampedModel):
    """
    A learner enrolled in the school (Nursery or Primary).

    Parents are NO LONGER stored as a direct FK on this model.
    All parent linkage goes through StudentParentRelationship.
    """

    GENDER_CHOICES = [
        ('male',   'Male'),
        ('female', 'Female'),
    ]
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
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
    student_id           = models.CharField(
                               max_length=20, unique=True,
                               help_text='Auto-generated e.g. STD2025001'
                           )
    first_name           = models.CharField(max_length=50)
    last_name            = models.CharField(max_length=50)
    other_names          = models.CharField(max_length=50, blank=True)
    date_of_birth        = models.DateField()
    gender               = models.CharField(max_length=10, choices=GENDER_CHOICES)
    profile_photo        = models.ImageField(
                               upload_to='students/', blank=True, null=True
                           )
    nationality          = models.CharField(max_length=50, default='Ugandan')
    district_of_origin   = models.CharField(max_length=100, blank=True)
    village              = models.CharField(max_length=100, blank=True)
    religion             = models.CharField(
                               max_length=20, choices=RELIGION_CHOICES, blank=True
                           )
    birth_certificate_no = models.CharField(
                               max_length=50, blank=True,
                               verbose_name='Birth Certificate Number'
                           )

    # ── Academic placement ────────────────────────────────────────────────────
    current_class  = models.ForeignKey(
                         'academics.SchoolSupportedClasses',
                         on_delete=models.SET_NULL,
                         null=True,
                         related_name='students',
                     )
    
    school_stream = models.ForeignKey(
                        SchoolStream, on_delete=models.CASCADE,
                        related_name='students',
                        null=True, blank=True
                    )
    
    date_enrolled  = models.DateField()
    academic_year  = models.CharField(
                         max_length=9,
                         help_text='Enrolment year e.g. 2025/2026'
                     )
    previous_school = models.CharField(max_length=200, blank=True)
    previous_class  = models.CharField(
                          max_length=50, blank=True,
                          help_text='Class attended at previous school'
                      )
    is_active       = models.BooleanField(default=True)

    # ── Secondary / emergency guardian ────────────────────────────────────────
    secondary_guardian_name         = models.CharField(max_length=100, blank=True)
    secondary_guardian_phone        = models.CharField(max_length=15, blank=True)
    secondary_guardian_relationship = models.CharField(max_length=50, blank=True)

    # ── Health ────────────────────────────────────────────────────────────────
    blood_group         = models.CharField(
                              max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True
                          )
    medical_notes       = models.TextField(
                              blank=True,
                              help_text='Allergies, chronic conditions, special needs, etc.'
                          )
    is_special_needs    = models.BooleanField(default=False)
    special_needs_notes = models.TextField(blank=True)

    # ── Departure ─────────────────────────────────────────────────────────────
    date_left  = models.DateField(null=True, blank=True)
    left_reason = models.CharField(
                      max_length=200, blank=True,
                      help_text='E.g. Transfer, Completed P7, Withdrew'
                  )

    # ── Link back to the admission that created this student (optional) ────────
    admission = models.OneToOneField(
                    'Admission',
                    on_delete=models.SET_NULL,
                    null=True, blank=True,
                    related_name='enrolled_student',
                    help_text='Admission application that resulted in this student record'
                )

    class Meta:
        verbose_name        = 'Student'
        verbose_name_plural = 'Students'
        ordering            = ['last_name', 'first_name']

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.other_names, self.last_name]
        return ' '.join(p for p in parts if p)

    def __str__(self) -> str:
        return f"{self.student_id} — {self.full_name}"

    def get_parents(self):
        """Return all ParentProfile objects linked to this student."""
        from accounts.models import ParentProfile
        return ParentProfile.objects.filter(
            student_relationships__student=self
        ).select_related('user')

    def get_active_parents(self):
        """Return only active/live parent profiles linked to this student."""
        return self.get_parents().filter(is_active=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT ↔ PARENT RELATIONSHIP
# ═══════════════════════════════════════════════════════════════════════════════

class StudentParentRelationship(TimeStampedModel):
    """
    Links a ParentProfile to a Student.

    access_token:
        A short opaque token that is the same for all parents of the same student.
        It is generated once when the FIRST parent is linked to a student and
        re-used for every subsequent parent linked to that same student.
        This token is set as the CustomUser password for every parent of this student,
        so all co-parents of a student share one password but each has their own
        parent_id (username).

        If a parent has children in multiple families (unlikely but possible),
        the parent's password is the token of the FIRST child they were linked to.
        Subsequent child tokens are stored in the relationship rows but do NOT
        overwrite the parent's existing password.
    """

    RELATIONSHIP_CHOICES = [
        ('father',         'Father'),
        ('mother',         'Mother'),
        ('legal_guardian', 'Legal Guardian'),
        ('uncle',          'Uncle'),
        ('aunt',           'Aunt'),
        ('grandparent',    'Grandparent'),
        ('sibling',        'Elder Sibling'),
        ('other',          'Other'),
    ]

    student      = models.ForeignKey(
                       Student,
                       on_delete=models.CASCADE,
                       related_name='parent_relationships',
                   )
    parent       = models.ForeignKey(
                       'accounts.ParentProfile',
                       on_delete=models.CASCADE,
                       related_name='student_relationships',
                   )
    relationship = models.CharField(
                       max_length=20,
                       choices=RELATIONSHIP_CHOICES,
                       default='other',
                   )
    # The shared access token for this student-family group.
    # Copied from the student's first relationship row when created.
    access_token = models.CharField(
                       max_length=64,
                       help_text=(
                           'Shared token among all parents of this student. '
                           'Used as the parent portal login password.'
                       ),
                   )
    is_primary   = models.BooleanField(
                       default=False,
                       help_text='The primary/emergency contact parent for this student.'
                   )

    class Meta:
        verbose_name        = 'Student–Parent Relationship'
        verbose_name_plural = 'Student–Parent Relationships'
        unique_together     = [('student', 'parent')]
        ordering            = ['student', '-is_primary', 'relationship']

    def __str__(self) -> str:
        return (
            f"{self.parent.full_name} "
            f"({self.get_relationship_display()}) → "
            f"{self.student.full_name}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMISSION
# ═══════════════════════════════════════════════════════════════════════════════

class Admission(TimeStampedModel):
    """
    Admission application before a student is formally enrolled.

    Tracks the full application lifecycle:
        Pending → Approved → Verified → (Student + Parents created)

    Parent data:
        Stored as a JSON array in `parents_data`.
        Each element is a dict representing one parent/guardian.
        This replaces all the old single-parent flat fields.

        Schema per parent dict:
        {
            "full_name":     str,
            "relationship":  str,   # father | mother | legal_guardian | …
            "phone":         str,
            "email":         str,   # optional
            "occupation":    str,   # optional
            "address":       str,
            "nin":           str,   # optional
        }

    Existing parent:
        If the parent already has a child in the school the form collects
        their parent_id instead of raw data.  In that case the element looks like:
        {
            "existing":   true,
            "parent_id":  "PAR20250001",
            "relationship": str,
        }
    """

    STATUS_CHOICES = [
        ('pending',     'Pending Review'),
        ('shortlisted', 'Shortlisted'),
        ('approved',    'Approved'),
        ('rejected',    'Rejected'),
        ('waitlisted',  'Waitlisted'),
        ('enrolled',    'Enrolled'),   # Student record has been created
    ]
    GENDER_CHOICES = [
        ('male',   'Male'),
        ('female', 'Female'),
    ]

    # ── Application reference ─────────────────────────────────────────────────
    admission_number = models.CharField(
                           max_length=20, unique=True,
                           help_text='Auto-generated e.g. ADM2025001'
                       )
    academic_year    = models.CharField(
                           max_length=9,
                           help_text='Intended year of entry e.g. 2026/2027'
                       )
    applied_class    = models.ForeignKey(
                           'academics.SchoolSupportedClasses',
                           on_delete=models.SET_NULL,
                           null=True,
                           related_name='admission_applications',
                           help_text='Class the child is applying to join'
                       )
    school_stream = models.ForeignKey(
                        SchoolStream, on_delete=models.CASCADE,
                        related_name='admissions',
                        null=True, blank=True
                    )

    # ── Applicant (student) details ───────────────────────────────────────────
    first_name           = models.CharField(max_length=50)
    last_name            = models.CharField(max_length=50)
    other_names          = models.CharField(max_length=50, blank=True)
    date_of_birth        = models.DateField()
    gender               = models.CharField(max_length=10, choices=GENDER_CHOICES)
    nationality          = models.CharField(max_length=50, default='Ugandan')
    district_of_origin   = models.CharField(max_length=100, blank=True)
    religion             = models.CharField(max_length=50, blank=True)
    birth_certificate_no = models.CharField(max_length=50, blank=True)

    # ── Previous schooling ────────────────────────────────────────────────────
    previous_school = models.CharField(max_length=200, blank=True)
    previous_class  = models.CharField(max_length=50, blank=True)
    last_result     = models.CharField(
                          max_length=100, blank=True,
                          help_text='E.g. Promoted with 85%, Division 2'
                      )

    # ── Multi-parent data (replaces all old single-parent flat fields) ─────────
    parents_data = models.JSONField(
                       default=list,
                       help_text=(
                           'JSON array of parent/guardian dicts. '
                           'See Admission docstring for schema.'
                       ),
                   )

    # ── Application status ────────────────────────────────────────────────────
    status           = models.CharField(
                           max_length=20,
                           choices=STATUS_CHOICES,
                           default='pending',
                       )
    application_date = models.DateField(auto_now_add=True)

    # Set when the admission moves to 'approved'
    admission_date   = models.DateField(
                           null=True, blank=True,
                           help_text='Date officially admitted / approved'
                       )

    # ── Verification ──────────────────────────────────────────────────────────
    is_verified     = models.BooleanField(
                          default=False,
                          help_text=(
                              'True once the admission has been verified and the '
                              'student + parent accounts have been created.'
                          ),
                      )
    verified_at     = models.DateTimeField(null=True, blank=True)
    verified_by     = models.ForeignKey(
                          CustomUser,
                          on_delete=models.SET_NULL,
                          null=True, blank=True,
                          related_name='admissions_verified',
                      )

    # ── Workflow fields ───────────────────────────────────────────────────────
    rejection_reason = models.TextField(blank=True)
    interview_date   = models.DateField(null=True, blank=True)
    interview_notes  = models.TextField(blank=True)
    reviewed_by      = models.ForeignKey(
                           CustomUser,
                           on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='admissions_reviewed',
                       )
    notes            = models.TextField(blank=True)

    # ── Link to created Student record (set during verification) ──────────────
    student = models.OneToOneField(
                  Student,
                  on_delete=models.SET_NULL,
                  null=True, blank=True,
                  related_name='admission_record',
              )

    class Meta:
        verbose_name        = 'Admission'
        verbose_name_plural = 'Admissions'
        ordering            = ['-application_date']

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.other_names, self.last_name]
        return ' '.join(p for p in parts if p)

    def get_parents_data(self) -> list:
        """Return parents_data as a Python list, handling string JSON gracefully."""
        if isinstance(self.parents_data, str):
            try:
                return json.loads(self.parents_data)
            except (ValueError, TypeError):
                return []
        return self.parents_data or []

    def __str__(self) -> str:
        return (
            f"{self.admission_number} — "
            f"{self.first_name} {self.last_name} "
            f"({self.academic_year})"
        )
