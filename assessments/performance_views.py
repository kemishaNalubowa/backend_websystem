# assessments/performance_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Assessment Performance Entry — 4-part wizard (add) + enable-edit + edit flow
#
# Rules enforced:
#   • No custom JS, no custom CSS, no JSON responses, no class-based views,
#     no forms.py.  Bootstrap 5 only.  Errors via django messages or field dicts.
#   • Student IDs are uppercased before lookup (handles lowercase input).
#   • Subjects whose EntryStatus is_done=True are silently skipped in Step 1
#     (cannot add new marks — must use edit flow).
#   • All state travels via request.session between parts.
# ─────────────────────────────────────────────────────────────────────────────

from django.shortcuts               import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth            import authenticate
from django.contrib                 import messages
from django.db                      import transaction
from django.urls                    import reverse

from students.models  import Student
from .models import (
    Assessment,
    AssessmentClass,
    AssessmentSubject,
    AssessmentTotalMark,
    AssessmentPerformance,
    AssessmentModification,
    AssessmentPerformanceEntryStatus,
)
from permissions.decorators import has_permission


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_mod(assessment):
    mod, _ = AssessmentModification.objects.get_or_create(
        assessment=assessment,
        defaults={'modify_class': True},
    )
    return mod


def _entry_session_key(assessment_pk):
    return f'perf_entry_{assessment_pk}'


def _edit_session_key(assessment_pk):
    return f'perf_edit_{assessment_pk}'


def _enable_edit_session_key(assessment_pk):
    return f'perf_enable_edit_{assessment_pk}'


def _clear_entry_session(request, assessment_pk):
    request.session.pop(_entry_session_key(assessment_pk), None)


def _clear_edit_session(request, assessment_pk):
    request.session.pop(_edit_session_key(assessment_pk), None)


def _clear_enable_edit_session(request, assessment_pk):
    request.session.pop(_enable_edit_session_key(assessment_pk), None)


# ─────────────────────────────────────────────────────────────────────────────
# Shared: build per-class subject lists (skipping done subjects for ADD flow)
# ─────────────────────────────────────────────────────────────────────────────

def _build_class_subjects(assessment, valid_assessment_classes, skip_done=True):
    """
    Returns a dict:
      { ac.pk: [AssessmentSubject, ...] }

    If skip_done=True (add flow), subjects whose EntryStatus.is_done is True
    are excluded.
    If skip_done=False (edit flow), only subjects where is_edit_allowed is True
    are included.
    """
    class_subjects = {}
    for ac in valid_assessment_classes:
        qs = AssessmentSubject.objects.filter(
            assessment=assessment,
            assessment_class=ac.school_class,
        ).select_related('subject')

        if skip_done:
            # Exclude subjects already fully done
            done_subject_pks = set(
                AssessmentPerformanceEntryStatus.objects.filter(
                    assessment=assessment,
                    school_class=ac,
                    is_done=True,
                ).values_list('subject__subject_id', flat=True)
            )
            qs = [s for s in qs if s.subject_id not in done_subject_pks]
        else:
            # Edit flow — include only subjects with edit enabled
            edit_allowed_pks = set(
                AssessmentPerformanceEntryStatus.objects.filter(
                    assessment=assessment,
                    school_class=ac,
                    is_edit_allowed=True,
                ).values_list('subject__subject_id', flat=True)
            )
            qs = [s for s in qs if s.subject_id in edit_allowed_pks]

        class_subjects[ac.pk] = list(qs)
    return class_subjects


def _get_total_marks_map(assessment):
    """{ AssessmentSubject.pk: AssessmentTotalMark } """
    return {
        tm.subject_id: tm
        for tm in AssessmentTotalMark.objects.filter(assessment=assessment)
                                             .select_related('subject')
    }


