from django.contrib import admin

from . models import (
    SchoolClass,
    SchoolSupportedClasses,
    SchoolClassTeacher,

    ClassSubject,
    Subject,
    TeacherSubject,
    TeacherClass)

admin.site.register(SchoolClass)
admin.site.register(SchoolSupportedClasses)
admin.site.register(SchoolClassTeacher)


admin.site.register(ClassSubject)
admin.site.register(Subject)
admin.site.register(TeacherSubject)
admin.site.register(TeacherClass)

