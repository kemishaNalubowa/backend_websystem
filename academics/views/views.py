from django.shortcuts import render, redirect
from django.urls import reverse
from academics.models import SchoolSupportedClasses, SchoolClass
from django.contrib import messages
from permissions.decorators import has_permission



@has_permission('class', action='read')
def school_supported_classes_manage(request):

    classes = SchoolClass.objects.all()

    supported_classes = (
        SchoolSupportedClasses.objects
        .select_related("supported_class")
        .all()
    )

    # =========================
    # ADD SUPPORTED CLASSES
    # =========================

    if request.method == "POST" and request.POST.get("action") == "create":

        total_added = 0

        for c in classes:

            value = request.POST.get(
                f"class_{c.key}"
            )

            if value == c.key:

                exists = (
                    SchoolSupportedClasses.objects
                    .filter(
                        supported_class=c
                    )
                    .exists()
                )

                if not exists:

                    SchoolSupportedClasses.objects.create(
                        supported_class=c
                    )

                    total_added += 1

        messages.success(
            request,
            f"{total_added} class(es) added."
        )

        return redirect(
            reverse(
                "academics:school_supported_classes_manage"
            )
        )

    # =========================
    # UPDATE SUPPORTED CLASSES
    # =========================

    if request.method == "POST" and request.POST.get("action") == "update":

        total_updated = 0

        # Clear existing

        SchoolSupportedClasses.objects.all().delete()

        for c in classes:

            value = request.POST.get(
                f"class_{c.key}"
            )

            if value == c.key:

                SchoolSupportedClasses.objects.create(
                    supported_class=c
                )

                total_updated += 1

        messages.success(
            request,
            f"Supported classes updated ({total_updated})."
        )

        return redirect(
            reverse(
                "academics:school_supported_classes_manage"
            )
        )

    supported_class_ids = (
    SchoolSupportedClasses.objects
    .values_list(
        "supported_class_id",
        flat=True
    )
)

    return render(
        request,
        "academics/class/supported_classes_manage.html",
        {
            "classes": classes,
            "supported_classes": supported_classes,
            "supported_class_ids": supported_class_ids,
        }
    )





# views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from academics.models import (
    SchoolSupportedClasses,
    SchoolClassTeacher
)

from accounts.models import (
    StaffProfile,
    CustomUser
)


@login_required
@has_permission("assign_class_teacher", action='read')
def assign_class_teacher(request):

    supported_classes = (
        SchoolSupportedClasses.objects
        .select_related("supported_class")
        .all()
    )

    class_teachers = (
        SchoolClassTeacher.objects
        .select_related(
            "teacher",
            "school_class__supported_class"
        )
        .all()
    )

    if request.method == "POST":

        class_id = request.POST.get("school_class")

        staff_id = request.POST.get("staff_id")

        password = request.POST.get("password")

        # -------------------------
        # Verify assigning user password
        # -------------------------

        if not request.user.check_password(password):

            messages.error(
                request,
                "Incorrect password."
            )

            return redirect(
                "academics:assign_class_teacher"
            )

        # -------------------------
        # Get supported class
        # -------------------------

        try:

            school_class = (
                SchoolSupportedClasses.objects
                .get(id=class_id)
            )

        except SchoolSupportedClasses.DoesNotExist:

            messages.error(
                request,
                "Class not found."
            )

            return redirect(
                "academics:assign_class_teacher"
            )

        # -------------------------
        # Find staff by employee ID
        # -------------------------

        try:

            staff_profile = (
                StaffProfile.objects
                .select_related("user")
                .get(
                    employee_id=staff_id,
                    is_active=True
                )
            )

        except StaffProfile.DoesNotExist:

            messages.error(
                request,
                "Staff not found."
            )

            return redirect(
                "academics:assign_class_teacher"
            )

        # -------------------------
        # Ensure teacher role
        # -------------------------

        if not staff_profile.is_teaching_staff:

            messages.error(
                request,
                "Selected staff is not a teacher."
            )

            return redirect(
                "academics:assign_class_teacher"
            )

        # -------------------------
        # Prevent duplicate assignment
        # -------------------------

        if SchoolClassTeacher.objects.filter(
            school_class=school_class
        ).exists():

            messages.warning(
                request,
                "This class already has a class teacher."
            )

            return redirect(
                "academics:assign_class_teacher"
            )

        # -------------------------
        # Assign teacher
        # -------------------------

        SchoolClassTeacher.objects.create(

            teacher=staff_profile.user,

            school_class=school_class

        )

        # -------------------------
        # Update staff profile
        # -------------------------

        staff_profile.is_class_teacher = True

        staff_profile.class_managed = (
            school_class.supported_class
        )

        staff_profile.save()

        messages.success(
            request,
            f"{staff_profile.full_name} assigned as class teacher."
        )

        return redirect(
            "academics:assign_class_teacher"
        )

    return render(
        request,
        "academics/class/assign_class_teacher.html",
        {
            "supported_classes": supported_classes,
            "class_teachers": class_teachers,
        }
    )
