# Generated by Django 3.1.2 on 2020-10-02 14:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0004_auto_20201002_0819'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketmessage',
            name='email_message_id',
            field=models.TextField(blank=True, null=True),
        ),
    ]