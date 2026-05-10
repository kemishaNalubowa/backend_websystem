# fees/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# URL patterns for the fees app.
# Namespace: 'fees'
# 
# Include in root urls.py as:
#   path('fees/', include('fees.urls', namespace='fees'))
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import path

from fees.views.fees_views import (
    fees_list, fees_add, fees_edit, fees_delete,
    fees_detail, fees_duplicate, fees_toggle_active,
)
from fees.views.payment_views import (
    payment_list, add_payment, payment_edit,
    payment_delete, payment_detail,
)
from fees.views.assessment_fees_views import (
    assessment_fees_list,
    assessment_fees_add,
    assessment_fees_edit,
    assessment_fees_delete,
    assessment_fees_detail,
)


from fees.views.payment_add_views import (
    payment_add_step1, payment_add_step2,
    payment_add_step3, payment_add_step4,
)



from fees.views.scholastic_requirements_views import (
    scholastic_requirements_list,
    add_scholastic_requirements,
    scholastic_requirements_detail,
    delete_scholastic_requirement,
    toggle_scholastic_requirement,

    scholastic_payment_list,
    scholastic_payment_detail,
    scholastic_payment_delete
) 



app_name = 'fees'

urlpatterns = [

    # ── School Fees (fee structure) ───────────────────────────────────────────
    #   /fees/school-fees/                        → list + stats
    #   /fees/school-fees/add/                    → add form
    #   /fees/school-fees/<pk>/                   → detail page
    #   /fees/school-fees/<pk>/edit/              → edit form
    #   /fees/school-fees/<pk>/delete/            → confirm + delete
    #   /fees/school-fees/<pk>/duplicate/         → clone → redirect to edit
    #   /fees/school-fees/<pk>/toggle-active/     → POST activate/deactivate
    path('school-fees/',                        fees_list,          name='fees_list'),
    path('school-fees/add/',                    fees_add,           name='fees_add'),
    path('school-fees/<int:pk>/',               fees_detail,        name='fees_detail'),
    path('school-fees/<int:pk>/edit/',          fees_edit,          name='fees_edit'),
    path('school-fees/<int:pk>/delete/',        fees_delete,        name='fees_delete'),
    path('school-fees/<int:pk>/duplicate/',     fees_duplicate,     name='fees_duplicate'),
    path('school-fees/<int:pk>/toggle-active/', fees_toggle_active, name='fees_toggle_active'),

    # ── Payments ──────────────────────────────────────────────────────────────
    #   /fees/payments/               → list + stats
    #   /fees/payments/add/           → record new payment
    #   /fees/payments/<pk>/          → detail (receipt view)
    #   /fees/payments/<pk>/edit/     → edit payment
    #   /fees/payments/<pk>/delete/   → confirm + delete
    path('payments/',                 payment_list,   name='payment_list'),
    path('payments/add/',             add_payment,    name='add_payment'),
    path('payments/<int:pk>/',        payment_detail, name='payment_detail'),
    path('payments/<int:pk>/edit/',   payment_edit,   name='payment_edit'),
    path('payments/<int:pk>/delete/', payment_delete, name='payment_delete'),

    # ── Assessment Fees ───────────────────────────────────────────────────────
    #   /fees/assessment-fees/                          → list + stats
    #   /fees/assessment-fees/add/                      → add single record
    #   /fees/assessment-fees/bulk-generate/            → POST: generate for class+term
    #   /fees/assessment-fees/<pk>/                     → detail page
    #   /fees/assessment-fees/<pk>/edit/                → edit form
    #   /fees/assessment-fees/<pk>/delete/              → confirm + delete
    #   /fees/assessment-fees/<pk>/recalculate/         → POST: sync from payments
    path('assessment-fees/',                          assessment_fees_list,          name='assessment_fees_list'),
    path('assessment-fees/add/',                      assessment_fees_add,           name='assessment_fees_add'),
    path('assessment-fees/<int:pk>/',                 assessment_fees_detail,        name='assessment_fees_detail'),
    path('assessment-fees/<int:pk>/edit/',            assessment_fees_edit,          name='assessment_fees_edit'),
    path('assessment-fees/<int:pk>/delete/',          assessment_fees_delete,        name='assessment_fees_delete'),
    


    path('payments/add/step1/', payment_add_step1, name='payment_add_step1'),
    path('payments/add/step2/', payment_add_step2, name='payment_add_step2'),
    path('payments/add/step3/', payment_add_step3, name='payment_add_step3'),
    path('payments/add/step4/', payment_add_step4, name='payment_add_step4'),


    path('scholastic-requirements/',                              scholastic_requirements_list,      name='scholastic_requirements_list'),
    path('scholastic-requirements/add/',                          add_scholastic_requirements,       name='add_scholastic_requirements'),
    path('scholastic-requirements/<int:pk>/edit/',                add_scholastic_requirements,       name='edit_scholastic_requirements'),
    path('scholastic-requirements/<int:pk>/',                     scholastic_requirements_detail,    name='scholastic_requirements_detail'),
    path('scholastic-requirements/<int:pk>/delete/',              delete_scholastic_requirement,     name='delete_scholastic_requirement'),
    path('scholastic-requirements/<int:pk>/toggle/',              toggle_scholastic_requirement,     name='toggle_scholastic_requirement'),
    path('scholastic-payments/',                    scholastic_payment_list,   name='scholastic_payment_list'),
    path('scholastic-payments/<int:pk>/',           scholastic_payment_detail, name='scholastic_payment_detail'),
    path('scholastic-payments/<int:pk>/delete/',    scholastic_payment_delete, name='scholastic_payment_delete'),

]
