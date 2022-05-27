from django.contrib import admin

from inventory.models import Inventory, Orders

# Register your models here.
admin.site.register(Inventory)
admin.site.register(Orders)
