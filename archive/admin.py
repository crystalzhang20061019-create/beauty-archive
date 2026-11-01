from django.contrib import admin
from .models import Brand, Category, InventoryItem, Product, ProductType, Purchase, Series, UsageRecord, UserSettings, WishlistItem

admin.site.register([Brand, Category, ProductType, Series, Product, InventoryItem, Purchase, UsageRecord, UserSettings, WishlistItem])
