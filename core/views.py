import csv
import io
import json
import os
import subprocess
import logging
import sys
import secrets
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db.models import Avg, Count
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.http import FileResponse, HttpResponse

from rest_framework import viewsets, generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

# Logger setup
logger = logging.getLogger(__name__)
User = get_user_model()

from .models import (
    Framework, Project, ScanResult, FrameworkCompliance, IssueCategory,
    ComplianceTrend, NotificationSettings, DisplaySettings, ApiIntegration,
    ComplianceSettings, SecuritySettings, HelpHero, Documentation, FAQ, 
    SupportResource, ReleaseNote, ContactMessage, Report
)
from .serializers import (
    FrameworkSerializer, ProjectSerializer, ScanResultSerializer, 
    RegisterSerializer, SecuritySettingsSerializer, UserSerializer,
    FrameworkComplianceSerializer, IssueCategorySerializer, ComplianceTrendSerializer,
    NotificationSettingsSerializer, DisplaySettingsSerializer, ApiIntegrationSerializer,
    ComplianceSettingsSerializer, HelpHeroSerializer, DocumentationSerializer, 
    FAQSerializer, SupportResourceSerializer, ReleaseNoteSerializer, 
    ContactMessageSerializer, 
)
# ✅ Sahi tareeqa: method_decorator use karein 'dispatch' method par
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get(self, request):
        return Response(UserSerializer(request.user).data)
    
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
# ================== PROJECT & AI SCAN INTEGRATION ==================
class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(uploaded_by=self.request.user).order_by('-id')

    def perform_create(self, serializer):
        # 1. Meta-data parsing
        desc_data = self.request.data.get('description', '{}')
        framework_name = "General AI"
        scan_mode = "standard"
        
        try:
            meta = json.loads(desc_data)
            framework_name = meta.get('framework', 'General AI')
            scan_mode = meta.get('scanType', 'standard')
        except:
            pass

        # 2. Project Initial Save
        project = serializer.save(
            uploaded_by=self.request.user, 
            framework=framework_name,
            status='Pending'
        )
        
        # 3. Trigger AI Engine
        try:
            file_path = project.file.path
            script_path = os.path.join(settings.BASE_DIR, 'ai_engine', 'predict.py')
            
            if os.path.exists(script_path):
                # Timeout logic
                p_timeout = 150 if scan_mode == 'deep' else 70
                
                result = subprocess.run(
                    [sys.executable, script_path, file_path, scan_mode],
                    capture_output=True, text=True, timeout=p_timeout
                )

                if result.returncode == 0:
                    ai_json = json.loads(result.stdout)
                    
                    # 4. Save Scan Result
                    ScanResult.objects.create(
                        project=project,
                        ethical_score=int(ai_json.get('ethical_score', 0)),
                        security_score=int(ai_json.get('security_score', 0)),
                        details=ai_json
                    )

                    # 5. SAVE TO COMPLIANCE TREND (Unique Timestamp)
                    avg_score = (int(ai_json.get('ethical_score', 0)) + int(ai_json.get('security_score', 0))) // 2
                    ComplianceTrend.objects.create(
                        user=self.request.user,
                        # Time add karne se har scan alag bar dikhayega
                        month=timezone.now().strftime("%b %d - %H:%M"), 
                        score=avg_score
                    )
                    
                    project.status = 'Completed'
                else:
                    logger.error(f"AI Error: {result.stderr}")
                    project.status = 'Failed'
            else:
                logger.error("AI Script path not found")
                project.status = 'Failed'
        except Exception as e:
            logger.error(f"Scan Crash: {str(e)}")
            project.status = 'Failed'
        
        project.save()
# ================== DASHBOARD API (CLEANED & FILTERED) ==================
class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        projects = Project.objects.filter(uploaded_by=user)
        scans = ScanResult.objects.filter(project__uploaded_by=user)

        # 1. Aggregate Scores
        agg = scans.aggregate(
            ethical_avg=Avg("ethical_score"),
            security_avg=Avg("security_score")
        )
        ethical_avg = int(agg.get("ethical_avg") or 0)
        security_avg = int(agg.get("security_avg") or 0)
        compliance_score = (ethical_avg + security_avg) // 2

        # 2. Issue Counters (Fixed the UnboundLocalError)
        critical = high = medium = total_issues = 0

        for scan in scans:
            data = scan.details
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    continue

            if not isinstance(data, dict):
                continue

            inner = data.get("details", data)
            critical += int(inner.get("critical", 0) or 0)
            high += int(inner.get("high", 0) or 0)
            medium += int(inner.get("medium", 0) or 0)

        total_issues = critical + high + medium

        # 3. Framework Cards
        f_cards = []
        for p in projects.order_by('-id')[:6]:
            s_obj = scans.filter(project=p).first()
            f_cards.append({
                "id": p.id,
                "name": p.framework,
                "score": int((s_obj.ethical_score + s_obj.security_score)/2) if s_obj else 0,
                "status": p.status,
                "description": f"Scan for {p.name}"
            })

        return Response({
            "user": UserSerializer(user).data,
            "stats": {
                "projects_scanned": projects.count(),
                "issues_detected": total_issues,
                "critical": critical,
                "high": high,
                "medium": medium,
                "compliance_score": compliance_score,
                "ethical_score": ethical_avg,
                "cybersecurity_score": security_avg,
            },
            "projects": ProjectSerializer(projects.order_by('-id')[:5], many=True).data,
            "frameworks": f_cards if f_cards else [{"name": "Ready", "score": 0}],
            "charts": {
                "issues_by_category": [
                    {"category_name": "Critical", "issue_count": critical},
                    {"category_name": "High", "issue_count": high},
                    {"category_name": "Medium", "issue_count": medium},
                ],
                "compliance_trend": ComplianceTrendSerializer(
                    ComplianceTrend.objects.filter(user=user).order_by('id'), 
                    many=True
                ).data
            }
        })
    permission_classes = [IsAuthenticated]
