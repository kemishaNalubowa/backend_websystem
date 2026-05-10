from django.db import migrations

SLUG_CATEGORY = 'subjects'

ARTICLES = [
    {
        'slug':  'what-is-a-subject',
        'title': 'What is a Subject?',
        'order': 1,
        'content': """
<p>
    A <strong>Subject</strong> is an academic course taught in the school, such as
    English Language, Mathematics, Science, or CRE. Each subject is defined once
    and then linked to the specific classes that study it and the teachers who teach it.
</p>

<h6 class="fw-semibold mt-4 mb-2">Fields on the Subjects list</h6>
<div class="table-responsive">
    <table class="table table-bordered table-sm align-middle">
        <thead class="table-light">
            <tr>
                <th style="width:140px;">Column</th>
                <th>What it means</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Name</strong></td>
                <td>
                    The full name of the subject, e.g. <em>Christian Religious Education</em>.
                </td>
            </tr>
            <tr>
                <td><strong>Code</strong></td>
                <td>
                    A short unique identifier, e.g. <code>CRE</code>, <code>ENG</code>,
                    <code>MAT</code>. Used on report cards and internal records.
                </td>
            </tr>
            <tr>
                <td><strong>Description</strong></td>
                <td>An optional note about the subject.</td>
            </tr>
            <tr>
                <td><strong>Status</strong></td>
                <td>
                    <span class="badge bg-success">Active</span> or
                    <span class="badge bg-secondary">Inactive</span>.
                    Inactive subjects are hidden from fee and assessment screens.
                </td>
            </tr>
            <tr>
                <td><strong>Actions</strong></td>
                <td>
                    Buttons to view details, edit, delete, assign classes,
                    or assign a teacher.
                </td>
            </tr>
        </tbody>
    </table>
</div>

<div class="alert alert-info mt-3">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>Subjects are school-level records.</strong> A subject is defined once for
    the whole school. You then separately link it to the classes that study it
    (Assign Classes) and the teachers who deliver it (Assign Teacher).
</div>
""",
    },

    {
        'slug':  'how-to-add-a-subject',
        'title': 'How to Add a Subject',
        'order': 2,
        'content': """
<p>Follow these steps to create a new subject in the system.</p>

<ol class="mt-3">
    <li class="mb-3">
        In the left sidebar, go to <strong>Academics &rarr; Subjects</strong>.
    </li>
    <li class="mb-3">
        Click the <strong>Add Subject</strong> button at the top of the list.
    </li>
    <li class="mb-3">
        Fill in the form:
        <div class="table-responsive mt-2">
            <table class="table table-bordered table-sm align-middle">
                <thead class="table-light">
                    <tr>
                        <th style="width:160px;">Field</th>
                        <th>What to enter</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Subject Name</strong></td>
                        <td>
                            The full name of the subject, e.g.
                            <em>Mathematics</em>, <em>English Language</em>,
                            <em>Christian Religious Education</em>.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Code</strong></td>
                        <td>
                            A short unique code, e.g. <code>MAT</code>, <code>ENG</code>,
                            <code>CRE</code>, <code>IRE</code>, <code>SCI</code>.
                            This must be unique — no two subjects can share the same code.
                            It appears on report cards.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Description</strong></td>
                        <td>Optional. A brief note about the subject.</td>
                    </tr>
                    <tr>
                        <td><strong>Active</strong></td>
                        <td>
                            Leave ticked to make the subject available across the system.
                            Untick to hide it from fees, assessments, and reports.
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </li>
    <li class="mb-3">Click <strong>Save</strong> to create the subject.</li>
</ol>

<div class="alert alert-info mt-3">
    <i class="bi bi-lightbulb-fill me-2"></i>
    <strong>Next step after saving:</strong> A subject on its own is not yet
    linked to any classes or teachers. After saving, use
    <strong>Assign Classes</strong> to choose which classes study the subject,
    and <strong>Assign Teacher</strong> to assign teachers per class.
</div>
""",
    },

    {
        'slug':  'how-to-edit-a-subject',
        'title': 'How to Edit a Subject',
        'order': 3,
        'content': """
<p>You can update a subject's name, code, description, or active status at any time.</p>

<ol class="mt-3">
    <li class="mb-3">
        Go to <strong>Academics &rarr; Subjects</strong>.
    </li>
    <li class="mb-3">
        Find the subject in the list and click its <strong>Edit</strong> button.
    </li>
    <li class="mb-3">
        Update the fields as needed and click <strong>Save</strong>.
    </li>
</ol>

<div class="alert alert-warning mt-3">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <strong>Changing the Code:</strong> The subject code is used on report cards
    and assessment records. If you change the code after results have already been
    entered, the existing records will reflect the new code going forward.
    Make sure any change is intentional and consistent with your report card layout.
</div>

<div class="alert alert-secondary mt-3">
    <i class="bi bi-toggle-off me-2"></i>
    <strong>Deactivating a subject:</strong> Unticking <em>Active</em> hides the
    subject from fee setup screens, assessment entry, and report generation. It does
    not delete the subject or its existing records — it simply makes it unavailable
    for new entries. You can reactivate it at any time.
</div>
""",
    },

    {
        'slug':  'how-to-delete-a-subject',
        'title': 'How to Delete a Subject',
        'order': 4,
        'content': """
<p>
    Deleting a subject permanently removes it and all records associated with it.
</p>

<h6 class="fw-semibold mt-4 mb-2">Steps to delete</h6>
<ol>
    <li class="mb-2">Go to <strong>Academics &rarr; Subjects</strong>.</li>
    <li class="mb-2">
        Find the subject and click its <strong>Delete</strong> button.
    </li>
    <li class="mb-2">
        Confirm the deletion in the prompt that appears.
    </li>
</ol>

<div class="alert alert-danger mt-4">
    <i class="bi bi-exclamation-octagon-fill me-2"></i>
    <strong>What gets deleted along with the subject:</strong>
    <ul class="mb-0 mt-2">
        <li>All <strong>class-subject links</strong> — every class that was assigned this subject loses the link.</li>
        <li>All <strong>teacher-subject assignments</strong> — teachers assigned to teach this subject across all classes are unassigned.</li>
        <li>All <strong>assessment records</strong> that were tied to this subject.</li>
        <li>All <strong>assessment fee records</strong> linked to this subject.</li>
    </ul>
    <p class="mt-2 mb-0"><strong>This action cannot be undone.</strong></p>
</div>

<div class="alert alert-warning mt-3">
    <i class="bi bi-lightbulb-fill me-2"></i>
    <strong>Recommendation:</strong> If a subject is no longer being taught but
    has historical assessment or payment records, <strong>deactivate it</strong>
    instead of deleting it. Go to Edit and untick <em>Active</em>. The records
    are preserved and the subject disappears from active screens.
</div>
""",
    },

    {
        'slug':  'how-to-assign-classes-to-a-subject',
        'title': 'How to Assign Classes to a Subject',
        'order': 5,
        'content': """
<p>
    Assigning classes to a subject tells the system which class levels study that
    subject. This is a <strong>2-step process</strong>.
</p>

<div class="alert alert-secondary mb-4">
    <i class="bi bi-info-circle me-2"></i>
    This creates a <strong>ClassSubject</strong> link between the subject and each
    selected class. A class can only be linked to the same subject once — duplicates
    are not allowed.
</div>

<h6 class="fw-semibold mb-3">Step 1 &mdash; Select Classes</h6>
<ol>
    <li class="mb-2">
        Go to <strong>Academics &rarr; Subjects</strong>, find the subject,
        and click <strong>Assign Classes</strong> in its Actions.
    </li>
    <li class="mb-2">
        A checklist of all available classes is shown — both Nursery
        (Baby Class, Middle Class, Top Class) and Primary (P1 &ndash; P7).
    </li>
    <li class="mb-2">
        Classes that are <strong>already linked</strong> to this subject will be
        pre-ticked and show an
        <span class="badge bg-success">Already linked</span> badge.
        You can leave them ticked to keep the link, or untick to remove it.
    </li>
    <li class="mb-2">
        Tick all the classes that should study this subject, then click
        <strong>Next</strong> (or <strong>Step 2 &mdash; Confirm</strong>).
    </li>
</ol>

<h6 class="fw-semibold mt-4 mb-3">Step 2 &mdash; Confirm Assignment</h6>
<ol>
    <li class="mb-2">
        A summary lists all the classes you selected, along with the subject name.
    </li>
    <li class="mb-2">
        On the right, enter your <strong>account password</strong> to authorise
        the assignment.
    </li>
    <li class="mb-2">
        Click <strong>Confirm Assignment</strong>. The selected classes are now
        linked to the subject.
    </li>
    <li class="mb-2">
        To go back and change your selection, click <strong>&larr; Back</strong>.
    </li>
</ol>

<div class="alert alert-info mt-3">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>Why is a password required?</strong> Class-subject assignments affect
    fee structures, assessment setups, and report cards. The password step ensures
    that changes are made intentionally by an authorised user.
</div>

<div class="alert alert-warning mt-3">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <strong>Removing a class:</strong> If you untick a class that was previously
    linked (<span class="badge bg-success">Already linked</span>) and confirm,
    that class-subject link is deleted. Any assessment records or fee records
    specifically tied to that class-subject combination may also be affected.
</div>
""",
    },

    {
        'slug':  'how-to-assign-a-teacher-to-a-subject',
        'title': 'How to Assign a Teacher to a Subject',
        'order': 6,
        'content': """
<p>
    Assigning a teacher to a subject maps which teacher delivers that subject
    in each class. This is a <strong>3-step process</strong>.
</p>

<div class="alert alert-secondary mb-4">
    <i class="bi bi-info-circle me-2"></i>
    Only classes that are already <strong>linked to this subject</strong> (via
    Assign Classes) will appear in this flow. If a class is missing, assign it
    to the subject first.
</div>

<h6 class="fw-semibold mb-3">Step 1 &mdash; Select Teachers</h6>
<ol>
    <li class="mb-2">
        Go to <strong>Academics &rarr; Subjects</strong>, find the subject,
        and click <strong>Assign Teacher</strong> in its Actions.
    </li>
    <li class="mb-2">
        Each class linked to this subject is shown as a separate block.
        For every class, select a teacher using the radio buttons.
    </li>
    <li class="mb-2">
        The teacher currently assigned to that class-subject shows a
        <span class="badge bg-success">Currently assigned</span> badge and
        is pre-selected.
    </li>
    <li class="mb-2">
        To make no change for a particular class, leave it on
        <strong>&mdash; Skip / no change &mdash;</strong>.
    </li>
    <li class="mb-2">
        Once you have selected teachers for all relevant classes,
        click <strong>Next &rarr; Step 2 &mdash; Review</strong>.
    </li>
</ol>

<h6 class="fw-semibold mt-4 mb-3">Step 2 &mdash; Review &amp; Adjust</h6>
<ol>
    <li class="mb-2">
        This screen shows a summary of your selections grouped by class.
        Each class displays:
        <ul class="mt-1">
            <li>
                <span class="badge bg-primary">New</span> — the teacher you
                just selected.
            </li>
            <li>
                <span class="badge bg-secondary">Previous</span> — the teacher
                who was already assigned. If this is the same person as the new
                selection, a <span class="badge bg-warning text-dark">Same as new &mdash; will be merged</span>
                badge is shown (no duplicate will be created).
            </li>
        </ul>
    </li>
    <li class="mb-2">
        If a <span class="badge bg-secondary">Previous</span> entry is shown and
        you want to <strong>remove</strong> that teacher, <strong>uncheck</strong>
        the checkbox next to their name.
    </li>
    <li class="mb-2">
        When you are satisfied, click <strong>Next &rarr; Step 3 &mdash; Confirm</strong>.
    </li>
</ol>

<h6 class="fw-semibold mt-4 mb-3">Step 3 &mdash; Confirm Changes</h6>
<ol>
    <li class="mb-2">
        A final summary shows two sections:
        <ul class="mt-1">
            <li>
                <span class="badge bg-success">&check; New Assignments</span>
                — teachers being added, listed with their class.
            </li>
            <li>
                <span class="badge bg-danger">&times; To Be Removed</span>
                — teachers being unassigned from this subject.
                Note: they remain assigned to their <em>class</em> — only the
                subject assignment is removed.
            </li>
        </ul>
    </li>
    <li class="mb-2">
        Enter your <strong>account password</strong> on the right to authorise
        the changes.
    </li>
    <li class="mb-2">
        Click <strong>Apply Changes</strong>. All new assignments are saved and
        all removals are applied.
    </li>
    <li class="mb-2">
        To go back and adjust, click <strong>&larr; Back</strong>.
    </li>
</ol>

<div class="alert alert-info mt-3">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>Skipped classes:</strong> Any class where you selected
    <em>Skip / no change</em> in Step 1 is not affected — its current
    teacher assignment stays exactly as it was.
</div>

<div class="alert alert-warning mt-3">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <strong>Removing a teacher</strong> from a subject only removes the
    <em>subject-level</em> assignment (TeacherSubject record). The teacher
    remains a member of staff and keeps any other subject or class assignments
    they hold.
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
        ('help_center', '0004_seed_terms_articles'),
    ]

    operations = [
        migrations.RunPython(seed_articles, reverse_code=unseed_articles),
    ]