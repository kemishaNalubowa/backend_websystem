# assessments/models.py
# ─────────────────────────────────────────────────────────────────────────────
# APP: assessments
# ─────────────────────────────────────────────────────────────────────────────
# Uganda Academic Context
#   Exam types : BOT · MOT · EOT · Test · Exercise · Quiz · Mock · PLE Prelims
#   Grading    : Marks out of configurable total; percentage-based or absolute
#   Divisions  : Used at upper primary (P4–P7) and especially PLE (P7)
#   Nursery    : Developmental ratings instead of marks
# ─────────────────────────────────────────────────────────────────────────────
# MODEL OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
#  Assessment            — Master record for every assessment given
#  AssessmentClass       — Bridge: which classes sat this assessment
#  AssessmentSubject     — Bridge: which subjects are in this assessment
#  AssessmentTeacher     — Bridge: which teachers organised / invigilated / marked
#  AssessmentPassMark    — Passmark per subject (set per teacher per assessment)
#  AssessmentPerformance — Per-student per-subject result (marks, grade, pass/fail)
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from academics.base import TimeStampedModel
from authentication.models import CustomUser

ASSESSMENT_TYPE_CHOICES = [
    ('bot',       'Beginning of Term Exam (BOT)'),
    ('mot',       'Middle of Term Exam (MOT)'),
    ('eot',       'End of Term Exam (EOT)'),
    ('test',      'Class Test'),
    ('exercise',  'Exercise / Classwork'),
    ('quiz',      'Quiz'),
    ('mock',      'Mock Examination'),
    ('ple',       'PLE / Prelims'),
    ('homework',  'Homework'),
    ('project',   'Project / Assignment'),
    ('practical', 'Practical / Oral'),
    ('other',     'Other'),
]

MONTH_CHOICES = [
    (1,  'January'),  (2,  'February'), (3,  'March'),
    (4,  'April'),    (5,  'May'),      (6,  'June'),
    (7,  'July'),     (8,  'August'),   (9,  'September'),
    (10, 'October'),  (11, 'November'), (12, 'December'),
]


# =============================================================================
# 1. ASSESSMENT  —  Master Record
# =============================================================================

class Assessment(TimeStampedModel):
    """
    The central record for every assessment given by the school.
    An assessment can span multiple classes, subjects, and teachers — those
    are captured via the bridge models AssessmentClass, AssessmentSubject,
    and AssessmentTeacher.

    Examples:
        "Term 1 BOT Exams 2026"  — type=bot,  multi-class, multi-subject
        "P3 Mathematics Test"    — type=test, single class, single subject
        "Weekly Science Quiz"    — type=quiz, single class, single subject
        "P7 Mock Exams 2026"     — type=mock, multi-class, multi-subject
    """
    title             = models.CharField(max_length=200,
                            help_text='E.g. "Term 1 BOT Exams 2026" or "P4 Maths Test Week 3"')
    assessment_type   = models.CharField(max_length=20, choices=ASSESSMENT_TYPE_CHOICES)
    description       = models.TextField(blank=True,
                            help_text='Instructions or notes about this assessment')

    # Paper / task file
    paper_file        = models.FileField(
                            upload_to='assessments/papers/',
                            blank=True, null=True,
                            help_text='Upload the exam paper or task sheet (PDF, DOCX, image)'
                        )
    marking_scheme    = models.FileField(
                            upload_to='assessments/schemes/',
                            blank=True, null=True,
                            help_text='Upload the marking guide / answer sheet (optional)'
                        )

    # Academic period
    term              = models.ForeignKey(
                            'academics.Term',
                            on_delete=models.CASCADE,
                            related_name='assessments'
                        )
    academic_year     = models.CharField(max_length=9, help_text='Format: 2025/2026')
    month             = models.IntegerField(choices=MONTH_CHOICES,
                            help_text='Month this assessment was given')
    date_given        = models.DateField(help_text='Date the assessment was administered')
    date_due          = models.DateField(null=True, blank=True,
                            help_text='Submission deadline (for homework, projects, etc.)')
    date_results_released = models.DateField(null=True, blank=True,
                            help_text='Date results were / will be released')

    # Marks configuration
    total_marks       = models.DecimalField(max_digits=7, decimal_places=1, default=100,
                            help_text='Default max marks (used per subject unless overridden)')
    duration_minutes  = models.PositiveIntegerField(null=True, blank=True,
                            help_text='Time allowed in minutes')

    # Status and visibility
    is_published      = models.BooleanField(default=False,
                            help_text='Visible to teachers for mark entry when True')
    results_published = models.BooleanField(default=False,
                            help_text='Results visible to parents on the portal when True')

    created_by        = models.ForeignKey(
                            CustomUser,
                            on_delete=models.SET_NULL,
                            null=True,
                            related_name='assessments_created'
                        )
    notes             = models.TextField(blank=True, help_text='Internal admin notes')

    class Meta:
        verbose_name        = 'Assessment'
        verbose_name_plural = 'Assessments'
        ordering            = ['-date_given', 'assessment_type']

    @property
    def total_students_sat(self):
        return self.assessment_classes.aggregate(
            total=models.Sum('students_sat')
        )['total'] or 0

    @property
    def total_students_invited(self):
        return self.assessment_classes.aggregate(
            total=models.Sum('students_invited')
        )['total'] or 0

    def __str__(self):
        return f"{self.title} | {self.get_assessment_type_display()} | {self.term}"


