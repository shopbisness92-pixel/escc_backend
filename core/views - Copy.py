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
    ContactMessageSerializer, ReportSerializer
)

# ================== USER REGISTRATION & PROFILE ==================
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

        # Avg Scores
        agg = scans.aggregate(e=Avg("ethical_score"), s=Avg("security_score"))
        e_avg, s_avg = agg['e'] or 0, agg['s'] or 0
        total_comp = int((e_avg + s_avg) / 2)

        # Issues Counters
        crit, high, med = 0, 0, 0
        for s in scans:
            if isinstance(s.details, dict):
                crit += s.details.get("critical", 0)
                high += s.details.get("high", 0)
                med += s.details.get("medium", 0)

        # Framework Cards
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
                "issues_detected": crit + high + med,
                "compliance_score": total_comp,
                "ethical_score": int(e_avg),
                "cybersecurity_score": int(s_avg),
            },
            "projects": ProjectSerializer(projects.order_by('-id')[:5], many=True).data,
            "frameworks": f_cards if f_cards else [{"name": "Ready", "score": 0}],
            "charts": {
                "issues_by_category": [
                    {"category_name": "Critical", "issue_count": crit},
                    {"category_name": "High Risk", "issue_count": high},
                    {"category_name": "Medium", "issue_count": med},
                ],
                # FIX: Added filter(user=user) for privacy and correctness
                "compliance_trend": ComplianceTrendSerializer(
                    ComplianceTrend.objects.filter(user=user).order_by('id'), 
                    many=True
                ).data
            }
        })
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        projects = Project.objects.filter(uploaded_by=user)
        scans = ScanResult.objects.filter(project__uploaded_by=user)

        # Avg Scores
        agg = scans.aggregate(e=Avg("ethical_score"), s=Avg("security_score"))
        e_avg, s_avg = agg['e'] or 0, agg['s'] or 0
        total_comp = int((e_avg + s_avg) / 2)

        # Issues Counters
        crit, high, med = 0, 0, 0
        for s in scans:
            if isinstance(s.details, dict):
                crit += s.details.get("critical", 0)
                high += s.details.get("high", 0)
                med += s.details.get("medium", 0)

        # Cards Data
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
                "issues_detected": crit + high + med,
                "compliance_score": total_comp,
                "ethical_score": int(e_avg),
                "cybersecurity_score": int(s_avg),
            },
            "projects": ProjectSerializer(projects.order_by('-id')[:5], many=True).data,
            "frameworks": f_cards if f_cards else [{"name": "Ready", "score": 0}],
            "charts": {
                "issues_by_category": [
                    {"category_name": "Critical", "issue_count": crit},
                    {"category_name": "High Risk", "issue_count": high},
                    {"category_name": "Medium", "issue_count": med},
                ],
                "compliance_trend": ComplianceTrendSerializer(ComplianceTrend.objects.all(), many=True).data
            }
        })
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

# ================== REPORTS ==================
class ReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        


 # ================== SCAN RESULT API ==================
class ScanResultViewSet(viewsets.ModelViewSet):
    serializer_class = ScanResultSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ScanResult.objects.filter(project__uploaded_by=self.request.user)       