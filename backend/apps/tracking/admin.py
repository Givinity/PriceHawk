from django.contrib import admin

from .models import Ad, ParseTarget, PricePoint

admin.site.register(Ad)
admin.site.register(ParseTarget)
admin.site.register(PricePoint)