# ═════════════════════════════════════════════════════════════════════════════
#  ADD FLOW — PART 1: Select class + enter student IDs
# ═════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission("add_performance_entry", action='create')
def perf_entry_part1(request, pk):
    """
    GET  — show assessment classes as checkboxes + student-ID textarea.
    POST — validate student IDs against chosen classes, categorise into
           (new_students, already_found), session data, redirect to Part 2.
    """
    assessment = get_object_or_404(Assessment, pk=pk)
    mod        = _get_or_create_mod(assessment)

    if not mod.modify_performance:
        messages.error(request, 'Performance entry is not currently open for this assessment.')
        return redirect(reverse('assessments:detail', args=[pk]))

    assessment_classes = list(
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )

    if not assessment_classes:
        messages.error(request, 'No classes are attached to this assessment.')
        return redirect(reverse('assessments:detail', args=[pk]))

    if request.method == 'POST':
        # ── 1. Read inputs ──────────────────────────────────────────────────
        raw_ids      = request.POST.get('student_ids', '')
        chosen_class_pks = request.POST.getlist('classes')  # list of AssessmentClass PKs

        errors = {}

        if not chosen_class_pks:
            errors['classes'] = 'Please select at least one class.'

        raw_student_ids = [s.strip().upper() for s in raw_ids.replace(',', '\n').splitlines() if s.strip()]
        if not raw_student_ids:
            errors['student_ids'] = 'Please enter at least one student ID.'

        if errors:
            return render(request, 'assessments/perf_entry/add/perf_entry_part1.html', {
                'assessment':        assessment,
                'assessment_classes': assessment_classes,
                'errors':            errors,
                'post':              request.POST,
            })

        # ── 2. Resolve chosen AssessmentClass objects ───────────────────────
        valid_acs = [ac for ac in assessment_classes if str(ac.pk) in chosen_class_pks]
        if not valid_acs:
            errors['classes'] = 'Invalid class selection.'
            return render(request, 'assessments/perf_entry/add/perf_entry_part1.html', {
                'assessment':        assessment,
                'assessment_classes': assessment_classes,
                'errors':            errors,
                'post':              request.POST,
            })

        # ── 3. Build per-class available subjects (skip done) ───────────────
        class_subjects = _build_class_subjects(assessment, valid_acs, skip_done=True)

        # ── 4. Validate each student ID ─────────────────────────────────────
        # a. Student must exist
        # b. Student's current_class must be one of the chosen assessment classes
        # c. Categorise: already_found (has ≥1 perf record) vs new
        #
        # Structure collected per student:
        #   {
        #     'student_id': str,
        #     'full_name':  str,
        #     'ac_pk':      int,   (the AssessmentClass pk they belong to)
        #     'found_perfs': {subject_pk: marks_obtained_or_None},
        #   }

        not_found_ids   = []   # IDs that didn't match any student in the chosen classes
        new_students    = []   # will need fresh performance rows
        already_found   = []   # already have at least some perf rows

        # Build a lookup: SchoolSupportedClasses pk → AssessmentClass obj
        sc_pk_to_ac = {ac.school_class_id: ac for ac in valid_acs}

        for sid in raw_student_ids:
            student = Student.objects.filter(student_id__iexact=sid).first()
            if not student:
                not_found_ids.append({'id': sid, 'reason': 'Student not found in system.'})
                continue

            ac = sc_pk_to_ac.get(student.current_class_id)
            if not ac:
                not_found_ids.append({
                    'id': sid,
                    'reason': f'{student.full_name} is not in any of the selected classes.',
                })
                continue

            # Get subjects available for this class (already filtered for done)
            subjects_for_class = class_subjects.get(ac.pk, [])

            # Find existing performance records for this student in this assessment
            existing_perfs = {
                perf.subject_id: perf
                for perf in AssessmentPerformance.objects.filter(
                    assessment=assessment,
                    student=student,
                    school_class=student.current_class,
                )
            }

            # Map: AssessmentSubject.subject_id → marks_obtained (None if not yet entered)
            subject_status = []
            for as_subj in subjects_for_class:
                perf = existing_perfs.get(as_subj.subject_id)
                subject_status.append({
                    'as_subj_pk':     as_subj.pk,
                    'subject_pk':     as_subj.subject_id,
                    'subject_name':   as_subj.subject.name,
                    'subject_code':   as_subj.subject.code,
                    'marks_obtained': str(perf.marks_obtained) if perf else None,
                    'perf_pk':        perf.pk if perf else None,
                })

            entry = {
                'student_id':    student.student_id,
                'full_name':     student.full_name,
                'ac_pk':         ac.pk,
                'class_name':    ac.school_class.supported_class.name,
                'subject_status': subject_status,
            }

            has_existing = any(s['marks_obtained'] is not None for s in subject_status)
            if has_existing:
                already_found.append(entry)
            else:
                new_students.append(entry)

        if not new_students and not already_found:
            messages.warning(request, 'No valid students found for the selected classes.')
            return render(request, 'assessments/perf_entry/add/perf_entry_part1.html', {
                'assessment':        assessment,
                'assessment_classes': assessment_classes,
                'errors':            {},
                'post':              request.POST,
            })

        # ── 5. Build available subjects per class for Part 2 display ────────
        class_subjects_serialisable = {
            str(ac.pk): [
                {
                    'as_subj_pk':   s.pk,
                    'subject_pk':   s.subject_id,
                    'subject_name': s.subject.name,
                    'subject_code': s.subject.code,
                    'passmark':     str(s.passmark) if s.passmark else None,
                }
                for s in subs
            ]
            for ac, subs in [
                (ac, class_subjects.get(ac.pk, [])) for ac in valid_acs
            ]
        }

        chosen_classes_info = [
            {'ac_pk': ac.pk, 'class_name': ac.school_class.supported_class.name}
            for ac in valid_acs
        ]

        # ── 6. Session and redirect ─────────────────────────────────────────
        session_data = {
            'not_found_ids':   not_found_ids,
            'new_students':    new_students,
            'already_found':   already_found,
            'chosen_classes':  chosen_classes_info,
            'class_subjects':  class_subjects_serialisable,
            # part2 will add 'chosen_subjects' after user selects
        }
        request.session[_entry_session_key(pk)] = session_data
        request.session.modified = True

        return redirect(reverse('assessments:perf_entry_part2', args=[pk]))

    return render(request, 'assessments/perf_entry/add/perf_entry_part1.html', {
        'assessment':        assessment,
        'assessment_classes': assessment_classes,
        'errors':            {},
        'post':              {},
    })


