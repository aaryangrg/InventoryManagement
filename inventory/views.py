from django.shortcuts import redirect, render
from requests import request
from .models import Inventory, Orders
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages


def inventory_home(request):
    context = {
        'items': Inventory.objects.all()
    }
    return render(request, 'inventory/home.html', context)

# add restriction on who can issue


def issue_item(request, pk):
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
            prev_order = Orders.objects.get(
                item_id=str(item.id), order_placed_by=request.user)
            if(prev_order):
                prev_order.item_quantity += int(quantity_issued)
                prev_order.save()
            else:
                new_order = Orders(item_id=item.id, item_name=item.item_name, item_quantity=int(
                    quantity_issued), order_placed_by=request.user, item_owner=item.owner)
                new_order.save()
            return redirect('inventory-home')
    else:
        return render(request, "inventory/issue.html", context)


def return_item(request, pk):
    item = Inventory.objects.get(id=pk)
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
            prev_order.item_quantity = prev_order.item_quantity - \
                int(quantity_returned)
            if prev_order.item_quantity == 0:
                prev_order.delete()
            else:
                prev_order.save()
            return redirect('inventory-home')
    else:
        return render(request, "inventory/return.html", context)


# The view showing item details


def user_profile(request, username):
    context = {
        "username": username,
        "user_orders": Orders.objects.filter(order_placed_by=username)
    }
    if(request.user.is_authenticated):
        return render(request, 'inventory/profile.html', context)


class ItemDetailView(DetailView):
    model = Inventory
    template_name = 'inventory/details.html'


# Creating new Inventory Items -> Moderators (non-email login)


class ItemCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Inventory
    fields = ['item_name', 'stock', 'description']

    # Owner is the current logged in User
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def test_func(self):
        for social_acc in SocialAccount.objects.all():
            if(str(social_acc) == str(self.request.user)):
                return False
        else:
            return True

# Updating Inventory Items -> Moderators (non-email login) + Item Owner


class ItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Inventory
    template_name = 'inventory/inventory_item_update.html'
    fields = ['item_name', 'stock', 'category', 'description']

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def test_func(self):
        # only allow update screen if the person is a moderator and also owns the item
        for social_acc in SocialAccount.objects.all():
            if(str(social_acc) == str(self.request.user)):
                return False
        # gets object we are trying to update
        item = self.get_object()
        if self.request.user == item.owner:
            return True
        else:
            return False

# Deleting Inventory Items -> Moderators (non-email login) + Item Owner


class ItemDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Inventory
    success_url = '/inventory/home'

    def test_func(self):
        # See if i can make this system more efficient?
        for social_acc in SocialAccount.objects.all():
            if(str(social_acc) == str(self.request.user)):
                return False
        item = self.get_object()
        if self.request.user == item.owner:
            return True
        else:
            return False
