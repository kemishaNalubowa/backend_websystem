# academics/models.py
# ─────────────────────────────────────────────────────────────────────────────
# APP: academics
# MODELS: Term, Subject, SchoolClass, ClassSubject, TeacherSubject, TeacherClass
# ─────────────────────────────────────────────────────────────────────────────
# Uganda Academic Structure
#   Nursery : Baby Class → Middle Class → Top Class  (ages ~3–5)
#   Primary : P1 → P2 → P3 → P4 → P5 → P6 → P7     (P7 sits PLE)
#   Terms   : Term 1 | Term 2 | Term 3
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from . base import TimeStampedModel 
from . import base






# academics/models.py  ── Term (final revision)
# ─────────────────────────────────────────────────────────────────────────────
# KEY CHANGES
#
#  1. academic_year  → @property from start_date.year  (no stored CharField)
#
#  2. exam_start_date / exam_end_date (generic, ambiguous)  →  REMOVED
#     Replaced with THREE dedicated exam windows that map 1-to-1 with the
#     AssessmentSubject.exam_type choices:
#
#       BOT  Beginning of Term exam  — sits at the START of the term
#            (tests what students remember from the previous term)
#       MOT  Middle of Term exam     — sits MIDWAY through the term
#            (progress check, sometimes called "mid-term test")
#       EOT  End of Term exam        — sits at the END of the term
#            (main terminal exam, results go on the report card)
#
#  3. Holiday Studies block retained from previous revision.
#
#  The AssessmentSubject.exam_type = ('bot'|'mot'|'eot'|'mock'|'ple')
#  now maps cleanly to bot_start/end, mot_start/end, eot_start/end on Term.
# ─────────────────────────────────────────────────────────────────────────────

from datetime import timedelta
from django.db import models
from django.core.exceptions import ValidationError


