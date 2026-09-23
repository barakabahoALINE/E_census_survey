from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AccountAuthenticationTests(TestCase):
    def signup_data(self, **overrides):
        data = {
            "full_name": "Jane Doe",
            "email": "Jane.Doe@example.com",
            "password1": "Strong-password-123!",
            "password2": "Strong-password-123!",
        }
        data.update(overrides)
        return data

    def test_successful_signup_stores_user_with_hashed_password(self):
        response = self.client.post(reverse("accounts:signup"), self.signup_data())

        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(email="jane.doe@example.com")
        self.assertEqual(user.first_name, "Jane Doe")
        self.assertEqual(user.last_name, "")
        self.assertTrue(user.check_password("Strong-password-123!"))
        self.assertNotEqual(user.password, "Strong-password-123!")

    def test_signup_uses_full_name_instead_of_username(self):
        response = self.client.get(reverse("accounts:signup"))

        self.assertContains(response, "Full name")
        self.assertNotContains(response, "Username")

    def test_duplicate_email_is_rejected_case_insensitively(self):
        self.client.post(reverse("accounts:signup"), self.signup_data())

        response = self.client.post(
            reverse("accounts:signup"),
            self.signup_data(email="JANE.DOE@EXAMPLE.COM"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.filter(email__iexact="jane.doe@example.com").count(), 1)

    def test_password_confirmation_mismatch_is_rejected(self):
        response = self.client.post(
            reverse("accounts:signup"),
            self.signup_data(password2="Different-password-123!"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "two password fields")
        self.assertEqual(User.objects.count(), 0)

    def test_successful_email_login(self):
        self.client.post(reverse("accounts:signup"), self.signup_data())

        response = self.client.post(
            reverse("accounts:login"),
            {"email": "JANE.DOE@example.com", "password": "Strong-password-123!"},
        )

        self.assertRedirects(response, reverse("monitoring:dashboard"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_form_renders_email_field(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, 'type="email"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, "Enter your email address")
        self.assertNotContains(response, "Username")

    def test_incorrect_password_is_rejected(self):
        self.client.post(reverse("accounts:signup"), self.signup_data())

        response = self.client.post(
            reverse("accounts:login"),
            {"email": "jane.doe@example.com", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid email and password")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_ends_session(self):
        user = User.objects.create_user(
            email="logout@example.com",
            password="Strong-password-123!",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertRedirects(self.client.get(reverse("monitoring:dashboard")), "/accounts/login/?next=/")

    def test_unauthenticated_user_cannot_access_dashboard(self):
        response = self.client.get(reverse("monitoring:dashboard"))

        self.assertRedirects(response, "/accounts/login/?next=/")

    def test_unauthenticated_user_cannot_access_sites_or_reports(self):
        for url in (reverse("monitoring:sites"), reverse("monitoring:reports")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"/accounts/login/?next={url}")

    def test_authenticated_user_can_access_dashboard(self):
        user = User.objects.create_user(
            email="dashboard@example.com",
            password="Strong-password-123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("monitoring:dashboard"))

        self.assertEqual(response.status_code, 200)