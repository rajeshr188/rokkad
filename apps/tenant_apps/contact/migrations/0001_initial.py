# Generated by Django 5.0.1 on 2024-02-24 17:18

import django.db.models.deletion
import phonenumber_field.modelfields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Customer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("firstname", models.CharField(blank=True, max_length=255)),
                ("lastname", models.CharField(blank=True, max_length=255)),
                (
                    "gender",
                    models.CharField(
                        choices=[("M", "M"), ("F", "F"), ("N", "N")],
                        default="M",
                        max_length=1,
                    ),
                ),
                (
                    "religion",
                    models.CharField(
                        choices=[
                            ("Hindu", "Hindu"),
                            ("Muslim", "Muslim"),
                            ("Christian", "Christian"),
                            ("Atheist", "Atheist"),
                        ],
                        default="Hindu",
                        max_length=10,
                    ),
                ),
                (
                    "pic",
                    models.ImageField(
                        blank=True, null=True, upload_to="customer_pics/"
                    ),
                ),
                ("Address", models.TextField(blank=True, max_length=100)),
                (
                    "customer_type",
                    models.CharField(
                        choices=[
                            ("R", "Retail"),
                            ("W", "Wholesale"),
                            ("S", "Supplier"),
                        ],
                        default="R",
                        max_length=30,
                    ),
                ),
                (
                    "relatedas",
                    models.CharField(
                        choices=[
                            ("s", "S/o"),
                            ("d", "D/o"),
                            ("f", "F/o"),
                            ("c", "C/o"),
                            ("p", "P/o"),
                            ("h", "H/o"),
                            ("w", "W/o"),
                            ("o", "O/o"),
                        ],
                        default="s",
                        max_length=5,
                    ),
                ),
                ("relatedto", models.CharField(blank=True, max_length=30)),
                ("area", models.CharField(blank=True, max_length=50)),
                ("active", models.BooleanField(blank=True, default=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created", "name", "relatedto"),
                "unique_together": {("name", "relatedas", "relatedto")},
            },
        ),
        migrations.CreateModel(
            name="Contact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "contact_type",
                    models.CharField(
                        choices=[("H", "Home"), ("O", "Office"), ("M", "Mobile")],
                        default="M",
                        max_length=1,
                    ),
                ),
                (
                    "phone_number",
                    phonenumber_field.modelfields.PhoneNumberField(
                        max_length=128, region=None, unique=True
                    ),
                ),
                ("last_updated", models.DateTimeField(auto_now=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contactno",
                        to="contact.customer",
                    ),
                ),
            ],
            options={
                "ordering": ("-created",),
            },
        ),
        migrations.CreateModel(
            name="Address",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("area", models.CharField(default="ChinaAllapuram", max_length=30)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("doorno", models.CharField(max_length=30)),
                ("zipcode", models.CharField(default="632001", max_length=6)),
                ("last_updated", models.DateTimeField(auto_now=True)),
                ("street", models.TextField(max_length=100)),
                ("city", models.CharField(default="Vellore", max_length=30)),
                (
                    "Customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="address",
                        to="contact.customer",
                    ),
                ),
            ],
            options={
                "ordering": ("-created",),
            },
        ),
        migrations.CreateModel(
            name="Proof",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "proof_type",
                    models.CharField(
                        choices=[
                            ("AA", "AadharNo"),
                            ("DL", "Driving License"),
                            ("PN", "PanCard No"),
                        ],
                        default="AA",
                        max_length=2,
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("proof_no", models.CharField(max_length=30)),
                ("doc", models.FileField(upload_to="upload/files/proofs")),
                ("last_updated", models.DateTimeField(auto_now=True)),
                (
                    "Customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contact.customer",
                    ),
                ),
            ],
            options={
                "ordering": ("-created",),
            },
        ),
        migrations.CreateModel(
            name="CustomerRelationship",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "relationship",
                    models.CharField(
                        choices=[
                            ("s", "S/o"),
                            ("d", "D/o"),
                            ("f", "F/o"),
                            ("c", "C/o"),
                            ("p", "P/o"),
                            ("h", "H/o"),
                            ("w", "W/o"),
                            ("o", "O/o"),
                        ],
                        default="s",
                        max_length=2,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relationships",
                        to="contact.customer",
                    ),
                ),
                (
                    "related_customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relatedby",
                        to="contact.customer",
                    ),
                ),
            ],
            options={
                "unique_together": {("customer", "related_customer", "relationship")},
            },
        ),
    ]