class Term(TimeStampedModel):
    """
    Academic term within a school year.
    Uganda runs 3 terms per calendar year.

    Each term contains THREE exam windows:
        BOT → Beginning of Term  (start of term, retention check)
        MOT → Middle of Term     (mid-term progress test)
        EOT → End of Term        (terminal exam, drives the report card)

    academic_year is derived from start_date.year — not stored separately.
    """

    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]

    # ── Core identity ─────────────────────────────────────────────────────────
    name          = models.IntegerField(
                        choices=TERM_CHOICES,
                        verbose_name='Term'
                    )
    start_date    = models.DateField(
                        help_text='First day of the term (school opens)'
                    )
    end_date      = models.DateField(
                        help_text='Last day of normal lessons before EOT exams'
                    )
    is_current    = models.BooleanField(
                        default=False,
                        help_text='Only one term should be marked current at a time'
                    )

    # ── BOT — Beginning of Term Exam ─────────────────────────────────────────
    # Held in the first 1–2 weeks of term.
    # Tests retention from the previous term / holiday studies.
    bot_start_date = models.DateField(
                         null=True, blank=True,
                         verbose_name='BOT Exam Start',
                         help_text='Beginning of Term exam start date'
                     )
    bot_end_date   = models.DateField(
                         null=True, blank=True,
                         verbose_name='BOT Exam End',
                         help_text='Beginning of Term exam end date'
                     )

    # ── MOT — Middle of Term Exam ─────────────────────────────────────────────
    # Held roughly halfway through the term.
    # Sometimes called "mid-term test" or "half-term assessment".
    mot_start_date = models.DateField(
                         null=True, blank=True,
                         verbose_name='MOT Exam Start',
                         help_text='Middle of Term exam start date'
                     )
    mot_end_date   = models.DateField(
                         null=True, blank=True,
                         verbose_name='MOT Exam End',
                         help_text='Middle of Term exam end date'
                     )

    # ── EOT — End of Term Exam ────────────────────────────────────────────────
    # The main terminal examination.
    # Results from EOT drive the report card and promotion decisions.
    eot_start_date = models.DateField(
                         null=True, blank=True,
                         verbose_name='EOT Exam Start',
                         help_text='End of Term exam start date'
                     )
    eot_end_date   = models.DateField(
                         null=True, blank=True,
                         verbose_name='EOT Exam End',
                         help_text='End of Term exam end date'
                     )

    # ── Closing & reopening ───────────────────────────────────────────────────
    closing_date   = models.DateField(
                         null=True, blank=True,
                         help_text='Last day students are in school (after EOT exams finish)'
                     )
    opening_date   = models.DateField(
                         null=True, blank=True,
                         help_text='Date school reopens for the NEXT term'
                     )

    # ── Holiday Studies ───────────────────────────────────────────────────────
    # After closing_date, selected classes (e.g. P6, P7) are recalled for
    # extra coaching before the next major exam or PLE season.
    # The long holiday only begins AFTER holiday studies end.
    #
    # Timeline example:
    #   closing_date        → 2 Aug   (all students go home)
    #   holiday_study_start → 9 Aug   (P6 & P7 return after 1 week at home)
    #   holiday_study_end   → 23 Aug  (coaching ends)
    #   long_holiday_start  → 24 Aug  (auto-set; everyone now on full holiday)
    #   opening_date        → 4 Sep   (next term opens)
    #
    has_holiday_studies   = models.BooleanField(
                                default=False,
                                help_text='Were selected classes called back for holiday coaching?'
                            )
    holiday_study_start   = models.DateField(
                                null=True, blank=True,
                                help_text='Date selected classes return for holiday coaching'
                            )
    holiday_study_end     = models.DateField(
                                null=True, blank=True,
                                help_text='Last day of holiday coaching'
                            )
    holiday_study_classes = models.ManyToManyField(
                                'SchoolClass',
                                blank=True,
                                related_name='holiday_study_terms',
                                help_text='Classes attending holiday studies e.g. P6, P7'
                            )
    
    holiday_study_class_stream = models.ManyToManyField(
                                'SchoolStream',
                                blank=True,
                                related_name='holiday_study_terms',
                                help_text='Classes attending holiday studies e.g. P6, P7'
    )

    holiday_study_note    = models.TextField(
                                blank=True,
                                help_text=(
                                    'Instructions for parents e.g. bring all books, '
                                    'report by 8:00 am, uniform required.'
                                )
                            )
    long_holiday_start    = models.DateField(
                                null=True, blank=True,
                                help_text=(
                                    'Date the full holiday begins for everyone. '
                                    'Auto-set to day after holiday_study_end '
                                    'when has_holiday_studies=True, '
                                    'otherwise same as closing_date.'
                                )
                            )

    # ─────────────────────────────────────────────────────────────────────────

    class Meta:
        verbose_name        = 'Term'
        verbose_name_plural = 'Terms'
        unique_together     = ['name', 'start_date']
        ordering            = ['-start_date', 'name']

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def academic_year(self) -> int | None:
        """
        Derived from start_date.year — single source of truth.
        Uganda academic year = calendar year.
        Returns e.g. 2025
        """
        return self.start_date.year if self.start_date else None

    @property
    def exam_window(self) -> dict:
        """
        Returns all three exam windows as a dict.
        Useful for calendar rendering and schedule views.

        Example:
            {
                'BOT': ('2025-02-10', '2025-02-14'),
                'MOT': ('2025-04-07', '2025-04-11'),
                'EOT': ('2025-05-26', '2025-05-30'),
            }
        """
        return {
            'BOT': (self.bot_start_date, self.bot_end_date),
            'MOT': (self.mot_start_date, self.mot_end_date),
            'EOT': (self.eot_start_date, self.eot_end_date),
        }

    @property
    def term_duration_days(self) -> int | None:
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return None

    @property
    def holiday_study_duration_days(self) -> int | None:
        if self.holiday_study_start and self.holiday_study_end:
            return (self.holiday_study_end - self.holiday_study_start).days + 1
        return None

    # ── Validation ────────────────────────────────────────────────────────────

    def clean(self):
        errors = {}

        # Core date order
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                errors['end_date'] = 'End date must be after start date.'

        # BOT must fall within the first portion of the term
        if self.bot_start_date:
            if self.start_date and self.bot_start_date < self.start_date:
                errors['bot_start_date'] = 'BOT exam cannot start before the term opens.'
            if self.bot_end_date and self.bot_end_date < self.bot_start_date:
                errors['bot_end_date'] = 'BOT exam end must be after BOT exam start.'

        # MOT must be after BOT
        if self.mot_start_date:
            if self.bot_end_date and self.mot_start_date <= self.bot_end_date:
                errors['mot_start_date'] = 'MOT exam must start after BOT exam ends.'
            if self.mot_end_date and self.mot_end_date < self.mot_start_date:
                errors['mot_end_date'] = 'MOT exam end must be after MOT exam start.'

        # EOT must be after MOT (and before/at closing)
        if self.eot_start_date:
            if self.mot_end_date and self.eot_start_date <= self.mot_end_date:
                errors['eot_start_date'] = 'EOT exam must start after MOT exam ends.'
            if self.eot_end_date and self.eot_end_date < self.eot_start_date:
                errors['eot_end_date'] = 'EOT exam end must be after EOT exam start.'
            if self.closing_date and self.eot_end_date and self.eot_end_date > self.closing_date:
                errors['eot_end_date'] = 'EOT exams must finish on or before the closing date.'

        # Holiday studies
        if self.has_holiday_studies:
            if not self.holiday_study_start:
                errors['holiday_study_start'] = (
                    'Holiday study start is required when has_holiday_studies is True.'
                )
            if not self.holiday_study_end:
                errors['holiday_study_end'] = (
                    'Holiday study end is required when has_holiday_studies is True.'
                )
            if self.holiday_study_start and self.closing_date:
                if self.holiday_study_start <= self.closing_date:
                    errors['holiday_study_start'] = (
                        'Holiday studies must start AFTER closing date — '
                        'students need at least a day at home first.'
                    )
            if self.holiday_study_start and self.holiday_study_end:
                if self.holiday_study_end < self.holiday_study_start:
                    errors['holiday_study_end'] = (
                        'Holiday study end must be after holiday study start.'
                    )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Auto-compute long_holiday_start if not manually set
        if not self.long_holiday_start:
            if self.has_holiday_studies and self.holiday_study_end:
                self.long_holiday_start = self.holiday_study_end + timedelta(days=1)
            elif self.closing_date:
                self.long_holiday_start = self.closing_date

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Term {self.name} — {self.academic_year}"



