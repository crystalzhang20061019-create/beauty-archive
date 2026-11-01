from django.core.management.base import BaseCommand
from archive.models import Category, ProductType

class Command(BaseCommand):
    help = "Create the starter category and product type choices. Safe to run more than once."
    def handle(self, *args, **options):
        catalog={"Makeup":["Lip Products","Eyeshadow","Blush","Foundation","Mascara","Eyeliner","Brows","Highlighter","Primer","Powder","Setting Spray"],"Skincare":["Cleanser","Toner","Serum","Moisturizer","Cream","Sunscreen","Mask","Eye Care","Treatment"],"Fragrance":["Perfume","Body Mist"],"Personal Care":["Body Care","Hair Care","Nails","Tools","Other"]}
        for category, types in catalog.items():
            obj,_=Category.objects.get_or_create(name=category)
            for name in types: ProductType.objects.get_or_create(category=obj,name=name)
        self.stdout.write(self.style.SUCCESS("Starter categories and product types are ready."))
