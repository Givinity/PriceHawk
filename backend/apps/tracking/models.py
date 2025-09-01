from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Source(models.TextChoices):
    """
    Источник данных (площадка). В MVP поддерживаем Avito.

    Храним как текстовое значение, чтобы было читаемо в БД
    и гибко в дальнейшем (добавятся другие площадки).
    """

    AVITO = "avito", "Avito"


class TargetMode(models.TextChoices):
    """
    Режим цели парсинга. В MVP поддерживается ТОЛЬКО листинг (страница со списком).

    - listing: URL каталога/выдачи/подборки (много объявлений)
    """

    LISTING = "listing", "Listing"


class ParseTarget(models.Model):
    """
    Цель парсинга, созданная пользователем.

    Пример: листинг Avito с фильтрами или ссылка на одно объявление.
    Планировщик/воркер периодически обрабатывает активные цели и обновляет
    объявления и их цены.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parse_targets",
        help_text=(
            "Владелец цели. Ограничиваем видимость и используем для квот/лимитов."
        ),
    )
    source = models.CharField(
        max_length=32,
        choices=Source.choices,
        default=Source.AVITO,
        help_text="Площадка-источник (в MVP: Avito).",
    )
    mode = models.CharField(
        max_length=16,
        choices=TargetMode.choices,
        default=TargetMode.LISTING,
        help_text="Режим: только листинг (страница со списком объявлений).",
    )
    url = models.URLField(
        max_length=2000,
        help_text=(
            "Полный URL. Рекомендуется хранить нормализованный адрес с параметрами."
        ),
    )
    city = models.CharField(
        max_length=64,
        blank=True,
        help_text="Город/регион (если влияет на выдачу; опционально).",
    )
    frequency_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(5)],
        help_text="Периодичность парсинга в минутах (не менее 5).",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Флаг мягкого выключения цели без удаления.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Когда цель была создана."
    )
    last_run_at = models.DateTimeField(
        null=True, blank=True, help_text="Когда цель обрабатывалась последний раз."
    )
    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Когда цель должна быть обработана в следующий раз (для планировщика)."
        ),
    )

    class Meta:
        verbose_name = "Цель парсинга"
        verbose_name_plural = "Цели парсинга"
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "source", "url"],
                name="parse_target_owner_source_url_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["source", "mode"], name="parse_target_src_mode_idx"),
            models.Index(fields=["is_active"], name="parse_target_active_idx"),
            models.Index(fields=["next_run_at"], name="parse_target_next_run_idx"),
            models.Index(
                fields=["owner", "is_active"], name="parse_target_owner_active_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source}:{self.mode} {self.url}"


class Ad(models.Model):
    """
    Объявление на площадке (дедупликация по паре (source, external_id)).

    Если то же объявление встречается в разных листингах/целях, мы обновляем
    единственную запись `Ad` и привязываем её к последней/релевантной цели
    (или храним историю связей отдельно — усложнение на будущее).
    """

    source = models.CharField(
        max_length=32,
        choices=Source.choices,
        help_text="Площадка-источник (Avito и др. в будущем).",
    )
    external_id = models.CharField(
        max_length=128,
        help_text=(
            "Первичный идентификатор объявления на площадке " "(например, id Avito)."
        ),
    )
    target = models.ForeignKey(
        ParseTarget,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ads",
        help_text=(
            "Цель, в рамках которой объявление было обнаружено (может быть NULL)."
        ),
    )
    title = models.CharField(
        max_length=512, help_text="Заголовок объявления (усечённый до 512 символов)."
    )
    url = models.URLField(max_length=2000, help_text="Прямой URL на объявление.")
    seller_name = models.CharField(
        max_length=256, blank=True, help_text="Имя/название продавца (если доступно)."
    )
    seller_id = models.CharField(
        max_length=128, blank=True, help_text="Идентификатор продавца на площадке."
    )
    location = models.CharField(
        max_length=256, blank=True, help_text="Локация/город из карточки."
    )
    currency = models.CharField(
        max_length=8, default="RUB", help_text="Код валюты (ISO, например RUB)."
    )
    price_current = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Актуальная цена по последнему сбору (если удалось извлечь).",
    )
    posted_at = models.DateTimeField(
        null=True, blank=True, help_text="Дата публикации объявления (если доступно)."
    )
    is_active = models.BooleanField(
        default=True,
        help_text=(
            "Активность объявления. Выключаем, если исчезло из выдачи/404 и т.п."
        ),
    )
    last_seen_at = models.DateTimeField(
        auto_now=True,
        help_text="Когда это объявление в последний раз было замечено парсером.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Когда объявление впервые появилось у нас."
    )

    class Meta:
        verbose_name = "Объявление"
        verbose_name_plural = "Объявления"
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"],
                name="ad_source_external_id_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["source", "external_id"], name="ad_src_extid_idx"),
            models.Index(fields=["is_active"], name="ad_active_idx"),
            models.Index(fields=["last_seen_at"], name="ad_last_seen_idx"),
            models.Index(fields=["target"], name="ad_target_idx"),
            models.Index(fields=["posted_at"], name="ad_posted_at_idx"),
        ]
        ordering = ["-last_seen_at"]

    def __str__(self) -> str:
        return f"{self.source}:{self.external_id} {self.title[:40]}"


class PricePoint(models.Model):
    """
    Точка истории цены для объявления.

    Пишем каждый раз при успешном извлечении цены. Для ускорения чтения
    храним последнюю цену также в `Ad.price_current`.
    """

    ad = models.ForeignKey(
        Ad,
        on_delete=models.CASCADE,
        related_name="price_points",
        help_text="Объявление, к которому относится эта цена.",
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Значение цены на момент сбора.",
    )
    currency = models.CharField(
        max_length=8, default="RUB", help_text="Код валюты (ISO, например RUB)."
    )
    collected_at = models.DateTimeField(
        help_text="Момент времени (UTC), когда зафиксирована эта цена."
    )

    class Meta:
        verbose_name = "История цены"
        verbose_name_plural = "История цен"
        constraints = [
            models.UniqueConstraint(
                fields=["ad", "collected_at", "price"],
                name="price_point_ad_dt_price_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["ad", "collected_at"], name="price_point_ad_dt_idx"),
        ]
        ordering = ["-collected_at"]

    def __str__(self) -> str:
        return f"{self.ad_id}: {self.price} {self.currency} @ {self.collected_at}"
