<<<<<<< HEAD
from django.contrib import admin
from django.urls import path, include

# 🔐 JWT AUTH
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView
)

# 📁 Media serve
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # 🛠 Admin
    path('admin/', admin.site.urls),

    # 🔹 Core APIs (projects, dashboard, register, etc.)
    path('api/', include('core.urls')),

    # 🔐 JWT Authentication
    path('api/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('accounts/', include('allauth.urls')), # <--- Yeh line hona ZAROORI hai
]

# 📂 Media files (development only)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
=======
from django.contrib import admin
from django.urls import path, include

# 🔐 JWT AUTH
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView
)

# 📁 Media serve
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # 🛠 Admin
    path('admin/', admin.site.urls),

    # 🔹 Core APIs (projects, dashboard, register, etc.)
    path('api/', include('core.urls')),

    # 🔐 JWT Authentication
    path('api/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('accounts/', include('allauth.urls')), # <--- Yeh line hona ZAROORI hai
]

# 📂 Media files (development only)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
>>>>>>> db10e5ef20a7e0293aa4275ab1c6357019f9d8ee
