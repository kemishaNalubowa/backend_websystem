from django.contrib import admin

from . models import SchoolClass,ClassSubject,Subject

admin.site.register(SchoolClass)
admin.site.register(ClassSubject)
admin.site.register(Subject)