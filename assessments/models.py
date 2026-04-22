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
from academics.models import SchoolStream,SchoolSupportedClasses

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
    # paper_file        = models.FileField(
    #                         upload_to='assessments/papers/',
    #                         blank=True, null=True,
    #                         help_text='Upload the exam paper or task sheet (PDF, DOCX, image)'
    #                     )
    # marking_scheme    = models.FileField(
    #                         upload_to='assessments/schemes/',
    #                         blank=True, null=True,
    #                         help_text='Upload the marking guide / answer sheet (optional)'
    #                     )

    # Academic period
    term              = models.ForeignKey(
                            'academics.Term',
                            on_delete=models.CASCADE,
                            related_name='assessments'
                        )
    # academic_year     = models.CharField(max_length=9, help_text='Format: 2025/2026')
    month             = models.IntegerField(choices=MONTH_CHOICES,
                            help_text='Month this assessment was given')
    date_given        = models.DateField(help_text='Date the assessment was administered')
    date_due          = models.DateField(null=True, blank=True,
                            help_text='Submission deadline (for homework, projects, etc.)')
    date_results_released = models.DateField(null=True, blank=True,
                            help_text='Date results were / will be released')

    # Marks configuration
    # total_marks       = models.DecimalField(max_digits=7, decimal_places=1, default=100,
    #                         help_text='Default max marks (used per subject unless overridden)')
    # duration_minutes  = models.PositiveIntegerField(null=True, blank=True,
    #                         help_text='Time allowed in minutes')

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
                           SchoolSupportedClasses, on_delete=models.CASCADE,
                           related_name='class_assessment_links'
                       )
    students_attended = models.PositiveIntegerField(default=0,
                           help_text='Students expected to sit')
    class Meta:
        verbose_name        = 'Assessment Class'
        verbose_name_plural = 'Assessment Classes'
    @property
    def attendance_rate(self):
        if self.students_invited:
            return round((self.students_sat / self.students_invited) * 100, 1)
        return 0.0

    def __str__(self):
        return (
            f"{self.assessment.title} | {self.school_class}"
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
    assessment_class  = models.ForeignKey(
                      SchoolSupportedClasses, on_delete=models.CASCADE,
                      related_name='assessment_subject', null=True
                  )
    
    subject     = models.ForeignKey(
                      'academics.Subject', on_delete=models.CASCADE,
                      related_name='subject_assessment_links'
                  )
    passmark = models.DecimalField(max_digits=7, decimal_places=1,
                      help_text='Max marks for this subject in this assessment')
    

    notes       = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name        = 'Assessment Subject'
        verbose_name_plural = 'Assessment Subjects'
        ordering            = ['assessment', ]

        unique_together = ['assessment', 'assessment_class', 'subject']  # ← add assessment_class

    def __str__(self):
        return f"{self.assessment.title} | {self.subject.code} | Max: {self.passmark}"


# =============================================================================
# 4. ASSESSMENT TEACHER  —  Which teachers organised / marked / invigilated
# =============================================================================

class AssessmentTeacher(TimeStampedModel):
    """
    Links an Assessment to one or more Teachers and captures each teacher's role.
    A teacher can also be linked to a specific subject or class they handled.
    """
    # ROLE_CHOICES = [
    #     ('organiser',     'Organiser / Coordinator'),
    #     ('invigilator',   'Invigilator'),
    #     ('marker',        'Marker / Examiner'),
    #     ('setter',        'Paper Setter'),
    #     ('class_teacher', 'Class Teacher'),
    #     ('supervisor',    'Supervisor'),
    # ]

    assessment    = models.ForeignKey(
                        Assessment, on_delete=models.CASCADE,
                        related_name='assessment_teachers'
                    )
    teacher       = models.ForeignKey(
                        CustomUser, on_delete=models.CASCADE,
                        related_name='teacher_assessment_links'
                    )

    subject       = models.ForeignKey(
                        'academics.Subject', on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='subject_assessment_teachers',
                        help_text='Subject this teacher is responsible for (marker / setter)'
                    )
    school_class  = models.ForeignKey(
                        SchoolSupportedClasses, on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='class_assessment_teachers',
                        help_text='Class this teacher handled (invigilator / class_teacher)'
                    )
    class Meta:
        verbose_name        = 'Assessment Teacher'
        verbose_name_plural = 'Assessment Teachers'


    def __str__(self):
        subj = f" → {self.subject.code}" if self.subject else ''
        return (
            f"{self.assessment.title} | {self.teacher.user.get_full_name()} | "
            f"{self.get_role_display()}{subj}"
        )


# =============================================================================
# 5. ASSESSMENT PASS MARK  —  Per-subject passmark  (NEW MODEL)
# =============================================================================

class AssessmentTotalMark(TimeStampedModel):

    assessment  = models.ForeignKey(
                      Assessment, on_delete=models.CASCADE,
                      related_name='total_mark'
                  )
    subject     = models.ForeignKey(
                      AssessmentSubject, on_delete=models.CASCADE,
                      related_name='assessment_total_mark'
                  )

    total_mark  = models.DecimalField(max_digits=6, decimal_places=1,
                      help_text=(
                          'The total mark value. '
                          'percentage → e.g. 50.0 (means 50%). '
                          'absolute   → e.g. 45.0 (means 45 marks).'
                      ))
    class Meta:
        verbose_name        = 'Assessment Total Mark'
        verbose_name_plural = 'Assessment Total Marks'
        ordering            = ['assessment']

    def __str__(self):
        return self.assessment.assessment_type
    

# =============================================================================
# 6. ASSESSMENT PERFORMANCE  —  Per-student per-subject result
# =============================================================================

class AssessmentPerformance(TimeStampedModel):
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
                       related_name='assessment_performances'
                   )
    

    school_class = models.ForeignKey(
                       'academics.SchoolClass', on_delete=models.CASCADE,
                       related_name='assessment_performances'
                   )
    marks_obtained = models.DecimalField(max_digits=7, decimal_places=1,
                         null=True, blank=True,
                         help_text='Marks scored (Primary). Leave blank for Nursery.')
    # Attendance

    # Teacher feedback
    comment        = models.CharField(max_length=300, blank=True,
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
        ordering            = ['assessment', 'student__last_name', ]

    # Computed helpers

    def __str__(self):
        self.student.student_id




# class SchoolLowerClassesAssessmentPerfomanceType(TimeStampedModel):
#     pass


# class LowerClassesAssessmentPerfomanceEntryType(TimeStampedModel):
#     assessment = models.ForeignKey(Assessment, related_name='lower_class_assessment_perfomance_entry_type', on_delete=models.CASCADE)





class AssessmentModification(TimeStampedModel):
    """
    Controls which steps of an assessment are open for adding or editing.

    Normal flow (edit_once=False):
        Assessment created  → modify_class=True, all others False
        After class saved   → modify_class=False, modify_subject=True
        After subject saved → modify_subject=False, modify_total_mark=True
        After total saved   → modify_total_mark=False, modify_teacher=True
        After teacher saved → modify_teacher=False  (flow complete)

    Edit-once flow (edit_once=True):
        Admin manually turns on any combination of flags.
        Each step, after saving, turns itself OFF.
        When the last enabled step among (class/subject/total_mark/teacher)
        is saved, edit_once itself is also turned OFF.
        No chaining to next step — always redirects to assessment detail.
    """
    assessment        = models.OneToOneField(
                            Assessment,
                            on_delete=models.CASCADE,
                            related_name='modification'
                        )
    modify_class      = models.BooleanField(default=True)
    modify_subject    = models.BooleanField(default=False)
    modify_total_mark = models.BooleanField(default=False)
    modify_teacher    = models.BooleanField(default=False)
    modify_performance = models.BooleanField(default=False)
    edit_once         = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Assessment Modification'
        verbose_name_plural = 'Assessment Modifications'

    def __str__(self):
        return f"Modification — {self.assessment.title}"

    def remaining_edit_once_steps(self):
        """Count of still-enabled steps when in edit_once mode."""
        return sum([
            self.modify_class,
            self.modify_subject,
            self.modify_total_mark,
            self.modify_teacher,
        ])

    def close_edit_once_if_done(self):
        """
        Call after turning off a step.
        Closes edit_once if no steps remain enabled.
        Does NOT call save() — caller must do that.
        """
        if self.edit_once and self.remaining_edit_once_steps() == 0:
            self.edit_once = False









# ─────────────────────────────────────────────────────────────────────────────
# ADD THIS MODEL to your assessments/models.py
# It tracks per-class, per-subject entry progress for each assessment.
# ─────────────────────────────────────────────────────────────────────────────

class AssessmentPerformanceEntryStatus(models.Model):
    """
    Tracks how many students have had their performance entered for a given
    (assessment × class × subject) combination.

    Created automatically when the first performance-entry batch is submitted
    for a class/subject pair.  Updated each time more entries are saved.
    """

    assessment      = models.ForeignKey(
                          'Assessment',
                          on_delete=models.CASCADE,
                          related_name='entry_statuses',
                      )
    school_class    = models.ForeignKey(
                          'AssessmentClass',        # bridge model
                          on_delete=models.CASCADE,
                          related_name='entry_statuses',
                      )
    subject         = models.ForeignKey(
                          'AssessmentSubject',       # bridge model (per class)
                          on_delete=models.CASCADE,
                          related_name='entry_statuses',
                      )

    # ── Counters ──────────────────────────────────────────────────────────────
    students_attended = models.PositiveIntegerField(
                            default=0,
                            help_text='Total students enrolled in this class (from AssessmentClass).'
                        )
    students_entered  = models.PositiveIntegerField(
                            default=0,
                            help_text='Students whose mark for this subject has been saved so far.'
                        )
    students_left     = models.PositiveIntegerField(
                            default=0,
                            help_text='students_attended − students_entered.'
                        )
    students_passed   = models.PositiveIntegerField(default=0)
    students_tried    = models.PositiveIntegerField(
                            default=0,
                            help_text='Attempted but did not reach the pass mark.'
                        )

    # ── Status flags ─────────────────────────────────────────────────────────
    attendance_entry_met = models.BooleanField(
                               default=False,
                               help_text='True when students_entered >= students_attended.'
                           )
    is_edit_allowed      = models.BooleanField(
                               default=False,
                               help_text='Set to True via the enable-edit workflow.'
                           )
    is_done              = models.BooleanField(
                               default=False,
                               help_text='True when entry is complete and locked.'
                           )

    class Meta:
        verbose_name        = 'Performance Entry Status'
        verbose_name_plural = 'Performance Entry Statuses'
        unique_together     = [('assessment', 'school_class', 'subject')]
        ordering            = ['school_class', 'subject']

    def __str__(self):
        return (
            f"{self.assessment} | "
            f"{self.school_class.school_class.supported_class.name} | "
            f"{self.subject.subject.name} — "
            f"{self.students_entered}/{self.students_attended}"
        )