# =============================================================================
# 2. ASSESSMENT CLASS  —  Which classes sat this assessment
# =============================================================================

class AssessmentClass(TimeStampedModel):
    """
    Links an Assessment to one or more SchoolClasses.
    Captures class-level attendance statistics for analytics.
    One Assessment can have many AssessmentClass rows (one per class involved).
    """
    VENUE_CHOICES = [
        ('classroom', 'Own Classroom'),
        ('hall',      'Assembly Hall'),
        ('library',   'Library'),
        ('lab',       'Science / Computer Lab'),
        ('outdoor',   'Outdoor / Grounds'),
        ('other',     'Other'),
    ]

    assessment       = models.ForeignKey(
                           Assessment, on_delete=models.CASCADE,
                           related_name='assessment_classes'
                       )
    school_class     = models.ForeignKey(
                           'academics.SchoolClass', on_delete=models.CASCADE,
                           related_name='class_assessment_links'
                       )
    students_invited = models.PositiveIntegerField(default=0,
                           help_text='Students expected to sit')
    students_sat     = models.PositiveIntegerField(default=0,
                           help_text='Students who actually sat')
    students_absent  = models.PositiveIntegerField(default=0)
    venue            = models.CharField(max_length=20, choices=VENUE_CHOICES, blank=True)
    invigilator      = models.ForeignKey(
                           CustomUser, on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='invigilated_classes'
                       )
    start_time       = models.TimeField(null=True, blank=True)
    end_time         = models.TimeField(null=True, blank=True)
    class_remarks    = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name        = 'Assessment Class'
        verbose_name_plural = 'Assessment Classes'
        unique_together     = ['assessment', 'school_class']
        ordering            = ['assessment', 'school_class']

    @property
    def attendance_rate(self):
        if self.students_invited:
            return round((self.students_sat / self.students_invited) * 100, 1)
        return 0.0

    def __str__(self):
        return (
            f"{self.assessment.title} | {self.school_class} | "
            f"Sat: {self.students_sat}/{self.students_invited}"
        )


# =============================================================================
# 3. ASSESSMENT SUBJECT  —  Which subjects are in this assessment
# =============================================================================

