# Generated by Django 4.0.4 on 2022-05-27 12:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_inventory_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='Orders',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_id', models.PositiveIntegerField()),
                ('item_name', models.CharField(max_length=50)),
                ('item_quantity', models.IntegerField()),
                ('order_time', models.DateTimeField(auto_now_add=True)),
                ('order_placed_by', models.CharField(max_length=100)),
                ('item_owner', models.CharField(max_length=100)),
            ],
        ),
        migrations.AlterField(
            model_name='inventory',
            name='description',
            field=models.TextField(default='This Item has no Description'),
        ),
    ]