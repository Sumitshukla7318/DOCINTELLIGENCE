from django.contrib import admin
from .models import Document,QAHistory

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "mime_type", "status", "file_size_display", "created_at")
    list_filter = ("status", "mime_type")
    search_fields = ("title", "owner__email", "original_filename")
    readonly_fields = ("id", "file_size", "mime_type", "original_filename", "created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(QAHistory)
class QAHistoryAdmin(admin.ModelAdmin):
    list_display = ("document", "question_preview", "asked_at")
    search_fields = ("question", "document__title", "document__owner__email")
    readonly_fields = ("id", "asked_at")
    ordering = ("-asked_at",)

    def question_preview(self, obj):
        return obj.question[:80]
    question_preview.short_description = "Question"