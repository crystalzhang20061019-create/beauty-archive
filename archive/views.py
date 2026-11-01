import csv, json, mimetypes
from calendar import month_name
from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Sum, Count, Max, Q
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from .forms import ProductForm, PurchaseForm, UsageForm, WishlistForm
from .models import Brand, Category, InventoryItem, Product, ProductType, Purchase, Series, UsageRecord, UserSettings, WishlistItem
from .services import historical_usd_rate, usd_value

def money(value): return Decimal(value or 0).quantize(Decimal("0.01"))

@login_required
def dashboard(request):
    today=timezone.localdate(); month_start=today.replace(day=1); items=InventoryItem.objects.filter(archived=False)
    purchases=Purchase.objects.select_related("item__product__brand","item__product__product_type").order_by("-date")
    month=purchases.filter(date__gte=month_start,date__lte=today)
    cats={"Makeup":Decimal("0"),"Skincare":Decimal("0"),"Other":Decimal("0")}
    for p in month:
        group=p.item.product.product_type.category.name.lower(); key="Makeup" if "makeup" in group else "Skincare" if "skin" in group else "Other"; cats[key]+=p.usd_amount
    settings_obj,_=UserSettings.objects.get_or_create(user=request.user); limit=today+timedelta(days=settings_obj.expiry_days)
    expiring=[i for i in items.exclude(status__in=["finished","decluttered"]).select_related("product__brand","product__product_type") if i.effective_expiration and today<=i.effective_expiration<=limit]
    ctx={"total_products":InventoryItem.objects.count(),"current_count":items.exclude(status__in=["finished","decluttered"]).count(),"makeup_count":items.filter(product__product_type__category__name__icontains="makeup").exclude(status__in=["finished","decluttered"]).count(),"skincare_count":items.filter(product__product_type__category__name__icontains="skin").exclude(status__in=["finished","decluttered"]).count(),"finished_count":items.filter(status="finished").count(),"unopened_count":items.filter(status="unopened").count(),"month_total":money(month.aggregate(v=Sum("usd_amount"))["v"]),"month_cats":{k:money(v) for k,v in cats.items()},"recent_purchases":purchases[:5],"recent_usage":UsageRecord.objects.select_related("item__product__brand","item__product").order_by("-date")[:5],"expiring":expiring[:6]}
    return render(request,"archive/dashboard.html",ctx)

@login_required
def collection(request):
    items=InventoryItem.objects.filter(archived=False).select_related("product__brand","product__series","product__product_type__category","purchase")
    q=request.GET.get("q","").strip()
    if q: items=items.filter(Q(product__brand__name__icontains=q)|Q(product__name__icontains=q)|Q(product__shade_code__icontains=q)|Q(product__shade_name__icontains=q)|Q(product__series__name__icontains=q)|Q(product__product_type__name__icontains=q)|Q(product__product_type__category__name__icontains=q))
    for field in ["status","product__product_type__category__id","product__product_type__id","product__brand__id"]:
        if request.GET.get(field): items=items.filter(**{field:request.GET[field]})
    if parse_date(request.GET.get("date_from", "")): items=items.filter(purchase__date__gte=parse_date(request.GET["date_from"]))
    if parse_date(request.GET.get("date_to", "")): items=items.filter(purchase__date__lte=parse_date(request.GET["date_to"]))
    if request.GET.get("expiring"):
        settings_obj,_=UserSettings.objects.get_or_create(user=request.user); today=timezone.localdate(); end=today+timedelta(days=settings_obj.expiry_days)
        expiring_ids=[i.pk for i in items.exclude(status__in=["finished","decluttered"]).only("id","open_date","expiration_date","pao_months") if i.effective_expiration and today<=i.effective_expiration<=end]
        items=items.filter(pk__in=expiring_ids)
    sort=request.GET.get("sort","recent"); sort_fields={"recent":"-purchase__date","oldest":"purchase__date","brand":"product__brand__name","high":"-purchase__usd_amount","low":"purchase__usd_amount"}
    if sort=="uses": items=items.annotate(usage_count=Sum("usage_records__count")).order_by("-usage_count")
    elif sort=="last_used": items=items.annotate(last_used_sort=Max("usage_records__date")).order_by("-last_used_sort")
    else: items=items.order_by(sort_fields.get(sort,"-purchase__date"))
    return render(request,"archive/collection.html",{"items":items,"categories":Category.objects.all(),"types":ProductType.objects.all(),"brands":Brand.objects.all(),"statuses":InventoryItem.Status.choices,"q":q})

