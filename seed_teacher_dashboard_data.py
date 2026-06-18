import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_websystem.settings')
django.setup()

from authentication.models import CustomUser
from accounts.models import StaffProfile
from students.models import Student
from academics.models import (
    SchoolSupportedClasses, SchoolStream, Subject,
    SchoolClassTeacher, TeacherClass, TeacherSubject, ClassSubject
)

def run():
    print("Seeding teacher assignments and student enrollment...")

    # Set standard passwords for testing
    password = 'Password@123'

    # Get supported classes
    classes = {
        'p1': SchoolSupportedClasses.objects.filter(supported_class__key='p1').first(),
        'p2': SchoolSupportedClasses.objects.filter(supported_class__key='p2').first(),
        'p3': SchoolSupportedClasses.objects.filter(supported_class__key='p3').first(),
        'p5': SchoolSupportedClasses.objects.filter(supported_class__key='p5').first(),
        'p6': SchoolSupportedClasses.objects.filter(supported_class__key='p6').first(),
    }

    # Ensure Primary Three stream (Lavender) exists
    p3_class = SchoolSupportedClasses.objects.filter(supported_class__key='p3').first()
    if p3_class:
        p3_stream, _ = SchoolStream.objects.get_or_create(
            class_level=p3_class.supported_class,
            name='Lavender',
            defaults={'is_active': True}
        )
    else:
        p3_stream = None

    # Get subjects
    subjects = {
        'ENG': Subject.objects.filter(code='ENG').first(),
        'MTC': Subject.objects.filter(code='MTC').first(),
        'SCI': Subject.objects.filter(code='SCI').first(),
        'SST': Subject.objects.filter(code='SST').first(),
        'RDG': Subject.objects.filter(code='RDG').first(),
    }

    # Map class subjects (ClassSubject)
    for c_key, c_obj in classes.items():
        if not c_obj:
            continue
        for s_key, s_obj in subjects.items():
            if not s_obj:
                continue
            ClassSubject.objects.get_or_create(
                school_class=c_obj,
                subject=s_obj
            )

    # Configure teachers
    teachers_to_assign = [
        {
            'username': 'EMP20260001',
            'name': 'Namulindwa Evelyn',
            'form_class': classes.get('p3'),
            'subject_assignments': [
                {'subject': subjects.get('ENG'), 'class': classes.get('p3'), 'stream': p3_stream},
                {'subject': subjects.get('MTC'), 'class': classes.get('p3'), 'stream': p3_stream},
            ]
        },
        {
            'username': 'EMP20260002',
            'name': 'Ssenkuumba Joel',
            'form_class': classes.get('p2'),
            'subject_assignments': [
                {'subject': subjects.get('SCI'), 'class': classes.get('p2'), 'stream': None},
            ]
        },
        {
            'username': 'EMP20260003',
            'name': 'Nalugwa Ann',
            'form_class': classes.get('p1'),
            'subject_assignments': [
                {'subject': subjects.get('RDG'), 'class': classes.get('p1'), 'stream': None},
            ]
        }
    ]

    for t in teachers_to_assign:
        user = CustomUser.objects.filter(username=t['username']).first()
        if not user:
            print(f"[Warning] Teacher {t['username']} not found. Creating user...")
            user = CustomUser.objects.create_user(
                username=t['username'],
                email=f"{t['username'].lower()}@joksschool.ac.ug",
                password=password,
                full_name=t['name'],
                user_type='staff'
            )
        else:
            user.set_password(password)
            user.save()
            print(f"Updated password for {user.username} ({user.full_name}) to: {password}")

        # Ensure StaffProfile exists
        profile, created = StaffProfile.objects.get_or_create(
            user=user,
            defaults={
                'employee_id': t['username'],
                'role': 'teacher',
                'qualification': 'diploma',
                'employment_type': 'permanent',
                'is_class_teacher': bool(t['form_class']),
                'designation': 'Teacher',
                'monthly_salary': 500000.0,
                'is_active': True,
            }
        )
        if not created:
            profile.role = 'teacher'
            profile.is_class_teacher = bool(t['form_class'])
            profile.save()

        # Class teacher assignment
        if t['form_class']:
            SchoolClassTeacher.objects.get_or_create(
                teacher=user,
                school_class=t['form_class']
            )
            print(f"Assigned {user.full_name} as form teacher for {t['form_class']}")

        # Subject assignments (TeacherClass and TeacherSubject)
        for sa in t['subject_assignments']:
            if not sa['subject'] or not sa['class']:
                continue
            
            # 1. TeacherClass (timetable-level class/stream assignment)
            TeacherClass.objects.get_or_create(
                teacher=user,
                school_class=sa['class'],
                school_stream=sa['stream'],
                defaults={'is_active': True}
            )
            
            # 2. TeacherSubject (teacher subject assignment)
            TeacherSubject.objects.get_or_create(
                teacher=user,
                subject=sa['subject'],
                school_class=sa['class']
            )
            print(f"Assigned {user.full_name} to teach {sa['subject'].name} in {sa['class']}")

    # Assign existing students to supported classes and streams
    students_to_assign = [
        {'student_id': 'STD20260001', 'class': classes.get('p3'), 'stream': p3_stream},
        {'student_id': 'STD20260002', 'class': classes.get('p3'), 'stream': p3_stream},
        {'student_id': 'STD20260003', 'class': classes.get('p3'), 'stream': p3_stream},
        {'student_id': 'STD20260004', 'class': classes.get('p2'), 'stream': None},
        {'student_id': 'STD20260005', 'class': classes.get('p2'), 'stream': None},
        {'student_id': 'STD20260006', 'class': classes.get('p1'), 'stream': None},
    ]

    for s_info in students_to_assign:
        student = Student.objects.filter(student_id=s_info['student_id']).first()
        if student and s_info['class']:
            student.current_class = s_info['class']
            student.school_stream = s_info['stream']
            student.is_active = True
            student.save()
            print(f"Assigned student {student.full_name} ({student.student_id}) to class {s_info['class']} (stream: {s_info['stream']})")
        else:
            print(f"[Warning] Student {s_info['student_id']} not found or class not provided.")

    print("Seeding completed successfully!")

if __name__ == '__main__':
    run()
