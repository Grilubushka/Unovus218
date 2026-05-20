from django.urls import path

from . import views


app_name = "learning"

urlpatterns = [
    path("", views.index, name="index"),
    path("questions/", views.questions, name="questions"),
    path("courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("elements/<int:pk>/feedback/", views.element_feedback, name="element_feedback"),
    path("modules/<int:pk>/skip/", views.module_skip, name="module_skip"),
    path("modules/<int:pk>/balance/", views.module_balance, name="module_balance"),
]
