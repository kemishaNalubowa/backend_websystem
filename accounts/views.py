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
from academics.models import SchoolClassTeacher, TeacherClass, TeacherSubject,Subject,ClassSubject



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







# ═══════════════════════════════════════════════════════════════════════════════
#  5. EDIT STAFF (full fields + same teaching logic as register_staff)
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
#  5. EDIT STAFF — Exact same staged flow as register_staff
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def edit_staff(request, pk):
    """
    Edit staff — exact same multi-stage flow as register_staff.

    Stage 1 (everyone)       – full personal + employment fields.
                               Non-teaching staff → save immediately.
                               Teaching staff     → session, redirect → Stage 2.

    Stage 2 (teaching only)  – which classes they teach + is_class_teacher flag.
                               → session, redirect → Stage 3.

    Stage 3 (teaching only)  – subjects taught per chosen class (only those
                               classes) → save.
    """
    user = get_object_or_404(User, pk=pk)
    if user.user_type not in ('teacher', 'staff', 'admin'):
        messages.error(request, 'Only staff accounts can be edited here.')
        return redirect('accounts:user_list')

    try:
        profile = StaffProfile.objects.get(user=user)
    except StaffProfile.DoesNotExist:
        messages.error(request, 'Staff profile not found.')
        return redirect('accounts:user_detail', pk=pk)

    lookups = _staff_form_lookups()

    # ── On the very first GET, clear any leftover session from a previous edit
    #    and do NOT pre-set is_a_teaching_staff so Stage 1 is always shown first.
    # ─────────────────────────────────────────────────────────────────────────
    if request.method == 'GET' and not request.session.get("is_a_teaching_staff"):
        for key in ("StaffData", "is_a_teaching_staff", "configure_class_tr", "is_a_class_tr"):
            request.session.pop(key, None)

    # ── Build tought_classes_subjects when already in teaching session flow ──
    tought_classes_subjects = []
    if request.session.get("is_a_teaching_staff"):
        staff_data   = request.session.get("StaffData") or {}
        teaching_req = staff_data.get("teaching_req") or {}
        tought_classes = teaching_req.get("tought_classes") or []
        if tought_classes:
            tought_classes_subjects = get_selected_clases_subjects(subjects=tought_classes)

    # ── Build selected_class_ids for Stage 2 pre-tick (existing assignments) ─
    selected_class_ids = list(
        TeacherClass.objects.filter(teacher=user)
        .values_list('school_class__supported_class__key', flat=True)
    )

    # ── Build selected_subjects_per_class for Stage 3 pre-tick ───────────────
    selected_subjects_per_class = {}
    for ts in TeacherSubject.objects.filter(teacher=user).select_related(
        'school_class__supported_class', 'subject'
    ):
        cls_key = ts.school_class.supported_class.key
        selected_subjects_per_class.setdefault(cls_key, [])
        selected_subjects_per_class[cls_key].append(ts.subject.code)

    # ─────────────────────────────────────────────────────────────────────────
    #  GET — render the appropriate stage
    # ─────────────────────────────────────────────────────────────────────────
    if request.method == 'GET':
        post = {
            # CustomUser fields
            'first_name':   user.first_name,
            'last_name':    user.last_name,
            'other_names':  user.other_names or '',
            'gender':       user.gender or '',
            'date_of_birth': user.date_of_birth or '',
            'phone':        user.phone or '',
            'alt_phone':    user.alt_phone or '',
            'email':        user.email or '',
            'nin':          user.nin or '',
            'address':      user.address or '',
            'profile_photo': user.profile_photo or None,
            # StaffProfile fields
            'role':             profile.role,
            'employment_type':  profile.employment_type,
            'date_joined':      profile.date_joined or '',
            'date_left':        profile.date_left or '',
            'qualification':    profile.qualification or '',
            'specialization':   profile.specialization or '',
            'nssf_number':      profile.nssf_number or '',
            'tin_number':       profile.tin_number or '',
            'salary_scale':     profile.salary_scale or '',
            'bank_name':        profile.bank_name or '',
            'bank_account':     profile.bank_account or '',
            'bio':              profile.bio or '',
            'notes':            profile.notes or '',
            'signature':        profile.signature or None,
            # teaching toggle — reflect current state
            'is_a_teaching_staff': bool(selected_class_ids),
            'is_class_teacher':    profile.is_class_teacher,
        }

        return render(request, f'{_T}edit_staff.html', {
            'form_title':             'Edit Staff / Teacher',
            'post':                   post,
            'errors':                 {},
            'classes':                get_sch_supported_classes(),
            'tought_classes_subjects': tought_classes_subjects,
            'selected_class_ids':     selected_class_ids,
            'selected_subjects_per_class': selected_subjects_per_class,
            'action':                 'edit',
            'pk':                     pk,
            **lookups,
        })

    # ─────────────────────────────────────────────────────────────────────────
    #  POST — stage dispatch (mirrors register_staff exactly)
    # ─────────────────────────────────────────────────────────────────────────

    # tr_tought_subjects_in_class is only populated in Stage 3; initialise here
    # so the save block can always reference it safely.
    tr_tought_subjects_in_class = {}

    # ── Stage 1 — not yet in teaching-staff flow ──────────────────────────────
    if not request.session.get("is_a_teaching_staff"):
        user_c, prof_c, errors = validate_and_parse_staff_registration(request.POST)

        if errors:
            for msg in errors.values():
                messages.error(request, msg)
            return render(request, f'{_T}edit_staff.html', {
                'form_title':             'Edit Staff / Teacher',
                'post':                   request.POST,
                'errors':                 errors,
                'classes':                get_sch_supported_classes(),
                'tought_classes_subjects': tought_classes_subjects,
                'selected_class_ids':     selected_class_ids,
                'selected_subjects_per_class': selected_subjects_per_class,
                'action':                 'edit',
                'pk':                     pk,
                **lookups,
            })

        # Teaching staff needs two more stages
        if prof_c.get('is_a_teaching_staff'):
            request.session["StaffData"] = {
                "user_data":    user_c,
                "profile_data": prof_c,
            }
            request.session["is_a_teaching_staff"] = True
            return redirect(reverse("accounts:edit_staff", args=[pk]))

        # Non-teaching → fall straight through to save block

    # ── Stage 2 / 3 — teaching-staff extra steps ──────────────────────────────
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

            return redirect(reverse("accounts:edit_staff", args=[pk]))

        else:
            # ── Stage 3: collect subjects per class, then save ────────────────
            for cls in tought_classes_subjects:
                class_key      = cls["key"]
                tought_subjects = []

                for cs in cls["subjects"]:
                    cs_code = cs.get("code")
                    submitted_value = str(request.POST.get(
                        f"{class_key.lower()}_tought_subject_{cs_code.lower()}"
                    ) or '').strip()

                    if submitted_value:
                        tought_subjects.append(submitted_value)

                if tought_subjects:
                    tr_tought_subjects_in_class[class_key] = tought_subjects

            staff_data = request.session.get("StaffData", {})
            user_c     = staff_data.get("user_data", {})
            prof_c     = staff_data.get("profile_data", {})

            # If flagged as class teacher in Stage 2, grab their assigned class
            if request.session.get("is_a_class_tr") is True:
                cls_tr_class = str(request.POST.get("cls_tr_class", "")).strip()
                if cls_tr_class:
                    class_ = get_sch_supported_classes().filter(
                        supported_class__key=cls_tr_class
                    ).first()
                    try:
                        prof_c["class_managed_id"] = class_
                    except ValueError:
                        messages.error(request, "Invalid class selected for class teacher.")
                        return redirect(reverse("accounts:edit_staff", args=[pk]))

    # ─────────────────────────────────────────────────────────────────────────
    #  SAVE — reached by non-teaching (Stage 1) and teaching staff (Stage 3)
    # ─────────────────────────────────────────────────────────────────────────
    try:
        with transaction.atomic():
            # ── Update CustomUser ────────────────────────────────────────────
            user.first_name  = user_c.get('first_name',  user.first_name)
            user.last_name   = user_c.get('last_name',   user.last_name)
            user.other_names = user_c.get('other_names', user.other_names)
            user.gender      = user_c.get('gender',      user.gender)
            user.phone       = user_c.get('phone',       user.phone)
            user.alt_phone   = user_c.get('alt_phone',   user.alt_phone)
            user.email       = user_c.get('email',       user.email)
            user.address     = user_c.get('address',     user.address)
            user.nin         = user_c.get('nin',         user.nin)

            # date_of_birth — optional, parse carefully
            dob_raw = user_c.get('date_of_birth', '')
            if dob_raw:
                from datetime import datetime as _dt
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try:
                        user.date_of_birth = _dt.strptime(dob_raw, fmt).date()
                        break
                    except ValueError:
                        continue

            # Profile photo (only replace if a new file was uploaded)
            if request.FILES.get('profile_photo'):
                user.profile_photo = request.FILES['profile_photo']

            user.save()

            # ── Update StaffProfile ──────────────────────────────────────────
            profile.role            = prof_c.get('role',            profile.role)
            profile.specialization  = prof_c.get('specialization',  profile.specialization)
            profile.is_class_teacher = prof_c.get('is_class_teacher', profile.is_class_teacher)

            # Employment fields (Stage 1 always submits these)
            emp_type = (request.POST.get('employment_type') or '').strip()
            if emp_type in {c[0] for c in StaffProfile.EMPLOYMENT_TYPE_CHOICES}:
                profile.employment_type = emp_type

            qual = (request.POST.get('qualification') or '').strip()
            if qual in {c[0] for c in StaffProfile.QUALIFICATION_CHOICES}:
                profile.qualification = qual

            # Date fields
            from datetime import datetime as _dt
            for field_name in ('date_joined', 'date_left'):
                raw = (request.POST.get(field_name) or '').strip()
                if raw:
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                        try:
                            setattr(profile, field_name, _dt.strptime(raw, fmt).date())
                            break
                        except ValueError:
                            continue
                elif field_name == 'date_left':
                    profile.date_left = None     # allow clearing

            # Payroll / HR text fields
            for f in ('nssf_number', 'tin_number', 'salary_scale',
                      'bank_name', 'bank_account', 'bio', 'notes'):
                val = (request.POST.get(f) or '').strip()
                setattr(profile, f, val)

            # Signature (only replace if a new file was uploaded)
            if request.FILES.get('signature'):
                profile.signature = request.FILES['signature']

            profile.save()

            # ── Clear and re-create teaching assignments ─────────────────────
            TeacherClass.objects.filter(teacher=user).delete()
            TeacherSubject.objects.filter(teacher=user).delete()
            SchoolClassTeacher.objects.filter(teacher=user).delete()

            if request.session.get("is_a_teaching_staff"):
                teaching_req = request.session.get("StaffData", {}).get("teaching_req", {})

                # Class teacher assignment
                if teaching_req.get("is_class_teacher"):
                    cls_tr_class = str(request.POST.get("cls_tr_class", "")).strip()
                    if cls_tr_class:
                        cls = get_sch_supported_classes().filter(
                            supported_class__key=cls_tr_class
                        ).first()
                        if cls:
                            SchoolClassTeacher.objects.create(teacher=user, school_class=cls)

                # Taught classes
                for tc in teaching_req.get("tought_classes", []):
                    for k, v in tc.items():
                        cls = get_sch_supported_classes().filter(
                            supported_class__key=v
                        ).first()
                        if cls:
                            TeacherClass.objects.create(school_class=cls, teacher=user)

                # Subjects per class
                for class_key, subjects in tr_tought_subjects_in_class.items():
                    class_obj = get_sch_supported_classes().filter(
                        supported_class__key=class_key.lower()
                    ).first()
                    if class_obj:
                        for subject_code in subjects:
                            subject_obj = Subject.objects.filter(
                                code=subject_code.upper()
                            ).first()
                            if subject_obj:
                                TeacherSubject.objects.create(
                                    teacher=user,
                                    school_class=class_obj,
                                    subject=subject_obj,
                                )

            # ── Clear session ────────────────────────────────────────────────
            for key in ("StaffData", "is_a_teaching_staff",
                        "configure_class_tr", "is_a_class_tr"):
                request.session.pop(key, None)

    except Exception as exc:
        messages.error(request, f'Could not update staff: {exc}')
        return redirect('accounts:edit_staff', pk=pk)

    messages.success(request, f'Staff account for {user.full_name} updated successfully.')
    return redirect('accounts:user_detail', pk=user.pk)