# ================== SETTINGS & INTEGRATIONS ==================
class NotificationSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        settings, _ = NotificationSettings.objects.get_or_create(user=request.user)
        return Response(NotificationSettingsSerializer(settings).data)
    def post(self, request):
        settings, _ = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Preferences updated"})

class DisplaySettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        settings, _ = DisplaySettings.objects.get_or_create(user=request.user)
        return Response(DisplaySettingsSerializer(settings).data)
    def patch(self, request):
        settings, _ = DisplaySettings.objects.get_or_create(user=request.user)
        serializer = DisplaySettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class ApiIntegrationAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        obj, _ = ApiIntegration.objects.get_or_create(user=request.user)
        return Response(ApiIntegrationSerializer(obj).data)
    def patch(self, request):
        obj, _ = ApiIntegration.objects.get_or_create(user=request.user)
        serializer = ApiIntegrationSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class RegenerateApiKeyAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        obj, _ = ApiIntegration.objects.get_or_create(user=request.user)
        obj.api_key = "sk_live_" + secrets.token_hex(24)
        obj.save()
        return Response({"api_key": obj.api_key})

class ComplianceSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        obj, _ = ComplianceSettings.objects.get_or_create(user=request.user)
        return Response(ComplianceSettingsSerializer(obj).data)
    def put(self, request):
        obj, _ = ComplianceSettings.objects.get_or_create(user=request.user)
        serializer = ComplianceSettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class SecuritySettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        settings, _ = SecuritySettings.objects.get_or_create(user=request.user)
        return Response(SecuritySettingsSerializer(settings).data)
    def put(self, request):
        settings, _ = SecuritySettings.objects.get_or_create(user=request.user)
        serializer = SecuritySettingsSerializer(settings, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"success": True})
        return Response(serializer.errors, status=400)

# ================== HELP CENTER ==================
class HelpCenterView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        hero = HelpHero.objects.first()
        hero_data = HelpHeroSerializer(hero).data if hero else {}
        return Response({
            "hero": hero_data,
            "documentation": DocumentationSerializer(Documentation.objects.all(), many=True).data,
            "faq": FAQSerializer(FAQ.objects.all(), many=True).data,
            "support": SupportResourceSerializer(SupportResource.objects.all(), many=True).data,
            "releases": ReleaseNoteSerializer(ReleaseNote.objects.all(), many=True).data,
        })

class ContactMessageView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        ContactMessage.objects.create(user=request.user, subject=request.data.get("subject"), message=request.data.get("message"))
        send_mail(
            subject=f"New Support Request: {request.data.get('subject')}",
            message=f"From: {request.user.email}\n\n{request.data.get('message')}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
        )
        return Response({"success": True})
    

#-------------------------contact
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import JSONParser
from django.conf import settings
from .models import GuestContactMessage # Naya model use karein

class ContactMessageView2(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        try:
            name = request.data.get("name")
            email = request.data.get("email")
            subject = request.data.get("subject")
            message = request.data.get("message")

            # 1. Database mein save karein
            GuestContactMessage.objects.create(
                name=name, email=email, subject=subject, message=message
            )

            # 2. EMAIL TO ADMIN (Plain Text)
            admin_subject = f"New Contact Form Submission: {subject}"
            admin_msg = f"User Name: {name}\nUser Email: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            
            # fail_silently=True taaki agar SMTP error ho toh app crash na ho
            from django.core.mail import send_mail
            send_mail(admin_subject, admin_msg, settings.DEFAULT_FROM_EMAIL, [settings.ADMIN_EMAIL], fail_silently=True)

            # 3. THANK YOU EMAIL TO USER (HTML Template)
            user_subject = "We received your message! - Ethical Software Compliance"
            context = {'name': name}
            
            # HTML Template ko load karein
            html_content = render_to_string('emails/thank_you.html', context)
            text_content = strip_tags(html_content) # Fallback text

            msg = EmailMultiAlternatives(user_subject, text_content, settings.DEFAULT_FROM_EMAIL, [email])
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)

            return Response({"success": True, "message": "Message sent successfully!"})

        except Exception as e:
            print(f"Error: {str(e)}")
            return Response({"success": False, "message": "Server error. Please try again later."}, status=500)


 # ================== SCAN RESULT API ==================
class ScanResultViewSet(viewsets.ModelViewSet):
    serializer_class = ScanResultSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ScanResult.objects.filter(project__uploaded_by=self.request.user)       
    





from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.linkedin_oauth2.views import LinkedInOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = "https://esccapp.netlify.app/" # Aapka React URL
    client_class = OAuth2Client

class LinkedInLogin(SocialLoginView):
    adapter_class = LinkedInOAuth2Adapter
    callback_url = "https://esccapp.netlify.app/"
    client_class = OAuth2Client    