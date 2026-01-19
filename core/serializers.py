from django.conf import settings
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
import random
from django.core.mail import send_mail

from .models import (
    SecuritySettings,
    User,
    Project,
    ScanResult,
    Framework,
    Stats,
    FrameworkCompliance,
    IssueCategory,
    ComplianceTrend,
    DisplaySettings,
    ApiIntegration,
    NotificationSettings,
    ComplianceSettings,
    HelpHero,
    Documentation,
    FAQ,
    SupportResource,
    ReleaseNote,
    ContactMessage,
    Report,
    Issue,
    Progress,
    HistoricalReport,
    Recommendation,
)

# ================== USER SERIALIZER ==================
class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'organization', 'avatar']
        extra_kwargs = {
            'username': {'required': False},
            'role': {'required': False},
            'email': {'required': False},
        }


# ================== REGISTER SERIALIZER ==================
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role', 'organization', 'job_title']
        extra_kwargs = {'role': {'default': 'developer'}}

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            role=validated_data.get('role', 'developer'),
            organization=validated_data.get('organization', ''),
            job_title=validated_data.get('job_title', '')
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


# ================== PROJECT SERIALIZER ==================
class ProjectSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Project
        # 'framework' field yahan honi chahiye
        fields = ['id', 'name', 'file', 'framework', 'status', 'uploaded_at', 'uploaded_by']

# ================== SCAN RESULT SERIALIZER ==================
class ScanResultSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = ScanResult
        fields = [
            'id', 'project', 'project_name', 'ethical_score', 
            'security_score', 'details', 'ai_recommendation', 'scanned_at'
        ]

# ================== FRAMEWORK SERIALIZER ==================
# ================== FRAMEWORK SERIALIZER (FIXED) ==================
class FrameworkSerializer(serializers.ModelSerializer):
    # React component 'name' aur 'description' expect karta hai
    class Meta:
        model = Framework
        fields = ['id', 'name', 'description'] 

# ================== FRAMEWORK COMPLIANCE SERIALIZER ==================
class FrameworkComplianceSerializer(serializers.ModelSerializer):
    # Frontend compatibility ke liye mappings
    title = serializers.CharField(source="framework.name", read_only=True)
    value = serializers.IntegerField(source="score", read_only=True)

    class Meta:
        model = FrameworkCompliance
        fields = ['id', 'title', 'value']


# ================== ISSUE CATEGORY SERIALIZER ==================
class IssueCategorySerializer(serializers.ModelSerializer):
    # FIX: React Charts 'category_name' aur 'issue_count' expect karte hain
    category_name = serializers.CharField(source='category')
    issue_count = serializers.IntegerField(source='count')
    class Meta:
        model = IssueCategory
        fields = ['id', 'category_name', 'issue_count']

class ComplianceTrendSerializer(serializers.ModelSerializer):
    # Agar model mein field 'month' hai to source='month' rahega
    # Agar model mein field 'label' hai to source='label' kar dein
    label = serializers.CharField(source='month', read_only=True) 
    
    class Meta:
        model = ComplianceTrend
        fields = ['id', 'label', 'score']

# ================== DASHBOARD STATS SERIALIZER ==================
class StatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stats
        fields = [
            'projects_scanned',
            'issues_detected',
            'compliance_score',
            'ethical_score',
            'cybersecurity_score',
            'ethical_issues',
            'security_weaknesses'
        ]


# ================== NOTIFICATION SETTINGS SERIALIZER ==================
class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = ["email_notifications", "sms_alerts", "system_updates", "weekly_reports"]


# ================== DISPLAY SETTINGS SERIALIZER ==================
class DisplaySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisplaySettings
        fields = ['theme', 'font_size']


# ================== API INTEGRATION SERIALIZER ==================
class ApiIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiIntegration
        fields = ["api_key", "webhook_url"]
        read_only_fields = ["api_key"]


# ================== COMPLIANCE SETTINGS SERIALIZER ==================
class ComplianceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceSettings
        fields = ["iso_27001", "gdpr", "hipaa", "soc2"]


# ================== SECURITY SETTINGS SERIALIZER ==================
class SecuritySettingsSerializer(serializers.ModelSerializer):
    new_password = serializers.CharField(write_only=True, required=False)
    otp = serializers.CharField(write_only=True, required=False)
    resend_otp = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = SecuritySettings
        fields = ["two_factor_enabled", "new_password", "otp", "resend_otp"]

    def update(self, instance, validated_data):
        user = instance.user
        otp = validated_data.get("otp")
        enable_2fa = validated_data.get("two_factor_enabled")
        password = validated_data.get("new_password")
        resend_otp = validated_data.get("resend_otp", False)

        OTP_EXPIRY = timedelta(minutes=5)

        # SEND / RESEND OTP
        if enable_2fa and (resend_otp or not instance.two_factor_enabled) and not otp:
            if instance.otp_created_at and timezone.now() < instance.otp_created_at + OTP_EXPIRY:
                otp_code = instance.otp_code
            else:
                otp_code = str(random.randint(100000, 999999))
                instance.otp_code = otp_code
                instance.otp_created_at = timezone.now()
                instance.save()

            send_mail(
                subject="Your 2FA OTP Code",
                message=f"Your OTP code is: {otp_code}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            raise serializers.ValidationError({"otp": "OTP sent to your email"})

        # VERIFY OTP
        if otp:
            if not instance.otp_created_at or instance.otp_code != otp or timezone.now() > instance.otp_created_at + OTP_EXPIRY:
                raise serializers.ValidationError({"otp": "Invalid or expired OTP"})
            instance.two_factor_enabled = enable_2fa
            instance.otp_code = ""
            instance.otp_created_at = None
            instance.save()

        # UPDATE PASSWORD
        if password:
            user.set_password(password)
            user.save()

        return instance


# ================== HELP CENTER SERIALIZERS ==================
class HelpHeroSerializer(serializers.ModelSerializer):
    class Meta:
        model = HelpHero
        fields = "__all__"

class DocumentationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documentation
        fields = "__all__"

class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = "__all__"

class SupportResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportResource
        fields = "__all__"

class ReleaseNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseNote
        fields = "__all__"


# ================== CONTACT MESSAGE SERIALIZER ==================
class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ["subject", "message"]

    def create(self, validated_data):
        user = self.context['request'].user
        contact = ContactMessage.objects.create(user=user, **validated_data)

        send_mail(
            subject=f"New Help Center Message: {validated_data['subject']}",
            message=f"From: {user.username} ({user.email})\n\n{validated_data['message']}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
        )

        return contact


# ================== REPORT SERIALIZERS ==================
from rest_framework import serializers
from .models import Report, Issue, Progress, HistoricalReport, Recommendation

class IssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = ['level', 'title', 'description']

class ProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Progress
        fields = ['framework', 'value']

class HistoricalReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalReport
        fields = ['date', 'score']

class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = ['text']

class ReportSerializer(serializers.ModelSerializer):
    # Mapping fields to match Frontend
    project_name = serializers.CharField(source='title', read_only=True)
    issues = IssueSerializer(many=True, read_only=True)
    progresses = ProgressSerializer(many=True, read_only=True)
    total_issues_count = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id', 'report_id', 'project_name', 'description', 
            'compliance_score', 'critical_issues', 'high_issues', 
            'medium_issues', 'generated_at', 'issues', 
            'progresses', 'total_issues_count'
        ]

    def get_total_issues_count(self, obj):
        try:
            # Check karein agar issues related_name exist karta hai
            return obj.issues.count()
        except AttributeError:
            return 0