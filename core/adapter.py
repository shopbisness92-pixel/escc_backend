<<<<<<< HEAD
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import redirect

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(self, request, provider_id, error, exception, extra_context):
        # Jab error aaye toh Django page dikhane ke bajaye React login par bhej do
=======
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import redirect

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(self, request, provider_id, error, exception, extra_context):
        # Jab error aaye toh Django page dikhane ke bajaye React login par bhej do
>>>>>>> db10e5ef20a7e0293aa4275ab1c6357019f9d8ee
        return redirect('http://localhost:3000/login?error=social_auth_failed')