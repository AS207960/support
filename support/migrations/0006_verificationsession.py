# Generated by Django 5.0.2 on 2024-02-27 18:11

import as207960_utils.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("support", "0005_customer_is_agent_alter_customer_user"),
    ]

    operations = [
        migrations.CreateModel(
            name="VerificationSession",
            fields=[
                (
                    "id",
                    as207960_utils.models.TypedUUIDField(
                        data_type="support_verificationsession",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("stripe_session", models.CharField(max_length=255)),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="support.ticket"
                    ),
                ),
            ],
        ),
    ]
