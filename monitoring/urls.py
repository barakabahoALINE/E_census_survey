from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
	path("", views.dashboard, name="dashboard"),
	path("sites/", views.sites, name="sites"),
	path("sites/<str:district>/", views.district_detail, name="district_detail"),
	path("reports/", views.reports, name="reports"),
	path("reports/export.csv", views.reports_csv, name="reports_csv"),
	path("settings/", views.settings, name="settings"),
]