@login_required
def browse(request,mode="category"):
    if mode not in ("category","brand"): mode="category"
    category=request.GET.get("category"); brand=request.GET.get("brand"); kind=request.GET.get("type"); series=request.GET.get("series")
    groups=[]; heading="Categories" if mode=="category" else "Brands"
    item_qs=InventoryItem.objects.filter(archived=False).select_related("product__brand","product__series","product__product_type__category","purchase")
    show_products=False
    if mode=="category":
        if not category:
            values=Category.objects.annotate(n=Count("types__products__items",filter=Q(types__products__items__archived=False))).order_by("name")
            groups=[{"name":v.name,"count":v.n,"url":f"?category={v.pk}"} for v in values]; heading="Categories"
        elif not kind:
            values=ProductType.objects.filter(category_id=category).annotate(n=Count("products__items",filter=Q(products__items__archived=False))).order_by("name")
            groups=[{"name":v.name,"count":v.n,"url":f"?category={category}&type={v.pk}"} for v in values]; heading="Product types"
        elif not brand:
            values=Brand.objects.filter(products__product_type_id=kind).annotate(n=Count("products__items",filter=Q(products__items__archived=False,products__product_type_id=kind))).order_by("name").distinct()
            groups=[{"name":v.name,"count":v.n,"url":f"?category={category}&type={kind}&brand={v.pk}"} for v in values]; heading="Brands"
        else:
            show_products=True; item_qs=item_qs.filter(product__product_type_id=kind,product__brand_id=brand)
            if series:
                item_qs=item_qs.filter(product__series_id=series); heading="Products"
            else:
                values=Series.objects.filter(brand_id=brand,products__product_type_id=kind).annotate(n=Count("products__items",filter=Q(products__items__archived=False,products__product_type_id=kind))).order_by("name")
                groups=[{"name":v.name,"count":v.n,"url":f"?category={category}&type={kind}&brand={brand}&series={v.pk}"} for v in values]; heading="Series"
                item_qs=item_qs.filter(product__series__isnull=True)
                show_products=True
    else:
        if not brand:
            values=Brand.objects.annotate(n=Count("products__items",filter=Q(products__items__archived=False))).order_by("name")
            groups=[{"name":v.name,"count":v.n,"url":f"?brand={v.pk}"} for v in values]; heading="Brands"
        elif not category:
            values=Category.objects.filter(types__products__brand_id=brand).annotate(n=Count("types__products__items",filter=Q(types__products__items__archived=False,types__products__brand_id=brand))).order_by("name").distinct()
            groups=[{"name":v.name,"count":v.n,"url":f"?brand={brand}&category={v.pk}"} for v in values]; heading="Categories"
        elif not kind:
            values=ProductType.objects.filter(category_id=category,products__brand_id=brand).annotate(n=Count("products__items",filter=Q(products__items__archived=False,products__brand_id=brand))).order_by("name").distinct()
            groups=[{"name":v.name,"count":v.n,"url":f"?brand={brand}&category={category}&type={v.pk}"} for v in values]; heading="Product types"
        elif not series:
            values=Series.objects.filter(brand_id=brand,products__product_type_id=kind).annotate(n=Count("products__items",filter=Q(products__items__archived=False,products__product_type_id=kind))).order_by("name")
            groups=[{"name":v.name,"count":v.n,"url":f"?brand={brand}&category={category}&type={kind}&series={v.pk}"} for v in values]; heading="Series"
            item_qs=item_qs.filter(product__brand_id=brand,product__product_type_id=kind,product__series__isnull=True)
        else:
            show_products=True; item_qs=item_qs.filter(product__brand_id=brand,product__product_type_id=kind,product__series_id=series); heading="Products"
    names={"category":Category.objects.filter(pk=category).first(),"brand":Brand.objects.filter(pk=brand).first()}
    return render(request,"archive/browse.html",{"mode":mode,"groups":groups,"heading":heading,"items":item_qs if show_products else [],"category_name":names["category"],"brand_name":names["brand"]})

