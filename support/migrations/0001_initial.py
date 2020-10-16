# Generated by Django 3.1.1 on 2020-09-29 15:56

import as207960_utils.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255)),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('phone', phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None)),
                ('phone_ext', models.CharField(blank=True, max_length=64, null=True, verbose_name='Phone extension')),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', as207960_utils.models.TypedUUIDField(data_type='support_ticket', primary_key=True, serialize=False)),
                ('ref', models.CharField(db_index=True, max_length=64, null=True)),
                ('state', models.CharField(choices=[('O', 'Open'), ('C', 'Closed')], default='O', max_length=1)),
                ('source', models.CharField(choices=[('P', 'Phone'), ('W', 'Web'), ('E', 'Email'), ('O', 'Other')], default='O', max_length=1)),
                ('priority', models.CharField(choices=[('L', 'Low'), ('N', 'Normal')], default='N', max_length=1)),
                ('due_date', models.DateTimeField(blank=True, null=True)),
                ('subject', models.CharField(max_length=255)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='support.customer')),
            ],
        ),
        migrations.CreateModel(
            name='TicketMessage',
            fields=[
                ('id', as207960_utils.models.TypedUUIDField(data_type='support_ticketmessage', primary_key=True, serialize=False)),
                ('type', models.CharField(choices=[('C', 'Customer'), ('R', 'Response'), ('N', 'Note'), ('S', 'System')], max_length=1)),
                ('date', models.DateTimeField()),
                ('message', models.TextField()),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='support.ticket')),
            ],
        ),
        migrations.CreateModel(
            name='TicketMessageAttachment',
            fields=[
                ('id', as207960_utils.models.TypedUUIDField(data_type='support_ticketattachment', primary_key=True, serialize=False)),
                ('file_name', models.TextField(blank=True, null=True)),
                ('file', models.FileField(upload_to='')),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='support.ticketmessage')),
            ],
        ),
    ]