class AssessmentSubject(TimeStampedModel):
    """
    Links an Assessment to one or more Subjects.
    Defines the total marks available per subject in this assessment.
    The passmark per subject is stored in AssessmentPassMark (separate model).

    Examples:
        BOT Exam:      English(100), Maths(100), Science(100), SST(100)
        Weekly Quiz:   Mathematics(20)
    """
    assessment  = models.ForeignKey(
                      Assessment, on_delete=models.CASCADE,
                      related_name='assessment_subjects'
                  )
    subject     = models.ForeignKey(
                      'academics.Subject', on_delete=models.CASCADE,
                      related_name='subject_assessment_links'
                  )
    total_marks = models.DecimalField(max_digits=7, decimal_places=1,
                      help_text='Max marks for this subject in this assessment')
    paper_file  = models.FileField(
                      upload_to='assessments/subject_papers/',
                      blank=True, null=True,
                      help_text='Subject-specific paper (if different from main paper)'
                  )
    sort_order  = models.PositiveIntegerField(default=0,
                      help_text='Order on report e.g. 1=English, 2=Maths')
    notes       = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name        = 'Assessment Subject'
        verbose_name_plural = 'Assessment Subjects'
        unique_together     = ['assessment', 'subject']
        ordering            = ['assessment', 'sort_order', 'subject__sort_order']

    def __str__(self):
        return f"{self.assessment.title} | {self.subject.code} | Max: {self.total_marks}"


# =============================================================================
# 4. ASSESSMENT TEACHER  —  Which teachers organised / marked / invigilated
# =============================================================================

class AssessmentTeacher(TimeStampedModel):
    """
    Links an Assessment to one or more Teachers and captures each teacher's role.
    A teacher can also be linked to a specific subject or class they handled.
    """
    ROLE_CHOICES = [
        ('organiser',     'Organiser / Coordinator'),
        ('invigilator',   'Invigilator'),
        ('marker',        'Marker / Examiner'),
        ('setter',        'Paper Setter'),
        ('class_teacher', 'Class Teacher'),
        ('supervisor',    'Supervisor'),
    ]

    assessment    = models.ForeignKey(
                        Assessment, on_delete=models.CASCADE,
                        related_name='assessment_teachers'
                    )
    teacher       = models.ForeignKey(
                        CustomUser, on_delete=models.CASCADE,
                        related_name='teacher_assessment_links'
                    )
    role          = models.CharField(max_length=20, choices=ROLE_CHOICES)
    subject       = models.ForeignKey(
                        'academics.Subject', on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='subject_assessment_teachers',
                        help_text='Subject this teacher is responsible for (marker / setter)'
                    )
    school_class  = models.ForeignKey(
                        'academics.SchoolClass', on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='class_assessment_teachers',
                        help_text='Class this teacher handled (invigilator / class_teacher)'
                    )
    notes         = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name        = 'Assessment Teacher'
        verbose_name_plural = 'Assessment Teachers'
        unique_together     = ['assessment', 'teacher', 'role']
        ordering            = ['assessment', 'role', 'teacher']

    def __str__(self):
        subj = f" → {self.subject.code}" if self.subject else ''
        return (
            f"{self.assessment.title} | {self.teacher.user.get_full_name()} | "
            f"{self.get_role_display()}{subj}"
        )


# =============================================================================
# 5. ASSESSMENT PASS MARK  —  Per-subject passmark  (NEW MODEL)
# =============================================================================

