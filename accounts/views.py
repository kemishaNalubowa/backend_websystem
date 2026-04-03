# accounts/views/accounts_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Views:
#   user_list               — all users with stats and filters
#   register_staff          — create teacher/staff/admin user + StaffProfile
#   user_detail             — full profile page (dispatches by user_type)
#   user_toggle_active      — POST: activate / deactivate account
#
# REMOVED:
#   register_parent         — parents are now created only through the
#                             student enrolment flow (direct create or
#                             admission verify). Creating a parent without
#                             linking them to a student is not supported.
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from academics.utils.subject_utils import get_sch_supported_classes

from academics.models import SchoolClass
from accounts.models import ParentProfile, StaffProfile, USER_TYPE_CHOICES
from accounts.utils import (
    generate_employee_id,
    generate_temp_key,
    get_user_list_stats,
    validate_and_parse_staff_registration,
    get_selected_clases_subjects,
    # VALID_STAFF_ROLES,
    # VALID_EMPLOYMENT_TYPES,
    # VALID_QUALIFICATIONS,

)
from django.utils.timezone import now

User = get_user_model()
_T   = 'accounts/'


# ── Helpers ────────────────────────────────────────────────────────────────────

def _staff_form_lookups() -> dict:
    return {
        'all_classes':           SchoolClass.objects.order_by('section'),
        'role_choices':          StaffProfile.ROLE_CHOICES,
        'employment_choices':    StaffProfile.EMPLOYMENT_TYPE_CHOICES,
        'qualification_choices': StaffProfile.QUALIFICATION_CHOICES,
        'user_type_choices': [
            ('teacher', 'Teacher'),
            ('staff',   'Support Staff'),
            ('admin',   'Administrator'),
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  1. USER LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def user_list(request):
    """
    All system users with stats and filters.

    Stats: total, by-type counts, active/inactive.

    Filters:
        ?q=          name / username / parent_id search
        ?type=       parent | teacher | staff | admin
        ?active=1|0  active or inactive accounts
    """
    qs = User.objects.prefetch_related('parent_profile', 'staff_profile')

    search        = request.GET.get('q', '').strip()
    type_filter   = request.GET.get('type', '').strip()
    active_filter = request.GET.get('active', '').strip()

    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)  |
            Q(last_name__icontains=search)   |
            Q(username__icontains=search)    |
            Q(parent_id__icontains=search)   |
            Q(email__icontains=search)       |
            Q(phone__icontains=search)
        )

    if type_filter:
        qs = qs.filter(user_type=type_filter)

    if active_filter == '1':
        qs = qs.filter(is_active=True)
    elif active_filter == '0':
        qs = qs.filter(is_active=False)

    qs = qs.order_by('user_type', 'last_name', 'first_name')

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    stats = get_user_list_stats()

    context = {
        'users':         page_obj.object_list,
        'page_obj':      page_obj,
        'search':        search,
        'type_filter':   type_filter,
        'active_filter': active_filter,
        'type_choices':  USER_TYPE_CHOICES,
        **stats,
    }
    return render(request, f'{_T}user_list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. REGISTER STAFF / TEACHER / ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def register_staff(request):
    """
    Multi-stage staff registration.

    Stage 1 (everyone)        – basic user + profile fields.
                                Non-teaching staff → save immediately.
                                Teaching staff     → session, redirect → Stage 2.

    Stage 2 (teaching only)   – which classes they teach + is_class_teacher flag.
                                → session, redirect → Stage 3.

    Stage 3 (teaching only)   – subjects taught per class → save.
    """
    lookups = _staff_form_lookups()

    tought_classes_subjects = {}

    if request.session.get("is_a_teaching_staff"):
        staff_data   = request.session.get("StaffData") or {}
        teaching_req = staff_data.get("teaching_req") or {}
        tought_classes = teaching_req.get("tought_classes")
        
        if tought_classes:
            tought_classes_subjects = get_selected_clases_subjects(subjects=tought_classes)


    if request.method == 'GET':
        return render(request, f'{_T}register_staff.html', {
            'form_title':            'Register Staff / Teacher',
            'post':                  {},
            'errors':                {},
            'classes':               get_sch_supported_classes(),
            'tought_classes_subjects': tought_classes_subjects,
            **lookups,
        })

    # ── Will be populated by whichever stage reaches the save block ───────────
    user_c: dict = {}
    prof_c: dict = {}

    # ─────────────────────────────────────────────────────────────────────────
    #  STAGE 1  –  basic info (only when NOT yet in teaching-staff session flow)
    # ─────────────────────────────────────────────────────────────────────────
    if not request.session.get("is_a_teaching_staff"):
        user_c, prof_c, errors = validate_and_parse_staff_registration(request.POST)

        if errors:
            for msg in errors.values():
                messages.error(request, msg)
            return render(request, f'{_T}register_staff.html', {
                'form_title': 'Register Staff / Teacher',
                'post':       request.POST,
                'errors':     errors,
                'classes':    get_sch_supported_classes(),
                **lookups,
            })

        # Teaching staff needs two more stages before we can save
        if prof_c.get('is_a_teaching_staff'):
            request.session["StaffData"] = {
                "user_data":    user_c,
                "profile_data": prof_c,
            }
            request.session["is_a_teaching_staff"] = True
            return redirect(reverse("accounts:register_staff"))

        # Non-teaching staff → fall straight through to the save block

    # ─────────────────────────────────────────────────────────────────────────
    #  STAGE 2 / 3  –  teaching-staff extra steps
    # ─────────────────────────────────────────────────────────────────────────
    else:
        if not request.session.get("configure_class_tr"):
            # ── Stage 2: collect which classes + is_class_teacher ─────────────
            supported_classes = get_sch_supported_classes()
            submitted_classes = []
            for sc in supported_classes:
                key    = sc.supported_class.key
                class_ = (request.POST.get(f"tought_class_{key}") or '').strip()
                if class_:
                    submitted_classes.append({f"class_{key}": class_})

            is_a_class_tr = (
                str(request.POST.get('is_class_teacher', '')).strip().lower()
                in ('1', 'true', 'on', 'yes')
            )

            prev_session = request.session.get("StaffData", {})
            prev_session["teaching_req"] = {
                "is_class_teacher": is_a_class_tr,
                "tought_classes":   submitted_classes,
            }
            request.session["StaffData"]          = prev_session
            request.session["configure_class_tr"] = True
            if is_a_class_tr:
                request.session["is_a_class_tr"] = True

            return redirect(reverse("accounts:register_staff"))

        else:
            # ── Stage 3: collect subjects per class, then save ────────────────
            tr_tought_subjects_in_class = {}
            for cls in tought_classes_subjects:

                class_key      = cls["key"]
                tought_subjects = []

                for cs in cls["subjects"]:
                    cs_code         = cs.get("code")

                    submitted_value = str(request.POST.get(
                        f"{class_key.lower()}_tought_subject_{cs_code.lower()}"
                    ) or '').strip()

                    if submitted_value:
                        tought_subjects.append(submitted_value)
                if tought_subjects:
                    tr_tought_subjects_in_class[class_key] = tought_subjects

           # Stage 3 — after collecting tr_tought_subjects_in_class
           
            print("TR____________________:", tr_tought_subjects_in_class)

            staff_data = request.session.get("StaffData", {})
            user_c     = staff_data.get("user_data", {})
            prof_c     = staff_data.get("profile_data", {})

            # If flagged as class teacher in Stage 2, grab their assigned class from this POST
            if request.session.get("is_a_class_tr") is True:
                cls_tr_class = str(request.POST.get("cls_tr_class", "")).strip()
                if cls_tr_class:
                    school_class = get_sch_supported_classes()
                    class_ = school_class.filter(supported_class__key=cls_tr_class).first()

                    try:
                        prof_c["class_managed_id"] = class_
                    except ValueError:
                        messages.error(request, "Invalid class selected for class teacher.")
                        return redirect(reverse("accounts:register_staff"))

            # Clear all session keys for this flow
            # for key in ("StaffData", "is_a_teaching_staff",
            #             "configure_class_tr", "is_a_class_tr"):
            #     request.session.pop(key, None)

            # Fall through to save block

    # ─────────────────────────────────────────────────────────────────────────
    #  SAVE  –  reached by non-teaching (Stage 1) and teaching staff (Stage 3)
    # ─────────────────────────────────────────────────────────────────────────
    try:
        with transaction.atomic():
            employee_id = generate_employee_id()
            password    = user_c.get('first_name', '')   # temp password = first name
            from authentication.models import CustomUser
            user = CustomUser.objects.create_user(
                username    = employee_id,               # login username = employee ID
                password    = password,
                email       = user_c.get('email', ''),
                user_type   = "staff",
                first_name  = user_c.get('first_name', ''),
                last_name   = user_c.get('last_name', ''),
                other_names = user_c.get('other_names', ''),
                gender      = user_c.get('gender', ''),
                phone       = user_c.get('phone', ''),
                alt_phone   = user_c.get('alt_phone', ''),
                is_active   = True,
            )



            from academics.models import SchoolClassTeacher, TeacherClass, TeacherSubject,Subject


            staff_data =request.session.get("StaffData", {})

            teaching_req = staff_data.get("teaching_req", {})

            if teaching_req:
                if teaching_req.get("is_class_teacher") is True:
                    SchoolClassTeacher.objects.create(
                        teacher=user,
                        school_class=prof_c.get("class_managed_id")
                    )

                if teaching_req.get("tought_classes"):
                    for tc in teaching_req.get("tought_classes"):
                        for k,v in tc.items():
                            cls= get_sch_supported_classes().filter(supported_class__key=v).first()

                            TeacherClass.objects.create(
                                school_class=cls,
                                teacher =user
                            )



                print("TR____________________:", tr_tought_subjects_in_class)

                if tr_tought_subjects_in_class:
                    for class_key, subjects in tr_tought_subjects_in_class.items():
                        class_obj = get_sch_supported_classes().filter(
                            supported_class__key=class_key.lower()
                        ).first()

                        if class_obj:
                            print(f"class obj {class_obj} is found")
                        if subjects:
                            print(f'Subjes in Class Obj are {subjects}')

                        for subject_code in subjects:
                            # subject FK on TeacherSubject points to SchoolSupportedClasses, not Subject
                            subject_obj =  Subject.objects.filter(
                                code=subject_code.upper()
                            ).first()

                            TeacherSubject.objects.create(   # ← inside the loop now
                                teacher=user,
                                school_class=class_obj,
                                subject=subject_obj,
                            )


            # Remove keys that are not StaffProfile model fields
            prof_c.pop('is_a_teaching_staff', None)
            class_managed_id = prof_c.pop('class_managed_id', None)

            sp = StaffProfile.objects.create(
                user        = user,
                employee_id = employee_id,
                date_joined = now().date(),   # required field; validator has it commented out
                **prof_c,
            )

            
            # Clear all session keys for this flow
            for key in ("StaffData", "is_a_teaching_staff",
                        "configure_class_tr", "is_a_class_tr"):
                request.session.pop(key, None)


    except Exception as exc:
        messages.error(request, f'Could not create staff account: {exc}')
        return render(request, f'{_T}register_staff.html', {
            'form_title': 'Register Staff / Teacher',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    type_label = dict(USER_TYPE_CHOICES).get(user.user_type, user.user_type)
    messages.success(
        request,
        f'{type_label} account created — {user.full_name} '
        f'(Username: {employee_id}, Temp Password: {password}).'
    )
    return redirect('accounts:user_detail', pk=user.pk)



# ═══════════════════════════════════════════════════════════════════════════════
#  3. USER DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def user_detail(request, pk):
    """
    Full profile page for any user type.
    Shows user fields + the linked ParentProfile or StaffProfile.

    For parents: children are fetched via StudentParentRelationship
    (not the old direct Student.parent FK which no longer exists).
    """
    user = get_object_or_404(
        User.objects.prefetch_related(
            'parent_profile',
            'staff_profile',
            'staff_profile__class_managed',
        ),
        pk=pk,
    )

    profile = None
    children_with_rels = []   # list of (Student, StudentParentRelationship)

    if user.user_type == 'parent':
        profile = getattr(user, 'parent_profile', None)

        if profile:
            from students.models import StudentParentRelationship
            rels = (
                StudentParentRelationship.objects
                .filter(parent=profile)
                .select_related(
                    'student',
                    'student__current_class',
                )
                .order_by('student__last_name', 'student__first_name')
            )
            children_with_rels = [
                (rel.student, rel) for rel in rels
            ]
    else:
        profile = getattr(user, 'staff_profile', None)

    context = {
        'user_obj':           user,
        'profile':            profile,
        'children_with_rels': children_with_rels,
        'type_label':         dict(USER_TYPE_CHOICES).get(user.user_type, user.user_type),
        'page_title':         user.full_name,
    }
    return render(request, f'{_T}user_detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. TOGGLE ACTIVE  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def user_toggle_active(request, pk):
    """POST-only: activate or deactivate a user account."""
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('accounts:user_list')

    user = get_object_or_404(User, pk=pk)

    if user.pk == request.user.pk:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('accounts:user_detail', pk=user.pk)

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])

    state = 'activated' if user.is_active else 'deactivated'
    messages.success(
        request, f'Account for "{user.full_name}" has been {state}.'
    )

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('accounts:user_detail', pk=user.pk)
