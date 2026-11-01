from django import forms
from .models import Brand, Category, InventoryItem, Product, ProductType, Purchase, Series, UsageRecord, WishlistItem

class ProductForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.all())
    product_type = forms.ModelChoiceField(queryset=ProductType.objects.all())
    brand = forms.ModelChoiceField(queryset=Brand.objects.all(), required=False)
    new_brand = forms.CharField(max_length=120, required=False)
    series = forms.ModelChoiceField(queryset=Series.objects.all(), required=False)
    new_series = forms.CharField(max_length=120, required=False)
    name = forms.CharField(max_length=180)
    shade_code = forms.CharField(max_length=80, required=False)
    shade_name = forms.CharField(max_length=120, required=False)
    finish = forms.CharField(max_length=120, required=False)
    description = forms.CharField(widget=forms.Textarea, required=False)
    status = forms.ChoiceField(choices=InventoryItem.Status.choices)
    image = forms.ImageField(required=False)
    open_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type":"date"}))
    expiration_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type":"date"}))
    pao_months = forms.IntegerField(required=False, min_value=1, max_value=120)
    rating = forms.IntegerField(required=False, min_value=1, max_value=5)
    review = forms.CharField(widget=forms.Textarea, required=False)
    pros = forms.CharField(widget=forms.Textarea, required=False)
    cons = forms.CharField(widget=forms.Textarea, required=False)
    repurchase = forms.ChoiceField(choices=[("", "Not decided"), ("yes", "Yes"), ("no", "No")], required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)
    purchase_date = forms.DateField(widget=forms.DateInput(attrs={"type":"date"}))
    original_amount = forms.DecimalField(label="Purchase price", max_digits=12, decimal_places=2, min_value=0)
    currency = forms.ChoiceField(label="Currency", choices=Purchase._meta.get_field("currency").choices)
    usd_amount = forms.DecimalField(label="USD amount (converted)", max_digits=12, decimal_places=2, min_value=0, required=False, help_text="Auto-filled from the purchase date and currency. Enter manually if the rate lookup is unavailable.")
    location = forms.CharField(max_length=180, required=False)
    purchase_notes = forms.CharField(widget=forms.Textarea, required=False)
    def clean(self):
        data = super().clean()
        if not data.get("brand") and not data.get("new_brand"):
            self.add_error("brand", "Choose a brand or enter a new one.")
        if data.get("product_type") and data.get("category") and data["product_type"].category_id != data["category"].id:
            self.add_error("product_type", "Choose a product type from the selected category.")
        if data.get("series") and data.get("brand") and data["series"].brand_id != data["brand"].id:
            self.add_error("series", "Choose a series from the selected brand.")
        return data

class UsageForm(forms.ModelForm):
    class Meta:
        model = UsageRecord
        fields = ["date", "count", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type":"date"})}

class WishlistForm(forms.ModelForm):
    class Meta:
        model = WishlistItem
        fields = ["brand", "series", "name", "shade", "image_url", "expected_price", "currency", "notes", "priority"]

class PurchaseForm(forms.Form):
    status = forms.ChoiceField(choices=InventoryItem.Status.choices, initial=InventoryItem.Status.UNOPENED)
    purchase_date = forms.DateField(widget=forms.DateInput(attrs={"type":"date"}))
    original_amount = forms.DecimalField(label="Purchase price", max_digits=12, decimal_places=2, min_value=0)
    currency = forms.ChoiceField(label="Currency", choices=Purchase._meta.get_field("currency").choices)
    usd_amount = forms.DecimalField(label="USD amount (converted)", max_digits=12, decimal_places=2, min_value=0, required=False)
    location = forms.CharField(max_length=180, required=False)
