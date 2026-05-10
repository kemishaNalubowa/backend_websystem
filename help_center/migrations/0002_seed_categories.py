from django.db import migrations

CATEGORIES = [
    {
        'title':       'Dashboard',
        'slug':        'dashboard',
        'description': 'Understanding your dashboard overview, statistics cards, and quick-access shortcuts.',
        'icon':        'bi-speedometer2',
        'order':       1,
    },
    {
        'title':       'Academic Year',
        'slug':        'academic-year',
        'description': 'How to create, activate, and manage the school academic year.',
        'icon':        'bi-calendar3',
        'order':       2,
    },
    {
        'title':       'Terms',
        'slug':        'terms',
        'description': 'Setting up and managing school terms within an academic year.',
        'icon':        'bi-calendar-range',
        'order':       3,
    },
    {
        'title':       'School Profile',
        'slug':        'school-profile',
        'description': 'Updating your school name, logo, address, and contact information.',
        'icon':        'bi-building',
        'order':       4,
    },
    {
        'title':       'School Settings',
        'slug':        'school-settings',
        'description': 'Configuring system-wide preferences and school-level options.',
        'icon':        'bi-gear',
        'order':       5,
    },
    {
        'title':       'Subjects',
        'slug':        'subjects',
        'description': 'Adding and managing the subjects offered across your school.',
        'icon':        'bi-book',
        'order':       6,
    },
    {
        'title':       'Supported Classes',
        'slug':        'supported-classes',
        'description': 'Defining the class levels your school supports, such as P1 through P7.',
        'icon':        'bi-diagram-3',
        'order':       7,
    },
    {
        'title':       'Class Teachers',
        'slug':        'class-teachers',
        'description': 'Assigning teachers to classes and managing class teacher records.',
        'icon':        'bi-person-workspace',
        'order':       8,
    },
    {
        'title':       'Admissions',
        'slug':        'admissions',
        'description': 'Processing new student admission requests and managing admission status.',
        'icon':        'bi-person-plus',
        'order':       9,
    },
    {
        'title':       'Students',
        'slug':        'students',
        'description': 'Enrolling students, viewing profiles, and managing student records.',
        'icon':        'bi-mortarboard',
        'order':       10,
    },
    {
        'title':       'Teachers',
        'slug':        'teachers',
        'description': 'Adding teacher profiles, qualifications, and subject assignments.',
        'icon':        'bi-person-badge',
        'order':       11,
    },
    {
        'title':       'Users',
        'slug':        'users',
        'description': 'Managing system user accounts, roles, and login access.',
        'icon':        'bi-people',
        'order':       12,
    },
    {
        'title':       'Permissions',
        'slug':        'permissions',
        'description': 'Setting up role-based access control and assigning permissions to user types.',
        'icon':        'bi-shield-lock',
        'order':       13,
    },
    {
        'title':       'Fees',
        'slug':        'fees',
        'description': 'Configuring school fee structures for terms and class levels.',
        'icon':        'bi-cash-stack',
        'order':       14,
    },
    {
        'title':       'Assessment Fees',
        'slug':        'assessment-fees',
        'description': 'Setting up and managing fees tied to student assessments.',
        'icon':        'bi-receipt',
        'order':       15,
    },
    {
        'title':       'Payments',
        'slug':        'payments',
        'description': 'Recording fee payments, viewing payment history, and generating receipts.',
        'icon':        'bi-credit-card',
        'order':       16,
    },
    {
        'title':       'Scholastic Requirements',
        'slug':        'scholastic-requirements',
        'description': 'Defining items students are required to bring or purchase each term.',
        'icon':        'bi-bag',
        'order':       17,
    },
    {
        'title':       'Scholastic Payments',
        'slug':        'scholastic-payments',
        'description': 'Recording and tracking payments made against scholastic requirements.',
        'icon':        'bi-bag-check',
        'order':       18,
    },
    {
        'title':       'Assessments',
        'slug':        'assessments',
        'description': 'Creating assessments, entering marks, and managing student results.',
        'icon':        'bi-clipboard-check',
        'order':       19,
    },
    {
        'title':       'Announcements',
        'slug':        'announcements',
        'description': 'Publishing school-wide announcements visible to staff and parents.',
        'icon':        'bi-megaphone',
        'order':       20,
    },
    {
        'title':       'Events',
        'slug':        'events',
        'description': 'Creating and managing school events on the calendar.',
        'icon':        'bi-calendar-event',
        'order':       21,
    },
    {
        'title':       'Parent Requests',
        'slug':        'parent-requests',
        'description': 'Viewing and responding to requests submitted by parents through the portal.',
        'icon':        'bi-envelope-paper',
        'order':       22,
    },
]


def seed_categories(apps, schema_editor):
    HelpCategory = apps.get_model('help_center', 'HelpCategory')
    for cat in CATEGORIES:
        HelpCategory.objects.get_or_create(
            slug=cat['slug'],
            defaults={
                'title':       cat['title'],
                'description': cat['description'],
                'icon':        cat['icon'],
                'order':       cat['order'],
            }
        )


def unseed_categories(apps, schema_editor):
    HelpCategory = apps.get_model('help_center', 'HelpCategory')
    HelpCategory.objects.filter(
        slug__in=[cat['slug'] for cat in CATEGORIES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('help_center', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_code=unseed_categories),
    ]