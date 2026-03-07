from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from common.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),

    # API v1
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/documents/", include("apps.documents.urls")),
    path("api/health/", health_check, name="health-check"), 

    # Schema (raw OpenAPI JSON — used by Swagger UI internally)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),

    # Swagger UI — interactive docs
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),

    # ReDoc — clean read-only docs (better for sharing with frontend devs)
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
] + static(settings.MEDIA_URL, document_root=getattr(settings, "MEDIA_ROOT", ""))