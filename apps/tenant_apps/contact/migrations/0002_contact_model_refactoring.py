# Generated migration for contact app model refactoring

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("contact", "0001_initial"),
    ]

    operations = [
        # Customer model: First remove the duplicate 'firstname' field, then rename 'name' to 'firstname'
        # Step 1: Remove the existing duplicate 'firstname' field
        # WARNING: This will delete any data in the old 'firstname' field!
        # If you need this data, create a data migration first to copy it to 'name'
        migrations.RemoveField(
            model_name="customer",
            name="firstname",
        ),
        # Step 2: Now rename 'name' to 'firstname'
        migrations.RenameField(
            model_name="customer",
            old_name="name",
            new_name="firstname",
        ),
        # Step 3: Update field definitions
        migrations.AlterField(
            model_name="customer",
            name="firstname",
            field=models.CharField(max_length=255, verbose_name="First Name"),
        ),
        migrations.AlterField(
            model_name="customer",
            name="lastname",
            field=models.CharField(
                max_length=255, blank=True, null=True, verbose_name="Last Name"
            ),
        ),
        # CustomerRelationship changes
        migrations.AddField(
            model_name="customerrelationship",
            name="created",
            field=models.DateTimeField(auto_now_add=True, editable=False, default=None),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="customerrelationship",
            name="relationship",
            field=models.CharField(
                max_length=1,
                choices=[
                    ("s", "Son of"),
                    ("f", "Father of"),
                    ("d", "Daughter of"),
                    ("c", "Child of"),
                    ("p", "Parent of"),
                    ("w", "Wife of"),
                    ("h", "Husband of"),
                    ("o", "Other"),
                ],
                default="s",
                verbose_name="Relationship",
            ),
        ),
        migrations.AlterField(
            model_name="customerrelationship",
            name="customer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="relationships_created",
                to="contact.customer",
                verbose_name="Customer",
            ),
        ),
        migrations.AlterField(
            model_name="customerrelationship",
            name="related_customer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="relationships_received",
                to="contact.customer",
                verbose_name="Related Customer",
            ),
        ),
        # Address model changes
        migrations.RenameField(
            model_name="address",
            old_name="doorno",
            new_name="door_number",
        ),
        migrations.RenameField(
            model_name="address",
            old_name="zipcode",
            new_name="zip_code",
        ),
        migrations.AlterField(
            model_name="address",
            name="door_number",
            field=models.CharField(
                max_length=30, blank=True, verbose_name="Door/Building No"
            ),
        ),
        migrations.AlterField(
            model_name="address",
            name="street",
            field=models.TextField(max_length=100, blank=True, verbose_name="Street"),
        ),
        migrations.AlterField(
            model_name="address",
            name="area",
            field=models.CharField(
                max_length=50, blank=True, verbose_name="Area/Locality"
            ),
        ),
        migrations.AlterField(
            model_name="address",
            name="state",
            field=models.CharField(
                max_length=2,
                choices=[
                    ("AP", "Andhra Pradesh"),
                    ("AR", "Arunachal Pradesh"),
                    ("AS", "Assam"),
                    ("BR", "Bihar"),
                    ("CG", "Chhattisgarh"),
                    ("GA", "Goa"),
                    ("GJ", "Gujarat"),
                    ("HR", "Haryana"),
                    ("HP", "Himachal Pradesh"),
                    ("JH", "Jharkhand"),
                    ("KA", "Karnataka"),
                    ("KL", "Kerala"),
                    ("MP", "Madhya Pradesh"),
                    ("MH", "Maharashtra"),
                    ("MN", "Manipur"),
                    ("ML", "Meghalaya"),
                    ("MZ", "Mizoram"),
                    ("NL", "Nagaland"),
                    ("OD", "Odisha"),
                    ("PB", "Punjab"),
                    ("RJ", "Rajasthan"),
                    ("SK", "Sikkim"),
                    ("TN", "Tamil Nadu"),
                    ("TS", "Telangana"),
                    ("TR", "Tripura"),
                    ("UP", "Uttar Pradesh"),
                    ("UK", "Uttarakhand"),
                    ("WB", "West Bengal"),
                    ("AN", "Andaman and Nicobar Islands"),
                    ("CH", "Chandigarh"),
                    ("DN", "Dadra and Nagar Haveli and Daman and Diu"),
                    ("DL", "Delhi"),
                    ("JK", "Jammu and Kashmir"),
                    ("LA", "Ladakh"),
                    ("LD", "Lakshadweep"),
                    ("PY", "Puducherry"),
                ],
                verbose_name="State",
            ),
        ),
        migrations.AlterField(
            model_name="address",
            name="zip_code",
            field=models.CharField(
                max_length=6,
                validators=[
                    django.core.validators.RegexValidator(
                        regex=r"^[0-9]{6}$", message="Enter a valid 6-digit PIN code"
                    )
                ],
                verbose_name="PIN Code",
                help_text="6-digit postal PIN code",
            ),
        ),
        migrations.AlterField(
            model_name="address",
            name="is_default",
            field=models.BooleanField(default=False, verbose_name="Default Address"),
        ),
        # Contact model changes
        migrations.AlterField(
            model_name="contact",
            name="is_default",
            field=models.BooleanField(default=False, verbose_name="Default"),
        ),
        # Proof model changes
        migrations.RenameField(
            model_name="proof",
            old_name="proof_no",
            new_name="proof_number",
        ),
        migrations.RenameField(
            model_name="proof",
            old_name="doc",
            new_name="document",
        ),
        migrations.AlterField(
            model_name="proof",
            name="document",
            field=models.FileField(
                upload_to="proofs/", blank=True, null=True, verbose_name="Document File"
            ),
        ),
        migrations.AlterField(
            model_name="proof",
            name="proof_type",
            field=models.CharField(
                max_length=2,
                choices=[
                    ("AA", "Aadhaar Number"),
                    ("DL", "Driving License"),
                    ("PN", "PAN Card"),
                    ("VI", "Voter ID"),
                    ("PP", "Passport"),
                ],
                default="AA",
                verbose_name="Document Type",
            ),
        ),
        # CustomerPic changes
        migrations.AlterField(
            model_name="customerpic",
            name="is_default",
            field=models.BooleanField(default=False, verbose_name="Default"),
        ),
        # Add indexes (matching the actual model Meta.indexes)
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(
                fields=["firstname", "lastname"], name="contact_cus_name_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(fields=["-created"], name="contact_cus_created_idx"),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(fields=["customer_type"], name="contact_cus_type_idx"),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(fields=["active"], name="contact_cus_active_idx"),
        ),
        migrations.AddIndex(
            model_name="customerrelationship",
            index=models.Index(
                fields=["customer", "relationship"], name="contact_rel_cus_rel_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="customerrelationship",
            index=models.Index(
                fields=["related_customer"], name="contact_rel_related_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="address",
            index=models.Index(
                fields=["customer", "-is_default"], name="contact_add_cus_def_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="address",
            index=models.Index(
                fields=["city", "state"], name="contact_add_city_st_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="contact",
            index=models.Index(
                fields=["customer", "-is_default"], name="contact_con_cus_def_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="proof",
            index=models.Index(
                fields=["customer", "proof_type"], name="contact_pro_cus_typ_idx"
            ),
        ),
        # Add Meta options
        migrations.AlterModelOptions(
            name="address",
            options={
                "ordering": ["-is_default", "-created"],
                "verbose_name": "Address",
                "verbose_name_plural": "Addresses",
            },
        ),
        migrations.AlterModelOptions(
            name="contact",
            options={
                "ordering": ["-is_default", "-created"],
                "verbose_name": "Contact",
                "verbose_name_plural": "Contacts",
            },
        ),
        migrations.AlterModelOptions(
            name="customerpic",
            options={
                "verbose_name": "Customer Picture",
                "verbose_name_plural": "Customer Pictures",
            },
        ),
        migrations.AlterModelOptions(
            name="customerrelationship",
            options={
                "verbose_name": "Customer Relationship",
                "verbose_name_plural": "Customer Relationships",
            },
        ),
        migrations.AlterModelOptions(
            name="proof",
            options={
                "ordering": ["-created"],
                "verbose_name": "Identity Proof",
                "verbose_name_plural": "Identity Proofs",
            },
        ),
    ]
