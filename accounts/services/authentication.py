from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class StaffSignupForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")


def create_staff_user(form: StaffSignupForm):
    """Create a regular staff account; administrator privileges are assigned separately."""
    user = form.save(commit=False)
    user.is_staff = True
    user.save()
    return user
