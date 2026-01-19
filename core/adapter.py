from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import redirect

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(self, request, provider_id, error, exception, extra_context):
        # Jab error aaye toh Django page dikhane ke bajaye React login par bhej do
        return redirect('http://localhost:3000/login?error=social_auth_failed')