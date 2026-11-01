from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", auth_views.LoginView.as_view(template_name="archive/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-reset/", auth_views.PasswordChangeView.as_view(template_name="archive/password_change.html", success_url="/settings/"), name="password_change"),
    path("collection/", views.collection, name="collection"),
    path("collection/browse/<str:mode>/", views.browse, name="browse"),
    path("products/add/", views.product_add, name="product_add"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/add-unit/", views.product_add_unit, name="product_add_unit"),
    path("products/<int:pk>/archive/", views.product_archive, name="product_archive"),
    path("products/<int:pk>/usage/add/", views.usage_add, name="usage_add"),
    path("usage/<int:pk>/edit/", views.usage_edit, name="usage_edit"),
    path("usage/<int:pk>/delete/", views.usage_delete, name="usage_delete"),
    path("statistics/", views.statistics, name="statistics"),
    path("exchange-quote/", views.exchange_quote, name="exchange_quote"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/<int:pk>/edit/", views.wishlist_edit, name="wishlist_edit"),
    path("wishlist/<int:pk>/delete/", views.wishlist_delete, name="wishlist_delete"),
    path("wishlist/<int:pk>/purchase/", views.wishlist_purchase, name="wishlist_purchase"),
    path("settings/", views.account_settings, name="settings"),
    path("export/<str:kind>.csv", views.export_csv, name="export_csv"),
    path("export/backup.json", views.export_json, name="export_json"),
]
