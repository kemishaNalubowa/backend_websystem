# =============================================================================
# fees/models.py  —  CORRECTED & EXTENDED
# =============================================================================
#
# MODELS
# ─────────────────────────────────────────────────────────────────────────────
#  SchoolFees                          — monetary fee structure per term
#  AssessmentFees                      — fee tied to a specific Assessment
#  FeesClass                           — bridge: fee / assessment_fee → class(es)
#  FeesPayment                         — one actual cash transaction receipt
#  StudentFeesPaymentsStatus           — running balance per student per fee
#  StudentClassPromotion               — full class-history / promotion trail
#  SchoolScholasticRequirements        — physical/cash items required per class per term
#  ScholasticRequirementClass          — bridge: requirement → class(es)
#  StudentScholasticRequirementStatus  — hybrid physical + cash tracker per student
#
# KEY DECISIONS & FIXES APPLIED
# ─────────────────────────────────────────────────────────────────────────────
#  FIX 1 — related_name clashes resolved.
#           FeesPayment and StudentFeesPaymentsStatus previously shared 4
#           identical related_names across student, school_fees,
#           assessment_fees, and school_class FKs. All renamed and unique.
#
#  FIX 2 — FeesPayment.school_fees / .assessment_fees are now both nullable.
#           Exactly one must be populated — enforced in clean().
#
#  FIX 3 — StudentFeesPaymentsStatus.school_fees / .assessment_fees are now
#           both nullable. Exactly one must be populated — enforced in clean().
#           unique_together added: (student, school_fees) and
#           (student, assessment_fees) prevent duplicate status rows.
#
#  FIX 4 — StudentClassPromotion.year_year renamed to to_year (was a typo).
#
#  FIX 5 — FeesClass.clean() enforces exactly one of fees / assessment_fee.
#           FeesClass.__str__ no longer crashes when fees is None.
#
#  FIX 6 — AssessmentFees is written expecting AssessmentClass.school_class
#           to point to SchoolSupportedClasses (the planned update).
#           The comment in FeesClass and below makes this explicit.
#
#  NEW   — SchoolScholasticRequirements (hybrid physical + cash item).
#  NEW   — ScholasticRequirementClass (bridge: requirement → class).
#  NEW   — StudentScholasticRequirementStatus (per-student tracker).
# =============================================================================

from django.db import models
from django.core.exceptions import ValidationError

from academics.base import TimeStampedModel
from authentication.models import CustomUser
from academics.models import SchoolSupportedClasses
from assessments.models import Assessment


# ─────────────────────────────────────────────────────────────────────────────
# SHARED CHOICES
# ─────────────────────────────────────────────────────────────────────────────

PAYMENT_TYPE_CHOICES = [
    ('school',     'School Fees Payment'),
    ('assessment', 'Assessment Fees Payment'),
]


# =============================================================================
# 1. SCHOOL FEES
# =============================================================================