class AssessmentPassMark(TimeStampedModel):
    """
    Defines the passmark for a specific subject in a specific assessment.
    Each teacher can set a different passmark per subject per assessment.

    Examples:
        English in BOT Exam  → 50%  (set by English teacher)
        Maths in BOT Exam    → 45%  (set by Maths teacher)
        Science in MOT Test  → 65%  (set by Science teacher)

    pass_type:
        'percentage' — value expressed as % of total_marks e.g. 50.0 means 50%
        'absolute'   — value expressed as raw marks e.g. 45.0 means 45 marks
    """
    PASS_TYPE_CHOICES = [
        ('percentage', 'Percentage of total marks'),
        ('absolute',   'Absolute marks'),
    ]

    assessment  = models.ForeignKey(
                      Assessment, on_delete=models.CASCADE,
                      related_name='pass_marks'
                  )
    subject     = models.ForeignKey(
                      'academics.Subject', on_delete=models.CASCADE,
                      related_name='assessment_pass_marks'
                  )
    pass_type   = models.CharField(max_length=15, choices=PASS_TYPE_CHOICES,
                      default='percentage')
    pass_value  = models.DecimalField(max_digits=6, decimal_places=1,
                      help_text=(
                          'The passmark value. '
                          'percentage → e.g. 50.0 (means 50%). '
                          'absolute   → e.g. 45.0 (means 45 marks).'
                      ))
    set_by      = models.ForeignKey(
                      CustomUser, on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='pass_marks_set',
                      help_text='The teacher who set this passmark'
                  )
    approved_by = models.ForeignKey(
                      CustomUser, on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='pass_marks_approved',
                      help_text='Head teacher or admin who approved this passmark'
                  )
    notes       = models.CharField(max_length=200, blank=True,
                      help_text='E.g. "Adjusted because paper was difficult"')

    class Meta:
        verbose_name        = 'Assessment Pass Mark'
        verbose_name_plural = 'Assessment Pass Marks'
        unique_together     = ['assessment', 'subject']
        ordering            = ['assessment', 'subject__sort_order']

    def get_absolute_pass_mark(self, total_marks):
        """
        Returns the passmark as a raw mark value.
        Pass total_marks from AssessmentSubject.total_marks.
        """
        if self.pass_type == 'percentage':
            return round((float(self.pass_value) / 100) * float(total_marks), 1)
        return float(self.pass_value)

    def __str__(self):
        display  = f"{self.pass_value}%" if self.pass_type == 'percentage' else f"{self.pass_value} marks"
        teacher  = self.set_by.user.get_full_name() if self.set_by else 'N/A'
        return (
            f"{self.assessment.title} | {self.subject.code} | "
            f"Passmark: {display} | Set by: {teacher}"
        )


# =============================================================================
# 6. ASSESSMENT PERFORMANCE  —  Per-student per-subject result
# =============================================================================