# ═════════════════════════════════════════════════════════════════════════════
#  ADD FLOW — PART 2: Choose subjects per class
# ═════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission("add_performance_entry", action='create')
def perf_entry_part2(request, pk):
    """
    GET  — show available subjects per class; user ticks which to enter now.
    POST — validate selections, session updated chosen subjects, redirect Part 3.
    """
    assessment   = get_object_or_404(Assessment, pk=pk)
    session_data = request.session.get(_entry_session_key(pk))

    if not session_data:
        messages.error(request, 'Session expired. Please start from Step 1.')
        return redirect(reverse('assessments:perf_entry_part1', args=[pk]))

    chosen_classes = session_data['chosen_classes']   # [{ac_pk, class_name}]
    class_subjects = session_data['class_subjects']   # {str(ac_pk): [{...}]}

    if request.method == 'POST':
        errors          = {}
        chosen_subjects = {}   # {str(ac_pk): [as_subj_pk, ...]}

        for cls_info in chosen_classes:
            ac_pk     = cls_info['ac_pk']
            available = class_subjects.get(str(ac_pk), [])
            selected  = request.POST.getlist(f'subjects_{ac_pk}')

            # Validate: selected pks must be in available list
            valid_pks = {str(s['as_subj_pk']) for s in available}
            chosen    = [s for s in selected if s in valid_pks]

            if not chosen:
                errors[f'subjects_{ac_pk}'] = (
                    f'Please select at least one subject for {cls_info["class_name"]}.'
                )
            else:
                chosen_subjects[str(ac_pk)] = [int(p) for p in chosen]

        if errors:
            return render(request, 'assessments/perf_entry/add/perf_entry_part2.html', {
                'assessment':    assessment,
                'chosen_classes': chosen_classes,
                'class_subjects': class_subjects,
                'errors':        errors,
                'post':          request.POST,
            })

        # Build the filtered student data: only include subject_status rows
        # matching chosen subjects for each student's class.
        def _filter_student_subjects(students, chosen_subjects):
            filtered = []
            for s in students:
                ac_pk     = str(s['ac_pk'])
                chosen_as = set(chosen_subjects.get(ac_pk, []))
                new_status = [
                    ss for ss in s['subject_status']
                    if ss['as_subj_pk'] in chosen_as
                ]
                if new_status:
                    filtered.append({**s, 'subject_status': new_status})
            return filtered

        filtered_new     = _filter_student_subjects(session_data['new_students'], chosen_subjects)
        filtered_already = _filter_student_subjects(session_data['already_found'], chosen_subjects)

        # Fetch total marks for chosen subjects
        total_marks_map = {}
        all_as_pks = {p for pks in chosen_subjects.values() for p in pks}
        for tm in AssessmentTotalMark.objects.filter(
            assessment=assessment,
            subject_id__in=all_as_pks,
        ).select_related('subject__subject'):
            total_marks_map[tm.subject_id] = str(tm.total_mark)

        session_data['chosen_subjects']  = chosen_subjects
        session_data['filtered_new']     = filtered_new
        session_data['filtered_already'] = filtered_already
        session_data['total_marks_map']  = total_marks_map   # {str(as_subj_pk): str}
        request.session[_entry_session_key(pk)] = session_data
        request.session.modified = True

        return redirect(reverse('assessments:perf_entry_part3', args=[pk]))

    return render(request, 'assessments/perf_entry/add/perf_entry_part2.html', {
        'assessment':    assessment,
        'chosen_classes': chosen_classes,
        'class_subjects': class_subjects,
        'errors':        {},
        'post':          {},
    })


# ═════════════════════════════════════════════════════════════════════════════
#  ADD FLOW — PART 3: Enter marks
# ═════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission("add_performance_entry", action='create')
def perf_entry_part3(request, pk):
    """
    GET  — render the marks-entry table.
           Cells where marks already exist show the value (read-only display).
           Empty cells show an input field.
    POST — collect submitted marks, validate, compute pass/tried,
           session everything, redirect Part 4 (preview + confirm).
    """
    assessment   = get_object_or_404(Assessment, pk=pk)
    session_data = request.session.get(_entry_session_key(pk))

    if not session_data or 'chosen_subjects' not in session_data:
        messages.error(request, 'Session expired. Please start from Step 1.')
        return redirect(reverse('assessments:perf_entry_part1', args=[pk]))

    chosen_classes   = session_data['chosen_classes']
    class_subjects   = session_data['class_subjects']
    chosen_subjects  = session_data['chosen_subjects']
    filtered_new     = session_data['filtered_new']
    filtered_already = session_data['filtered_already']
    total_marks_map  = session_data['total_marks_map']
    not_found_ids    = session_data.get('not_found_ids', [])

    # Build a combined ordered list for rendering: class → students
    class_student_map = {}   # {ac_pk: {class_name, subjects_headers, students[]}}

    for cls_info in chosen_classes:
        ac_pk     = cls_info['ac_pk']
        as_pks    = chosen_subjects.get(str(ac_pk), [])
        # ordered subjects for header
        subj_hdrs = [
            s for s in class_subjects.get(str(ac_pk), [])
            if s['as_subj_pk'] in as_pks
        ]
        students_here = [
            s for s in (filtered_new + filtered_already)
            if s['ac_pk'] == ac_pk
        ]
        class_student_map[ac_pk] = {
            'class_name':       cls_info['class_name'],
            'subject_headers':  subj_hdrs,
            'students':         students_here,
        }

    if request.method == 'POST':
        errors = {}
        # Collect submitted marks: key = 'mark_{student_id}_{as_subj_pk}'
        # Build a list of entries to save:
        # [{ student_id, as_subj_pk, marks_obtained, is_new, total_mark, passmark }]
        entries_to_save  = []
        entries_preview  = []   # for Part 4 (already-found shown with ✔)

        for cls_info in chosen_classes:
            ac_pk    = cls_info['ac_pk']
            as_pks   = chosen_subjects.get(str(ac_pk), [])
            subj_map = {
                s['as_subj_pk']: s
                for s in class_subjects.get(str(ac_pk), [])
                if s['as_subj_pk'] in as_pks
            }
            students_here = [
                s for s in (filtered_new + filtered_already)
                if s['ac_pk'] == ac_pk
            ]

            for student in students_here:
                for ss in student['subject_status']:
                    as_pk = ss['as_subj_pk']
                    if as_pk not in as_pks:
                        continue

                    already_entered = ss['marks_obtained'] is not None

                    if already_entered:
                        # Re-use existing; no input expected
                        total_str  = total_marks_map.get(str(as_pk))
                        passmark   = subj_map.get(as_pk, {}).get('passmark')
                        entries_preview.append({
                            'student_id':    student['student_id'],
                            'full_name':     student['full_name'],
                            'class_name':    cls_info['class_name'],
                            'ac_pk':         ac_pk,
                            'as_subj_pk':    as_pk,
                            'subject_name':  ss['subject_name'],
                            'subject_code':  ss['subject_code'],
                            'marks_obtained': ss['marks_obtained'],
                            'total_mark':    total_str,
                            'passmark':      passmark,
                            'from_db':       True,
                            'passed':        _compute_pass(ss['marks_obtained'], passmark),
                        })
                    else:
                        field_key = f'mark_{student["student_id"]}_{as_pk}'
                        raw = (request.POST.get(field_key) or '').strip()
                        if not raw:
                            errors[field_key] = f'Mark required for {student["full_name"]} — {ss["subject_name"]}.'
                            continue
                        try:
                            from decimal import Decimal, InvalidOperation
                            mark = Decimal(raw)
                            if mark < 0:
                                raise ValueError
                        except (ValueError, InvalidOperation):
                            errors[field_key] = f'Invalid mark for {student["full_name"]} — {ss["subject_name"]}.'
                            continue

                        total_str = total_marks_map.get(str(as_pk))
                        if total_str:
                            total_dec = Decimal(total_str)
                            if mark > total_dec:
                                errors[field_key] = (
                                    f'Mark {mark} exceeds total {total_dec} for '
                                    f'{student["full_name"]} — {ss["subject_name"]}.'
                                )
                                continue

                        passmark = subj_map.get(as_pk, {}).get('passmark')
                        passed   = _compute_pass(str(mark), passmark)

                        entry = {
                            'student_id':    student['student_id'],
                            'full_name':     student['full_name'],
                            'class_name':    cls_info['class_name'],
                            'ac_pk':         ac_pk,
                            'as_subj_pk':    as_pk,
                            'subject_name':  ss['subject_name'],
                            'subject_code':  ss['subject_code'],
                            'marks_obtained': str(mark),
                            'total_mark':    total_str,
                            'passmark':      passmark,
                            'from_db':       False,
                            'passed':        passed,
                        }
                        entries_to_save.append(entry)
                        entries_preview.append(entry)

        if errors:
            return render(request, 'assessments/perf_entry/add/perf_entry_part3.html', {
                'assessment':      assessment,
                'class_student_map': class_student_map,
                'total_marks_map': total_marks_map,
                'not_found_ids':   not_found_ids,
                'errors':          errors,
                'post':            request.POST,
            })

        session_data['entries_to_save']  = entries_to_save
        session_data['entries_preview']  = entries_preview
        request.session[_entry_session_key(pk)] = session_data
        request.session.modified = True

        return redirect(reverse('assessments:perf_entry_part4', args=[pk]))

    return render(request, 'assessments/perf_entry/add/perf_entry_part3.html', {
        'assessment':      assessment,
        'class_student_map': class_student_map,
        'total_marks_map': total_marks_map,
        'not_found_ids':   not_found_ids,
        'errors':          {},
        'post':            {},
    })


