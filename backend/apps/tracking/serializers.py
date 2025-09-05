from rest_framework import serializers

from .models import Ad, ParseTarget, PricePoint


class ParseTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParseTarget
        fields = (
            "id",
            "owner",
            "source",
            "mode",
            "url",
            "city",
            "frequency_minutes",
            "is_active",
            "created_at",
            "last_run_at",
            "next_run_at",
        )
        read_only_fields = ("id", "owner", "created_at", "last_run_at", "next_run_at")


class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = (
            "id",
            "source",
            "external_id",
            "target",
            "title",
            "url",
            "seller_name",
            "seller_id",
            "location",
            "currency",
            "price_current",
            "posted_at",
            "is_active",
            "last_seen_at",
            "created_at",
        )
        read_only_fields = ("id", "last_seen_at", "created_at")


class PricePointSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricePoint
        fields = ("id", "ad", "price", "currency", "collected_at")
        read_only_fields = ("id",)
