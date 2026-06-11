import os
import django
from datetime import date, datetime
from django.utils import timezone

# Configure settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_websystem.settings')
django.setup()

from authentication.models import CustomUser
from accounts.models import ParentProfile
from students.models import Student, StudentParentRelationship
from academics.models import SchoolSupportedClasses, SchoolStream, Term, Subject, SchoolClass
from fees.models import SchoolFees, FeesPayment, StudentFeesPaymentsStatus
from assessments.models import Assessment, AssessmentSubject, AssessmentPerformance, AssessmentTotalMark
from school.models import SchoolAnnouncement, SchoolEvent

def seed_data():
    print("Starting database seeding...")

    # 1. Fetch Student & Parent
    student = Student.objects.filter(student_id='STD20260001').first()
    if not student:
        print("[ERROR] Student muwonge deo (STD20260001) not found in database!")
        return

    # 2. Supported Class
    supported_class = SchoolSupportedClasses.objects.filter(pk=24).first() # Primary Three
    if not supported_class:
        print("[ERROR] Supported class Primary Three (PK 24) not found!")
        return

    # 3. Stream
    school_class = SchoolClass.objects.get(pk=6) # Primary Three
    stream, created = SchoolStream.objects.get_or_create(
        name='Lavender',
        class_level=school_class,
        defaults={'is_active': True}
    )
    if created:
        print(f"Created stream: {stream.name}")

    # 4. Assign student details
    student.current_class = supported_class
    student.school_stream = stream
    student.date_enrolled = date(2023, 1, 10)
    student.academic_year = '2025/2026'
    student.save()
    print(f"Updated student {student.full_name}: Class={supported_class.supported_class.name}, Stream={stream.name}")

    # 5. Terms
    term = Term.objects.filter(pk=2).first() # Term 2
    if not term:
        term = Term.objects.create(name='Term 2', start_date=date(2026, 5, 1), end_date=date(2026, 8, 30), is_active=True)
        print("Created Term 2")
    else:
        term.is_active = True
        term.save()
        print("Term 2 found and activated.")

    # Make Term 1 inactive
    Term.objects.filter(pk=1).update(is_active=False)

    # 6. School Fees
    fee, created = SchoolFees.objects.get_or_create(
        term=term,
        fees_type='tuition',
        is_active=True,
        defaults={
            'title': 'Term 2 Tuition Fees',
            'amount': 450000.0,
            'description': 'Standard tuition fees for Primary Three',
            'due_date': date(2026, 6, 30)
        }
    )
    from fees.models import FeesClass
    FeesClass.objects.get_or_create(
        fees=fee,
        school_class=supported_class
    )
    print(f"Set up School Fee: {fee.title} = {fee.amount} UGX")

    # 7. Student Fees Payment Status
    status, created = StudentFeesPaymentsStatus.objects.get_or_create(
        student=student,
        school_fees=fee,
        defaults={
            'payment_type': 'school_fees',
            'school_class': supported_class,
            'amount_paid': 300000.0,
            'amount_balance': 150000.0,
            'fully_paid': False
        }
    )
    if not created:
        status.amount_paid = 300000.0;
        status.amount_balance = 150000.0;
        status.fully_paid = False;
        status.save()
    print(f"Set student payment status: Paid={status.amount_paid}, Balance={status.amount_balance}")

    # 8. Fees Payment Transaction
    payment, created = FeesPayment.objects.get_or_create(
        receipt_number='MM987654321',
        defaults={
            'student': student,
            'term': term,
            'school_fees': fee,
            'school_class': supported_class,
            'amount': 300000.0,
            'payment_date': date(2026, 5, 15)
        }
    )
    print(f"Created payment receipt: {payment.receipt_number} for {payment.amount} UGX")

    # 9. Assessments
    midterm, created = Assessment.objects.get_or_create(
        title='Mid-Term Examinations',
        term=term,
        assessment_type='midterm',
        defaults={
            'date_given': date(2026, 4, 10),
            'month': 6,
            'is_published': True,
            'results_published': True
        }
    )
    finalterm, created = Assessment.objects.get_or_create(
        title='End of Term Examinations',
        term=term,
        assessment_type='final',
        defaults={
            'date_given': date(2026, 5, 25),
            'month': 6,
            'is_published': True,
            'results_published': True
        }
    )
    print("Created midterm and final assessments.")

    # 10. Subjects and Grades
    subjects_info = {
        'Mathematics': {'mid': 88.0, 'final': 92.0, 'comment': 'Excellent numerical skills.'},
        'English': {'mid': 75.0, 'final': 78.0, 'comment': 'Good comprehension and composition.'},
        'Science': {'mid': 82.0, 'final': 85.0, 'comment': 'Great enthusiasm for practical work.'},
        'Social Studies': {'mid': 68.0, 'final': 72.0, 'comment': 'Keen interest in community topics.'}
    }

    for sub_name, scores in subjects_info.items():
        subject = Subject.objects.filter(name=sub_name).first()
        if not subject:
            subject = Subject.objects.create(name=sub_name, code=sub_name[:3].upper())
            print(f"Created subject: {sub_name}")

        # Midterm Assessment Subject
        sub_mid, _ = AssessmentSubject.objects.get_or_create(
            assessment=midterm,
            assessment_class=supported_class,
            subject=subject,
            defaults={'passmark': 50.0}
        )
        # Midterm Total Mark
        AssessmentTotalMark.objects.get_or_create(
            assessment=midterm,
            subject=sub_mid,
            defaults={'total_mark': 100.0}
        )
        # Midterm Performance
        AssessmentPerformance.objects.get_or_create(
            assessment=midterm,
            student=student,
            subject=subject,
            school_class=supported_class,
            defaults={
                'marks_obtained': scores['mid'],
                'comment': scores['comment'],
                'is_verified': True
            }
        )

        # End of Term Assessment Subject
        sub_final, _ = AssessmentSubject.objects.get_or_create(
            assessment=finalterm,
            assessment_class=supported_class,
            subject=subject,
            defaults={'passmark': 50.0}
        )
        # End of Term Total Mark
        AssessmentTotalMark.objects.get_or_create(
            assessment=finalterm,
            subject=sub_final,
            defaults={'total_mark': 100.0}
        )
        # End of Term Performance
        AssessmentPerformance.objects.get_or_create(
            assessment=finalterm,
            student=student,
            subject=subject,
            school_class=supported_class,
            defaults={
                'marks_obtained': scores['final'],
                'comment': scores['comment'],
                'is_verified': True
            }
        )

    print("Populated academic performances for Mathematics, English, Science, and Social Studies.")

    # 11. School Announcements
    announcement, created = SchoolAnnouncement.objects.get_or_create(
        title='Upcoming Parents General Meeting',
        defaults={
            'content': 'Dear Parents, there will be a general meeting on Saturday, June 20th at 10:00 AM at the school main hall to discuss academic performance and term closing.',
            'audience': 'parents',
            'priority': 'high',
            'is_published': True,
            'published_at': timezone.now()
        }
    )
    print(f"Created announcement: {announcement.title}")

    # 12. School Events
    event, created = SchoolEvent.objects.get_or_create(
        title='End of Term Exams Begin',
        defaults={
            'description': 'Final examinations for Term 2 will begin for all classes.',
            'event_type': 'exam',
            'start_date': date(2026, 6, 10),
            'end_date': date(2026, 6, 15),
            'is_published': True
        }
    )
    print(f"Created event: {event.title}")

    print("Database seeding completed successfully!")

if __name__ == '__main__':
    seed_data()
