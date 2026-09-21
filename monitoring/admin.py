from django.contrib import admin

from .models import Candidate, Submission


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("national_id", "full_name", "district", "exam_date")
    list_filter = ("district", "exam_date")
    search_fields = ("national_id", "full_name", "district")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("national_id", "full_name", "district", "score", "submitted_location", "submitted_at")
    list_filter = ("district", "submitted_location", "submitted_at")
    search_fields = ("national_id", "full_name", "district")