def _compute_pass(marks_str, passmark_str):
    """Returns 'Pass', 'Tried', or None (if passmark not set)."""
    if not passmark_str:
        return None
    try:
        from decimal import Decimal
        m = Decimal(str(marks_str))
        p = Decimal(str(passmark_str))
        return 'Pass' if m >= p else 'Tried'
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════════════
#  ADD FLOW — PART 4: Preview + confirm with password
# ═════════════════════════════════════════════════════════════════════════════

@login_required
@has_permission("add_performance_entry", action='create')
def perf_entry_part4(request, pk):
    """
    GET  — display preview table.
           From-DB cells show ✔ icon.  New submissions show the entered mark.
           Passmark status shown for every row.
    POST — validate user password, save to DB inside a transaction,
           update/create EntryStatus rows, clear session.
    """
    assessment   = get_object_or_404(Assessment, pk=pk)
    session_data = request.session.get(_entry_session_key(pk))

    if not session_data or 'entries_to_save' not in session_data:
        messages.error(request, 'Session expired. Please start from Step 1.')
        return redirect(reverse('assessments:perf_entry_part1', args=[pk]))

    entries_preview  = session_data['entries_preview']
    entries_to_save  = session_data['entries_to_save']
    chosen_classes   = session_data['chosen_classes']
    chosen_subjects  = session_data['chosen_subjects']
    class_subjects   = session_data['class_subjects']

    # Build a grouped preview for the template
    preview_by_class = {}
    for entry in entries_preview:
        ac_pk = entry['ac_pk']
        if ac_pk not in preview_by_class:
            as_pks    = chosen_subjects.get(str(ac_pk), [])
            subj_hdrs = [
                s for s in class_subjects.get(str(ac_pk), [])
                if s['as_subj_pk'] in as_pks
            ]
            preview_by_class[ac_pk] = {
                'class_name':      entry['class_name'],
                'subject_headers': subj_hdrs,
                'rows':            {},   # student_id → {sub_pk: entry}
            }
        rows = preview_by_class[ac_pk]['rows']
        sid  = entry['student_id']
        if sid not in rows:
            rows[sid] = {'full_name': entry['full_name'], 'cells': {}}
        rows[sid]['cells'][entry['as_subj_pk']] = entry

    if request.method == 'POST':
        password = request.POST.get('confirm_password', '').strip()
        user     = authenticate(request, username=request.user.username, password=password)

        if user is None:
            messages.error(request, 'Incorrect password. Please try again.')
            return render(request, 'assessments/perf_entry/add/perf_entry_part4.html', {
                'assessment':     assessment,
                'preview_by_class': preview_by_class,
                'chosen_classes': chosen_classes,
                'chosen_subjects': chosen_subjects,
                'class_subjects': class_subjects,
                'errors':         {'confirm_password': 'Incorrect password.'},
            })

        with transaction.atomic():
            # ── Save new performance rows ────────────────────────────────────
            for entry in entries_to_save:
                student   = Student.objects.get(student_id=entry['student_id'])
                as_subj   = AssessmentSubject.objects.get(pk=entry['as_subj_pk'])
                ac        = AssessmentClass.objects.get(pk=entry['ac_pk'])

                AssessmentPerformance.objects.get_or_create(
                    assessment   = assessment,
                    student      = student,
                    subject      = as_subj.subject,
                    school_class = student.current_class,
                    defaults={
                        'marks_obtained': entry['marks_obtained'],
                        'entered_by':     request.user,
                    }
                )

            # ── Update EntryStatus per (class × subject) ─────────────────────
            # Gather all ac_pk/as_subj_pk combos touched in this batch
            touched = {}   # (ac_pk, as_subj_pk) → [entries]
            for entry in entries_preview:  # both from_db and new
                key = (entry['ac_pk'], entry['as_subj_pk'])
                touched.setdefault(key, []).append(entry)

            for (ac_pk, as_subj_pk), batch_entries in touched.items():
                ac      = AssessmentClass.objects.get(pk=ac_pk)
                as_subj = AssessmentSubject.objects.get(pk=as_subj_pk)

                status, created = AssessmentPerformanceEntryStatus.objects.get_or_create(
                    assessment   = assessment,
                    school_class = ac,
                    subject      = as_subj,
                    defaults={
                        'students_attended': ac.students_attended,
                    }
                )

                # Count total performances for this class+subject now in DB
                total_entered = AssessmentPerformance.objects.filter(
                    assessment   = assessment,
                    school_class = ac.school_class,
                    subject      = as_subj.subject,
                ).count()

                passed_count = sum(
                    1 for e in batch_entries if e.get('passed') == 'Pass'
                )
                tried_count = sum(
                    1 for e in batch_entries if e.get('passed') == 'Tried'
                )

                status.students_attended = ac.students_attended
                status.students_entered  = total_entered
                status.students_left     = max(0, ac.students_attended - total_entered)
                status.students_passed  += passed_count
                status.students_tried   += tried_count

                if total_entered >= ac.students_attended:
                    status.attendance_entry_met = True
                    status.is_done              = True

                status.save()

        _clear_entry_session(request, pk)
        messages.success(request, 'Performance records saved successfully.')
        return redirect(reverse('assessments:detail', args=[pk]))

    return render(request, 'assessments/perf_entry/add/perf_entry_part4.html', {
        'assessment':      assessment,
        'preview_by_class': preview_by_class,
        'chosen_classes':  chosen_classes,
        'chosen_subjects': chosen_subjects,
        'class_subjects':  class_subjects,
        'errors':          {},
    })


