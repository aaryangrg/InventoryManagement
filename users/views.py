from django.shortcuts import render, redirect
from django.contrib import messages
from .form import UserRegisterForm


def register(request):
    if request.method == "POST":
        # if invalid we want to show the old data -> they can modify it
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f'Acount Created for {username}')
            return redirect('inventory-home')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})


def test(request):
    data = request.POST
    return render(request, 'users/test.html', {'data': data})
