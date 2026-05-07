from django.db import models

# Create your models here.


# ──────────────────────────────────────────
# PERMISSION MODEL
# ──────────────────────────────────────────
class Permission(models.Model):

    permission_title = models.CharField(max_length=255)
    permission_code  = models.CharField(max_length=100, unique=True)
    description      = models.TextField(blank=True)
    date             = models.DateField(auto_now_add=True)
    is_active        = models.BooleanField(default=True)

    # ── Supported actions ──────────────────
    support_add      = models.BooleanField(default=False)
    support_edit     = models.BooleanField(default=False)
    support_delete   = models.BooleanField(default=False)
    support_view     = models.BooleanField(default=False)
    support_toggle   = models.BooleanField(default=False)

    # ── Supported action limits ────────────
    support_my_limit  = models.BooleanField(default=False)
    support_all_limit = models.BooleanField(default=False)

    class Meta:
        verbose_name        = "Permission"
        verbose_name_plural = "Permissions"
        ordering            = ["permission_title"]

    def __str__(self):
        return f"{self.permission_title} [{self.permission_code}]"


# ──────────────────────────────────────────
# USER TYPE PERMISSION ASSIGNMENT MODEL
# ──────────────────────────────────────────
class UserTypePermission(models.Model):

    ROLE_CHOICES = [
        # Teaching
        ('head_teacher',    'Head Teacher'),
        ('deputy_head',     'Deputy Head Teacher'),
        ('teacher',         'Class Teacher'),
        ('subject_teacher', 'Subject Teacher'),
        # Non-teaching
        ('bursar',          'Bursar'),
        ('secretary',       'School Secretary'),
        ('librarian',       'Librarian'),
        ('lab_technician',  'Lab Technician'),
        ('nurse',           'School Nurse / Health Worker'),
        ('security',        'Security Personnel'),
        ('cleaner',         'Cleaner / Janitor'),
        ('driver',          'Driver'),
        ('cook',            'Cook / Catering Staff'),
        ('it_officer',      'IT Officer'),
        ('other',           'Other'),
        # Parent
        ('parent',          'Parent'),
        # Admin
        ('admin',           'Admin'),
    ]

    CAN_MY  = "can_my"
    CAN_ALL = "can_all"

    ACTION_EFFECT_CHOICES = [
        (CAN_MY,  "Can My  – own records only"),
        (CAN_ALL, "Can All – all records"),
    ]

    permission    = models.ForeignKey(
                        Permission,
                        on_delete=models.CASCADE,
                        related_name="role_assignments",
                    )
    role          = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # ── actions ──────────────────────────────
    can_create    = models.BooleanField(default=False)
    can_read      = models.BooleanField(default=False)
    can_edit      = models.BooleanField(default=False)
    can_delete    = models.BooleanField(default=False)
    can_toggle    = models.BooleanField(default=False)   # ← new

    # ── scope ────────────────────────────────
    action_effect = models.CharField(
                        max_length=10,
                        choices=ACTION_EFFECT_CHOICES,
                        default=None,
                        null=True,
                        blank=True,
                    )

    assigned_at   = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    is_active     = models.BooleanField(default=False)

    class Meta:
        verbose_name        = "User Type Permission"
        verbose_name_plural = "User Type Permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["permission", "role"],
                name="unique_permission_per_role",
            )
        ]
        ordering = ["role", "permission__permission_title"]

    def __str__(self):
        actions = ", ".join(filter(None, [
            "create" if self.can_create else "",
            "read"   if self.can_read   else "",
            "edit"   if self.can_edit   else "",
            "delete" if self.can_delete else "",
            "toggle" if self.can_toggle else "",   # ← new
        ])) or "no actions"
        return (
            f"{self.get_role_display()} → "
            f"{self.permission.permission_title} "
            f"[{actions}] ({self.get_action_effect_display()})"
        )