# ═════════════════════════════════════════════════════════════════════════════
#  ENABLE-EDIT FLOW — PART 1: Choose classes + subjects to unlock
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def enable_edit_part1(request, pk):
    """
    GET  — show classes and their subjects categorised as Done / Not Done.
    POST — user picks classes+subjects to enable + enters password.
           Validates password, sets is_edit_allowed=True on the chosen
           EntryStatus rows, and also sets mod.edit_performance=True if needed.
    """
    assessment = get_object_or_404(Assessment, pk=pk)

    assessment_classes = list(
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )

    # Build display: per class, subjects split into done vs not-done
    class_subject_status = []
    for ac in assessment_classes:
        subjects = list(
            AssessmentSubject.objects.filter(
                assessment=assessment,
                assessment_class=ac.school_class,
            ).select_related('subject')
        )
        status_map = {
            es.subject_id: es
            for es in AssessmentPerformanceEntryStatus.objects.filter(
                assessment=assessment,
                school_class=ac,
            )
        }
        done_subs    = []
        not_done_subs = []
        for s in subjects:
            es = status_map.get(s.pk)
            if es and es.is_done:
                done_subs.append({'as_subj': s, 'status': es})
            else:
                not_done_subs.append({'as_subj': s, 'status': es})

        class_subject_status.append({
            'ac':          ac,
            'done':        done_subs,
            'not_done':    not_done_subs,
        })

    if request.method == 'POST':
        errors   = {}
        to_enable = []   # list of (ac, as_subj) pairs

        for cls_data in class_subject_status:
            ac = cls_data['ac']
            for item in cls_data['done']:
                field = f'enable_{ac.pk}_{item["as_subj"].pk}'
                if request.POST.get(field):
                    to_enable.append((ac, item['as_subj']))

        if not to_enable:
            errors['selection'] = 'Please select at least one subject to enable for editing.'

        password = request.POST.get('confirm_password', '').strip()
        user     = authenticate(request, username=request.user.username, password=password)
        if user is None:
            errors['confirm_password'] = 'Incorrect password.'

        if errors:
            return render(request, 'assessments/perf_entry/enable_edit_part1.html', {
                'assessment':          assessment,
                'class_subject_status': class_subject_status,
                'errors':              errors,
            })

        with transaction.atomic():
            for ac, as_subj in to_enable:
                status = AssessmentPerformanceEntryStatus.objects.filter(
                    assessment=assessment,
                    school_class=ac,
                    subject=as_subj,
                ).first()
                if status:
                    status.is_edit_allowed = True
                    status.is_done         = False
                    status.save(update_fields=['is_edit_allowed', 'is_done'])

            # Ensure the modification record allows performance editing
            mod = _get_or_create_mod(assessment)
            mod.modify_performance = True
            mod.save(update_fields=['modify_performance'])

        messages.success(
            request,
            f'Edit unlocked for {len(to_enable)} subject(s). '
            'Teachers can now modify those performance records.'
        )
        return redirect(reverse('assessments:detail', args=[pk]))

    return render(request, 'assessments/perf_entry/enable_edit_part1.html', {
        'assessment':          assessment,
        'class_subject_status': class_subject_status,
        'errors':              {},
    })


