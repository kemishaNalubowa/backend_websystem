# fees/models.py
# ─────────────────────────────────────────────────────────────────────────────
# APP: fees
# MODELS: SchoolFees, FeesPayment, AssessmentFees
# ─────────────────────────────────────────────────────────────────────────────
# All monetary amounts are in Uganda Shillings (UGX).
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from academics.base import TimeStampedModel
from authentication.models import CustomUser
from academics.models import SchoolStream

class SchoolFees(TimeStampedModel):
    """
    Fee structure per class per term.
    Defines what each class owes for each fee category in a given term.
    Multiple fee types can exist per class per term (tuition, lunch, transport, etc.)
    """
    FEES_TYPE_CHOICES = [
        ('tuition',     'Tuition Fees'),
        ('development', 'Development / Building Levy'),
        ('activity',    'Activity / Games Fees'),
        ('lunch',       'Lunch / Feeding Fees'),
        ('transport',   'Transport / Bus Fees'),
        ('uniform',     'Uniform Fees'),
        ('boarding',    'Boarding Fees'),
        ('pta',         'PTA Contribution'),
        ('exam',        'Examination Fees'),
        ('admission',   'Admission / Registration Fees'),
        ('other',       'Other'),
    ]

    school_class  = models.ForeignKey(
                        'academics.SchoolSupportedClasses',
                        on_delete=models.CASCADE,
                        related_name='fee_structures'
                    )

    term          = models.ForeignKey(
                        'academics.Term',
                        on_delete=models.CASCADE,
                        related_name='fee_structures'
                    )
    fees_type     = models.CharField(max_length=20, choices=FEES_TYPE_CHOICES)
    title     = models.CharField(max_length=20,blank=True, null=True)
    
    amount        = models.DecimalField(max_digits=12, decimal_places=2,
                        help_text='Amount in Uganda Shillings (UGX)')
    description   = models.TextField(blank=True)
    due_date      = models.DateField(null=True, blank=True,
                        help_text='Payment deadline for this fee')
    is_compulsory = models.BooleanField(default=True)
    is_active     = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'School Fees Structure'
        verbose_name_plural = 'School Fees Structures'
        unique_together     = ['school_class', 'term', 'fees_type']
        ordering            = ['term', 'school_class', 'fees_type']

    def __str__(self):
        return (
            f"{self.school_class} | {self.get_fees_type_display()} | "
            f"{self.term} — UGX {self.amount:,.0f}"
        )


# ─────────────────────────────────────────────────────────────────────────────

class FeesPayment(TimeStampedModel):
    """
    Records an actual payment made by a parent/guardian for a student.
    """
    receipt_number   = models.CharField(max_length=30, unique=True,
                           help_text='Auto-generated receipt number e.g. RCP2025001')
    student          = models.ForeignKey(
                           'students.Student',
                           on_delete=models.CASCADE,
                           related_name='fee_payments'
                       )
    term             = models.ForeignKey(
                           'academics.Term',
                           on_delete=models.CASCADE,
                           related_name='fee_payments'
                       )
    school_fees      = models.ForeignKey(
                           SchoolFees,
                           on_delete=models.CASCADE,
                           related_name='payments',
                           help_text='Which fee item this payment is for'
                       )
    school_class      = models.ForeignKey(
                           'academics.SchoolClass',
                           on_delete=models.CASCADE,
                           related_name='school_class',
                           help_text='Which Class the student in'
                       )
    school_stream = models.ForeignKey(
                        SchoolStream, on_delete=models.CASCADE,
                        related_name='fees_payments',
                        null=True, blank=True
                    )
    
    
    amount_paid      = models.DecimalField(max_digits=12, decimal_places=2,
                           help_text='Amount paid in UGX')
    payment_date     = models.DateField()


    def __str__(self):
        return (
            f"RCP {self.receipt_number} | {self.student}"
        )


# ─────────────────────────────────────────────────────────────────────────────

class AssessmentFees(TimeStampedModel):
    """
    Fees assessment / statement for a student for a given term.
    Summarises total fees required, total paid, and outstanding balance.
    Auto-updated (or computed via signal / view) whenever a payment is made.
    """
    student          = models.ForeignKey(
                           'students.Student',
                           on_delete=models.CASCADE,
                           related_name='fee_assessments'
                       )
    term             = models.ForeignKey(
                           'academics.Term',
                           on_delete=models.CASCADE,
                           related_name='student_fee_assessments'
                       )
    total_required   = models.DecimalField(max_digits=12, decimal_places=2,
                           help_text='Sum of all compulsory fees for this student this term (UGX)')
    total_paid       = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                           help_text='Total amount paid so far this term (UGX)')
    balance          = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                           help_text='Outstanding balance = total_required − total_paid (UGX)')
    discount_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                           help_text='Any approved fee discount e.g. staff child, scholarship (UGX)')
    discount_reason  = models.CharField(max_length=200, blank=True)
    is_cleared       = models.BooleanField(default=False,
                           help_text='True when balance is fully paid')
    last_payment_date= models.DateField(null=True, blank=True)
    generated_by     = models.ForeignKey(
                           CustomUser,
                           on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='fee_assessments_generated'
                       )
    notes            = models.TextField(blank=True)

    class Meta:
        verbose_name        = 'Fees Assessment'
        verbose_name_plural = 'Fees Assessments'
        unique_together     = ['student', 'term']
        ordering            = [ 'term__name', 'student__last_name']

    def save(self, *args, **kwargs):
        # Auto-compute balance on every save
        self.balance = self.total_required - self.discount_amount - self.total_paid
        self.is_cleared = self.balance <= 0
        super().save(*args, **kwargs)

    def __str__(self):
        status = 'CLEARED' if self.is_cleared else f'BALANCE UGX {self.balance:,.0f}'
        return f"{self.student} | {self.term} | {status}"
