# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.contrib.auth.decorators import login_required

from academics.models import Term, AcademicYear
from permissions.decorators import has_permission


@login_required
@has_permission('term', action='read')
def terms_list(request):

    # =========================
    # ADD TERM
    # =========================

    if request.method == "POST" and request.POST.get("action") == "create":

        name = request.POST.get("name")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        academic_year_id = request.POST.get("academic_year")

        try:

            academic_year = AcademicYear.objects.get(
                id=academic_year_id
            )

            Term.objects.create(
                name=name,
                start_date=parse_date(start_date),
                end_date=parse_date(end_date),
                academic_year=academic_year,
            )

            messages.success(
                request,
                "Term added successfully."
            )

        except Exception as e:

            messages.error(
                request,
                str(e)
            )

        return redirect("academics:terms_list")

    # =========================
    # LIST TERMS
    # =========================

    terms = Term.objects.select_related(
        "academic_year"
    ).all()

    academic_years = AcademicYear.objects.all()

    context = {
        "terms": terms,
        "academic_years": academic_years,
    }

    return render(
        request,
        "academics/terms/terms_list.html",
        context
    )


# =========================
# EDIT TERM
# =========================

@login_required
@has_permission('term', action='edit')
def term_update(request, pk):

    term = get_object_or_404(
        Term,
        pk=pk
    )

    if request.method == "POST":

        try:

            term.name = request.POST.get("name")

            term.start_date = parse_date(
                request.POST.get("start_date")
            )

            term.end_date = parse_date(
                request.POST.get("end_date")
            )

            term.academic_year_id = request.POST.get(
                "academic_year"
            )

            term.save()

            messages.success(
                request,
                "Term updated successfully."
            )

        except Exception as e:

            messages.error(
                request,
                str(e)
            )

    return redirect("academics:terms_list")


# =========================
# DELETE TERM WITH PASSWORD
# =========================

@login_required
@has_permission('term', action='delete')
def term_delete(request, pk):

    term = get_object_or_404(
        Term,
        pk=pk
    )

    if request.method == "POST":

        password = request.POST.get("password")

        if not request.user.check_password(password):

            messages.error(
                request,
                "Incorrect password."
            )

            return redirect("academics:terms_list")

        term.delete()

        messages.success(
            request,
            "Term deleted successfully."
        )

    return redirect("academics:terms_list")
