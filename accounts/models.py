# accounts/models.py
# ─────────────────────────────────────────────────────────────────────────────
# APP: accounts
# MODELS: ParentProfile, StaffProfile
#
# Changes from previous version:
#   ParentProfile — added `access_token` field (unique, 64 chars).
#                   Generated once at parent creation; used as portal password.
#                   Removed direct reference to students (now via
#                   StudentParentRelationship).
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models

from authentication.models import CustomUser
from academics.models import SchoolStream


# ═══════════════════════════════════════════════════════════════════════════════
#  CHOICES  (shared)
# ═══════════════════════════════════════════════════════════════════════════════

GENDER_CHOICES = [
    ('male',              'Male'),
    ('female',            'Female'),
    ('other',             'Other'),
    ('prefer_not_to_say', 'Prefer not to say'),
]

USER_TYPE_CHOICES = [
    ('parent',  'Parent / Guardian'),
    ('teacher', 'Teacher'),
    ('staff',   'Support Staff'),
    ('admin',   'Administrator'),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  PARENT PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

class ParentProfile(models.Model):
    """
    Extended guardian / parent information.
    Linked 1-to-1 with a CustomUser whose user_type = 'parent'.

    Login flow:
        username  → user.parent_id  (e.g. PAR20250001)
        password  → access_token    (shared among all parents of a student)

    The access_token is generated once at account creation, stored here,
    and set as the hashed password on the linked CustomUser.
    It is also stored (un-hashed as an identifier) on each
    StudentParentRelationship row so the portal can verify which
    student a token belongs to.
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

    # ── Link to CustomUser ────────────────────────────────────────────────────
    user = models.OneToOneField(
               CustomUser,
               on_delete=models.CASCADE,
               related_name='parent_profile',
               limit_choices_to={'user_type': 'parent'},
           )

    # ── Portal access token ───────────────────────────────────────────────────
    access_token = models.CharField(
                       max_length=64,
                       unique=True,
                       help_text=(
                           'Opaque token used as the parent portal login password. '
                           'Generated once at account creation. Shared across all '
                           'parents of the same student via StudentParentRelationship.'
                       ),
                   )

    # ── Guardian details ──────────────────────────────────────────────────────
    relationship = models.CharField(
                       max_length=20,
                       choices=RELATIONSHIP_CHOICES,
                   )
    occupation   = models.CharField(max_length=100, blank=True)
    employer     = models.CharField(max_length=200, blank=True)
    work_phone   = models.CharField(max_length=15, blank=True)
    work_address = models.TextField(blank=True)

    # ── Uganda location ───────────────────────────────────────────────────────
    district   = models.CharField(max_length=100, blank=True)
    sub_county = models.CharField(max_length=100, blank=True)
    village    = models.CharField(max_length=100, blank=True)
    religion   = models.CharField(max_length=50, blank=True)

    # ── Emergency contact ─────────────────────────────────────────────────────
    emergency_contact_name  = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    emergency_contact_rel   = models.CharField(
                                  max_length=50, blank=True,
                                  verbose_name='Emergency contact relationship',
                              )

    # ── Meta ──────────────────────────────────────────────────────────────────
    notes      = models.TextField(blank=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Parent Profile'
        verbose_name_plural = 'Parent Profiles'
        ordering            = ['user__last_name', 'user__first_name']

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def parent_id(self) -> str:
        return self.user.parent_id or ''

    @property
    def full_name(self) -> str:
        return self.user.full_name

    @property
    def phone(self) -> str:
        return self.user.phone

    def get_students(self):
        """Return all Student objects linked to this parent."""
        from students.models import Student
        return Student.objects.filter(
            parent_relationships__parent=self
        ).select_related('current_class')

    def __str__(self) -> str:
        return (
            f"{self.user.full_name} "
            f"({self.get_relationship_display()}) "
            f"[{self.parent_id}]"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  STAFF PROFILE  (unchanged from previous version)
# ═══════════════════════════════════════════════════════════════════════════════

class StaffProfile(models.Model):
    """
    Extended professional profile for teaching and non-teaching staff.
    Linked 1-to-1 with a CustomUser whose user_type in ('teacher','staff','admin').
    """

    ROLE_CHOICES = [
        ('head_teacher',    'Head Teacher'),
        ('deputy_head',     'Deputy Head Teacher'),
        ('teacher',         'Class Teacher'),
        ('subject_teacher', 'Subject Teacher'),
        ('bursar',          'Bursar'),
        ('secretary',       'School Secretary'),
        ('librarian',       'Librarian'),
        ('lab_technician',  'Lab Technician'),
        ('nurse',           'School Nurse / Health Worker'),
        ('security',        'Security Personnel'),
        ('cleaner',         'Cleaner / Janitor'),
        ('driver',          'Driver'),
        ('cook',            'Cook / Catering Staff'),
        ('it_officer',      'IT Officer'),
        ('other',           'Other'),
    ]

    QUALIFICATION_CHOICES = [
        ('ptc',           'Primary Teachers Certificate (PTC)'),
        ('grade3',        'Grade III Certificate'),
        ('diploma',       'Diploma in Education'),
        ('degree',        'Bachelor of Education (B.Ed)'),
        ('pgde',          'PGDE'),
        ('masters',       'Masters in Education'),
        ('certificate',   'Certificate (Non-Education)'),
        ('diploma_other', 'Diploma (Non-Education)'),
        ('bachelors',     'Bachelors (Non-Education)'),
        ('none',          'No Formal Qualification'),
        ('other',         'Other'),
    ]

    EMPLOYMENT_TYPE_CHOICES = [
        ('permanent', 'Permanent'),
        ('contract',  'Contract'),
        ('part_time', 'Part-Time'),
        ('volunteer', 'Volunteer'),
        ('intern',    'Intern'),
    ]

    # ── Link ──────────────────────────────────────────────────────────────────
    user = models.OneToOneField(
               CustomUser,
               on_delete=models.CASCADE,
               related_name='staff_profile',
               limit_choices_to={'user_type__in': ('teacher', 'staff', 'admin')},
           )

    # ── Employment ────────────────────────────────────────────────────────────
    employee_id     = models.CharField(
                          max_length=20, unique=True,
                          help_text='Auto-generated e.g. EMP20250001',
                      )
    role            = models.CharField(max_length=20, choices=ROLE_CHOICES)
    employment_type = models.CharField(
                          max_length=15,
                          choices=EMPLOYMENT_TYPE_CHOICES,
                          default='permanent',
                      )
    date_joined     = models.DateField()
    date_left       = models.DateField(null=True, blank=True)
    is_active       = models.BooleanField(default=True)

    # ── Teaching-specific ─────────────────────────────────────────────────────
    qualification  = models.CharField(
                         max_length=20, choices=QUALIFICATION_CHOICES, blank=True
                     )
    specialization = models.CharField(max_length=100, blank=True)
    is_class_teacher = models.BooleanField(default=False)
    class_managed  = models.ForeignKey(
                         'academics.SchoolClass',
                         on_delete=models.SET_NULL,
                         null=True, blank=True,
                         related_name='form_teacher',
                     )
    school_stream = models.ForeignKey(
                        SchoolStream, on_delete=models.CASCADE,
                        related_name='form_teacher',
                        null=True, blank=True
                    )

    # ── Uganda payroll / HR ───────────────────────────────────────────────────
    nssf_number  = models.CharField(max_length=20, blank=True)
    tin_number   = models.CharField(max_length=20, blank=True)
    salary_scale = models.CharField(max_length=50, blank=True)
    bank_name    = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=30, blank=True)

    # ── Profile ───────────────────────────────────────────────────────────────
    bio       = models.TextField(blank=True)
    notes     = models.TextField(blank=True)
    signature = models.ImageField(
                    upload_to='staff/signatures/', blank=True, null=True
                )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'
        ordering            = ['user__last_name', 'user__first_name']

    @property
    def full_name(self) -> str:
        return self.user.full_name

    @property
    def is_teaching_staff(self) -> bool:
        return self.user.user_type == 'teacher'

    @property
    def is_non_teaching_staff(self) -> bool:
        return self.user.user_type == 'staff'

    def __str__(self) -> str:
        return (
            f"{self.employee_id} — {self.user.full_name} "
            f"({self.get_role_display()})"
        )
