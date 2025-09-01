from django.conf import settings
from django.db import models


class TelegramProfile(models.Model):
    """
    Привязка Django-пользователя к аккаунту Telegram.

    Используется для аутентификации через бота и для отправки уведомлений
    по chat_id. OneToOne гарантирует не более одной привязки на пользователя.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram",
        help_text="Пользователь, к которому привязан Telegram-аккаунт.",
    )
    telegram_user_id = models.BigIntegerField(
        unique=True,
        help_text="Уникальный идентификатор пользователя в Telegram (int64).",
    )
    chat_id = models.BigIntegerField(
        unique=True,
        help_text="Чат для доставки уведомлений (обычно совпадает с telegram_user_id).",
    )
    username = models.CharField(
        max_length=64,
        blank=True,
        help_text="Username в Telegram (если есть).",
    )
    linked_at = models.DateTimeField(
        auto_now_add=True, help_text="Когда выполнена привязка."
    )
    is_active = models.BooleanField(
        default=True,
        help_text=(
            "Флаг активности привязки (если пользователь удалил бота — выключаем)."
        ),
    )

    class Meta:
        verbose_name = "Профиль Telegram"
        verbose_name_plural = "Профили Telegram"
        indexes = [
            models.Index(fields=["telegram_user_id"], name="tg_profile_user_id_idx"),
            models.Index(fields=["chat_id"], name="tg_profile_chat_id_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} / tg:{self.telegram_user_id}"
