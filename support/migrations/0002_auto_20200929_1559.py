# Generated by Django 3.1.1 on 2020-09-29 15:59

from django.db import migrations, models
import support.models


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='ref',
            field=models.CharField(db_index=True, default=support.models.make_ticket_ref, max_length=64, unique=False),
        ),
    ]
