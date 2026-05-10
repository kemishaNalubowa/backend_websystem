from django.db import migrations

SLUG_CATEGORY = 'class-teachers'

ARTICLES = [
    {
        'slug':  'what-are-class-teachers',
        'title': 'What are Class Teachers?',
        'order': 1,
        'content': """
<p>
    A <strong>Class Teacher</strong> is the primary teacher responsible for a
    specific class level. In Ugandan primary schools, the class teacher oversees
    the general welfare, discipline, and progress of students in their assigned class.
</p>

<p>
    The <strong>School Class Teachers</strong> page shows which teacher is
    currently assigned as the class teacher for each supported class.
</p>

<h6 class="fw-semibold mt-4 mb-2">Columns on the Class Teachers list</h6>
<div class="table-responsive">
    <table class="table table-bordered table-sm align-middle">
        <thead class="table-light">
            <tr>
                <th style="width:160px;">Column</th>
                <th>What it means</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Class</strong></td>
                <td>
                    The supported class level the teacher is assigned to,
                    e.g. <em>Primary Two</em>, <em>Baby Class</em>.
                </td>
            </tr>
            <tr>
                <td><strong>Teacher</strong></td>
                <td>
                    The full name of the staff member currently assigned as
                    class teacher for that class.
                </td>
            </tr>
        </tbody>
    </table>
</div>

<div class="alert alert-info mt-3">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>Only assigned classes appear in the list.</strong> A supported class
    that has no class teacher assigned yet will not show a row here. Use
    <strong>Assign Class Teacher</strong> to add one.
</div>

<div class="alert alert-secondary mt-3">
    <i class="bi bi-person-badge me-2"></i>
    <strong>Class Teacher vs Subject Teacher:</strong> A class teacher is the
    teacher in overall charge of a class. A subject teacher (assigned via
    <em>Subjects &rarr; Assign Teacher</em>) teaches a specific subject in a class.
    The same person can hold both roles.
</div>
""",
    },

    {
        'slug':  'how-to-assign-a-class-teacher',
        'title': 'How to Assign a Class Teacher',
        'order': 2,
        'content': """
<p>
    Follow these steps to assign a teacher as the class teacher for a
    specific class.
</p>

<ol class="mt-3">
    <li class="mb-3">
        In the left sidebar, go to <strong>Academics &rarr; Class Teachers</strong>.
    </li>
    <li class="mb-3">
        Click the <strong>
            <i class="bi bi-person-plus"></i> Assign Class Teacher
        </strong> button at the top right. A modal form will open.
    </li>
    <li class="mb-3">
        Fill in the three fields:
        <div class="table-responsive mt-2">
            <table class="table table-bordered table-sm align-middle">
                <thead class="table-light">
                    <tr>
                        <th style="width:170px;">Field</th>
                        <th>What to enter</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Select Class</strong></td>
                        <td>
                            Choose the class level from the dropdown, e.g.
                            <em>Primary Two</em>. Only your school's supported
                            classes appear here.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Staff ID</strong></td>
                        <td>
                            Type the employee ID of the teacher you want to assign,
                            e.g. <code>EMP20250001</code>. The Staff ID is found on
                            the teacher's profile under
                            <strong>Staff &rarr; Teachers</strong>.
                            You must type the exact ID — the field does not
                            auto-suggest.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Your Password</strong></td>
                        <td>
                            Enter your own account login password to authorise
                            the assignment.
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </li>
    <li class="mb-3">
        Click <strong>Assign Teacher</strong>. If all three fields are valid,
        the modal closes and the assignment appears in the list.
    </li>
</ol>

<div class="alert alert-warning mt-3">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <strong>Common errors:</strong>
    <ul class="mb-0 mt-2">
        <li>
            <strong>Wrong Staff ID</strong> — if the ID does not match any
            active staff member, the system will show an error. Double-check
            the ID on the teacher's profile page.
        </li>
        <li>
            <strong>Wrong password</strong> — you must enter <em>your own</em>
            login password, not the teacher's password. The assignment will not
            proceed if the password is incorrect.
        </li>
        <li>
            <strong>Class not in dropdown</strong> — only supported classes
            appear. If a class is missing, first add it under
            <strong>Academics &rarr; Supported Classes</strong>.
        </li>
    </ul>
</div>
""",
    },

    {
        'slug':  'how-to-change-a-class-teacher',
        'title': 'How to Change (Reassign) a Class Teacher',
        'order': 3,
        'content': """
<p>
    If a class teacher needs to be replaced — for example when a teacher transfers
    or a new term begins — you reassign the class using the same
    <strong>Assign Class Teacher</strong> button.
</p>

<ol class="mt-3">
    <li class="mb-3">
        Go to <strong>Academics &rarr; Class Teachers</strong>.
    </li>
    <li class="mb-3">
        Click <strong>
            <i class="bi bi-person-plus"></i> Assign Class Teacher
        </strong>.
    </li>
    <li class="mb-3">
        In the modal, select the <strong>same class</strong> that already has
        a teacher, enter the <strong>Staff ID of the new teacher</strong>, and
        enter <strong>your password</strong>.
    </li>
    <li class="mb-3">
        Click <strong>Assign Teacher</strong>. The previous class teacher
        assignment for that class is replaced with the new one.
    </li>
</ol>

<div class="alert alert-info mt-3">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>The previous teacher is not deleted from the system.</strong>
    Only their <em>class teacher</em> role for that class is removed.
    The teacher's staff profile, any subject assignments, and all other
    records remain untouched.
</div>

<div class="alert alert-secondary mt-3">
    <i class="bi bi-lightbulb-fill me-2"></i>
    <strong>Where to find a teacher's Staff ID:</strong> Go to
    <strong>Staff &rarr; Teachers</strong>, open the teacher's profile,
    and copy the Employee ID shown there (format: <code>EMP20250001</code>).
</div>
""",
    },
]


def seed_articles(apps, schema_editor):
    HelpCategory = apps.get_model('help_center', 'HelpCategory')
    HelpArticle  = apps.get_model('help_center', 'HelpArticle')

    try:
        category = HelpCategory.objects.get(slug=SLUG_CATEGORY)
    except HelpCategory.DoesNotExist:
        return

    for article in ARTICLES:
        HelpArticle.objects.get_or_create(
            slug=article['slug'],
            defaults={
                'category':     category,
                'title':        article['title'],
                'content':      article['content'].strip(),
                'order':        article['order'],
                'is_published': True,
            }
        )


def unseed_articles(apps, schema_editor):
    HelpArticle = apps.get_model('help_center', 'HelpArticle')
    HelpArticle.objects.filter(
        slug__in=[a['slug'] for a in ARTICLES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('help_center', '0006_seed_supported_classes_articles'),
    ]

    operations = [
        migrations.RunPython(seed_articles, reverse_code=unseed_articles),
    ]