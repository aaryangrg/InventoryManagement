# from msilib.schema import Property
from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import User
from django.urls import reverse
# Create your models here.


class Moderator(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # number_of_orders = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.user.username

    @property
    def number_of_orders(self):
        return Orders.objects.filter(order_placed_by=self, order_returned=False).count()


class Category(models.Model):
    CATEGORY_CHOICES = [
        ('General', 'General'),
        ('Sports', 'Sports'),
        ('Leisure', 'Leisure'),
        ('Decor', 'Decor'),
        ('School', 'School'),
        ('Kitchen', 'Kitchen'),
        ('Technology', 'Technology'),
    ]
    category_name = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, default="General")

    def __str__(self):
        return self.category_name


class Inventory(models.Model):
    item_name = models.CharField(max_length=50)
    description = models.TextField(default="This Item has no Description")
    stock = models.PositiveIntegerField()
    date_posted = models.DateTimeField(auto_now_add=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="category_items")
    owner = models.ForeignKey(
        Moderator, on_delete=models.CASCADE, related_name="uploaded_items")

    class Meta:
        unique_together = ('category', 'item_name', 'description', 'owner')

    def __str__(self):
        return self.item_name

    def __contains__(self, search_word):
        if self.item_name.lower().find(search_word) >= 0:
            return True
        else:
            return False

    def get_absolute_url(self):
        return reverse('item-details', kwargs={'pk': self.pk})

    @property
    def stock_left(self):
        return self.stock

    @property
    def stock_issued(self):
        if Orders.objects.filter(item=self):
            return Orders.objects.filter(item=self).aggregate(Sum("item_quantity"))["item_quantity__sum"]
        else:
            return 0

    @property
    def stock_total(self):
        if Orders.objects.filter(item=self):
            return self.stock + Orders.objects.filter(item=self).aggregate(Sum("item_quantity"))["item_quantity__sum"]
        else:
            return self.stock


class Orders(models.Model):
    item = models.ForeignKey(
        Inventory, on_delete=models.PROTECT, null=True)
    item_quantity = models.IntegerField()
    order_time = models.DateTimeField(auto_now_add=True)
    order_placed_by = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="orders")
    order_returned = models.BooleanField(default=False)

    def __str__(self):
        return self.order_placed_by.user.username + "-" + self.item.item_name
