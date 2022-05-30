from faulthandler import disable
from ftplib import all_errors
from hashlib import new
import re
from typing import final
from unicodedata import category
from django.shortcuts import redirect, render, HttpResponse
from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied
from requests import request
from .models import Inventory, Orders
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
import logging
from django.contrib.auth.models import User
from django.core.mail import EmailMessage, send_mail
from datetime import datetime
import mimetypes
import os
import csv

formatter = logging.Formatter('%(asctime)s %(message)s')


class ParseInventory(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        if message.split(" ")[-1] == "Inventory":
            return True
        else:
            return False


class ParseTransactions(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        message_words = message.split(" ")
        for word in message_words:
            if word.lower() in ["ordered", "returned"]:
                return True
        return False


def setup_logger(name, log_file, level=logging.INFO):
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


# INVENTORY LOG
inventory_log = setup_logger('inventory_logger', 'Inventory.log')
inventory_log.addFilter(ParseInventory())

# ORDERS LOG
orders_log = setup_logger('orders_log', 'Orders.log')
orders_log.addFilter(ParseTransactions())


def filter_by_words(words, objects):
    final_set = set()
    for word in words:
        for item in objects:
            if item.item_name.lower().find(word) >= 0:
                final_set.add(item)
    if len(final_set) != 0:
        return list(final_set)

    return objects


def inventory_home(request):
    allowed_user = False
    search_category = ""
    displayed_objects = Inventory.objects.all()
    for social_acc in SocialAccount.objects.all():
        if(str(social_acc) == str(request.user)):
            break
    else:
        allowed_user = True
    if request.method == "POST":
        search_category = request.POST.get('search_category')
        search_text = request.POST.get('item_name')
        search_words = search_text.strip().lower().split(' ')
        if(search_category != "All"):
            displayed_objects = Inventory.objects.all().filter(category=search_category)
        else:
            displayed_objects = Inventory.objects.all()
        displayed_objects = filter_by_words(search_words, displayed_objects)
    context = {
        'items': displayed_objects,
        'download_allowed': allowed_user,
        'current_category': search_category
    }
    return render(request, 'inventory/home.html', context)


# add restriction on who can issue


def issue_item(request, pk):
    # Check if user is not moderator -> Else throw Error
    # if not len(SocialAccount.objects.all().filter(user=request.user)):
    #     raise PermissionDenied()
    # Check if the user owns the item -> If yes throw error(issuer cannot borrow)
    if Inventory.objects.all().filter(id=pk)[0].owner == request.user:
        raise PermissionDenied()
    context = {
        'object': Inventory.objects.get(id=pk)
    }
    if request.method == "POST":
        item = Inventory.objects.get(id=pk)
        quantity_issued = request.POST.get('quantity_issued')
        if int(quantity_issued) > item.stock:
            messages.add_message(
                request, messages.ERROR, f'You can issue upto {item.stock} items', extra_tags="ISSUE_ERROR")
            return render(request, "inventory/issue.html", context)
        else:
            item.stock = item.stock - int(quantity_issued)
            item.save()
            orders_log.error(
                f'{request.user} ordered {int(quantity_issued)} X {item.item_name}')
            send_mail('Issued Items', f'Your ordered {int(quantity_issued)} X {item.item_name}. Hope you enjoy your purchase!',
                      'purchases.inventorymanagement@gmail.com', [request.user.email], fail_silently=False)
            try:
                prev_order = Orders.objects.get(
                    item_id=str(item.id), order_placed_by=request.user)
                prev_order.item_quantity += int(quantity_issued)
                prev_order.save()
            except Exception as e:
                new_order = Orders(item_id=item.id, item_name=item.item_name, item_quantity=int(
                    quantity_issued), order_placed_by=request.user, item_owner=item.owner)
                new_order.save()
            return redirect('inventory-home')
    else:
        return render(request, "inventory/issue.html", context)


def return_item(request, pk):
    # Check if user is moderator -> Throw error
    if not len(SocialAccount.objects.all().filter(user=request.user)):
        raise PermissionDenied()
    item = Inventory.objects.get(id=pk)
    try:
        prev_order = Orders.objects.get(
            item_id=str(item.id), order_placed_by=request.user)
        context = {
            'object': prev_order,
            'item': item
        }
        if request.method == "POST":
            quantity_returned = request.POST.get('quantity_returned')
            if int(quantity_returned) > prev_order.item_quantity:
                messages.add_message(
                    request, messages.ERROR, f'You can return upto {prev_order.item_quantity} items', extra_tags="RETURN_ERROR")
                return render(request, "inventory/return.html", context)
            else:
                item.stock = item.stock + int(quantity_returned)
                item.save()
                orders_log.info(
                    f'{request.user} returned {int(quantity_returned)} X {item.item_name}')
                prev_order.item_quantity = prev_order.item_quantity - \
                    int(quantity_returned)
                if prev_order.item_quantity == 0:
                    prev_order.delete()
                else:
                    prev_order.save()
                send_mail('Returned Items', f'You returned {int(quantity_returned)} X {item.item_name}. You have {prev_order.item_quantity} Left!',
                          'purchases.inventorymanagement@gmail.com', [request.user.email], fail_silently=False)
                return redirect('inventory-home')
        else:
            return render(request, "inventory/return.html", context)
    except Exception as e:
        return render(request, "inventory/return.html", {'object': None, 'item': item})


# The view showing item details


def user_profile(request, username):
    context = {
        "username": username,
        "user_orders": Orders.objects.filter(order_placed_by=username)
    }
    if(request.user.is_authenticated):
        return render(request, 'inventory/profile.html', context)


def file_parse(request):
    if len(SocialAccount.objects.all().filter(user=request.user)):
        raise PermissionDenied()
    # make sure some file is uploaded
    if request.method == 'POST' and request.FILES:
        uploaded_items = request.FILES["data_sheet"].read().decode(
            'utf-8').split("\n")
        item_reader = csv.DictReader(uploaded_items)
        for item in item_reader:
            new_item = Inventory(item_name=item['item_name'], stock=item['stock'],
                                 category=item['category'], description=item['description'], owner=request.user, date_posted=datetime.now())
            new_item.save()
        return redirect('inventory-home')
    else:
        return render(request, 'inventory/file_upload.html')

# add restriction on only mods being able to reach this endpoint


def download_inventory(request, filename):
    # If user is not moderator -> Raise exception
    if len(SocialAccount.objects.all().filter(user=request.user)):
        raise PermissionDenied()
    if filename != '':
        # Define Django project base directory
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Define the full file path
        filepath = BASE_DIR + f'/inventory/files/{filename}'
        try:
            HEADER_LIST = ['item_name', 'stock', 'category', 'owner',
                           'description', 'date_posted']
            with open(f'{filepath}', 'w') as inventory_file:
                inventory_writer = csv.DictWriter(inventory_file, delimiter=',',
                                                  fieldnames=HEADER_LIST)
                inventory_writer.writeheader()
                inventory_items = Inventory.objects.all()
                for item in inventory_items:
                    inventory_writer.writerow(
                        {'item_name': item.item_name, 'stock': item.stock, 'category': item.category, 'description': item.description, 'owner': item.owner, 'date_posted': item.date_posted})
            inventory_file.close()
            # opening in binary prevents errors in the case of non-ascii characters
            path = open(filepath, 'rb')
            # Set the mime type
            mime_type, _ = mimetypes.guess_type(filepath)
            # Set the return value of the HttpResponse
            response = HttpResponse(path, content_type=mime_type)
            # Set the HTTP header for sending to browser
            response['Content-Disposition'] = f"attachment; filename={filename}"
            # Return the response value
            return response
        except:
            pass
    else:
        return render(request, 'inventory/download_failed.html')


class ItemDetailView(DetailView):
    model = Inventory
    template_name = 'inventory/details.html'


# Creating new Inventory Items -> Moderators (non-email login)


class ItemCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Inventory
    fields = ['item_name', 'stock', 'category', 'description']

    # Owner is the current logged in User
    def form_valid(self, form):
        form.instance.owner = self.request.user
        quantity = self.request.POST["stock"]
        name = self.request.POST["item_name"]
        inventory_log.info(
            f"{self.request.user} added {quantity} X {name} to Inventory")
        return super().form_valid(form)

    def test_func(self):
        if not len(SocialAccount.objects.all().filter(user=self.request.user)):
            return True
        else:
            return False


# Updating Inventory Items -> Moderators (non-email login) + Item Owner


class ItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Inventory
    template_name = 'inventory/inventory_item_update.html'
    fields = ['item_name', 'stock', 'category', 'description']

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def test_func(self):
        # Is moderator?
        if not len(SocialAccount.objects.all().filter(user=self.request.user)):
            item = self.get_object()
            # Is owner of the original item?
            if self.request.user == item.owner:
                return True
            else:
                return False
        else:
            return False


# Deleting Inventory Items -> Moderators (non-email login) + Item Owner


class ItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Inventory
    success_url = '/inventory/home'

    def test_func(self):
        # See if i can make this system more efficient?
        if not len(SocialAccount.objects.all().filter(user=self.request.user)):
            item = self.get_object()
            # Is owner of the original item?
            if self.request.user == item.owner:
                return True
            else:
                return False
        else:
            return False
