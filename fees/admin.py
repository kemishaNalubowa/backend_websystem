from fees.models import (
    AssessmentFees,
    SchoolFees,
    FeesClass,
    FeesPayment,
    StudentFeesPaymentsStatus,
    StudentClassPromotion,
    SchoolScholasticRequirements,
    ScholasticRequirementClass,
    ScholasticRequirementPayment,
    StudentScholasticRequirementStatus
    )
from django.contrib import admin

admin.site.register(AssessmentFees)
admin.site.register(SchoolFees)
admin.site.register(FeesClass)
admin.site.register(FeesPayment)
admin.site.register(StudentFeesPaymentsStatus)
admin.site.register(StudentClassPromotion)
admin.site.register(ScholasticRequirementClass)
admin.site.register(SchoolScholasticRequirements)
admin.site.register(ScholasticRequirementPayment)
admin.site.register(StudentScholasticRequirementStatus)