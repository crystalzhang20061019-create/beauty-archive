from decimal import Decimal
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

CURRENCIES = [(c, c) for c in "USD CNY EUR GBP JPY KRW THB HKD TWD CAD AUD".split()]

class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    def __str__(self): return self.name

class ProductType(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="types")
    name = models.CharField(max_length=80)
    class Meta: unique_together = [("category", "name")]
    def __str__(self): return self.name

class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    def __str__(self): return self.name

class Series(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="series")
    name = models.CharField(max_length=120)
    class Meta: unique_together = [("brand", "name")]
    def __str__(self): return self.name

class Product(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    series = models.ForeignKey(Series, on_delete=models.PROTECT, null=True, blank=True, related_name="products")
    product_type = models.ForeignKey(ProductType, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=180)
    shade_code = models.CharField(max_length=80, blank=True)
    shade_name = models.CharField(max_length=120, blank=True)
    finish = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    class Meta: indexes = [models.Index(fields=["name", "shade_code"])]
    def __str__(self): return f"{self.brand} {self.name}" + (f" · {self.shade_code}" if self.shade_code else "")

class InventoryItem(models.Model):
    class Status(models.TextChoices):
        UNOPENED = "unopened", "Unopened"
        IN_USE = "in_use", "In Use"
        FINISHED = "finished", "Finished"
        EXPIRED = "expired", "Expired"
        DECLUTTERED = "decluttered", "Decluttered"
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="items")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNOPENED, db_index=True)
    image = models.ImageField(upload_to="products/%Y/%m/", blank=True)
    open_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    pao_months = models.PositiveSmallIntegerField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True)
    pros = models.TextField(blank=True)
    cons = models.TextField(blank=True)
    repurchase = models.BooleanField(null=True, blank=True)
    notes = models.TextField(blank=True)
    archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    @property
    def effective_expiration(self):
        dates = [self.expiration_date] if self.expiration_date else []
        if self.open_date and self.pao_months:
            from datetime import date
            from calendar import monthrange
            month = self.open_date.month - 1 + self.pao_months
            year = self.open_date.year + month // 12
            month = month % 12 + 1
            dates.append(date(year, month, min(self.open_date.day, monthrange(year, month)[1])))
        return min(dates) if dates else None
    @property
    def total_uses(self): return sum(self.usage_records.values_list("count", flat=True))
    @property
    def usage_days(self): return self.usage_records.values("date").distinct().count()
    @property
    def first_used(self): return self.usage_records.order_by("date").values_list("date", flat=True).first()
    @property
    def last_used(self): return self.usage_records.order_by("-date").values_list("date", flat=True).first()
    def __str__(self): return str(self.product)

class Purchase(models.Model):
    item = models.OneToOneField(InventoryItem, on_delete=models.CASCADE, related_name="purchase")
    date = models.DateField(default=timezone.localdate, db_index=True)
    original_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="USD")
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("1"))
    rate_date = models.DateField(null=True, blank=True)
    rate_source = models.CharField(max_length=120, default="Manual / USD")
    usd_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), db_index=True)
    location = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)
    def __str__(self): return f"{self.date}: ${self.usd_amount}"

class UsageRecord(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="usage_records")
    date = models.DateField(default=timezone.localdate, db_index=True)
    count = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    notes = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: ordering = ["-date", "-created_at"]

class WishlistItem(models.Model):
    brand = models.CharField(max_length=120, blank=True)
    series = models.CharField(max_length=120, blank=True)
    name = models.CharField(max_length=180)
    shade = models.CharField(max_length=120, blank=True)
    image_url = models.URLField(blank=True)
    expected_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="USD")
    notes = models.TextField(blank=True)
    priority = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    added_at = models.DateTimeField(default=timezone.now)
    purchased = models.BooleanField(default=False, db_index=True)
    purchased_item = models.ForeignKey(InventoryItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="wishlist_source")

class UserSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="archive_settings")
    expiry_days = models.PositiveSmallIntegerField(default=90)