# ═════════════════════════════════════════════════════════════════════════════
#  EDIT FLOW — PART 1: Enter student IDs + choose class (edit-only)
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def perf_edit_part1(request, pk):
    """
    Edit flow mirrors the add flow but:
      - Only classes/subjects with is_edit_allowed=True are shown.
      - Students not found in performance records are reported but not added.
    """
    assessment = get_object_or_404(Assessment, pk=pk)
    mod        = _get_or_create_mod(assessment)

    if not mod.modify_performance:
        messages.error(request, 'Performance editing is not currently open.')
        return redirect(reverse('assessments:detail', args=[pk]))

    # Only show classes that have at least one subject with is_edit_allowed
    assessment_classes = list(
        AssessmentClass.objects
        .filter(assessment=assessment)
        .select_related('school_class__supported_class')
        .order_by('school_class__supported_class__order')
    )

    editable_acs = []
    for ac in assessment_classes:
        has_editable = AssessmentPerformanceEntryStatus.objects.filter(
            assessment=assessment,
            school_class=ac,
            is_edit_allowed=True,
        ).exists()
        if has_editable:
            editable_acs.append(ac)

    if not editable_acs:
        messages.error(request, 'No subjects are currently open for editing. Use "Enable Edit" first.')
        return redirect(reverse('assessments:detail', args=[pk]))

    if request.method == 'POST':
        raw_ids          = request.POST.get('student_ids', '')
        chosen_class_pks = request.POST.getlist('classes')

        errors = {}
        if not chosen_class_pks:
            errors['classes'] = 'Please select at least one class.'
        raw_student_ids = [s.strip().upper() for s in raw_ids.replace(',', '\n').splitlines() if s.strip()]
        if not raw_student_ids:
            errors['student_ids'] = 'Please enter at least one student ID.'

        if errors:
            return render(request, 'assessments/perf_edit_part1.html', {
                'assessment':    assessment,
                'editable_acs':  editable_acs,
                'errors':        errors,
                'post':          request.POST,
            })

        valid_acs = [ac for ac in editable_acs if str(ac.pk) in chosen_class_pks]
        if not valid_acs:
            errors['classes'] = 'Invalid class selection.'
            return render(request, 'assessments/perf_edit_part1.html', {
                'assessment':    assessment,
                'editable_acs':  editable_acs,
                'errors':        errors,
                'post':          request.POST,
            })

        class_subjects = _build_class_subjects(assessment, valid_acs, skip_done=False)
        sc_pk_to_ac    = {ac.school_class_id: ac for ac in valid_acs}

        found_students  = []
        not_found_ids   = []

        for sid in raw_student_ids:
            student = Student.objects.filter(student_id__iexact=sid).first()
            if not student:
                not_found_ids.append({'id': sid, 'reason': 'Student not found.'})
                continue

            ac = sc_pk_to_ac.get(student.current_class_id)
            if not ac:
                not_found_ids.append({
                    'id': sid,
                    'reason': f'{student.full_name} not in selected editable classes.',
                })
                continue

            subjects_for_class = class_subjects.get(ac.pk, [])
            existing_perfs = {
                perf.subject_id: perf
                for perf in AssessmentPerformance.objects.filter(
                    assessment=assessment,
                    student=student,
                    school_class=student.current_class,
                )
            }

            # Edit flow: only include students that already have a performance record
            has_any_perf = any(s.subject_id in existing_perfs for s in subjects_for_class)
            if not has_any_perf:
                not_found_ids.append({
                    'id': sid,
                    'reason': f'{student.full_name} has no existing performance to edit.',
                })
                continue

            subject_status = []
            for as_subj in subjects_for_class:
                perf = existing_perfs.get(as_subj.subject_id)
                subject_status.append({
                    'as_subj_pk':     as_subj.pk,
                    'subject_pk':     as_subj.subject_id,
                    'subject_name':   as_subj.subject.name,
                    'subject_code':   as_subj.subject.code,
                    'marks_obtained': str(perf.marks_obtained) if perf else None,
                    'perf_pk':        perf.pk if perf else None,
                })

            found_students.append({
                'student_id':    student.student_id,
                'full_name':     student.full_name,
                'ac_pk':         ac.pk,
                'class_name':    ac.school_class.supported_class.name,
                'subject_status': subject_status,
            })

        class_subjects_serialisable = {
            str(ac.pk): [
                {
                    'as_subj_pk':   s.pk,
                    'subject_pk':   s.subject_id,
                    'subject_name': s.subject.name,
                    'subject_code': s.subject.code,
                    'passmark':     str(s.passmark) if s.passmark else None,
                }
                for s in subs
            ]
            for ac, subs in [(ac, class_subjects.get(ac.pk, [])) for ac in valid_acs]
        }

        chosen_classes_info = [
            {'ac_pk': ac.pk, 'class_name': ac.school_class.supported_class.name}
            for ac in valid_acs
        ]

        session_data = {
            'not_found_ids':   not_found_ids,
            'found_students':  found_students,
            'chosen_classes':  chosen_classes_info,
            'class_subjects':  class_subjects_serialisable,
        }
        request.session[_edit_session_key(pk)] = session_data
        request.session.modified = True
        return redirect(reverse('assessments:perf_edit_part2', args=[pk]))

    return render(request, 'assessments/perf_edit_part1.html', {
        'assessment':   assessment,
        'editable_acs': editable_acs,
        'errors':       {},
        'post':         {},
    })


