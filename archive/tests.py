from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Brand, Category, InventoryItem, Product, ProductType, Purchase, UsageRecord, WishlistItem

class ArchiveBehaviorTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username="owner",password="local-test-password")
        self.category=Category.objects.create(name="Makeup")
        self.kind=ProductType.objects.create(category=self.category,name="Lip Products")
        self.brand=Brand.objects.create(name="Dior")
        self.product=Product.objects.create(brand=self.brand,product_type=self.kind,name="Rouge Dior",shade_code="999")
        self.item=InventoryItem.objects.create(product=self.product,status="unopened")
        self.purchase=Purchase.objects.create(item=self.item,date=date(2026,10,3),original_amount=Decimal("49.00"),currency="USD",usd_amount=Decimal("49.00"))

    def test_private_pages_require_login(self):
        response=self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code,302)
        self.assertIn(reverse("login"),response.url)

    def test_dashboard_and_collection_render_for_signed_in_user(self):
        self.client.login(username="owner",password="local-test-password")
        self.assertEqual(self.client.get(reverse("dashboard")).status_code,200)
        self.assertEqual(self.client.get(reverse("collection")).status_code,200)
        self.assertEqual(self.client.get(reverse("product_detail",args=[self.item.pk])).status_code,200)

    def test_all_private_sections_render(self):
        self.client.login(username="owner",password="local-test-password")
        for name in ["statistics","wishlist","settings"]:
            with self.subTest(page=name): self.assertEqual(self.client.get(reverse(name)).status_code,200)
        for mode in ["category","brand"]:
            with self.subTest(browse=mode): self.assertEqual(self.client.get(reverse("browse",args=[mode])).status_code,200)
        self.assertEqual(self.client.get(reverse("product_add")).status_code,200)
        self.assertEqual(self.client.get(reverse("collection"),{"sort":"last_used"}).status_code,200)

    def test_add_product_creates_item_and_purchase(self):
        self.client.login(username="owner",password="local-test-password")
        response=self.client.post(reverse("product_add"),{"category":self.category.pk,"product_type":self.kind.pk,"brand":self.brand.pk,"name":"Lip Glow","status":"unopened","purchase_date":"2026-10-31","original_amount":"38.00","currency":"USD"})
        self.assertEqual(response.status_code,302)
        item=InventoryItem.objects.get(product__name="Lip Glow")
        self.assertEqual(item.purchase.usd_amount,Decimal("38.00"))

    def test_additional_purchase_reuses_product_but_has_separate_item(self):
        self.client.login(username="owner",password="local-test-password")
        response=self.client.post(reverse("product_add_unit",args=[self.item.pk]),{"purchase_date":"2026-10-20","original_amount":"52.00","currency":"USD","status":"in_use"})
        self.assertEqual(response.status_code,302)
        self.assertEqual(InventoryItem.objects.filter(product=self.product).count(),2)
        new_item=InventoryItem.objects.exclude(pk=self.item.pk).get()
        self.assertEqual(new_item.status,"in_use")
        self.assertEqual(new_item.purchase.usd_amount,Decimal("52.00"))

    def test_both_collection_routes_reach_the_same_item(self):
        self.client.login(username="owner",password="local-test-password")
        for url in [
            reverse("browse",args=["category"]),
            reverse("browse",args=["category"])+f"?category={self.category.pk}",
            reverse("browse",args=["category"])+f"?category={self.category.pk}&type={self.kind.pk}",
            reverse("browse",args=["category"])+f"?category={self.category.pk}&type={self.kind.pk}&brand={self.brand.pk}",
            reverse("browse",args=["brand"]),
            reverse("browse",args=["brand"])+f"?brand={self.brand.pk}",
            reverse("browse",args=["brand"])+f"?brand={self.brand.pk}&category={self.category.pk}",
            reverse("browse",args=["brand"])+f"?brand={self.brand.pk}&category={self.category.pk}&type={self.kind.pk}",
        ]:
            with self.subTest(url=url): self.assertEqual(self.client.get(url).status_code,200)

    @patch("archive.services.requests.get")
    def test_historical_conversion_stores_rate_and_usd_value(self,mock_get):
        response=Mock(); response.raise_for_status.return_value=None; response.json.return_value={"date":"2026-10-02","rates":{"USD":7.1234}}; mock_get.return_value=response
        from .services import historical_usd_rate, usd_value
        rate,rate_date,source=historical_usd_rate("CNY",date(2026,10,3))
        self.assertEqual(rate,Decimal("7.1234")); self.assertEqual(rate_date,date(2026,10,2)); self.assertEqual(source,"Frankfurter.app")
        self.assertEqual(usd_value(Decimal("399"),rate),Decimal("2842.24"))

    def test_wishlist_conversion_records_actual_purchase_once(self):
        self.client.login(username="owner",password="local-test-password")
        wish=WishlistItem.objects.create(brand="Dior",name="Lip Oil",shade="Rose")
        response=self.client.post(reverse("wishlist_purchase",args=[wish.pk]),{"status":"unopened","purchase_date":"2026-10-30","original_amount":"35.00","currency":"USD"})
        self.assertEqual(response.status_code,302)
        wish.refresh_from_db()
        self.assertTrue(wish.purchased)
        self.assertEqual(Purchase.objects.count(),2)
        self.assertEqual(wish.purchased_item.purchase.usd_amount,Decimal("35.00"))

    @patch("archive.views.historical_usd_rate",return_value=(None,None,None))
    def test_failed_wishlist_rate_lookup_does_not_create_a_product(self,_mock_rate):
        self.client.login(username="owner",password="local-test-password")
        wish=WishlistItem.objects.create(brand="Dior",name="Lip Oil")
        response=self.client.post(reverse("wishlist_purchase",args=[wish.pk]),{"status":"unopened","purchase_date":"2026-10-30","original_amount":"35.00","currency":"CNY"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(InventoryItem.objects.count(),1)
        self.assertFalse(WishlistItem.objects.get(pk=wish.pk).purchased)

    def test_usage_count_and_distinct_usage_days(self):
        UsageRecord.objects.create(item=self.item,date=date(2026,10,1),count=1)
        UsageRecord.objects.create(item=self.item,date=date(2026,10,1),count=2)
        UsageRecord.objects.create(item=self.item,date=date(2026,10,2),count=1)
        self.assertEqual(self.item.total_uses,4)
        self.assertEqual(self.item.usage_days,2)

    def test_status_change_does_not_change_purchase_total(self):
        self.item.status=InventoryItem.Status.FINISHED
        self.item.save()
        self.assertEqual(Purchase.objects.get(pk=self.purchase.pk).usd_amount,Decimal("49.00"))

    def test_archive_preserves_purchase_and_usage(self):
        UsageRecord.objects.create(item=self.item,date=date(2026,10,1),count=1)
        self.client.login(username="owner",password="local-test-password")
        response=self.client.post(reverse("product_archive",args=[self.item.pk]))
        self.assertEqual(response.status_code,302)
        self.item.refresh_from_db()
        self.assertTrue(self.item.archived)
        self.assertTrue(Purchase.objects.filter(pk=self.purchase.pk).exists())
        self.assertEqual(self.item.usage_records.count(),1)

    def test_private_media_requires_authentication(self):
        response=self.client.get("/private-media/not-a-real-photo.jpg")
        self.assertEqual(response.status_code,302)
