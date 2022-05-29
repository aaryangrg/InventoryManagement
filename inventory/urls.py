from django.contrib import admin
from django.urls import path, include
from .views import ItemDetailView, ItemCreateView, ItemUpdateView, ItemDeleteView
from . import views
urlpatterns = [
    path('home/', views.inventory_home, name='inventory-home'),
    # the Generic View automatically handles retreiving the object from the database etc
    path('<int:pk>/', ItemDetailView.as_view(), name='item-details'),
    # This view creates the generic form and writes the object to the database + redirectes where we want to go from there
    path('new-item/', ItemCreateView.as_view(), name='item-create'),
    path('<int:pk>/update', ItemUpdateView.as_view(), name='item-update'),
    path('<int:pk>/delete', ItemDeleteView.as_view(), name='item-delete'),
    path('<int:pk>/issue', views.issue_item, name='item-issue'),
    path('<int:pk>/return', views.return_item, name='item-return'),
    path('<username>/profile', views.user_profile, name='user-profile'),
    path('file-upload/', views.file_parse, name='file-upload'),
    path('download/<filename>',
         views.download_inventory, name='download-inventory'),
]
