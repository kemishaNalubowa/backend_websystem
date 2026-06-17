from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'user_type', 'phone', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('user_type', 'parent_id', 'other_names', 'gender', 'date_of_birth', 'profile_photo', 'phone', 'alt_phone', 'address', 'nin', 'is_first_login', 'reset_token', 'reset_token_expiry')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)