class AssessmentPerformance(TimeStampedModel):
    """
    Records every student's result for every subject in an assessment.
    One row = one student × one subject × one assessment.

    Pass/fail is auto-computed on save by comparing marks_obtained
    against AssessmentPassMark for that subject.

    Supports both:
        Primary  — numerical marks + computed UNEB-style grade (D1–F9)
        Nursery  — developmental rating (EE / ME / AE / NS)

    Analytics entry points:
        Per student   → filter by student + assessment
        Per subject   → filter by subject + assessment
        Per class     → filter by school_class + assessment
        Per teacher   → via AssessmentTeacher, then filter performances for their subjects
    """
    GRADE_CHOICES = [
        ('D1', 'Distinction 1 (90–100%)'),
        ('D2', 'Distinction 2 (80–89%)'),
        ('C3', 'Credit 3 (70–79%)'),
        ('C4', 'Credit 4 (65–69%)'),
        ('C5', 'Credit 5 (60–64%)'),
        ('C6', 'Credit 6 (55–59%)'),
        ('P7', 'Pass 7 (45–54%)'),
        ('P8', 'Pass 8 (35–44%)'),
        ('F9', 'Fail 9 (0–34%)'),
    ]
    NURSERY_RATING_CHOICES = [
        ('EE', 'Exceeds Expectations'),
        ('ME', 'Meets Expectations'),
        ('AE', 'Approaching Expectations'),
        ('NS', 'Needs Support'),
    ]

    # Core links
    assessment   = models.ForeignKey(
                       Assessment, on_delete=models.CASCADE,
                       related_name='performances'
                   )
    student      = models.ForeignKey(
                       'students.Student', on_delete=models.CASCADE,
                       related_name='assessment_performances'
                   )
    subject      = models.ForeignKey(
                       'academics.Subject', on_delete=models.CASCADE,
                       related_name='student_performances'
                   )
    school_class = models.ForeignKey(
                       'academics.SchoolClass', on_delete=models.CASCADE,
                       related_name='assessment_performances'
                   )

    # Marks (Primary)
    marks_obtained = models.DecimalField(max_digits=7, decimal_places=1,
                         null=True, blank=True,
                         help_text='Marks scored (Primary). Leave blank for Nursery.')
    total_marks    = models.DecimalField(max_digits=7, decimal_places=1,
                         help_text='Max marks available for this subject in this assessment')
    grade          = models.CharField(max_length=5, choices=GRADE_CHOICES, blank=True,
                         help_text='Auto-computed UNEB-style grade on save')

    # Nursery developmental rating
    nursery_rating = models.CharField(max_length=5, choices=NURSERY_RATING_CHOICES, blank=True,
                         help_text='Developmental rating for Nursery (Baby–Top Class)')

    # Pass / fail — auto-computed against AssessmentPassMark
    is_pass        = models.BooleanField(null=True, blank=True,
                         help_text='Auto-computed vs AssessmentPassMark. Null = not yet computed.')

    # Attendance
    is_absent      = models.BooleanField(default=False)
    absent_reason  = models.CharField(max_length=200, blank=True,
                         help_text='E.g. "Sick", "Travel", "Family emergency"')

    # Teacher feedback
    remarks        = models.CharField(max_length=300, blank=True,
                         help_text='Subject teacher remark e.g. "Excellent" or "Needs more reading"')
    entered_by     = models.ForeignKey(
                         CustomUser, on_delete=models.SET_NULL,
                         null=True, blank=True,
                         related_name='performances_entered',
                         help_text='Teacher / staff who entered these marks'
                     )
    verified_by    = models.ForeignKey(
                         CustomUser, on_delete=models.SET_NULL,
                         null=True, blank=True,
                         related_name='performances_verified',
                         help_text='Head teacher / second marker who verified the marks'
                     )
    is_verified    = models.BooleanField(default=False,
                         help_text='True when marks have been verified by authorised staff')

    class Meta:
        verbose_name        = 'Assessment Performance'
        verbose_name_plural = 'Assessment Performances'
        unique_together     = ['assessment', 'student', 'subject']
        ordering            = ['assessment', 'school_class', 'student__last_name', 'subject__sort_order']

    # Computed helpers

    @property
    def percentage(self):
        if self.marks_obtained is not None and self.total_marks:
            return round(float(self.marks_obtained) / float(self.total_marks) * 100, 1)
        return None

    def _compute_grade(self, pct):
        if pct is None:
            return ''
        if pct >= 90: return 'D1'
        if pct >= 80: return 'D2'
        if pct >= 70: return 'C3'
        if pct >= 65: return 'C4'
        if pct >= 60: return 'C5'
        if pct >= 55: return 'C6'
        if pct >= 45: return 'P7'
        if pct >= 35: return 'P8'
        return 'F9'

    def _compute_pass(self):
        if self.marks_obtained is None or self.is_absent:
            return None
        try:
            pm = AssessmentPassMark.objects.get(
                assessment=self.assessment,
                subject=self.subject
            )
            threshold = pm.get_absolute_pass_mark(float(self.total_marks))
            return float(self.marks_obtained) >= threshold
        except AssessmentPassMark.DoesNotExist:
            return None

    def save(self, *args, **kwargs):
        pct = self.percentage
        if pct is not None and not self.nursery_rating:
            self.grade = self._compute_grade(pct)
        self.is_pass = self._compute_pass()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.is_absent:
            status = 'ABSENT'
        elif self.nursery_rating:
            status = self.nursery_rating
        elif self.marks_obtained is not None:
            status = f"{self.marks_obtained}/{self.total_marks} ({self.percentage}%) {self.grade}"
        else:
            status = 'Not entered'
        pass_flag = ' PASS' if self.is_pass is True else (' FAIL' if self.is_pass is False else '')
        return f"{self.student} | {self.subject.code} | {self.assessment.title} | {status}{pass_flag}"