def _save_new_item(form):
    d=form.cleaned_data; brand=d.get("brand") or Brand.objects.get_or_create(name=d["new_brand"].strip())[0]
    series=d.get("series")
    if d.get("new_series"): series=Series.objects.get_or_create(brand=brand,name=d["new_series"].strip())[0]
    if series and series.brand_id!=brand.id: form.add_error("series","Series must belong to the selected brand."); return None
    product=Product.objects.create(brand=brand,series=series,product_type=d["product_type"],name=d["name"],shade_code=d["shade_code"],shade_name=d["shade_name"],finish=d["finish"],description=d["description"])
    item=InventoryItem(product=product,status=d["status"],image=d.get("image"),open_date=d["open_date"],expiration_date=d["expiration_date"],pao_months=d["pao_months"],rating=d["rating"],review=d["review"],pros=d["pros"],cons=d["cons"],repurchase={"yes":True,"no":False}.get(d["repurchase"]),notes=d["notes"]); item.save()
    amt=d["original_amount"]; currency=d["currency"]; rate,rate_date,source=historical_usd_rate(currency,d["purchase_date"])
    if rate is None:
        if d.get("usd_amount") is None:
            item.delete(); product.delete(); form.add_error("usd_amount","Historical rate unavailable. Enter the USD amount to continue."); return None
        rate=d["usd_amount"]/amt if amt else Decimal("1"); rate_date=None; source="Manual USD amount"; usd=d["usd_amount"]
    else: usd=usd_value(amt,rate)
    Purchase.objects.create(item=item,date=d["purchase_date"],original_amount=amt,currency=currency,exchange_rate=rate,rate_date=rate_date,rate_source=source,usd_amount=usd,location=d["location"],notes=d["purchase_notes"])
    return item

@login_required
def product_add(request):
    form=ProductForm(request.POST or None,request.FILES or None)
    if request.method=="POST" and form.is_valid():
        item=_save_new_item(form)
        if item: messages.success(request,"Product added successfully."); return redirect("product_detail",pk=item.pk)
    return render(request,"archive/product_form.html",{"form":form,"title":"Add a product"})

@login_required
def product_edit(request,pk):
    item=get_object_or_404(InventoryItem.objects.select_related("product__brand","product__series","product__product_type__category","purchase"),pk=pk,archived=False)
    if request.method=="POST":
        form=ProductForm(request.POST,request.FILES)
        if form.is_valid():
            d=form.cleaned_data; p=item.product; purchase=item.purchase
            purchase_changed=(purchase.date!=d["purchase_date"] or purchase.original_amount!=d["original_amount"] or purchase.currency!=d["currency"])
            new_rate=new_rate_date=new_source=new_usd=None
            if purchase_changed:
                new_rate,new_rate_date,new_source=historical_usd_rate(d["currency"],d["purchase_date"])
                if new_rate is not None: new_usd=usd_value(d["original_amount"],new_rate)
                elif d.get("usd_amount") is not None: new_usd=d["usd_amount"]; new_rate=new_usd/d["original_amount"] if d["original_amount"] else Decimal("1"); new_source="Manual USD amount"
                else: form.add_error("usd_amount","Historical rate unavailable. Enter the USD amount to save these purchase changes."); return render(request,"archive/product_form.html",{"form":form,"title":"Edit product","editing":True})
            p.brand=d.get("brand") or Brand.objects.get_or_create(name=d["new_brand"].strip())[0]; p.series=d.get("series")
            if d.get("new_series"): p.series=Series.objects.get_or_create(brand=p.brand,name=d["new_series"].strip())[0]
            if p.series and p.series.brand_id!=p.brand_id: form.add_error("series","Series must belong to the selected brand."); return render(request,"archive/product_form.html",{"form":form,"title":"Edit product","editing":True})
            p.product_type=d["product_type"]; p.name=d["name"]; p.shade_code=d["shade_code"]; p.shade_name=d["shade_name"]; p.finish=d["finish"]; p.description=d["description"]; p.save()
            item.status=d["status"]; item.open_date=d["open_date"]; item.expiration_date=d["expiration_date"]; item.pao_months=d["pao_months"]; item.rating=d["rating"]; item.review=d["review"]; item.pros=d["pros"]; item.cons=d["cons"]; item.repurchase={"yes":True,"no":False}.get(d["repurchase"]); item.notes=d["notes"]
            if d.get("image"): item.image=d["image"]
            item.save(); purchase.date=d["purchase_date"]; purchase.original_amount=d["original_amount"]; purchase.currency=d["currency"]; purchase.location=d["location"]; purchase.notes=d["purchase_notes"]
            if purchase_changed: purchase.exchange_rate=new_rate; purchase.rate_date=new_rate_date; purchase.rate_source=new_source; purchase.usd_amount=new_usd
            purchase.save(); messages.success(request,"Product updated."); return redirect("product_detail",pk=pk)
    else:
        p=item.product; x=item.purchase
        form=ProductForm(initial={"category":p.product_type.category,"product_type":p.product_type,"brand":p.brand,"series":p.series,"name":p.name,"shade_code":p.shade_code,"shade_name":p.shade_name,"finish":p.finish,"description":p.description,"status":item.status,"open_date":item.open_date,"expiration_date":item.expiration_date,"pao_months":item.pao_months,"rating":item.rating,"review":item.review,"pros":item.pros,"cons":item.cons,"repurchase":"yes" if item.repurchase is True else "no" if item.repurchase is False else "","notes":item.notes,"purchase_date":x.date,"original_amount":x.original_amount,"currency":x.currency,"usd_amount":x.usd_amount,"location":x.location,"purchase_notes":x.notes})
    return render(request,"archive/product_form.html",{"form":form,"title":"Edit product","editing":True})