# ═════════════════════════════════════════════════════════════════════════════
#  EDIT FLOW — PART 2: Choose subjects per class
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def perf_edit_part2(request, pk):
    assessment   = get_object_or_404(Assessment, pk=pk)
    session_data = request.session.get(_edit_session_key(pk))

    if not session_data:
        messages.error(request, 'Session expired. Please start from Edit Step 1.')
        return redirect(reverse('assessments:perf_edit_part1', args=[pk]))

    chosen_classes = session_data['chosen_classes']
    class_subjects = session_data['class_subjects']
    not_found_ids  = session_data.get('not_found_ids', [])

    if request.method == 'POST':
        errors          = {}
        chosen_subjects = {}

        for cls_info in chosen_classes:
            ac_pk     = cls_info['ac_pk']
            available = class_subjects.get(str(ac_pk), [])
            selected  = request.POST.getlist(f'subjects_{ac_pk}')
            valid_pks = {str(s['as_subj_pk']) for s in available}
            chosen    = [s for s in selected if s in valid_pks]

            if not chosen:
                errors[f'subjects_{ac_pk}'] = (
                    f'Please select at least one subject for {cls_info["class_name"]}.'
                )
            else:
                chosen_subjects[str(ac_pk)] = [int(p) for p in chosen]

        if errors:
            return render(request, 'assessments/perf_edit_part2.html', {
                'assessment':    assessment,
                'chosen_classes': chosen_classes,
                'class_subjects': class_subjects,
                'not_found_ids': not_found_ids,
                'errors':        errors,
                'post':          request.POST,
            })

        # Filter students to only chosen subjects
        def _filter(students, chosen_subjects):
            result = []
            for s in students:
                ac_pk     = str(s['ac_pk'])
                chosen_as = set(chosen_subjects.get(ac_pk, []))
                new_ss    = [ss for ss in s['subject_status'] if ss['as_subj_pk'] in chosen_as]
                if new_ss:
                    result.append({**s, 'subject_status': new_ss})
            return result

        filtered = _filter(session_data['found_students'], chosen_subjects)

        all_as_pks = {p for pks in chosen_subjects.values() for p in pks}
        total_marks_map = {
            str(tm.subject_id): str(tm.total_mark)
            for tm in AssessmentTotalMark.objects.filter(
                assessment=assessment,
                subject_id__in=all_as_pks,
            )
        }

        session_data['chosen_subjects']  = chosen_subjects
        session_data['filtered_students'] = filtered
        session_data['total_marks_map']  = total_marks_map
        request.session[_edit_session_key(pk)] = session_data
        request.session.modified = True
        return redirect(reverse('assessments:perf_edit_part3', args=[pk]))

    return render(request, 'assessments/perf_edit_part2.html', {
        'assessment':    assessment,
        'chosen_classes': chosen_classes,
        'class_subjects': class_subjects,
        'not_found_ids': not_found_ids,
        'errors':        {},
        'post':          {},
    })


# ═════════════════════════════════════════════════════════════════════════════
#  EDIT FLOW — PART 3: Enter updated marks
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def perf_edit_part3(request, pk):
    assessment   = get_object_or_404(Assessment, pk=pk)
    session_data = request.session.get(_edit_session_key(pk))

    if not session_data or 'chosen_subjects' not in session_data:
        messages.error(request, 'Session expired. Please start from Edit Step 1.')
        return redirect(reverse('assessments:perf_edit_part1', args=[pk]))

    chosen_classes    = session_data['chosen_classes']
    class_subjects    = session_data['class_subjects']
    chosen_subjects   = session_data['chosen_subjects']
    filtered_students = session_data['filtered_students']
    total_marks_map   = session_data['total_marks_map']

    class_student_map = {}
    for cls_info in chosen_classes:
        ac_pk     = cls_info['ac_pk']
        as_pks = [int(x) for x in chosen_subjects.get(str(ac_pk), [])]
        subj_hdrs = [
            s for s in class_subjects.get(str(ac_pk), [])
            if s['as_subj_pk'] in as_pks
        ]
        students_here = [s for s in filtered_students if s['ac_pk'] == ac_pk]
        class_student_map[ac_pk] = {
            'class_name':      cls_info['class_name'],
            'subject_headers': subj_hdrs,
            'students':        students_here,
        }

    if request.method == 'POST':
        errors         = {}
        entries_update = []

        for cls_info in chosen_classes:
            ac_pk    = cls_info['ac_pk']
            as_pks = [int(x) for x in chosen_subjects.get(str(ac_pk), [])]
            subj_map = {
                s['as_subj_pk']: s
                for s in class_subjects.get(str(ac_pk), [])
                if s['as_subj_pk'] in as_pks
            }
            students_here = [s for s in filtered_students if s['ac_pk'] == ac_pk]

            for student in students_here:
                for ss in student['subject_status']:
                    as_pk = ss['as_subj_pk']
                    if as_pk not in as_pks:
                        continue

                    field_key = f'mark_{student["student_id"]}_{as_pk}'
                    print("field key:", field_key or '4589458945878')
                    

                    raw = (request.POST.get(field_key) or '').strip()
                    print("Raw:", raw or '000000000000000000000')
                    if not raw:
                        errors[field_key] = (
                            f'Mark required for {student["full_name"]} — {ss["subject_name"]}.,,,,,,,, {field_key}'
                        )
                        continue

                    try:
                        from decimal import Decimal, InvalidOperation
                        mark = Decimal(raw)
                        if mark < 0:
                            raise ValueError
                    except (ValueError, InvalidOperation):
                        errors[field_key] = (
                            f'Invalid mark for {student["full_name"]} — {ss["subject_name"]}.'
                        )
                        continue

                    total_str = total_marks_map.get(str(as_pk))
                    if total_str:
                        from decimal import Decimal
                        if mark > Decimal(total_str):
                            errors[field_key] = (
                                f'Mark {mark} exceeds total {total_str} for '
                                f'{student["full_name"]} — {ss["subject_name"]}.'
                            )
                            continue

                    passmark = subj_map.get(as_pk, {}).get('passmark')
                    entries_update.append({
                        'perf_pk':       ss.get('perf_pk'),
                        'student_id':    student['student_id'],
                        'full_name':     student['full_name'],
                        'class_name':    cls_info['class_name'],
                        'ac_pk':         ac_pk,
                        'as_subj_pk':    as_pk,
                        'subject_name':  ss['subject_name'],
                        'subject_code':  ss['subject_code'],
                        'old_marks':     ss['marks_obtained'],
                        'marks_obtained': str(mark),
                        'total_mark':    total_str,
                        'passmark':      passmark,
                        'passed':        _compute_pass(str(mark), passmark),
                    })

        if errors:
            return render(request, 'assessments/perf_edit_part3.html', {
                'assessment':      assessment,
                'class_student_map': class_student_map,
                'total_marks_map': total_marks_map,
                'errors':          errors,
                'post':            request.POST,
            })

        session_data['entries_update'] = entries_update
        request.session[_edit_session_key(pk)] = session_data
        request.session.modified = True
        return redirect(reverse('assessments:perf_edit_part4', args=[pk]))

    return render(request, 'assessments/perf_edit_part3.html', {
        'assessment':      assessment,
        'class_student_map': class_student_map,
        'total_marks_map': total_marks_map,
        'errors':          {},
        'post':            {},
    })


