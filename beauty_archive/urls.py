from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from archive import views

urlpatterns = [path("admin/", admin.site.urls), path("", include("archive.urls")), path("private-media/<path:path>", views.private_media, name="private_media")]