# ─────────────────────────────────────────────────────────────────────────────

class Subject(TimeStampedModel):
    """
    Academic subject taught in the school.
    Mapped to Uganda's MoES curriculum for nursery and primary levels.
    """
    LEVEL_CHOICES = [
        ('nursery',       'Nursery (Baby – Top Class)'),
        ('lower_primary', 'Lower Primary (P1 – P3)'),
        ('upper_primary', 'Upper Primary (P4 – P7)'),
        ('all',           'All Levels'),
    ]

    name          = models.CharField(max_length=100,
                        help_text='E.g. English Language, Mathematics, Science, SST, MTC, CRE, IRE')
    code          = models.CharField(max_length=10, unique=True,
                        help_text='Short code e.g. ENG, MAT, SCI, SST, MTC, CRE, IRE, LIT')
    # level         = models.CharField(max_length=20, choices=LEVEL_CHOICES,
                        # help_text='Which school level this subject belongs to')
    description   = models.TextField(blank=True)
    # is_compulsory = models.BooleanField(default=True,
                        # help_text='Is this subject compulsory for all students at the level?')
    is_active     = models.BooleanField(default=True)
    # sort_order    = models.PositiveIntegerField(default=0,
                        # help_text='Order in which subject appears on report cards')

    class Meta:
        verbose_name        = 'Subject'
        verbose_name_plural = 'Subjects'
        ordering            = ['name']

    def __str__(self):
        return f"{self.code} — {self.name}"