@login_required
def product_detail(request,pk):
    item=get_object_or_404(InventoryItem.objects.select_related("product__brand","product__series","product__product_type__category","purchase"),pk=pk,archived=False)
    return render(request,"archive/product_detail.html",{"item":item,"records":item.usage_records.all(),"other_items":InventoryItem.objects.filter(product=item.product,archived=False).exclude(pk=item.pk).select_related("purchase"),"usage_form":UsageForm(initial={"date":timezone.localdate(),"count":1})})

@login_required
def product_add_unit(request,pk):
    reference=get_object_or_404(InventoryItem.objects.select_related("product__brand","product"),pk=pk,archived=False); form=PurchaseForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        d=form.cleaned_data; amount=d["original_amount"]; rate,rate_date,source=historical_usd_rate(d["currency"],d["purchase_date"])
        if rate is None and d["usd_amount"] is None: form.add_error("usd_amount","Historical rate unavailable. Enter the USD amount to continue.")
        else:
            if rate is None: rate=d["usd_amount"]/amount if amount else Decimal("1"); usd=d["usd_amount"]; source="Manual USD amount"
            else: usd=usd_value(amount,rate)
            with transaction.atomic():
                item=InventoryItem.objects.create(product=reference.product,status=d["status"])
                Purchase.objects.create(item=item,date=d["purchase_date"],original_amount=amount,currency=d["currency"],exchange_rate=rate,rate_date=rate_date,rate_source=source,usd_amount=usd,location=d["location"])
            messages.success(request,"Another unit was added to your collection."); return redirect("product_detail",pk=item.pk)
    return render(request,"archive/purchase_form.html",{"form":form,"reference":reference,"unit_mode":True})

@login_required
def product_archive(request,pk):
    item=get_object_or_404(InventoryItem,pk=pk)
    if request.method=="POST": item.archived=True; item.save(update_fields=["archived"]); messages.success(request,"Product archived. Purchase and usage history are preserved.")
    return redirect("collection")

@login_required
def usage_add(request,pk):
    item=get_object_or_404(InventoryItem,pk=pk,archived=False); form=UsageForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): record=form.save(commit=False); record.item=item; record.save(); messages.success(request,"Usage recorded."); return redirect("product_detail",pk=pk)
    return render(request,"archive/usage_form.html",{"form":form,"item":item})

@login_required
def usage_edit(request,pk):
    record=get_object_or_404(UsageRecord,pk=pk); form=UsageForm(request.POST or None,instance=record)
    if request.method=="POST" and form.is_valid(): form.save(); messages.success(request,"Usage updated."); return redirect("product_detail",pk=record.item_id)
    return render(request,"archive/usage_form.html",{"form":form,"item":record.item,"editing":True})

@login_required
def usage_delete(request,pk):
    record=get_object_or_404(UsageRecord,pk=pk); item_id=record.item_id
    if request.method=="POST": record.delete(); messages.success(request,"Usage record removed.")
    return redirect("product_detail",pk=item_id)

