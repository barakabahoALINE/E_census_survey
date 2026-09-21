from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from .services.authentication import StaffSignupForm, create_staff_user


class StaffLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class StaffLogoutView(LogoutView):
    next_page = "accounts:login"


def signup(request):
    if request.user.is_authenticated:
        return redirect("monitoring:dashboard")
    form = StaffSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = create_staff_user(form)
        login(request, user)
        return redirect("monitoring:dashboard")
    return render(request, "accounts/signup.html", {"form": form})
