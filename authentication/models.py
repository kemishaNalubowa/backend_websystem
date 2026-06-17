
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models








# ═══════════════════════════════════════════════════════════════════════════════
#  CHOICES
# ═══════════════════════════════════════════════════════════════════════════════


GENDER_CHOICES = [
    ('male',              'Male'),
    ('female',            'Female'),
    ('other',             'Other'),
    ('prefer_not_to_say', 'Prefer not to say'),
]

USER_TYPE_CHOICES = [
    ('parent',  'Parent / Guardian'),
    ('teacher', 'Teacher'),
    ('staff',   'Support Staff'),
    ('admin',   'Administrator'),
]



# ═══════════════════════════════════════════════════════════════════════════════
#  CUSTOM USER MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class CustomUserManager(BaseUserManager):

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('Username is required.')
        email = self.normalize_email(email) if email else ''
        user  = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_parent_user(self, parent_id: str, password=None, **extra_fields):
        """
        Create a parent account.
        username is set to parent_id so the standard login form works.
        """
        extra_fields['user_type'] = 'parent'
        extra_fields['parent_id'] = parent_id
        return self.create_user(
            username=parent_id,
            email=extra_fields.pop('email', ''),
            password=password,
            **extra_fields,
        )

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff',         True)
        extra_fields.setdefault('is_superuser',      True)
        extra_fields.setdefault('is_active',         True)
        extra_fields.setdefault('is_email_verified', True)
        extra_fields.setdefault('user_type',         'admin')
        return self.create_user(username, email, password, **extra_fields)


# ═══════════════════════════════════════════════════════════════════════════════
#  CUSTOM USER
# ═══════════════════════════════════════════════════════════════════════════════

class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Central user account for every person in the system.

    Staff / Teacher / Admin  →  log in with  username  + password
    Parent / Guardian        →  log in with  parent_id + password
                                (username is set = parent_id at creation)
    """

    # ── Core auth ─────────────────────────────────────────────────────────────
    username         = models.CharField(max_length=50, unique=True)
    email            = models.EmailField(blank=True)

    # ── User type & parent identifier ─────────────────────────────────────────
    user_type        = models.CharField(
                           max_length=10,
                           choices=USER_TYPE_CHOICES,
                           default='staff',
                       )
    parent_id        = models.CharField(
                           max_length=20,
                           unique=True,
                           null=True,
                           blank=True,
                           help_text=(
                               'Auto-generated login ID for parents '
                               '(e.g. PAR20250001). Null for all non-parent types.'
                           ),
                       )

    # ── Personal details ──────────────────────────────────────────────────────
    first_name       = models.CharField(max_length=50)
    last_name        = models.CharField(max_length=50)
    other_names      = models.CharField(max_length=50, blank=True)
    gender           = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    date_of_birth    = models.DateField(null=True, blank=True)
    profile_photo    = models.ImageField(upload_to='profiles/', blank=True, null=True)

    # ── Contact ───────────────────────────────────────────────────────────────
    phone            = models.CharField(max_length=15, blank=True)
    alt_phone        = models.CharField(max_length=15, blank=True)
    address          = models.TextField(blank=True)

    # ── Uganda-specific ───────────────────────────────────────────────────────
    nin              = models.CharField(
                           max_length=20,
                           blank=True,
                           verbose_name='National ID Number (NIN)',
                       )

    # ── Account flags ─────────────────────────────────────────────────────────
    is_active         = models.BooleanField(default=True)
    is_staff          = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_first_login    = models.BooleanField(default=True, help_text='Flags if the user must change password on next login.')

    # ── Password Recovery ─────────────────────────────────────────────────────
    reset_token        = models.CharField(max_length=10, blank=True, null=True)
    reset_token_expiry = models.DateTimeField(blank=True, null=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    date_joined      = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)



    objects          = CustomUserManager()


    USERNAME_FIELD   = 'username'
    REQUIRED_FIELDS  = ['first_name', 'last_name']

    class Meta:
        verbose_name        = 'User'
        verbose_name_plural = 'Users'
        ordering            = ['last_name', 'first_name']

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.other_names, self.last_name]
        return ' '.join(p for p in parts if p).strip()

    @property
    def is_parent_user(self) -> bool:
        return self.user_type == 'parent'

    @property
    def is_teacher_user(self) -> bool:
        return self.user_type == 'teacher'

    @property
    def is_support_staff_user(self) -> bool:
        return self.user_type == 'staff'

    @property
    def is_admin_user(self) -> bool:
        return self.user_type == 'admin'

    @property
    def login_identifier(self) -> str:
        """The credential this user presents at the login screen."""
        return self.parent_id if self.user_type == 'parent' else self.username

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.first_name

    def __str__(self) -> str:
        label = dict(USER_TYPE_CHOICES).get(self.user_type, self.user_type)
        return f'{self.full_name} ({label})'