class SchoolFees(TimeStampedModel):
    """
    A single monetary fee line defined by admin for a given term.
    Which class(es) it applies to is declared in FeesClass (bridge).
    All amounts are Uganda Shillings (UGX).

    Examples:
        fees_type='tuition', amount=250000  — Tuition Term 1 2024
        fees_type='lunch',   amount=60000   — Lunch Term 2 2024
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

    term        = models.ForeignKey(
                      'academics.Term',
                      on_delete=models.CASCADE,
                      related_name='fee_structures'
                  )
    fees_type   = models.CharField(max_length=20, choices=FEES_TYPE_CHOICES)
    title       = models.CharField(
                      max_length=100, blank=True, null=True,
                      help_text='Optional label when fees_type alone is ambiguous'
                  )
    amount      = models.DecimalField(
                      max_digits=12, decimal_places=2,
                      help_text='Amount in Uganda Shillings (UGX)'
                  )
    description = models.TextField(blank=True)
    due_date    = models.DateField(null=True, blank=True,
                      help_text='Payment deadline for this fee')
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'School Fees Structure'
        verbose_name_plural = 'School Fees Structures'
        ordering            = ['term', 'fees_type']

    def __str__(self):
        label = self.title or self.get_fees_type_display()
        return f"{label} | {self.term} — UGX {self.amount:,.0f}"


# =============================================================================
# 2. ASSESSMENT FEES
# =============================================================================

class AssessmentFees(TimeStampedModel):
    """
    A monetary fee tied specifically to an Assessment record.
    Example: BOT exam fee Term 1 2024 — UGX 5,000.

    Which class(es) this applies to flows from the Assessment's own class
    links:  Assessment → AssessmentClass → SchoolSupportedClasses
    (AssessmentClass.school_class WILL point to SchoolSupportedClasses
    after the planned update — all logic here is written for that state.)

    Admin can further narrow or override class assignment via FeesClass.
    """

    term         = models.ForeignKey(
                       'academics.Term',
                       on_delete=models.CASCADE,
                       related_name='student_fee_assessments'
                   )
    # AssessmentClass.school_class → SchoolSupportedClasses (after update)
    assessment   = models.ForeignKey(
                       Assessment,
                       on_delete=models.CASCADE,
                       related_name='assessment_fee',
                       null=True, blank=True
                   )
    amount       = models.DecimalField(
                       max_digits=12, decimal_places=2,
                       null=True,
                       help_text='Amount in Uganda Shillings (UGX)'
                   )
    due_date     = models.DateField(null=True, blank=True,
                       help_text='Payment deadline for this assessment fee')
    generated_by = models.ForeignKey(
                       CustomUser,
                       on_delete=models.SET_NULL,
                       null=True, blank=True,
                       related_name='fee_assessments_generated'
                   )

    class Meta:
        verbose_name        = 'Assessment Fee'
        verbose_name_plural = 'Assessment Fees'
        ordering            = ['term__name']

    def __str__(self):
        return f"Assessment Fee | {self.assessment} | {self.term}"


# =============================================================================
# 3. FEES CLASS  (Bridge)
# =============================================================================

class FeesClass(TimeStampedModel):
    """
    Bridge: one fee line × one class.
    Create multiple rows to apply the same fee to multiple classes.

    Exactly one of `fees` or `assessment_fee` must be non-null per row.
    `school_class` always points to SchoolSupportedClasses.
    """

    fees           = models.ForeignKey(
                         SchoolFees,
                         on_delete=models.CASCADE,
                         related_name='affected_school_class',
                         null=True, blank=True
                     )
    assessment_fee = models.ForeignKey(
                         AssessmentFees,
                         on_delete=models.CASCADE,
                         related_name='assessment_fee_affected_class',
                         null=True, blank=True
                     )
    school_class   = models.ForeignKey(
                         SchoolSupportedClasses,
                         on_delete=models.CASCADE,
                         related_name='affected_fees_class'
                     )

    class Meta:
        verbose_name        = 'Fees Class Assignment'
        verbose_name_plural = 'Fees Class Assignments'
        unique_together     = [
            ('fees',           'school_class'),
            ('assessment_fee', 'school_class'),
        ]

    def clean(self):
        has_fees       = self.fees_id is not None
        has_assessment = self.assessment_fee_id is not None

        if has_fees and has_assessment:
            raise ValidationError(
                'FeesClass must link to either SchoolFees OR AssessmentFees — not both.'
            )
        if not has_fees and not has_assessment:
            raise ValidationError(
                'FeesClass must link to at least one of SchoolFees or AssessmentFees.'
            )

    def __str__(self):
        if self.fees:
            fee_label = self.fees.title or self.fees.get_fees_type_display()
        elif self.assessment_fee:
            fee_label = str(self.assessment_fee)
        else:
            fee_label = '(no fee linked)'
        return f"{fee_label} → {self.school_class}"


# =============================================================================
# 4. FEES PAYMENT
# =============================================================================

class FeesPayment(TimeStampedModel):
    """
    One actual payment transaction — produces one receipt.

    school_class records which class the student was in AT THE TIME of payment.
    This is critical for historical audit even after the student is promoted.

    Exactly one of school_fees / assessment_fees must be non-null.
    Enforced in clean().
    """ 

    receipt_number  = models.CharField(
                          max_length=30, unique=True,
                          help_text='Auto-generated e.g. RCP2025001'
                      )
    student         = models.ForeignKey(
                          'students.Student',
                          on_delete=models.CASCADE,
                          related_name='fees_payment_records'           # FIX 1
                      )
    term            = models.ForeignKey(
                          'academics.Term',
                          on_delete=models.CASCADE,
                          related_name='fees_payment_records'           # FIX 1
                      )
    school_fees     = models.ForeignKey(
                          SchoolFees,
                          on_delete=models.CASCADE,
                          related_name='fee_payment_transactions',       # FIX 1
                          null=True, blank=True,                         # FIX 2
                          help_text='Populated when paying a school fee line'
                      )
    assessment_fees = models.ForeignKey(
                          AssessmentFees,
                          on_delete=models.CASCADE,
                          related_name='assessment_fee_transactions',    # FIX 1
                          null=True, blank=True,                         # FIX 2
                          help_text='Populated when paying an assessment fee line'
                      )
    school_class    = models.ForeignKey(
                          SchoolSupportedClasses,
                          on_delete=models.CASCADE,
                          related_name='fees_payment_records',           # FIX 1
                          help_text="Student's class AT THE TIME of payment"
                      )
    amount          = models.DecimalField(
                          max_digits=12, decimal_places=2,
                          help_text='Amount paid in UGX'
                      )
    payment_date    = models.DateField()
    handled_by      = models.ForeignKey(
                          CustomUser,
                          on_delete=models.SET_NULL,
                          null=True,
                          related_name='payments_handled'
                      )

    class Meta:
        verbose_name        = 'Fees Payment'
        verbose_name_plural = 'Fees Payments'
        ordering            = ['-payment_date', '-created_at']

    def clean(self):
        has_school     = self.school_fees_id is not None
        has_assessment = self.assessment_fees_id is not None

        if has_school and has_assessment:
            raise ValidationError(
                'A payment must reference either SchoolFees OR AssessmentFees — not both.'
            )
        if not has_school and not has_assessment:
            raise ValidationError(
                'A payment must reference at least one of SchoolFees or AssessmentFees.'
            )

    def __str__(self):
        return f"RCP {self.receipt_number} | {self.student}"


# =============================================================================
# 5. STUDENT FEES PAYMENT STATUS
# =============================================================================

class StudentFeesPaymentsStatus(TimeStampedModel):
    """
    Running balance tracker — one row per (student × fee line).
    Updated each time a FeesPayment is saved.

    amount_balance = fee.amount − amount_paid
    fully_paid flips True when amount_balance reaches 0 or below.

    This is the PRIMARY model the pending-fees query reads to determine
    what a student still owes. It is also the model that gets created
    automatically (with amount_paid=0, amount_balance=fee.amount) the first
    time a student becomes liable for a fee.

    Exactly one of school_fees / assessment_fees must be non-null.
    """

    student         = models.ForeignKey(
                          'students.Student',
                          on_delete=models.CASCADE,
                          related_name='fee_payment_status_records'     # FIX 1
                      )
    payment_type    = models.CharField(max_length=25, choices=PAYMENT_TYPE_CHOICES)
    school_fees     = models.ForeignKey(
                          SchoolFees,
                          on_delete=models.CASCADE,
                          related_name='student_payment_statuses',      # FIX 1
                          null=True, blank=True,                         # FIX 3
                          help_text='Populated when tracking a school fee balance'
                      )
    assessment_fees = models.ForeignKey(
                          AssessmentFees,
                          on_delete=models.CASCADE,
                          related_name='student_assessment_statuses',   # FIX 1
                          null=True, blank=True,                         # FIX 3
                          help_text='Populated when tracking an assessment fee balance'
                      )
    school_class    = models.ForeignKey(
                          SchoolSupportedClasses,
                          on_delete=models.CASCADE,
                          related_name='fee_status_records',            # FIX 1
                          help_text="Student's class when this status row was created"
                      )
    amount_paid     = models.DecimalField(
                          max_digits=12, decimal_places=2,
                          default=0,
                          help_text='Cumulative amount paid so far in UGX'
                      )
    amount_balance  = models.DecimalField(
                          max_digits=12, decimal_places=2,
                          help_text='Remaining balance in UGX'
                      )
    fully_paid      = models.BooleanField(default=False)
    fully_paid_on   = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Student Fees Payment Status'
        verbose_name_plural = 'Student Fees Payment Statuses'
        unique_together     = [                                         # FIX 3
            ('student', 'school_fees'),
            ('student', 'assessment_fees'),
        ]
        ordering = ['student', 'payment_type']

    def clean(self):
        has_school     = self.school_fees_id is not None
        has_assessment = self.assessment_fees_id is not None

        if has_school and has_assessment:
            raise ValidationError(
                'A status row must reference either SchoolFees OR AssessmentFees — not both.'
            )
        if not has_school and not has_assessment:
            raise ValidationError(
                'A status row must reference at least one of SchoolFees or AssessmentFees.'
            )

    def __str__(self):
        if self.payment_type == 'school' and self.school_fees:
            label = self.school_fees.title or self.school_fees.get_fees_type_display()
        elif self.payment_type == 'assessment' and self.assessment_fees:
            label = str(self.assessment_fees)
        else:
            label = '(unknown fee)'
        status = 'CLEARED' if self.fully_paid else f'BAL UGX {self.amount_balance:,.0f}'
        return f"{self.student.student_id} | {label} | {status}"


# =============================================================================
# 6. STUDENT CLASS PROMOTION
# =============================================================================

class StudentClassPromotion(TimeStampedModel):
    """
    One row per promotion event for a student.
    This is the backbone of the pending-fees query: we walk this table to
    reconstruct which class a student was in during every year of their
    school life, then match fees accordingly.

    Example rows for one student:
        from_class=P1  from_year=2020  to_class=P2  to_year=2021
        from_class=P2  from_year=2021  to_class=P3  to_year=2022
        from_class=P3  from_year=2022  to_class=P4  to_year=2023  ← is_to_class_the_current=True

    Reconstructed history:
        2020 → P1  |  2021 → P2  |  2022 → P3  |  2023 → P4 (current)

    Repeated class: two consecutive rows with the same from_class and
    different from_year values — correct and expected.

    is_to_class_the_current must be True only on the LATEST row.
    The view/util is responsible for flipping old rows to False on promotion.
    """

    student                  = models.ForeignKey(
                                   'students.Student',
                                   on_delete=models.CASCADE,
                                   related_name='class_promotions'
                               )
    from_class               = models.ForeignKey(
                                   SchoolSupportedClasses,
                                   on_delete=models.CASCADE,
                                   related_name='promotions_from_students'
                               )
    to_class                 = models.ForeignKey(
                                   SchoolSupportedClasses,
                                   on_delete=models.CASCADE,
                                   related_name='promotions_to_students'
                               )
    from_year                = models.CharField(
                                   max_length=4,
                                   help_text='4-digit year the student WAS IN from_class e.g. 2022'
                               )
    to_year                  = models.CharField(           # FIX 4 (was year_year)
                                   max_length=4,
                                   help_text='4-digit year the student MOVED INTO to_class e.g. 2023'
                               )
    is_to_class_the_current  = models.BooleanField(
                                   default=False,
                                   help_text='True only on the most recent promotion row'
                               )

    class Meta:
        verbose_name        = 'Student Class Promotion'
        verbose_name_plural = 'Student Class Promotions'
        ordering            = ['student', 'from_year']

    def __str__(self):
        return (
            f"{self.student.student_id} | "
            f"{self.from_class} ({self.from_year}) → "
            f"{self.to_class} ({self.to_year})"
        )


# =============================================================================
# 7. SCHOOL SCHOLASTIC REQUIREMENTS
# =============================================================================

class SchoolScholasticRequirements(TimeStampedModel):
    """
    Defines one physical item (or cash-equivalent) required from students
    of specific class(es) in a given term.

    HYBRID DESIGN — every requirement has:
        quantity        → how many physical units are needed
        monetary_value  → the UGX amount accepted as a full cash substitute

    A student can satisfy the requirement by:
        (A) Bringing the physical items in full
        (B) Paying the full monetary_value in cash
        (C) Any mix — e.g. bring 1 broom + pay UGX 1,500 for the second

    The per-student tracking is in StudentScholasticRequirementStatus.
    Which class(es) this requirement applies to is in ScholasticRequirementClass.

    Examples:
        item_name='Broom', quantity=2, unit='pieces', monetary_value=3000
        item_name='A4 Ream', quantity=1, unit='reams', monetary_value=15000
        item_name='Graph book', quantity=2, unit='pieces', monetary_value=4000
    """

    UNIT_CHOICES = [
        ('pieces', 'Pieces'),
        ('reams',  'Reams'),
        ('litres', 'Litres'),
        ('kg',     'Kilograms'),
        ('pairs',  'Pairs'),
        ('sets',   'Sets'),
        ('other',  'Other'),
    ]

    term            = models.ForeignKey(
                          'academics.Term',
                          on_delete=models.CASCADE,
                          related_name='scholastic_requirements'
                      )
    item_name       = models.CharField(
                          max_length=150,
                          help_text='E.g. "Broom", "Graph book", "A4 Ream"'
                      )
    quantity        = models.PositiveIntegerField(
                          help_text='Number of units required per student'
                      )
    unit            = models.CharField(
                          max_length=20, choices=UNIT_CHOICES, default='pieces'
                      )
    monetary_value  = models.DecimalField(
                          max_digits=10, decimal_places=2,
                          help_text=(
                              'UGX cash equivalent for the FULL required quantity. '
                              'Used when student pays cash instead of bringing items.'
                          )
                      )
    description     = models.TextField(
                          blank=True,
                          help_text='Extra instructions e.g. "Short-handle brooms only"'
                      )
    is_active       = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Scholastic Requirement'
        verbose_name_plural = 'Scholastic Requirements'
        ordering            = ['term', 'item_name']

    @property
    def unit_price(self):
        """UGX value per single unit."""
        if self.quantity:
            return round(self.monetary_value / self.quantity, 2)
        return self.monetary_value

    def __str__(self):
        return (
            f"{self.quantity} {self.get_unit_display()} of {self.item_name} "
            f"| {self.term} — UGX {self.monetary_value:,.0f}"
        )


# =============================================================================
# 8. SCHOLASTIC REQUIREMENT CLASS  (Bridge)
# =============================================================================

class ScholasticRequirementClass(TimeStampedModel):
    """
    Bridge: one scholastic requirement × one class.
    Create multiple rows to apply the same requirement to multiple classes.
    Mirrors the FeesClass pattern exactly.
    """

    requirement  = models.ForeignKey(
                       SchoolScholasticRequirements,
                       on_delete=models.CASCADE,
                       related_name='assigned_classes'
                   )
    school_class = models.ForeignKey(
                       SchoolSupportedClasses,
                       on_delete=models.CASCADE,
                       related_name='scholastic_requirements'
                   )

    class Meta:
        verbose_name        = 'Scholastic Requirement Class Assignment'
        verbose_name_plural = 'Scholastic Requirement Class Assignments'
        unique_together     = [('requirement', 'school_class')]

    def __str__(self):
        return f"{self.requirement.item_name} → {self.school_class}"





class ScholasticRequirementPayment(TimeStampedModel):
    """
    One transaction event toward a scholastic requirement.
    A single event can be:
        (A) Physical only  — student brings items, no cash
        (B) Cash only      — student pays cash, no items
        (C) Mixed          — student brings some items AND pays some cash

    At least one of brought_item / brought_cash must be True (enforced in clean()).

    After saving, the view/util MUST recompute StudentScholasticRequirementStatus
    for the same (student, requirement):

        status.quantity_brought   += items_brought
        status.amount_paid_ugx    += amount_paid_ugx (or 0 if cash not involved)
        physical_credit            = status.quantity_brought * requirement.unit_price
        balance                    = max(0,
                                         requirement.monetary_value
                                         - physical_credit
                                         - status.amount_paid_ugx)
        status.amount_balance_ugx  = balance
        status.fully_met           = balance == 0
        if status.fully_met and not status.fully_met_on:
            status.fully_met_on    = payment_date
        status.last_brought_on     = payment_date  (if brought_item)
        status.last_paid_on        = payment_date  (if brought_cash)
        status.save()
    """

    receipt_number  = models.CharField(
                          max_length=30, unique=True,
                          help_text='Auto-generated e.g. SRP2025001'
                      )
    student         = models.ForeignKey(
                          'students.Student',
                          on_delete=models.CASCADE,
                          related_name='scholastic_payment_records'
                      )
    requirement     = models.ForeignKey(
                          SchoolScholasticRequirements,
                          on_delete=models.CASCADE,
                          related_name='payment_records'
                      )
    school_class    = models.ForeignKey(
                          SchoolSupportedClasses,
                          on_delete=models.CASCADE,
                          related_name='scholastic_payment_records',
                          help_text="Student's class AT THE TIME of this transaction"
                      )

    # ── Physical side ─────────────────────────────────────────────────────────
    brought_item    = models.BooleanField(
                          default=False,
                          help_text='True if physical items were received in this transaction'
                      )
    items_brought   = models.PositiveIntegerField(
                          default=0,
                          help_text='Number of physical units received in this transaction'
                      )

    # ── Cash side ─────────────────────────────────────────────────────────────
    brought_cash    = models.BooleanField(
                          default=False,
                          help_text='True if a cash payment was received in this transaction'
                      )
    amount_paid_ugx = models.DecimalField(
                          max_digits=10, decimal_places=2,
                          default=0,
                          help_text='Cash paid in this transaction (UGX). 0 when no cash involved.'
                      )

    # ── Settlement flag ───────────────────────────────────────────────────────
    paid_fully      = models.BooleanField(
                          default=False,
                          help_text='True if this transaction fully settled the requirement for this student'
                      )

    # ── Shared ────────────────────────────────────────────────────────────────
    payment_date    = models.DateField()
    handled_by      = models.ForeignKey(
                          CustomUser,
                          on_delete=models.SET_NULL,
                          null=True, blank=True,
                          related_name='scholastic_payments_handled'
                      )
    notes           = models.TextField(blank=True)

    class Meta:
        verbose_name        = 'Scholastic Requirement Payment'
        verbose_name_plural = 'Scholastic Requirement Payments'
        ordering            = ['-payment_date', '-created_at']

    def clean(self):
        if not self.brought_item and not self.brought_cash:
            raise ValidationError(
                'A transaction must involve physical items, cash, or both.'
            )
        if self.brought_item and self.items_brought < 1:
            raise ValidationError(
                {'items_brought': 'Enter the number of items received (must be at least 1).'}
            )
        if self.brought_cash and self.amount_paid_ugx <= 0:
            raise ValidationError(
                {'amount_paid_ugx': 'Enter the cash amount received (must be greater than 0).'}
            )
        if not self.brought_item and self.items_brought > 0:
            raise ValidationError(
                {'items_brought': 'Tick "Brought item" when recording physical units.'}
            )
        if not self.brought_cash and self.amount_paid_ugx > 0:
            raise ValidationError(
                {'amount_paid_ugx': 'Tick "Brought cash" when recording a cash payment.'}
            )

    def __str__(self):
        parts = []
        if self.brought_item:
            parts.append(f"{self.items_brought} item(s)")
        if self.brought_cash:
            parts.append(f"UGX {self.amount_paid_ugx:,.0f}")
        detail = ' + '.join(parts)
        return (
            f"SRP {self.receipt_number} | {self.student} | "
            f"{self.requirement.item_name} | {detail}"
        )
# =============================================================================
# 9. STUDENT SCHOLASTIC REQUIREMENT STATUS
# =============================================================================

class StudentScholasticRequirementStatus(TimeStampedModel):
    """
    Hybrid tracker — one row per (student × requirement).
    Tracks physical contributions and cash payments independently,
    settling them together into a single fully_met flag.

    ── HOW SETTLEMENT WORKS ────────────────────────────────────────────────

    requirement.quantity       = total physical units needed  (e.g. 2)
    requirement.monetary_value = full cash equivalent         (e.g. UGX 3,000)
    requirement.unit_price     = monetary_value / quantity    (e.g. UGX 1,500)

    Each time the student brings items:
        quantity_brought  += units_received
        physical_credit    = quantity_brought * unit_price
        effective_balance  = monetary_value − physical_credit − amount_paid_ugx

    Each time the student pays cash:
        amount_paid_ugx   += amount_received
        effective_balance  = monetary_value − physical_credit − amount_paid_ugx

    fully_met = True when effective_balance <= 0

    The view/util must compute and save amount_balance_ugx and fully_met
    on every update. The formula is always:
        amount_balance_ugx = max(0,
            requirement.monetary_value
            − (quantity_brought * requirement.unit_price)
            − amount_paid_ugx
        )
        fully_met = amount_balance_ugx == 0

    ── EXAMPLE ─────────────────────────────────────────────────────────────

    Requirement: 2 brooms, UGX 3,000 total, UGX 1,500/broom

    Event 1 — student brings 1 broom:
        quantity_brought=1, amount_paid_ugx=0
        physical_credit=1,500  →  balance = 3,000−1,500−0 = 1,500

    Event 2 — student pays UGX 1,500 cash:
        quantity_brought=1, amount_paid_ugx=1,500
        balance = 3,000−1,500−1,500 = 0  →  fully_met=True
    """

    student            = models.ForeignKey(
                             'students.Student',
                             on_delete=models.CASCADE,
                             related_name='scholastic_requirement_statuses'
                         )
    requirement        = models.ForeignKey(
                             SchoolScholasticRequirements,
                             on_delete=models.CASCADE,
                             related_name='student_statuses'
                         )
    # Class the student was in when this requirement was assigned to them.
    # Preserved permanently — does not change when the student is promoted.
    school_class       = models.ForeignKey(
                             SchoolSupportedClasses,
                             on_delete=models.CASCADE,
                             related_name='scholastic_student_statuses',
                             help_text="Student's class when requirement was assigned"
                         )

    # ── Physical side ─────────────────────────────────────────────────────
    quantity_brought   = models.PositiveIntegerField(
                             default=0,
                             help_text='Total physical units brought by the student so far'
                         )
    last_brought_on    = models.DateField(
                             null=True, blank=True,
                             help_text='Date the most recent physical items were received'
                         )

    # ── Cash side ─────────────────────────────────────────────────────────
    amount_paid_ugx    = models.DecimalField(
                             max_digits=10, decimal_places=2,
                             default=0,
                             help_text='Total cash paid so far in UGX toward this requirement'
                         )
    last_paid_on       = models.DateField(
                             null=True, blank=True,
                             help_text='Date of the most recent cash payment'
                         )

    # ── Combined balance ──────────────────────────────────────────────────
    # Computed and stored by the view/util on every update.
    # Formula: max(0, monetary_value − (quantity_brought × unit_price) − amount_paid_ugx)
    amount_balance_ugx = models.DecimalField(
                             max_digits=10, decimal_places=2,
                             default=0,
                             help_text='Remaining balance in UGX after crediting both physical and cash'
                         )

    # ── Settlement ────────────────────────────────────────────────────────
    fully_met          = models.BooleanField(
                             default=False,
                             help_text='True when combined physical + cash covers the full requirement'
                         )
    fully_met_on       = models.DateField(
                             null=True, blank=True,
                             help_text='Date the requirement was fully satisfied'
                         )

    # ── Audit ─────────────────────────────────────────────────────────────
    notes              = models.TextField(
                             blank=True,
                             help_text='E.g. "Brought 1 broom, paid UGX 1,500 for the second"'
                         )
    recorded_by        = models.ForeignKey(
                             CustomUser,
                             on_delete=models.SET_NULL,
                             null=True, blank=True,
                             related_name='scholastic_statuses_recorded',
                             help_text='Staff member who last updated this record'
                         )

    class Meta:
        verbose_name        = 'Student Scholastic Requirement Status'
        verbose_name_plural = 'Student Scholastic Requirement Statuses'
        unique_together     = [('student', 'requirement')]
        ordering            = ['student', 'requirement__term', 'requirement__item_name']

    def __str__(self):
        physical = (
            f"{self.quantity_brought}/{self.requirement.quantity} "
            f"{self.requirement.get_unit_display()}"
        )
        cash   = f"UGX {self.amount_paid_ugx:,.0f} cash"
        status = 'MET' if self.fully_met else f'BAL UGX {self.amount_balance_ugx:,.0f}'
        return (
            f"{self.student.student_id} | {self.requirement.item_name} | "
            f"{physical} | {cash} | {status}"
        )
