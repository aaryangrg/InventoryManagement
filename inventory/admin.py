from django.contrib import admin

from inventory.models import Category, Customer, Inventory, Moderator, Orders

# Register your models here.
admin.site.register(Inventory)
admin.site.register(Orders)
admin.site.register(Moderator)
admin.site.register(Customer)
admin.site.register(Category)