@login_required
def statistics(request):
    year=int(request.GET.get("year",timezone.localdate().year)); rows=Purchase.objects.filter(date__year=year).values("date__month").annotate(total=Sum("usd_amount")); mm={r["date__month"]:r["total"] for r in rows}
    max_value=max((Decimal(v) for v in mm.values()),default=Decimal("0"))
    chart=[{"label":month_name[m],"value":money(mm.get(m)),"height":int(150*Decimal(mm.get(m,0))/max_value) if max_value else 2} for m in range(1,13)]
    return render(request,"archive/statistics.html",{"year":year,"month_values":chart,"brand_spend":Purchase.objects.values("item__product__brand__name").annotate(total=Sum("usd_amount")).order_by("-total")[:12],"category_spend":Purchase.objects.values("item__product__product_type__category__name").annotate(total=Sum("usd_amount")).order_by("-total"),"most_used":InventoryItem.objects.annotate(n=Sum("usage_records__count")).filter(n__gt=0).order_by("-n")[:8],"items_count":InventoryItem.objects.filter(archived=False).count(),"all_uses":UsageRecord.objects.aggregate(n=Sum("count"))["n"] or 0})

@login_required
def wishlist(request):
    form=WishlistForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): form.save(); messages.success(request,"Wish added."); return redirect("wishlist")
    items=WishlistItem.objects.filter(purchased=False)
    if request.GET.get("brand"): items=items.filter(brand__icontains=request.GET["brand"])
    if request.GET.get("priority"): items=items.filter(priority=request.GET["priority"])
    return render(request,"archive/wishlist.html",{"form":form,"items":items.order_by("priority","-added_at")})

@login_required
def wishlist_edit(request,pk):
    item=get_object_or_404(WishlistItem,pk=pk,purchased=False); form=WishlistForm(request.POST or None,instance=item)
    if request.method=="POST" and form.is_valid(): form.save(); messages.success(request,"Wish updated."); return redirect("wishlist")
    return render(request,"archive/wishlist_form.html",{"form":form,"item":item})

@login_required
def wishlist_delete(request,pk):
    item=get_object_or_404(WishlistItem,pk=pk)
    if request.method=="POST": item.delete(); messages.success(request,"Wish removed.")
    return redirect("wishlist")

@login_required
def wishlist_purchase(request,pk):
    wish=get_object_or_404(WishlistItem,pk=pk,purchased=False); form=PurchaseForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        d=form.cleaned_data; amount=d["original_amount"]; rate,rate_date,source=historical_usd_rate(d["currency"],d["purchase_date"])
        if rate is None and d["usd_amount"] is None: form.add_error("usd_amount","Historical rate unavailable. Enter USD amount.")
        else:
            if rate is None: rate=d["usd_amount"]/amount if amount else Decimal("1"); usd=d["usd_amount"]; source="Manual USD amount"
            else: usd=usd_value(amount,rate)
            with transaction.atomic():
                brand=Brand.objects.filter(name__iexact=wish.brand).first() or Brand.objects.create(name=wish.brand or "Unspecified"); category,_=Category.objects.get_or_create(name="Other"); ptype,_=ProductType.objects.get_or_create(category=category,name="Personal care"); series=Series.objects.filter(brand=brand,name=wish.series).first() if wish.series else None
                product=Product.objects.create(brand=brand,series=series,product_type=ptype,name=wish.name,shade_name=wish.shade); item=InventoryItem.objects.create(product=product,status=d["status"])
                Purchase.objects.create(item=item,date=d["purchase_date"],original_amount=amount,currency=d["currency"],exchange_rate=rate,rate_date=rate_date,rate_source=source,usd_amount=usd,location=d["location"]); wish.purchased=True; wish.purchased_item=item; wish.save()
            messages.success(request,"Wishlist item purchased and added to your collection."); return redirect("product_detail",pk=item.pk)
    return render(request,"archive/purchase_form.html",{"form":form,"wish":wish})

@login_required
def account_settings(request):
    settings_obj,_=UserSettings.objects.get_or_create(user=request.user); password_form=PasswordChangeForm(request.user,request.POST if request.method=="POST" and "old_password" in request.POST else None)
    if request.method=="POST" and "expiry_days" in request.POST:
        try: settings_obj.expiry_days=max(1,min(int(request.POST["expiry_days"]),365)); settings_obj.save(); messages.success(request,"Settings saved.")
        except ValueError: messages.error(request,"Enter a valid number of days.")
    if request.method=="POST" and "old_password" in request.POST and password_form.is_valid(): user=password_form.save(); update_session_auth_hash(request,user); messages.success(request,"Password changed."); return redirect("settings")
    return render(request,"archive/settings.html",{"settings_obj":settings_obj,"password_form":password_form})

