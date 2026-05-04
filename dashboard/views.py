from django.shortcuts import render

# Create your views here.
def cover_page(request):
    return render (request, "dashboard/cover.html")







# ═══════════════════════════════════════════════════════════════════════════════
#  COVER / LANDING
# ═══════════════════════════════════════════════════════════════════════════════

def cover_page(request):
    return render(request, 'dashboard/cover.html')



# # ═══════════════════════════════════════════════════════════════════════════════
# #  STUDENT DETAIL
# # ═══════════════════════════════════════════════════════════════════════════════
# @login_required
# def parent_dashboard_student(request, student_id):
#     parent  = _get_parent_profile(request)
#     student = _get_owned_student(parent, student_id)

#     current_class = student.current_class  # may be None

#     # ── Fees structure + per-fee payment status ───────────────────────────────
#     if current_class:
#         fees_qs = SchoolFees.objects.filter(
#             affected_school_class__school_class=current_class,
#             is_active=True,
#         ).select_related('term').distinct().order_by('term', 'fees_type')

#         total_fees_amount = Decimal('0')
#         total_paid        = Decimal('0')
#         total_balance     = Decimal('0')
#         fully_paid_count  = 0
#         fees_structure_data = []

#         for fee in fees_qs:
#             status = StudentFeesPaymentsStatus.objects.filter(
#                 student=student,
#                 school_fees=fee,
#             ).first()

#             # Build transactions list with running balance
#             raw_txns = FeesPayment.objects.filter(
#                 student=student,
#                 school_fees=fee,
#             ).order_by('payment_date', 'created_at')

#             running = fee.amount
#             enriched_txns = []
#             for txn in raw_txns:
#                 prev_bal = running
#                 running  = running - txn.amount
#                 enriched_txns.append({
#                     'txn':             txn,
#                     'prev_balance':    prev_bal,
#                     'current_balance': max(running, Decimal('0')),
#                 })

#             fees_structure_data.append({
#                 'fee':          fee,
#                 'status':       status,
#                 'transactions': enriched_txns,
#             })

#             # Stats
#             total_fees_amount += fee.amount
#             if status:
#                 total_paid    += status.amount_paid
#                 total_balance += status.amount_balance
#                 if status.fully_paid:
#                     fully_paid_count += 1
#             else:
#                 total_balance += fee.amount   # nothing paid yet

#         fees_stats = {
#             'total_fees':        total_fees_amount,
#             'total_paid':        total_paid,
#             'total_balance':     total_balance,
#             'fully_paid_count':  fully_paid_count,
#             'total_items':       len(fees_structure_data),
#         }
#     else:
#         fees_structure_data = []
#         fees_stats          = None

#     # ── Fees payment history ──────────────────────────────────────────────────
#     fees_payments = FeesPayment.objects.filter(
#         student=student,
#     ).select_related('term', 'school_class', 'school_fees').order_by('-payment_date')

#     # ── Scholastic requirements ───────────────────────────────────────────────
#     if current_class:
#         scholastic_items = SchoolScholasticRequirements.objects.filter(
#             assigned_classes__school_class=current_class,
#             is_active=True,
#         ).select_related('term').order_by('term', 'item_name')
#     else:
#         scholastic_items = SchoolScholasticRequirements.objects.none()

#     # ── Scholastic payment history ────────────────────────────────────────────
#     scholastic_payments = ScholasticRequirementPayment.objects.filter(
#         student=student,
#     ).select_related('requirement').order_by('-payment_date')

#     # ── Assessment performance ────────────────────────────────────────────────
#     performance = AssessmentPerformance.objects.filter(
#         student=student,
#     ).order_by('-created_at')

#     # ── Parent's requests for this specific student ───────────────────────────
#     student_requests = ParentsRequest.objects.filter(
#         parent=request.user,
#         student=student,
#     ).order_by('-created_at')

#     return render(request, 'dashboard/parent_student.html', {
#         'parent':               parent,
#         'student':              student,
#         'current_class':        current_class,
#         'fees_structure_data':  fees_structure_data,   # ← replaces fees_structure
#         'fees_stats':           fees_stats,             # ← new
#         'fees_payments':        fees_payments,
#         'scholastic_items':     scholastic_items,
#         'scholastic_payments':  scholastic_payments,
#         'performance':          performance,
#         'student_requests':     student_requests,
#     })
