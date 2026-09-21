from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from .services.candidate_status import (
    candidate_status_queryset,
    district_counts,
    district_summary_rows,
    filter_candidates,
    paginate_candidates,
)
from .services.dashboard import build_dashboard_summary
from .services.reports import build_csv_response, build_report_context


@login_required
def dashboard(request):
    context = build_dashboard_summary()
    context["active_nav"] = "dashboard"
    return render(request, "monitoring/dashboard.html", context)


@login_required
def sites(request):
    return render(request, "monitoring/sites.html", {"districts": district_summary_rows(), "active_nav": "sites"})


@login_required
def district_detail(request, district):
    status = request.GET.get("status", "all")
    search = request.GET.get("search", "").strip()
    page_obj = paginate_candidates(
        filter_candidates(candidate_status_queryset(), district=district, status=status, search=search),
        request.GET.get("page"),
    )
    context = {
        "district": district,
        "summary": district_counts(district),
        "page_obj": page_obj,
        "status": status,
        "search": search,
        "active_nav": "sites",
    }
    return render(request, "monitoring/district_detail.html", context)


@login_required
def reports(request):
    filters = {
        "district": request.GET.get("district", "").strip(),
        "status": request.GET.get("status", "all").strip(),
        "search": request.GET.get("search", "").strip(),
    }
    report = build_report_context(**filters)
    page_obj = paginate_candidates(report["candidates"], request.GET.get("page"))
    return render(request, "monitoring/reports.html", {
        **report,
        "page_obj": page_obj,
        "district": filters["district"],
        "status": filters["status"],
        "search": filters["search"],
        "available_districts": district_summary_rows(),
        "active_nav": "reports",
    })


@login_required
def reports_csv(request):
    filters = {
        "district": request.GET.get("district", "").strip(),
        "status": request.GET.get("status", "all").strip(),
        "search": request.GET.get("search", "").strip(),
    }
    report = build_report_context(**filters)
    response = HttpResponse(build_csv_response(report["candidates"]), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = "attachment; filename=exam-submission-report.csv"
    return response


@login_required
def settings(request):
    return render(request, "monitoring/settings.html", {"active_nav": "settings"})
