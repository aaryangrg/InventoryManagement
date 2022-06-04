from unicodedata import category
from black import Mode
from django.shortcuts import redirect, render, HttpResponse
from django.http import HttpResponseForbidden, JsonResponse
from django.core.exceptions import PermissionDenied
from requests import request
from .models import Inventory, Orders, Category, Customer, Moderator
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
import logging
from django.contrib.auth.models import User
from django.core.mail import send_mail
from datetime import datetime
import mimetypes
import os
import csv
from django.contrib.auth.decorators import login_required
from functools import wraps

formatter = logging.Formatter('%(asctime)s %(message)s')


# SECONDARY PERMISSIONS : (class + functional views)
class UserIsModerator(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return len(Moderator.objects.filter(user=self.request.user)) != 0

    def handle_no_permission(self):
        return HttpResponseForbidden("<h1>Only moderators can access this page!</h1>")


def user_is_owner(item, user):
    if(item.owner.user == user):
        return True
    else:
        return False


def user_is_moderator(view):
    @wraps(view)
    def _view(request, *args, **kwargs):
        if not Moderator.objects.filter(user=request.user).first():
            return HttpResponseForbidden("<h1> Only moderators can access this page! </h1>")
            # raise PermissionDenied()
        return view(request, *args, **kwargs)
    return _view


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


# check if any search word is in the item name.
def filter_by_words(words, objects):
    final_set = set()
    for word in words:
        for item in objects:
            if item.item_name.lower().find(word) >= 0:
                final_set.add(item)
    if len(final_set) != 0:
        return list(final_set)

    return objects


@login_required(login_url='/accounts/login/')
def inventory_home(request):
    allowed_user = False
    search_category = ""
    displayed_objects = Inventory.objects.all()
    # To check if the user can download the inventory as a csv
    if len(Moderator.objects.filter(user=request.user)) != 0:
        allowed_user = True
    if request.method == "POST":
        search_category = request.POST.get('search_category')
        search_text = request.POST.get('item_name')
        search_words = search_text.strip().lower().split(' ')
        if(search_category != "All"):
            displayed_objects = Inventory.objects.all().filter(
                category=Category.objects.filter(category_name=search_category).first())
        else:
            displayed_objects = Inventory.objects.all()
        displayed_objects = filter_by_words(search_words, displayed_objects)
    context = {
        'items': displayed_objects,
        'download_allowed': allowed_user,
        'current_category': search_category
    }
    return render(request, 'inventory/home.html', context)


@login_required(login_url='/accounts/login/')
def issue_item(request, pk):
    # Owner cannot issue their own item
    if(user_is_owner(Inventory.objects.filter(id=pk).first(), request.user)):
        return HttpResponse("<h1>You cannot issue your own item!</h1>")
        # raise PermissionDenied()
    context = {
        'object': Inventory.objects.get(id=pk),
        'failed_message': ""
    }
    if request.method == "POST":
        item = Inventory.objects.get(id=pk)
        quantity_issued = request.POST.get('quantity_issued')
        if int(quantity_issued) > item.stock:
            context["failed_message"] = f"You can issue upto {item.stock} items"
            # return user to the same issue page + correct input suggestion
            return render(request, "inventory/issue.html", context)
        else:
            item.stock = item.stock - int(quantity_issued)
            item.save()
            orders_log.error(
                f'{request.user} ordered {int(quantity_issued)} X {item.item_name}')
            send_mail('Issued Items', f'You ordered {int(quantity_issued)} X {item.item_name}. Hope you enjoy your purchase!',
                      'purchases.inventorymanagement@gmail.com', [request.user.email], fail_silently=False)
            prev_order = Orders.objects.all().filter(item=item,
                                                     order_placed_by=Customer.objects.filter(user=request.user).first()).first()
            if prev_order:
                prev_order.item_quantity += int(quantity_issued)
                prev_order.save()
            else:
                # Updating number of customer orders (increases by 1)
                curr_customer = Customer.objects.filter(
                    user=request.user).first()
                curr_customer.number_of_orders += 1
                curr_customer.save()
                new_order = Orders(item=item, item_quantity=int(
                    quantity_issued), order_placed_by=curr_customer)
                new_order.save()
            return redirect('inventory-home')
    else:
        return render(request, "inventory/issue.html", context)


@login_required(login_url='/accounts/login/')
def return_item(request, pk):
    # Owner cannot return their own item
    if(user_is_owner(Inventory.objects.filter(id=pk).first(), request.user)):
        raise PermissionDenied()
    item = Inventory.objects.get(id=pk)
    prev_order = Orders.objects.filter(
        item=item, order_placed_by=Customer.objects.filter(user=request.user).first()).first()
    context = {
        'object': prev_order,
        'item': item,
        'failed_message': ""
    }
    if request.method == "POST" and prev_order:
        quantity_returned = request.POST.get('quantity_returned')
        if int(quantity_returned) > prev_order.item_quantity:
            context["failed_message"] = f"You can return upto {prev_order.item_quantity} items"
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
                # Updating number of customer orders (decreases by 1)
                curr_customer = Customer.objects.filter(
                    user=request.user).first()
                curr_customer.number_of_orders -= 1
                curr_customer.save()
            else:
                prev_order.save()
            orders_log.error(
                f'{request.user} returned {int(quantity_returned)} X {item.item_name}')
            send_mail('Returned Items', f'You returned {int(quantity_returned)} X {item.item_name}. You have {prev_order.item_quantity} Left!',
                      'purchases.inventorymanagement@gmail.com', [request.user.email], fail_silently=False)
            return redirect('inventory-home')
    else:
        return render(request, "inventory/return.html", context)


@login_required(login_url='/accounts/login/')
def user_profile(request, username):
    context = {
        "username": username,
        "user_orders": Orders.objects.filter(order_placed_by=Customer.objects.filter(user=request.user).first())
    }
    if(request.user.is_authenticated and username == request.user.username):
        return render(request, 'inventory/profile.html', context)
    else:
        return HttpResponseForbidden("<h1>That's not your account!<h1>")


@login_required(login_url='/accounts/login/')
@user_is_moderator
def file_parse(request):
    # make sure some file is uploaded (i.e. no empty upload submission)
    if request.method == 'POST' and request.FILES:
        uploaded_items = request.FILES["data_sheet"].read().decode(
            'utf-8').split("\n")
        item_reader = csv.DictReader(uploaded_items)
        for item in item_reader:
            new_item = Inventory(item_name=item['item_name'], stock=item['stock'],
                                 category=Category.objects.filter(category_name=item['category']).first(), description=item['description'], owner=Moderator.objects.filter(user=request.user).first(), date_posted=datetime.now())
            inventory_log.info(
                f"{request.user} added {new_item.stock} X {new_item.item_name} to Inventory")
            new_item.save()
        return redirect('inventory-home')
    else:
        return render(request, 'inventory/file_upload.html')


@login_required(login_url='/accounts/login/')
@user_is_moderator
def download_inventory(request, filename):
    if filename != '':
        # Django project base dir
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # full path
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
            # opening in binary prevents errors in decoding non-ascii characters
            path = open(filepath, 'rb')
            # Set the mime type
            mime_type, _ = mimetypes.guess_type(filepath)
            response = HttpResponse(path, content_type=mime_type)
            # Set the HTTP header for sending to browser
            response['Content-Disposition'] = f"attachment; filename={filename}"
            # Return the response value
            return response
        except:
            pass
    else:
        return render(request, 'inventory/download_failed.html')


# Doesnt require login - all other stages have a login requirement (Similar to how you can view items on amazon without signing in)
class ItemDetailView(DetailView):
    model = Inventory
    template_name = 'inventory/details.html'


# Creating new Inventory Items -> Moderators (non-email login)
class ItemCreateView(UserIsModerator, CreateView):
    model = Inventory
    fields = ['item_name', 'stock', 'category', 'description']

    # Owner is the current logged in User
    def form_valid(self, form):
        form.instance.owner = Moderator.objects.filter(
            user=self.request.user).first()
        quantity = self.request.POST["stock"]
        name = self.request.POST["item_name"]
        inventory_log.info(
            f"{self.request.user} added {quantity} X {name} to Inventory")
        return super().form_valid(form)


class ItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Inventory
    template_name = 'inventory/inventory_item_update.html'
    fields = ['item_name', 'stock', 'category', 'description']

    def form_valid(self, form):
        form.instance.owner = Moderator.objects.filter(
            user=self.request.user).first()
        return super().form_valid(form)

    def test_func(self):
        item = self.get_object()
        return user_is_owner(item, self.request.user)


class ItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Inventory
    success_url = '/inventory/home'

    def test_func(self):
        item = self.get_object()
        return user_is_owner(item, self.request.user)