@login_required
def export_csv(request,kind):
    response=HttpResponse(content_type="text/csv; charset=utf-8"); response.write("\ufeff"); response["Content-Disposition"]=f'attachment; filename="beauty-archive-{kind}.csv"'; w=csv.writer(response)
    if kind=="products":
        w.writerow(["brand","product","shade","category","type","status","purchase_date","usd_amount","uses","usage_days"])
        for i in InventoryItem.objects.select_related("product__brand","product__product_type__category","purchase"): w.writerow([i.product.brand.name,i.product.name,i.product.shade_code,i.product.product_type.category.name,i.product.product_type.name,i.status,i.purchase.date,i.purchase.usd_amount,i.total_uses,i.usage_days])
    elif kind=="purchases":
        w.writerow(["date","brand","product","original_amount","currency","exchange_rate","usd_amount","rate_source"])
        for p in Purchase.objects.select_related("item__product__brand","item__product"): w.writerow([p.date,p.item.product.brand,p.item.product.name,p.original_amount,p.currency,p.exchange_rate,p.usd_amount,p.rate_source])
    elif kind=="usage":
        w.writerow(["date","brand","product","count","notes"])
        for u in UsageRecord.objects.select_related("item__product__brand","item__product"): w.writerow([u.date,u.item.product.brand,u.item.product.name,u.count,u.notes])
    elif kind=="spending":
        w.writerow(["year","month","usd_total"])
        for r in Purchase.objects.values("date__year","date__month").annotate(total=Sum("usd_amount")).order_by("date__year","date__month"): w.writerow([r["date__year"],r["date__month"],r["total"]])
    else: return HttpResponse(status=404)
    return response

@login_required
def export_json(request):
    data={"products":[],"wishlist":list(WishlistItem.objects.values()),"settings":list(UserSettings.objects.filter(user=request.user).values())}
    for i in InventoryItem.objects.select_related("product__brand","product__series","product__product_type__category","purchase").prefetch_related("usage_records"):
        data["products"].append({"brand":i.product.brand.name,"series":i.product.series.name if i.product.series else None,"category":i.product.product_type.category.name,"type":i.product.product_type.name,"name":i.product.name,"shade_code":i.product.shade_code,"shade_name":i.product.shade_name,"finish":i.product.finish,"description":i.product.description,"item":{"status":i.status,"image_path":i.image.name if i.image else None,"open_date":str(i.open_date or ""),"expiration_date":str(i.expiration_date or ""),"pao_months":i.pao_months,"rating":i.rating,"review":i.review,"pros":i.pros,"cons":i.cons,"repurchase":i.repurchase,"notes":i.notes,"archived":i.archived},"purchase":{"date":str(i.purchase.date),"amount":str(i.purchase.original_amount),"currency":i.purchase.currency,"exchange_rate":str(i.purchase.exchange_rate),"rate_date":str(i.purchase.rate_date or ""),"rate_source":i.purchase.rate_source,"usd_amount":str(i.purchase.usd_amount),"location":i.purchase.location,"notes":i.purchase.notes},"usage":[{"date":str(u.date),"count":u.count,"notes":u.notes} for u in i.usage_records.all()]})
    response=HttpResponse(json.dumps(data,ensure_ascii=False,default=str,indent=2),content_type="application/json"); response["Content-Disposition"]='attachment; filename="beauty-archive-backup.json"'; return response

@login_required
def exchange_quote(request):
    currency=request.GET.get("currency","USD"); raw_date=request.GET.get("date",""); amount=request.GET.get("amount","0")
    try:
        from datetime import date as date_type
        when=date_type.fromisoformat(raw_date); value=Decimal(amount)
        rate,rate_date,source=historical_usd_rate(currency,when)
        if rate is None: return JsonResponse({"available":False,"message":"Historical rate unavailable. Enter the USD amount manually."})
        return JsonResponse({"available":True,"rate":str(rate),"rate_date":str(rate_date),"source":source,"usd_amount":str(usd_value(value,rate))})
    except (ValueError, TypeError): return JsonResponse({"available":False,"message":"Enter a valid purchase date and amount."},status=400)

@login_required
def private_media(request,path):
    try: file=default_storage.open(path,"rb")
    except (FileNotFoundError,OSError): raise Http404
    response=FileResponse(file,content_type=mimetypes.guess_type(path)[0] or "application/octet-stream")
    response["Cache-Control"]="private, no-store"
    return response
