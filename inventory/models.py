from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
# Create your models here.


class Inventory(models.Model):
    CATEGORY_CHOICES = [
        ('General', 'General'),
        ('Sports', 'Sports'),
        ('Leisure', 'Leisure'),
        ('Decor', 'Decor'),
        ('School', 'School'),
        ('Kitchen', 'Kitchen'),
        ('Technology', 'Technology'),
    ]
    item_name = models.CharField(max_length=50)
    description = models.TextField(default="This Item has no Description")
    stock = models.PositiveIntegerField()
    date_posted = models.DateTimeField(auto_now_add=True)
    category = models.TextField(choices=CATEGORY_CHOICES, default='General')
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('category', 'item_name', 'description', 'owner')

    def __str__(self):
        return self.item_name

    def get_absolute_url(self):
        return reverse('item-details', kwargs={'pk': self.pk})


class Orders(models.Model):
    item_id = models.PositiveIntegerField()
    item_name = models.CharField(max_length=50)
    item_quantity = models.IntegerField()
    order_time = models.DateTimeField(auto_now_add=True)
    order_placed_by = models.CharField(max_length=100)
    item_owner = models.CharField(max_length=100)

    def __str__(self):
        return self.order_placed_by
