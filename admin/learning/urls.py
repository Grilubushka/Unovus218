from django.urls import path

from .api import CertificateUploadView, FeedbackView, OnboardingCompleteView, ProgressMarkView, RoadmapView
from . import views


app_name = "learning"

urlpatterns = [
    path("", views.index, name="index"),
    path("questions/", views.questions, name="questions"),
    path("courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("elements/<int:pk>/feedback/", views.element_feedback, name="element_feedback"),
    path("modules/<int:pk>/skip/", views.module_skip, name="module_skip"),
    path("modules/<int:pk>/balance/", views.module_balance, name="module_balance"),
    path("api/onboarding/complete", OnboardingCompleteView.as_view(), name="api_onboarding_complete"),
    path("api/roadmap", RoadmapView.as_view(), name="api_roadmap"),
    path("api/progress/mark", ProgressMarkView.as_view(), name="api_progress_mark"),
    path("api/feedback", FeedbackView.as_view(), name="api_feedback"),
    path("api/certificates/upload", CertificateUploadView.as_view(), name="api_certificates_upload"),
]