# ─────────────────────────────────────────────────────────────────────────────

class SchoolClass(TimeStampedModel):
    """
    Static class levels seeded once during setup.
    Covers nursery (Baby, Middle, Top) and primary (P1-P7).
    Records cannot be added, edited, or deleted after seeding.
    """
    key = models.CharField(max_length=10, unique=True)   # 'p1', 'baby' etc.
    name = models.CharField(max_length=50)               # 'Primary One'
    section = models.CharField(max_length=20, choices=[
        ('nursery', 'Nursery'),
        ('primary', 'Primary'),
    ])
    order = models.PositiveIntegerField()                # for sorted display

    class Meta:
        ordering = ['order']
        verbose_name = 'Class'
        verbose_name_plural = 'Classes'

    def __str__(self):
        return self.name

    # def save(self, *args, **kwargs):
    #     if self.pk:
    #         raise PermissionError("Class records are static and cannot be modified.")
    #     super().save(*args, **kwargs)

    # def delete(self, *args, **kwargs):
    #     raise PermissionError("Class records are static and cannot be deleted.")



class SchoolSupportedClasses(TimeStampedModel):
    supported_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="school_supported_classess")
    def __str__(self):
        return self.supported_class
    





class SchoolStream(TimeStampedModel):
    """
    School-defined streams per class level.
    e.g. Primary Three A, Primary Three B.
    Only relevant if school.has_streams is True.
    """
    # school = models.ForeignKey(
    #     'schools.School',
    #     on_delete=models.CASCADE,
    #     related_name='streams'
    # )
    class_level = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        related_name='streams'
    )
    name = models.CharField(max_length=20)   # 'A', 'B', 'East', 'West'
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['class_level__order', 'name']
        unique_together = ( 'class_level', 'name')
        verbose_name = 'Stream'
        verbose_name_plural = 'Streams'

    def __str__(self):
        return f"{self.class_level.name} {self.name}"   # "Primary Three A"
    




# class SchoolClass(TimeStampedModel):
#     """
#     A class/grade level in the school.
#     Supports both Nursery (Baby/Middle/Top) and Primary (P1–P7).
#     Streams (e.g. P3A, P3B) are handled via the `stream` field.
#     """
#     LEVEL_CHOICES = [
#         # Nursery
#         ('baby',   'Baby Class'),
#         ('middle', 'Middle Class'),
#         ('top',    'Top Class'),
#         # Primary
#         ('p1',     'Primary One (P1)'),
#         ('p2',     'Primary Two (P2)'),
#         ('p3',     'Primary Three (P3)'),
#         ('p4',     'Primary Four (P4)'),
#         ('p5',     'Primary Five (P5)'),
#         ('p6',     'Primary Six (P6)'),
#         ('p7',     'Primary Seven (P7)'),
#     ]
#     SECTION_CHOICES = [
#         ('nursery', 'Nursery'),
#         ('primary', 'Primary'),
#     ]

#     level         = models.CharField(max_length=10, choices=LEVEL_CHOICES)
#     stream        = models.CharField(max_length=5, blank=True,
#                         help_text='Stream / section e.g. A, B, C. Leave blank if no streaming.')
#     section       = models.CharField(max_length=10, choices=SECTION_CHOICES)
#     capacity      = models.PositiveIntegerField(default=45,
#                         help_text='Maximum number of students allowed in this class')
#     # class_teacher = models.ForeignKey(
#     #                     'accounts.Teacher',
#     #                     on_delete=models.SET_NULL,
#     #                     null=True, blank=True,
#     #                     related_name='class_managed',
#     #                     help_text='The designated class/form teacher'
#     #                 )
#     classroom     = models.CharField(max_length=50, blank=True,
#                         help_text='Room number or name e.g. Room 4, Block B')
#     academic_year = models.CharField(max_length=9,
#                         help_text='Format: 2025/2026')
#     is_active     = models.BooleanField(default=True)