# ═════════════════════════════════════════════════════════════════════════════
#  EDIT FLOW — PART 4: Preview + confirm + save
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def perf_edit_part4(request, pk):
    assessment   = get_object_or_404(Assessment, pk=pk)
    session_data = request.session.get(_edit_session_key(pk))

    if not session_data or 'entries_update' not in session_data:
        messages.error(request, 'Session expired. Please start from Edit Step 1.')
        return redirect(reverse('assessments:perf_edit_part1', args=[pk]))

    entries_update = session_data['entries_update']
    chosen_classes = session_data['chosen_classes']
    chosen_subjects = session_data['chosen_subjects']
    class_subjects  = session_data['class_subjects']

    preview_by_class = {}
    for entry in entries_update:
        ac_pk = entry['ac_pk']
        if ac_pk not in preview_by_class:
            as_pks    = chosen_subjects.get(str(ac_pk), [])
            subj_hdrs = [
                s for s in class_subjects.get(str(ac_pk), [])
                if s['as_subj_pk'] in as_pks
            ]
            preview_by_class[ac_pk] = {
                'class_name':      entry['class_name'],
                'subject_headers': subj_hdrs,
                'rows':            {},
            }
        rows = preview_by_class[ac_pk]['rows']
        sid  = entry['student_id']
        if sid not in rows:
            rows[sid] = {'full_name': entry['full_name'], 'cells': {}}
        rows[sid]['cells'][entry['as_subj_pk']] = entry

    if request.method == 'POST':
        password = request.POST.get('confirm_password', '').strip()
        user     = authenticate(request, username=request.user.username, password=password)

        if user is None:
            messages.error(request, 'Incorrect password.')
            return render(request, 'assessments/perf_edit_part4.html', {
                'assessment':      assessment,
                'preview_by_class': preview_by_class,
                'chosen_classes':  chosen_classes,
                'errors':          {'confirm_password': 'Incorrect password.'},
            })

        with transaction.atomic():
            updated_ac_subj = set()

            for entry in entries_update:
                if entry['perf_pk']:
                    try:
                        perf = AssessmentPerformance.objects.get(pk=entry['perf_pk'])
                        perf.marks_obtained = entry['marks_obtained']
                        perf.entered_by     = request.user
                        perf.save(update_fields=['marks_obtained', 'entered_by'])
                    except AssessmentPerformance.DoesNotExist:
                        pass
                updated_ac_subj.add((entry['ac_pk'], entry['as_subj_pk']))

            # Turn off is_edit_allowed for all modified class+subject pairs
            for ac_pk, as_subj_pk in updated_ac_subj:
                status = AssessmentPerformanceEntryStatus.objects.filter(
                    assessment=assessment,
                    school_class_id=ac_pk,
                    subject_id=as_subj_pk,
                ).first()
                if status:
                    status.is_edit_allowed = False
                    status.is_done         = True
                    status.save(update_fields=['is_edit_allowed', 'is_done'])

            # If no more edit_allowed statuses remain, turn off mod.modify_performance
            still_open = AssessmentPerformanceEntryStatus.objects.filter(
                assessment=assessment,
                is_edit_allowed=True,
            ).exists()
            if not still_open:
                mod = _get_or_create_mod(assessment)
                mod.modify_performance = False
                mod.save(update_fields=['modify_performance'])

        _clear_edit_session(request, pk)
        messages.success(request, 'Performance records updated successfully.')
        return redirect(reverse('assessments:detail', args=[pk]))

    return render(request, 'assessments/perf_edit_part4.html', {
        'assessment':      assessment,
        'preview_by_class': preview_by_class,
        'chosen_classes':  chosen_classes,
        'errors':          {},
    })
