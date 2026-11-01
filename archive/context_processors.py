from decimal import Decimal
from django.db.models import Sum
from .models import Purchase

def archive_summary(request):
    if not request.user.is_authenticated: return {"total_spent": "0.00"}
    total=Purchase.objects.aggregate(total=Sum("usd_amount"))["total"] or Decimal("0.00")
    return {"total_spent": total.quantize(Decimal("0.01"))}
