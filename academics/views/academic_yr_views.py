# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.core.exceptions import ValidationError

from academics.models import AcademicYear


# =========================
# LIST ACADEMIC YEARS
# =========================

def academic_year_list(request):

    years = AcademicYear.objects.all()

    context = {
        "years": years,
        "current_year": AcademicYear.objects.current(),
    }

    return render(
        request,
        "academics/academic_year/list.html",
        context
    )


# =========================
# ADD ACADEMIC YEAR
# =========================

# def academic_year_create(request):

#     if request.method == "POST":

#         name = request.POST.get("name")
#         start_date = request.POST.get("start_date")
#         end_date = request.POST.get("end_date")
#         is_active = request.POST.get("is_active")

#         try:

#             year = AcademicYear(
#                 name=name,
#                 start_date=parse_date(start_date),
#                 end_date=parse_date(end_date),
#                 is_active=True if is_active else False
#             )

#             year.save()

#             messages.success(
#                 request,
#                 "Academic year created successfully."
#             )

#             return redirect(
#                 "academics:academic_year_list"
#             )

#         except ValidationError as e:

#             messages.error(
#                 request,
#                 e.message
#             )

#         except Exception:

#             messages.error(
#                 request,
#                 "Something went wrong."
#             )

#     return render(
#         request,
#         "academics/academic_year/create.html"
#     )



from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date



def academic_year_create(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        start_date_str = request.POST.get("start_date")
        end_date_str = request.POST.get("end_date")
        is_active = bool(request.POST.get("is_active")) 
          # Better handling

        if not name:
            messages.error(request, "Academic year name is required.")
            return render(request, "academics/academic_year/create.html")

        try:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)

            if not start_date:
                raise ValidationError("Invalid start date format.")
            if not end_date:
                raise ValidationError("Invalid end date format.")
            if start_date >= end_date:
                raise ValidationError("End date must be after start date.")

            # Check for overlapping academic years (recommended)
            if AcademicYear.objects.filter(
                start_date__lte=end_date,
                end_date__gte=start_date,
                is_active=True
            ).exists():
                raise ValidationError("This period overlaps with an existing active academic year.")

            year = AcademicYear(
                name=name,
                start_date=start_date,
                end_date=end_date,
                is_active=is_active,
                year=start_date.year
            )
            year.full_clean()          # This triggers model validation
            year.save()

            messages.success(request, "Academic year created successfully.")
            return redirect("academics:academic_year_list")

        except ValidationError as e:
            # Handle both single message and error_dict
            error_msg = e.message if hasattr(e, 'message') else str(e)
            if hasattr(e, 'error_dict'):
                error_msg = " ".join([f"{k}: {v[0]}" for k, v in e.error_dict.items()])
            messages.error(request, error_msg)

        except Exception as e:
            messages.error(request, f"Something went wrong: {str(e)}")

    # GET request or form errors
    return render(request, "academics/academic_year/create.html")







# =========================
# UPDATE ACADEMIC YEAR
# =========================

def academic_year_update(request, pk):

    year = get_object_or_404(
        AcademicYear,
        pk=pk
    )

    if request.method == "POST":

        name = request.POST.get("name")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        is_active = request.POST.get("is_active")

        try:

            year.name = name
            year.start_date = parse_date(start_date)
            year.end_date = parse_date(end_date)
            year.is_active = True if is_active else False

            year.save()

            messages.success(
                request,
                "Academic year updated successfully."
            )

            return redirect(
                "academics:academic_year_list"
            )

        except ValidationError as e:

            messages.error(
                request,
                e.message
            )

        except Exception:

            messages.error(
                request,
                "Update failed."
            )

    context = {
        "year": year
    }

    return render(
        request,
        "academics/academic_year/update.html",
        context
    )


# =========================
# DELETE ACADEMIC YEAR
# =========================

def academic_year_delete(request, pk):

    year = get_object_or_404(
        AcademicYear,
        pk=pk
    )

    if request.method == "POST":

        year.delete()

        messages.success(
            request,
            "Academic year deleted successfully."
        )

        return redirect(
            "academics:academic_year_list"
        )

    context = {
        "year": year
    }

    return render(
        request,
        "academics/academic_year/delete.html",
        context
    )
