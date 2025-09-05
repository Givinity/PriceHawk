import hmac
import json
from hashlib import sha256

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Ad, ParseTarget, PricePoint
from .serializers import AdSerializer, ParseTargetSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(obj, "owner_id", None) == getattr(request.user, "id", None)


class ParseTargetViewSet(viewsets.ModelViewSet):
    queryset = ParseTarget.objects.all()
    serializer_class = ParseTargetSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        return qs.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class AdViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ad.objects.all().select_related("target")
    serializer_class = AdSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        target_id = self.request.query_params.get("target")
        is_active = self.request.query_params.get("is_active")
        if not self.request.user.is_superuser:
            qs = qs.filter(target__owner=self.request.user)
        if target_id:
            qs = qs.filter(target_id=target_id)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        posted_gte = self.request.query_params.get("posted_at__gte")
        if posted_gte:
            qs = qs.filter(posted_at__gte=posted_gte)
        return qs


def _valid_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    if not signature:
        return False
    mac = hmac.new(key=secret.encode("utf-8"), msg=raw_body, digestmod=sha256)
    expected = mac.hexdigest()
    return hmac.compare_digest(expected, signature)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def ingest_avito(request: Request) -> Response:
    """
    Приём данных от воркера Avito. Защита: HMAC SHA256 по сырому телу.

    Заголовки:
    - X-Signature: hex(HMAC_SHA256(body, INGEST_HMAC_SECRET))
    - X-Idempotency-Key: уникальный ключ события (опционально)
    """

    secret = getattr(settings, "INGEST_HMAC_SECRET", None)
    signature = request.headers.get("X-Signature", "")
    raw = request.body
    if not secret or not _valid_signature(raw, signature, secret):
        return Response(
            {"detail": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return Response({"detail": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

    items = payload.get("items", [])
    source = payload.get("source", "avito")
    target_id = payload.get("target_id")
    fetched_at = payload.get("fetched_at") or timezone.now().isoformat()

    created, updated, price_points = 0, 0, 0
    with transaction.atomic():
        for item in items:
            ext_id = item.get("external_id")
            if not ext_id:
                continue
            defaults = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "seller_name": item.get("seller_name", ""),
                "seller_id": item.get("seller_id", ""),
                "location": item.get("location", ""),
                "currency": item.get("currency", "RUB"),
                "price_current": item.get("price"),
                "posted_at": item.get("posted_at"),
                "is_active": item.get("is_active", True),
                "target_id": target_id,
            }
            ad, is_created = Ad.objects.update_or_create(
                source=source, external_id=ext_id, defaults=defaults
            )
            created += int(is_created)
            updated += int(not is_created)

            if item.get("price") is not None:
                PricePoint.objects.get_or_create(
                    ad=ad,
                    price=item["price"],
                    currency=item.get("currency", "RUB"),
                    collected_at=fetched_at,
                )
                price_points += 1

    return Response(
        {
            "status": "accepted",
            "created": created,
            "updated": updated,
            "price_points": price_points,
        },
        status=status.HTTP_202_ACCEPTED,
    )
