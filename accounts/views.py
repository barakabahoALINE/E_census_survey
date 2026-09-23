from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from .services.authentication import EmailLoginForm, StaffSignupForm


class StaffLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True


class StaffLogoutView(LogoutView):
    next_page = "accounts:login"


def signup(request):
    if request.user.is_authenticated:
        return redirect("monitoring:dashboard")
    form = StaffSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("accounts:login")
    return render(request, "accounts/signup.html", {"form": form})
