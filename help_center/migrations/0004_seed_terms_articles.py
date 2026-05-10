from django.db import migrations

SLUG_CATEGORY = 'terms'

ARTICLES = [
    {
        'slug':  'what-is-a-term',
        'title': 'What is a Term?',
        'order': 1,
        'content': """
<p>
    A <strong>Term</strong> is a defined period within an Academic Year during which
    teaching, assessments, and fee collection take place. The system supports
    three terms per academic year, matching the Uganda Ministry of Education
    school calendar.
</p>

<h6 class="fw-semibold mt-4 mb-2">Available terms</h6>
<ul>
    <li><strong>Term 1</strong> — typically runs from January to around late March / early April.</li>
    <li><strong>Term 2</strong> — typically runs from May to around late August.</li>
    <li><strong>Term 3</strong> — typically runs from September to around November / December.</li>
</ul>

<h6 class="fw-semibold mt-4 mb-2">Columns on the Terms list</h6>
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
                <td><strong>Term</strong></td>
                <td>
                    The term name (Term 1, Term 2, or Term 3). If today's date falls
                    within this term's date range and the term is active, a
                    <span class="badge bg-primary">Current</span> badge appears
                    next to the name.
                </td>
            </tr>
            <tr>
                <td><strong>Academic Year</strong></td>
                <td>The academic year this term belongs to, e.g. <code>2026</code>.</td>
            </tr>
            <tr>
                <td><strong>Start Date</strong></td>
                <td>The date on which this term officially begins.</td>
            </tr>
            <tr>
                <td><strong>End Date</strong></td>
                <td>The date on which this term officially ends.</td>
            </tr>
            <tr>
                <td><strong>Actions</strong></td>
                <td>
                    <span class="badge bg-warning text-dark"><i class="bi bi-pencil"></i> Edit</span>
                    to update the term, or
                    <span class="badge bg-danger"><i class="bi bi-trash"></i> Delete</span>
                    to permanently remove it.
                </td>
            </tr>
        </tbody>
    </table>
</div>

<div class="alert alert-info mt-3">
    <i class="bi bi-info-circle-fill me-2"></i>
    <strong>How &ldquo;Current&rdquo; is determined:</strong> The
    <span class="badge bg-primary">Current</span> badge is set automatically by
    the system. It appears when today&rsquo;s date is on or between the term&rsquo;s
    Start Date and End Date <em>and</em> the term is active. You cannot set it manually.
</div>
""",
    },

    {
        'slug':  'how-to-add-a-term',
        'title': 'How to Add a Term',
        'order': 2,
        'content': """
<p>
    Follow these steps to add a new term to an academic year.
</p>

<ol class="mt-3">
    <li class="mb-3">
        In the left sidebar, click <strong>Academics &rarr; Terms</strong>.
    </li>
    <li class="mb-3">
        On the Terms list page, click the <strong>Add Term</strong> button.
        A modal form will open.
    </li>
    <li class="mb-3">
        Fill in the form:
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
                        <td><strong>Term Name</strong></td>
                        <td>
                            Select from the dropdown: <strong>Term 1</strong>,
                            <strong>Term 2</strong>, or <strong>Term 3</strong>.
                            This is a fixed list — you cannot type a custom name.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Academic Year</strong></td>
                        <td>
                            Select the academic year this term belongs to from the
                            dropdown. Only existing academic years appear here.
                            If none are available, create an academic year first.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Start Date</strong></td>
                        <td>
                            The date this term begins. Use the calendar picker
                            or type in <code>mm/dd/yyyy</code> format.
                        </td>
                    </tr>
                    <tr>
                        <td><strong>End Date</strong></td>
                        <td>
                            The date this term ends. Must be after the Start Date.
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </li>
    <li class="mb-3">
        Click <strong>Save Term</strong>. The modal will close and the new term
        will appear in the list.
    </li>
</ol>

<div class="alert alert-warning mt-3">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <strong>Before you add a term, make sure:</strong>
    <ul class="mb-0 mt-2">
        <li>An <strong>Academic Year already exists</strong> in the system. Terms cannot be created without one.</li>
        <li>The term&rsquo;s date range <strong>falls within the selected Academic Year&rsquo;s date range</strong>. For example, a term under the 2026 academic year should not extend beyond the year&rsquo;s End Date.</li>
        <li>You are not creating a duplicate — each academic year should have at most one Term 1, one Term 2, and one Term 3.</li>
    </ul>
</div>

<div class="alert alert-info mt-3">
    <i class="bi bi-lightbulb-fill me-2"></i>
    <strong>Tip:</strong> Set up all three terms for an academic year before
    the year begins. Fee structures, assessments, and other records are
    linked to specific terms — having them ready in advance avoids delays.
</div>
""",
    },

    {
        'slug':  'how-to-edit-a-term',
        'title': 'How to Edit a Term',
        'order': 3,
        'content': """
<p>
    You can update a term&rsquo;s name, academic year, or date range at any time.
</p>

<ol class="mt-3">
    <li class="mb-3">
        Go to <strong>Academics &rarr; Terms</strong> in the sidebar.
    </li>
    <li class="mb-3">
        In the list, find the term you want to change and click the
        <span class="badge bg-warning text-dark">
            <i class="bi bi-pencil"></i>
        </span>
        <strong>Edit</strong> button in its Actions column.
        An edit form or modal will open, pre-filled with the term&rsquo;s current values.
    </li>
    <li class="mb-3">
        Update whichever fields need changing:
        <ul class="mt-2">
            <li><strong>Term Name</strong> — switch between Term 1, Term 2, or Term 3.</li>
            <li><strong>Academic Year</strong> — move the term to a different academic year if needed.</li>
            <li><strong>Start Date / End Date</strong> — adjust the date range.</li>
        </ul>
    </li>
    <li class="mb-3">
        Click <strong>Save</strong> to apply the changes.
    </li>
</ol>

<div class="alert alert-warning mt-3">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <strong>Things to be careful about when editing:</strong>
    <ul class="mb-0 mt-2">
        <li>
            Changing a term&rsquo;s <strong>date range</strong> while the term is already
            underway does not automatically adjust any assessment dates or payment
            deadlines that were set for that term. Review those records after editing.
        </li>
        <li>
            If the term has existing <strong>fee records or assessment records</strong>
            attached, moving it to a different Academic Year may cause those records
            to appear under the wrong year. Only move a term to a different year if
            it has no linked data.
        </li>
    </ul>
</div>
""",
    },

    {
        'slug':  'how-to-delete-a-term',
        'title': 'How to Delete a Term',
        'order': 4,
        'content': """
<p>
    Deleting a term permanently removes it and all records linked to it.
    Read carefully before proceeding.
</p>

<h6 class="fw-semibold mt-4 mb-2">Steps to delete</h6>
<ol>
    <li class="mb-2">
        Go to <strong>Academics &rarr; Terms</strong> in the sidebar.
    </li>
    <li class="mb-2">
        Find the term in the list and click the
        <span class="badge bg-danger">
            <i class="bi bi-trash"></i>
        </span>
        <strong>Delete</strong> button in its Actions column.
    </li>
    <li class="mb-2">
        A <strong>password confirmation prompt</strong> will appear. Enter your
        account password and confirm to proceed.
    </li>
</ol>

<div class="alert alert-danger mt-4">
    <i class="bi bi-exclamation-octagon-fill me-2"></i>
    <strong>Warning — what gets deleted along with the term:</strong>
    <p class="mt-2 mb-2">
        All records that are linked to a term will be permanently deleted
        along with it. This includes:
    </p>
    <ul class="mb-0">
        <li>All <strong>fee structures</strong> configured for this term</li>
        <li>All <strong>assessment fees</strong> tied to this term</li>
        <li>All <strong>scholastic requirements</strong> for this term</li>
        <li>All <strong>payment records</strong> recorded under this term</li>
        <li>All <strong>assessment results</strong> entered for this term</li>
    </ul>
    <p class="mt-2 mb-0"><strong>This action cannot be undone.</strong></p>
</div>

<div class="alert alert-secondary mt-3">
    <i class="bi bi-shield-lock-fill me-2"></i>
    <strong>Why does deletion require a password?</strong><br>
    Because deleting a term with linked data (fees, payments, results) is
    irreversible, the system requires you to confirm your identity with your
    login password before the deletion proceeds. If the password entered is
    incorrect the term will <em>not</em> be deleted.
</div>

<div class="alert alert-warning mt-3">
    <i class="bi bi-lightbulb-fill me-2"></i>
    <strong>Recommendation:</strong> Only delete a term that was created by
    mistake and has no real data under it. For past terms that are no longer
    active, leave them in the system as historical records — they do not
    interfere with the current term.
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
        ('help_center', '0003_seed_academic_year_articles'),
    ]

    operations = [
        migrations.RunPython(seed_articles, reverse_code=unseed_articles),
    ]