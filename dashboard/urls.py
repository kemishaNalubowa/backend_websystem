from django.urls import path, include
from .import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", views.cover_page, name="cover_page"), 

    path("auth/", include("authentication.urls")),
    path("academics/", include("academics.urls",  namespace="academics")),
    path("accounts/", include("accounts.urls",  namespace="accounts")),
    path("assessments/", include("assessments.urls",  namespace="assessments")),
    path("communication/", include("communication.urls",  namespace="communication")),
    path("fees/", include("fees.urls",  namespace="fees")),
    path("school/", include("school.urls",  namespace="school")),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

