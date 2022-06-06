from hashlib import new
from inventory.models import Moderator, Inventory, Category
import csv
from datetime import datetime


def parse_inventory_csv(items, mod_user):
    prev_mod_items = Moderator.objects.filter(
        user=mod_user).first().uploaded_items.all()
    item_reader = csv.DictReader(items)
    for item in item_reader:
        previous_item = prev_mod_items.filter(item_name=item['item_name'], category=Category.objects.filter(
            category_name=item['category']).first(), description=item['description'])
        # if the item already exists --> update its stock to the new stock value
        if previous_item.exists():
            previous_item.first().stock = item["stock"]

        else:
            new_item = Inventory(item_name=item['item_name'], category=Category.objects.filter(
                category_name=item['category']).first(), description=item['description'], stock=item["stock"], owner=Moderator.objects.filter(user=mod_user).first(), date_posted=datetime.now())
            new_item.save()
        previous_item.first().save()
    pass
