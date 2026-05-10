from django.db import migrations

SLUG_CATEGORY = 'academic-year'

ARTICLES = [
    {
        'slug':    'what-is-an-academic-year',
        'title':   'What is an Academic Year?',
        'order':   1,
        'content': """
<p>
    An <strong>Academic Year</strong> is the top-level time container for all school
    activity in the system. Every term, class, fee structure, assessment, and payment
    record belongs to a specific academic year.
</p>

<h6 class="fw-semibold mt-4 mb-2">Fields on the Academic Years list</h6>
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
                    The label for the academic year, for example <code>2026</code>.
                    Each name must be unique across all years.
                </td>
            </tr>
            <tr>
                <td><strong>Start Date</strong></td>
                <td>The date on which the academic year officially begins.</td>
            </tr>
            <tr>
                <td><strong>End Date</strong></td>
                <td>The date on which the academic year officially ends.</td>
            </tr>
            <tr>
                <td><strong>Status</strong></td>
                <td>
                    Shows <span class="badge bg-success">Active</span> or
                    <span class="badge bg-secondary">Inactive</span>.
                    Only <strong>one</strong> academic year can be Active at any time.
                    Activating a new year automatically deactivates the previous one.
                </td>
            </tr>
            <tr>
                <td><strong>Current</strong></td>
                <td>
                    Shows <span class="badge bg-primary">Yes</span> when today's date
                    falls within the year's Start Date and End Date <em>and</em> the year
                    is Active. Otherwise shows <span class="badge bg-secondary">No</span>.
                </td>
            </tr>
            <tr>
                <td><strong>Actions</strong></td>
                <td>
                    Buttons to <strong>Edit</strong> or <strong>Delete</strong>
                    that specific academic year.
                </td>
            </tr>
        </tbody>
    </table>
</div>

<div class="alert alert-info mt-4">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>Status vs Current — what is the difference?</strong><br>
    A year can be <em>Active</em> but not yet <em>Current</em>. For example, if you
    activate the <code>2027</code> academic year in December 2026, it will show
    <span class="badge bg-success">Active</span> but
    <span class="badge bg-secondary">No</span> under Current because today's date is
    not yet inside the 2027 date range. <em>Current</em> is determined automatically
    by the system — you cannot set it manually.
</div>
""",
    },

    {
        'slug':    'how-to-add-an-academic-year',
        'title':   'How to Add an Academic Year',
        'order':   2,
        'content': """
<p>
    Follow these steps to create a new academic year in the system.
</p>

<ol class="mt-3">
    <li class="mb-3">
        In the left sidebar, click <strong>Academics</strong> to expand the section,
        then click <strong>Academic Years</strong>.
    </li>
    <li class="mb-3">
        On the Academic Years list page, click the <strong>Add Academic Year</strong>
        button (usually at the top right of the list).
    </li>
    <li class="mb-3">
        Fill in the form fields:
        <div class="table-responsive mt-2">
            <table class="table table-bordered table-sm align-middle">
                <thead class="table-light">
                    <tr>
                        <th style="width:180px;">Field</th>
                        <th>What to enter</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Academic Year Name</strong></td>
                        <td>
                            A short, unique label. The system pre-fills this with the
                            current year, e.g. <code>2026</code>. You may change it
                            to any unique name.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Start Date</strong></td>
                        <td>
                            The date the academic year begins. Use the calendar picker
                            or type in <code>mm/dd/yyyy</code> format.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>End Date</strong></td>
                        <td>
                            The date the academic year ends. Must be after the Start Date.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Set as Active Academic Year</strong></td>
                        <td>
                            Tick this checkbox to make this the current active year.
                            Any previously active year will automatically be set to
                            <span class="badge bg-secondary">Inactive</span>.
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </li>
    <li class="mb-3">
        Click <strong>Save</strong> to create the academic year.
    </li>
</ol>

<div class="alert alert-warning mt-3">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <strong>Validation rules the system enforces:</strong>
    <ul class="mb-0 mt-2">
        <li>The <strong>End Date must be after the Start Date</strong> — the system will reject equal or reversed dates.</li>
        <li>The new year's date range <strong>must not overlap</strong> with any existing academic year. If there is an overlap, the system will show an error and the record will not be saved.</li>
        <li>The <strong>Academic Year Name must be unique</strong> — you cannot create two years with the same name.</li>
    </ul>
</div>

<div class="alert alert-info mt-3">
    <i class="bi bi-lightbulb-fill me-2"></i>
    <strong>Tip:</strong> Create the next academic year <em>before</em> it starts so that you can set up its terms, classes, and fees in advance without affecting the currently running year.
</div>
""",
    },

    {
        'slug':    'how-to-edit-an-academic-year',
        'title':   'How to Edit an Academic Year',
        'order':   3,
        'content': """
<p>
    You can update an academic year's name, dates, or active status at any time.
</p>

<ol class="mt-3">
    <li class="mb-3">
        In the left sidebar, go to <strong>Academics &rarr; Academic Years</strong>.
    </li>
    <li class="mb-3">
        In the list, find the academic year you want to change and click its
        <strong>Edit</strong> button in the Actions column.
    </li>
    <li class="mb-3">
        Update whichever fields you need:
        <ul class="mt-2">
            <li><strong>Name</strong> — change the year label. Must remain unique.</li>
            <li><strong>Start Date / End Date</strong> — adjust the date range. The updated range must still not overlap any other year.</li>
            <li><strong>Set as Active</strong> — tick to make this year the active one. The previously active year will be deactivated automatically.</li>
        </ul>
    </li>
    <li class="mb-3">
        Click <strong>Save</strong> to apply your changes.
    </li>
</ol>

<div class="alert alert-warning mt-3">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <strong>Same validation rules apply as when adding:</strong>
    the end date must be after the start date, the date range must not overlap
    another year, and the name must stay unique. If any rule is broken the system
    will show an error and your changes will not be saved.
</div>

<div class="alert alert-info mt-3">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>Changing dates on an active year:</strong> if terms, fees, or other
    records have already been created under this year, changing its date range
    does not automatically adjust those records. Review your terms after editing
    to make sure their dates still fall within the new academic year range.
</div>
""",
    },

    {
        'slug':    'how-to-delete-an-academic-year',
        'title':   'How to Delete an Academic Year',
        'order':   4,
        'content': """
<p>
    Deleting an academic year permanently removes it from the system.
    Read this article carefully before proceeding.
</p>

<h6 class="fw-semibold mt-4 mb-2">Steps to delete</h6>
<ol>
    <li class="mb-2">
        Go to <strong>Academics &rarr; Academic Years</strong> in the sidebar.
    </li>
    <li class="mb-2">
        Find the academic year in the list and click <strong>Delete</strong>
        in its Actions column.
    </li>
    <li class="mb-2">
        A confirmation prompt will appear. Confirm to proceed with deletion.
    </li>
</ol>

<div class="alert alert-danger mt-4">
    <i class="bi bi-exclamation-octagon-fill me-2"></i>
    <strong>Warning — what gets deleted along with the academic year:</strong>
    <p class="mt-2 mb-2">
        All records that belong to an academic year are linked to it. Deleting the year
        will cascade and permanently remove all of the following:
    </p>
    <ul class="mb-0">
        <li>All <strong>Terms</strong> created under this year</li>
        <li>All <strong>Class</strong> assignments for this year</li>
        <li>All <strong>Fee structures</strong> configured for this year</li>
        <li>All <strong>Assessment fees</strong> for this year</li>
        <li>All <strong>Scholastic requirements</strong> for this year</li>
        <li>All <strong>Payment records</strong> recorded under this year</li>
        <li>All <strong>Assessment results</strong> for this year</li>
        <li>All <strong>Admission records</strong> for this year</li>
    </ul>
    <p class="mt-2 mb-0">
        <strong>This action cannot be undone.</strong>
    </p>
</div>

<div class="alert alert-warning mt-3">
    <i class="bi bi-shield-exclamation me-2"></i>
    <strong>Recommendation:</strong> Instead of deleting a past academic year,
    leave it in the system as a historical record. Simply ensure it is set to
    <span class="badge bg-secondary">Inactive</span> so it does not interfere
    with the current year. Deletion should only be used to remove a year that
    was created by mistake and has no real data under it.
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
        return  # category seed migration has not run — skip gracefully

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
        ('help_center', '0002_seed_categories'),
    ]

    operations = [
        migrations.RunPython(seed_articles, reverse_code=unseed_articles),
    ]