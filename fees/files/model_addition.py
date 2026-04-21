# =============================================================================
# 10. SCHOLASTIC REQUIREMENT PAYMENT
# =============================================================================
# Add this class to fees/models.py after StudentScholasticRequirementStatus.
# It mirrors FeesPayment but is specific to scholastic (physical/cash) items.
# Each record represents one cash transaction toward a requirement.
# After saving a payment, the view MUST update the linked
# StudentScholasticRequirementStatus (amount_paid_ugx, amount_balance_ugx,
# fully_met) using the standard balance formula.
# =============================================================================

class ScholasticRequirementPayment(TimeStampedModel):
    """
    One cash payment transaction toward a scholastic requirement.

    One row = one receipt.  school_class records the student's class AT THE
    TIME of payment (immutable audit trail even after promotion).

    After inserting this record the view/util must recompute
    StudentScholasticRequirementStatus for the same (student, requirement):

        status.amount_paid_ugx += amount_paid_ugx
        physical_credit         = status.quantity_brought * requirement.unit_price
        balance                 = max(0,
                                      requirement.monetary_value
                                      - physical_credit
                                      - status.amount_paid_ugx)
        status.amount_balance_ugx = balance
        status.fully_met          = balance == 0
        if status.fully_met and not status.fully_met_on:
            status.fully_met_on = payment_date
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
                          help_text="Student's class AT THE TIME of payment"
                      )
    amount_paid_ugx = models.DecimalField(
                          max_digits=10, decimal_places=2,
                          help_text='Cash amount paid in this transaction (UGX)'
                      )
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

    def __str__(self):
        return (
            f"SRP {self.receipt_number} | {self.student} | "
            f"{self.requirement.item_name} | UGX {self.amount_paid_ugx:,.0f}"
        )
