from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdViewSet, ParseTargetViewSet, ingest_avito

router = DefaultRouter()
router.register(r"targets", ParseTargetViewSet, basename="parse-target")
router.register(r"ads", AdViewSet, basename="ad")


urlpatterns = [
    path("", include(router.urls)),
    path("ingest/avito", ingest_avito, name="ingest-avito"),
]
