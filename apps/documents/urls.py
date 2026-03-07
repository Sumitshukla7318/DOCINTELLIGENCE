from django.urls import path
# from .views import DocumentUploadView, DocumentListView, DocumentDetailView
from .views import DocumentUploadView, DocumentListView, DocumentDetailView, DocumentQAView,DocumentRetryView,DocumentQAHistoryView


urlpatterns = [
    path("", DocumentListView.as_view(), name="document-list"),
    path("upload/", DocumentUploadView.as_view(), name="document-upload"),
    path("<uuid:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path("<uuid:pk>/qa/", DocumentQAView.as_view(), name="document-qa"),
    path("<uuid:pk>/retry/", DocumentRetryView.as_view(), name="document-retry"),
    path("<uuid:pk>/qa/history/", DocumentQAHistoryView.as_view(), name="document-qa-history"),
]