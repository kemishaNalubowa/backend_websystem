from django.db import migrations

SLUG_CATEGORY = 'supported-classes'

ARTICLES = [
    {
        'slug':  'what-are-supported-classes',
        'title': 'What are Supported Classes?',
        'order': 1,
        'content': """
<p>
    <strong>Supported Classes</strong> are the class levels that your school
    actually offers to students. The system contains a master list of all
    possible class levels for Ugandan nursery and primary schools — your school
    selects only the ones it runs.
</p>

<h6 class="fw-semibold mt-4 mb-2">All available class levels</h6>
<div class="row g-3">
    <div class="col-md-6">
        <div class="card border">
            <div class="card-header bg-light fw-semibold py-2">
                <i class="bi bi-building me-1 text-primary"></i> Nursery Section
            </div>
            <ul class="list-group list-group-flush">
                <li class="list-group-item py-2">Baby Class</li>
                <li class="list-group-item py-2">Middle Class</li>
                <li class="list-group-item py-2">Top Class</li>
            </ul>
        </div>
    </div>
    <div class="col-md-6">
        <div class="card border">
            <div class="card-header bg-light fw-semibold py-2">
                <i class="bi bi-mortarboard me-1 text-primary"></i> Primary Section
            </div>
            <ul class="list-group list-group-flush">
                <li class="list-group-item py-2">Primary One (P1)</li>
                <li class="list-group-item py-2">Primary Two (P2)</li>
                <li class="list-group-item py-2">Primary Three (P3)</li>
                <li class="list-group-item py-2">Primary Four (P4)</li>
                <li class="list-group-item py-2">Primary Five (P5)</li>
                <li class="list-group-item py-2">Primary Six (P6)</li>
                <li class="list-group-item py-2">Primary Seven (P7)</li>
            </ul>
        </div>
    </div>
</div>

<h6 class="fw-semibold mt-4 mb-2">Columns on the Supported Classes list</h6>
<div class="table-responsive">
    <table class="table table-bordered table-sm align-middle">
        <thead class="table-light">
            <tr>
                <th style="width:60px;">#</th>
                <th style="width:200px;">Column</th>
                <th>What it means</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>1</td>
                <td><strong>#</strong></td>
                <td>Row number — display order from lowest to highest class level.</td>
            </tr>
            <tr>
                <td>2</td>
                <td><strong>Class</strong></td>
                <td>The name of the class level, e.g. <em>Primary One</em>, <em>Baby Class</em>.</td>
            </tr>
            <tr>
                <td>3</td>
                <td><strong>Section</strong></td>
                <td>
                    Whether the class belongs to <strong>Nursery</strong> or
                    <strong>Primary</strong> section.
                </td>
            </tr>
        </tbody>
    </table>
</div>

<div class="alert alert-info mt-3">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>Why this matters:</strong> Only supported classes appear in student
    enrollment, fee setup, class teacher assignment, and subject-to-class linking.
    A class that is not marked as supported cannot receive students or fees.
</div>
""",
    },

    {
        'slug':  'how-to-add-supported-classes',
        'title': 'How to Add Supported Classes',
        'order': 2,
        'content': """
<p>
    Use this when your school is being set up for the first time, or when your
    school starts offering a new class level that was not previously selected.
</p>

<ol class="mt-3">
    <li class="mb-3">
        In the left sidebar, go to <strong>Academics &rarr; Supported Classes</strong>.
    </li>
    <li class="mb-3">
        Click the <strong class="text-primary">
            <i class="bi bi-plus-circle"></i> Add Classes
        </strong> button at the top right of the page.
        A modal window will open showing a checkbox grid of all available class levels.
    </li>
    <li class="mb-3">
        <strong>Tick</strong> every class level your school currently offers.
        The classes are arranged in a 3-column grid:
        <ul class="mt-2">
            <li>Nursery levels: Baby Class, Middle Class, Top Class</li>
            <li>Primary levels: Primary One through Primary Seven</li>
        </ul>
    </li>
    <li class="mb-3">
        Click <strong>Save</strong>. The modal closes and the selected classes
        appear in the Supported Classes list.
    </li>
</ol>

<div class="alert alert-warning mt-3">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <strong>If a class level is already supported</strong>, ticking it again from
    the Add modal will not create a duplicate — the system ignores class levels
    that are already on the supported list.
</div>

<div class="alert alert-info mt-3">
    <i class="bi bi-lightbulb-fill me-2"></i>
    <strong>Tip:</strong> Add all the class levels your school runs during initial
    setup before creating fee structures, enrolling students, or assigning subjects.
    Other parts of the system depend on this list.
</div>
""",
    },

    {
        'slug':  'how-to-edit-supported-classes',
        'title': 'How to Edit (Update) Supported Classes',
        'order': 3,
        'content': """
<p>
    Use the Edit Classes function to change which class levels your school supports —
    for example when adding a new class level or removing one your school no
    longer runs.
</p>

<ol class="mt-3">
    <li class="mb-3">
        Go to <strong>Academics &rarr; Supported Classes</strong>.
    </li>
    <li class="mb-3">
        Click the <strong class="text-warning">
            <i class="bi bi-pencil"></i> Edit Classes
        </strong> button at the top right.
        The same checkbox modal opens, but this time <strong>all currently
        supported classes are pre-ticked</strong>.
    </li>
    <li class="mb-3">
        Make your changes:
        <ul class="mt-2">
            <li>
                <strong>Tick a class that is not yet checked</strong> to add
                it as a supported class.
            </li>
            <li>
                <strong>Untick a class that is currently checked</strong> to
                remove it from the supported list.
            </li>
        </ul>
    </li>
    <li class="mb-3">
        Click <strong>Update</strong>. The list refreshes to show only
        the classes that remain ticked.
    </li>
</ol>

<div class="alert alert-danger mt-3">
    <i class="bi bi-exclamation-octagon-fill me-2"></i>
    <strong>Warning — what happens when you remove a supported class:</strong>
    <p class="mt-2 mb-2">
        Unticking a class and clicking Update removes that
        <code>SchoolSupportedClasses</code> record. Because other records link
        to it, the following are also permanently deleted:
    </p>
    <ul class="mb-0">
        <li>All <strong>subject-to-class links</strong> for that class (ClassSubject records)</li>
        <li>All <strong>teacher-to-class assignments</strong> for that class</li>
        <li>All <strong>fee structures</strong> configured for that class</li>
        <li>All <strong>student enrollment records</strong> placing students in that class</li>
    </ul>
    <p class="mt-2 mb-0">
        <strong>This cannot be undone.</strong> Only remove a class level if you
        are certain the school will never use it again and it has no real
        student data.
    </p>
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
        ('help_center', '0005_seed_subjects_articles'),
    ]

    operations = [
        migrations.RunPython(seed_articles, reverse_code=unseed_articles),
    ]