from django.db import models


class Candidate(models.Model):
    national_id = models.CharField(max_length=32, unique=True, db_index=True)
    full_name = models.CharField(max_length=255)
    district = models.CharField(max_length=100, db_index=True)
    registered_location = models.CharField(max_length=255, blank=True)
    exam_date = models.DateField(null=True, blank=True, db_index=True)
    sector = models.CharField(max_length=100, blank=True)
    cell = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    qualification = models.CharField(max_length=100, blank=True)
    field_of_study = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["district", "full_name"]
        indexes = [models.Index(fields=["district", "national_id"])]

    def __str__(self):
        return f"{self.full_name} ({self.national_id})"


class Submission(models.Model):
    national_id = models.CharField(max_length=32, unique=True, db_index=True)
    full_name = models.CharField(max_length=255, blank=True)
    district = models.CharField(max_length=100, blank=True, db_index=True)
    submitted_location = models.CharField(max_length=255, blank=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at", "national_id"]

    def __str__(self):
        return f"Submission for {self.national_id}"
