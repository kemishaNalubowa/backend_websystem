from django.contrib import admin
from .models import SchoolSetting, SchoolAnnouncement, SchoolEvent, DynamicImage


@admin.register(SchoolSetting)
class SchoolSettingAdmin(admin.ModelAdmin):
    list_display = ['school_name', 'district', 'phone', 'email']


@admin.register(SchoolAnnouncement)
class SchoolAnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'audience', 'priority', 'is_published', 'published_at']
    list_filter = ['audience', 'priority', 'is_published']
    search_fields = ['title', 'content']


@admin.register(SchoolEvent)
class SchoolEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'start_date', 'end_date', 'venue', 'is_published']
    list_filter = ['event_type', 'is_published']
    search_fields = ['title', 'description', 'venue']
    date_hierarchy = 'start_date'


@admin.register(DynamicImage)
class DynamicImageAdmin(admin.ModelAdmin):
    list_display  = ['label', 'key', 'category', 'is_active', 'updated_at']
    list_filter   = ['category', 'is_active']
    search_fields = ['key', 'label', 'description']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Image Identity', {
            'fields': ('key', 'label', 'category', 'is_active')
        }),
        ('File', {
            'fields': ('image',)
        }),
        ('Notes', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