#     class Meta:
#         verbose_name        = 'Class'
#         verbose_name_plural = 'Classes'
#         unique_together     = ['level', 'stream', 'academic_year']
#         ordering            = ['section', 'level', 'stream']

#     @property
#     def display_name(self):
#         name = self.get_level_display()
#         if self.stream:
#             name = f"{name} {self.stream.upper()}"
#         return name

#     def __str__(self):
#         return self.display_name


# ─────────────────────────────────────────────────────────────────────────────

class ClassSubject(TimeStampedModel):
    """
    Maps which subjects are taught in a given class.
    E.g. P4 teaches: English, Maths, Science, SST, MTC, CRE.
    """
    school_class = models.ForeignKey(
                        SchoolSupportedClasses, on_delete=models.CASCADE,
                        related_name='class_subjects'
                    )
    
    # school_stream = models.ForeignKey(
    #                     SchoolStream, on_delete=models.CASCADE,
    #                     related_name='class_subjects',
    #                     null=True, blank=True
    #                 )
    
    subject      = models.ForeignKey(
                        Subject, on_delete=models.CASCADE,
                        related_name='class_subjects'
                    )
    # is_active    = models.BooleanField(default=True)
    # notes        = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name        = 'Class Subject'
        verbose_name_plural = 'Class Subjects'
        unique_together     = ['school_class', 'subject']
        ordering            = ['school_class',]

    def __str__(self):
        return f"{self.school_class} → {self.subject.code}"


# ─────────────────────────────────────────────────────────────────────────────

class TeacherSubject(TimeStampedModel):
    """
    Records which subjects a teacher is qualified / assigned to teach.
    A teacher may teach multiple subjects (common in small primary schools).
    """
    # teacher    = models.ForeignKey(
    #                 'accounts.Teacher', on_delete=models.CASCADE,
    #                 related_name='teacher_subjects'
    #             )
    subject    = models.ForeignKey(
                    Subject, on_delete=models.CASCADE,
                    related_name='subject_teachers'
                )
    is_primary = models.BooleanField(default=False,
                    help_text='Is this the teacher\'s main / specialist subject?')
    notes      = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name        = 'Teacher Subject'
        verbose_name_plural = 'Teacher Subjects'
        unique_together     = [ 'subject']
        ordering            = [ '-is_primary']

    def __str__(self):
        flag = ' (Primary)' if self.is_primary else ''
        return f"{self.teacher.user.get_full_name()} → {self.subject.code}{flag}"


# ─────────────────────────────────────────────────────────────────────────────

class TeacherClass(TimeStampedModel):
    """
    Assignment of a teacher to teach a specific subject in a specific class
    for a given term. This is the timetable-level assignment.
    """
    # teacher      = models.ForeignKey(
    #                     'accounts.Teacher', on_delete=models.CASCADE,
    #                     related_name='teacher_class_assignments'
    #                 )
    school_class = models.ForeignKey(
                        SchoolClass, on_delete=models.CASCADE,
                        related_name='class_teacher_assignments'
                    )
    subject      = models.ForeignKey(
                        Subject, on_delete=models.CASCADE,
                        related_name='teaching_assignments'
                    )
    school_stream = models.ForeignKey(
                        SchoolStream, on_delete=models.CASCADE,
                        related_name='teaching_assessments',
                        null=True, blank=True
                    )
    term         = models.ForeignKey(
                        Term, on_delete=models.CASCADE,
                        related_name='teaching_assignments'
                    )
    periods_per_week = models.PositiveIntegerField(default=5,
                            help_text='Number of teaching periods per week')
    is_active    = models.BooleanField(default=True)
    notes        = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name        = 'Teacher Class Assignment'
        verbose_name_plural = 'Teacher Class Assignments'
        unique_together     = [ 'school_class', 'subject', 'term']
        ordering            = ['term', 'school_class', 'subject']

    def __str__(self):
        return (
            f"{self.teacher.user.get_full_name()} | "
            f"{self.school_class} | {self.subject.code} | {self.term}"
        )
