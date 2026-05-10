import uuid

from django.db import models, transaction
from django.db.models import Avg, F, ExpressionWrapper, DurationField, Sum
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


class CustomerQuerySet(models.QuerySet):
    """Custom QuerySet for Customer model with optimized queries"""

    def with_contacts(self):
        """Prefetch all related contact information"""
        return self.prefetch_related(
            "address",
            "contactno",
            "pics",
            "relationships_created",
            "relationships_received",
        )

    def active(self):
        """Filter only active customers"""
        return self.filter(active=True)


class RelationType(models.TextChoices):
    """Types of family relationships"""

    Son = "s", "S/o"
    Daughter = "d", "D/o"
    Father = "f", "F/o"
    Child = "c", "C/o"
    Parent = "p", "P/o"
    Husband = "h", "H/o"
    Wife = "w", "W/o"
    Other = "o", "O/o"


class Customer(models.Model):
    """
    Customer Model - represents customers/contacts in the system.
    Optimized with proper indexing and clean field structure.
    """

    class CustomerType(models.TextChoices):
        Retail = "R", "Retail"
        Wholesale = "W", "Wholesale"
        Supplier = "S", "Supplier"

    # Timestamps
    created = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name=_("Created")
    )
    updated = models.DateTimeField(
        auto_now=True, editable=False, verbose_name=_("Updated")
    )

    # User tracking
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        verbose_name=_("Created By"),
        related_name="customers_created",
    )

    # Personal Information
    firstname = models.CharField(max_length=255, verbose_name=_("First Name"))
    lastname = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Last Name")
    )

    gender = models.CharField(
        max_length=1,
        choices=(("M", "Male"), ("F", "Female"), ("N", "Non-binary")),
        default="M",
        verbose_name=_("Gender"),
    )

    religion = models.CharField(
        max_length=10,
        choices=(
            ("Hindu", "Hindu"),
            ("Muslim", "Muslim"),
            ("Christian", "Christian"),
            ("Atheist", "Atheist"),
        ),
        default="Hindu",
        verbose_name=_("Religion"),
    )

    dob = models.DateField(null=True, blank=True, verbose_name=_("Date of Birth"))
    email = models.EmailField(blank=True, null=True, verbose_name=_("Email"))

    # Customer Classification
    customer_type = models.CharField(
        max_length=30,
        choices=CustomerType.choices,
        default=CustomerType.Retail,
        verbose_name=_("Customer Type"),
    )

    # Family Relationship
    relatedas = models.CharField(
        max_length=5,
        choices=RelationType.choices,
        default=RelationType.Son,
        verbose_name=_("Related As"),
    )
    relatedto = models.CharField(
        max_length=30, blank=True, null=True, verbose_name=_("Related To")
    )

    # Status
    active = models.BooleanField(default=True, verbose_name=_("Active"))

    # Manager
    objects = CustomerQuerySet.as_manager()

    class Meta:
        ordering = ("-created", "firstname", "lastname")
        unique_together = ("firstname", "lastname", "relatedas", "relatedto")
        indexes = [
            models.Index(fields=["firstname", "lastname"]),
            models.Index(fields=["-created"]),
            models.Index(fields=["customer_type"]),
            models.Index(fields=["active"]),
        ]
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")

    @property
    def name(self):
        """Get customer's full name"""
        if self.lastname:
            return f"{self.firstname} {self.lastname}".strip()
        return self.firstname

    def __str__(self):
        """Clean string representation"""
        return f"{self.name} ({self.get_customer_type_display()})"

    def get_absolute_url(self):
        return reverse("contact_customer_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("contact_customer_update", args=(self.pk,))

    def clean(self):
        """Validate customer data"""
        if self.dob and self.dob > timezone.now().date():
            raise ValidationError({"dob": _("Date of birth cannot be in the future")})
        if not self.firstname:
            raise ValidationError({"firstname": _("First name is required")})

    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.clean()
        super().save(*args, **kwargs)

    def get_default_pic(self):
        """Get customer's default profile picture"""
        default_pic = self.pics.filter(is_default=True).first()
        if default_pic and default_pic.image:
            return default_pic.image
        return None

    def get_default_address(self):
        """Get customer's default address"""
        # Use .all() so Django prefetch cache is honoured (avoids N+1)
        addresses = list(self.address.all())
        return next((a for a in addresses if a.is_default), None) or (addresses[0] if addresses else None)

    # Backward compatibility alias
    def get_address(self):
        """Backward compatibility - returns default address"""
        return self.get_default_address() or ""

    def get_default_contact(self):
        """Get customer's default contact"""
        # Use .all() so Django prefetch cache is honoured (avoids N+1)
        contacts = list(self.contactno.all())
        return next((c for c in contacts if c.is_default), None) or (contacts[0] if contacts else None)

    # Backward compatibility alias
    def get_contactno(self):
        """Backward compatibility - returns default contact"""
        return self.get_default_contact() or ""

    def merge(self, dup):
        """Merge duplicate customer into this customer"""
        with transaction.atomic():
            # Transfer simple related objects first.
            dup.loan_set.update(customer=self)
            dup.pics.all().update(customer=self)

            # Move addresses one-by-one so default enforcement in save() is honored.
            for dup_address in dup.address.all():
                dup_address.customer = self
                dup_address.save(update_fields=["customer"])

            # Contacts have unique_together(customer, phone_number, contact_type).
            # Merge conflicting duplicates instead of bulk reassigning.
            for dup_contact in dup.contactno.all():
                existing_contact = self.contactno.filter(
                    phone_number=dup_contact.phone_number,
                    contact_type=dup_contact.contact_type,
                ).first()

                if existing_contact:
                    fields_to_update = []
                    if dup_contact.is_verified and not existing_contact.is_verified:
                        existing_contact.is_verified = True
                        fields_to_update.append("is_verified")
                    if dup_contact.is_default and not existing_contact.is_default:
                        existing_contact.is_default = True
                        fields_to_update.append("is_default")
                    if fields_to_update:
                        existing_contact.save(update_fields=fields_to_update)
                    dup_contact.delete()
                else:
                    dup_contact.customer = self
                    dup_contact.save(update_fields=["customer"])

            # Proofs have unique_together(customer, proof_type).
            for dup_proof in dup.proofs.all():
                existing_proof = self.proofs.filter(proof_type=dup_proof.proof_type).first()
                if existing_proof:
                    fields_to_update = []
                    if dup_proof.is_verified and not existing_proof.is_verified:
                        existing_proof.is_verified = True
                        fields_to_update.append("is_verified")
                    if not existing_proof.document and dup_proof.document:
                        existing_proof.document = dup_proof.document
                        fields_to_update.append("document")
                    if fields_to_update:
                        existing_proof.save(update_fields=fields_to_update)
                    dup_proof.delete()
                else:
                    dup_proof.customer = self
                    dup_proof.save(update_fields=["customer"])

            # Relationships have unique_together(customer, related_customer, relationship).
            for rel in dup.relationships_created.all():
                new_related_customer = (
                    self if rel.related_customer_id == dup.id else rel.related_customer
                )
                if new_related_customer == self:
                    rel.delete()
                    continue

                exists = CustomerRelationship.objects.filter(
                    customer=self,
                    related_customer=new_related_customer,
                    relationship=rel.relationship,
                ).exclude(pk=rel.pk).exists()
                if exists:
                    rel.delete()
                else:
                    rel.customer = self
                    rel.related_customer = new_related_customer
                    rel.save(update_fields=["customer", "related_customer"])

            for rel in dup.relationships_received.all():
                new_customer = self if rel.customer_id == dup.id else rel.customer
                if new_customer == self:
                    rel.delete()
                    continue

                exists = CustomerRelationship.objects.filter(
                    customer=new_customer,
                    related_customer=self,
                    relationship=rel.relationship,
                ).exclude(pk=rel.pk).exists()
                if exists:
                    rel.delete()
                else:
                    rel.customer = new_customer
                    rel.related_customer = self
                    rel.save(update_fields=["customer", "related_customer"])

            # Final safety pass: keep exactly one default address/contact.
            default_addresses = self.address.filter(is_default=True).order_by("pk")
            if default_addresses.count() > 1:
                keep_address = default_addresses.first()
                self.address.filter(is_default=True).exclude(pk=keep_address.pk).update(
                    is_default=False
                )

            default_contacts = self.contactno.filter(is_default=True).order_by("pk")
            if default_contacts.count() > 1:
                keep_contact = default_contacts.first()
                self.contactno.filter(is_default=True).exclude(pk=keep_contact.pk).update(
                    is_default=False
                )

            # Delete duplicate customer
            dup.delete()

    @property
    def get_contact(self):
        """Get list of contact numbers"""
        return list(self.contactno.values_list("phone_number", flat=True))

    def get_next(self):
        """Get next customer in list"""
        return Customer.objects.filter(id__gt=self.id).order_by("id").first()

    def get_previous(self):
        """Get previous customer in list"""
        return Customer.objects.filter(id__lt=self.id).order_by("-id").first()

    @property
    def get_loans(self):
        """Get all unreleased loans"""
        return self.loan_set.unreleased()

    def get_total_loanamount(self):
        """Get total loan amount for unreleased loans"""
        amount = self.loan_set.unreleased().aggregate(
            total=Coalesce(Sum("loan_amount"), 0)
        )
        return amount["total"]

    def get_total_interest_due(self):
        """Calculate total interest due on unreleased loans"""
        total_int = 0
        for loan in self.get_loans:
            total_int += loan.interestdue()
        return total_int

    @property
    def get_loans_count(self):
        """Get count of unreleased loans"""
        return self.loan_set.unreleased().count()

    def get_interestdue(self):
        """Get total interest due from unreleased loans"""
        return self.loan_set.unreleased().aggregate(total=Sum("interest"))["total"]

    def get_weight(self):
        """Get total weight - placeholder for future implementation"""
        return 0

    @property
    def get_release_average(self):
        """Calculate average time to release loans in months"""
        average_release_time = (
            self.loan_set.released()
            .annotate(
                duration=ExpressionWrapper(
                    F("release__release_date") - F("loan_date"),
                    output_field=DurationField(),
                )
            )
            .aggregate(average=Avg("duration"))["average"]
        )

        if average_release_time is None:
            return 0

        # Convert to months (approximate)
        return round(average_release_time.days / 30.44)


def customer_pic_upload_to(instance, filename):
    """Generate upload path for customer pictures"""
    ext = filename.split(".")[-1]
    return f"customer_pics/{uuid.uuid4()}.{ext}"


class CustomerPic(models.Model):
    """Customer profile picture model"""

    customer = models.ForeignKey(
        Customer, related_name="pics", on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to=customer_pic_upload_to)
    is_default = models.BooleanField(default=False, verbose_name=_("Default"))

    class Meta:
        verbose_name = _("Customer Picture")
        verbose_name_plural = _("Customer Pictures")

    def save(self, *args, **kwargs):
        """Ensure only one default picture per customer"""
        if self.is_default:
            CustomerPic.objects.filter(customer=self.customer, is_default=True).update(
                is_default=False
            )
        super().save(*args, **kwargs)


class CustomerRelationship(models.Model):
    """
    Model representing relationships between customers.
    Automatically creates bidirectional relationships.
    """

    REVERSE_RELATIONSHIPS = {
        "s": "f",  # Son of -> Father of
        "f": "s",  # Father of -> Son of
        "d": "f",  # Daughter of -> Father of
        "c": "p",  # Child of -> Parent of
        "p": "c",  # Parent of -> Child of
        "w": "h",  # Wife of -> Husband of
        "h": "w",  # Husband of -> Wife of
        "o": "o",  # Other -> Other
    }

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="relationships_created",
        verbose_name=_("Customer"),
    )
    related_customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="relationships_received",
        verbose_name=_("Related Customer"),
    )
    relationship = models.CharField(
        max_length=1,
        choices=RelationType.choices,
        default=RelationType.Son,
        verbose_name=_("Relationship"),
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        unique_together = ("customer", "related_customer", "relationship")
        indexes = [
            models.Index(fields=["customer", "relationship"]),
            models.Index(fields=["related_customer"]),
        ]
        verbose_name = _("Customer Relationship")
        verbose_name_plural = _("Customer Relationships")

    def __str__(self):
        return f"{self.customer.name} - {self.get_relationship_display()} - {self.related_customer.name}"

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Save with automatic reverse relationship creation"""
        if not self.pk:  # Only on creation
            super().save(*args, **kwargs)

            reverse_type = self.REVERSE_RELATIONSHIPS.get(self.relationship)
            if reverse_type:
                CustomerRelationship.objects.get_or_create(
                    customer=self.related_customer,
                    related_customer=self.customer,
                    relationship=reverse_type,
                )
        else:
            super().save(*args, **kwargs)


class Address(models.Model):
    """
    Customer address model with support for multiple addresses per customer.
    Includes validation for Indian postal codes.
    """

    # Constants
    COUNTRIES = [
        ("IN", "India"),
        ("US", "United States"),
        ("UK", "United Kingdom"),
        # Add more as needed
    ]

    INDIAN_STATES = [
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
    ]

    # Validators
    zip_code_validator = RegexValidator(
        regex=r"^[0-9]{6}$", message=_("Enter a valid 6-digit PIN code")
    )

    # Relationships
    customer = models.ForeignKey(
        "contact.Customer",
        on_delete=models.CASCADE,
        related_name="address",
        verbose_name=_("Customer"),
    )

    # Address Fields
    door_number = models.CharField(
        max_length=30, blank=True, verbose_name=_("Door/Building No")
    )
    street = models.TextField(max_length=100, blank=True, verbose_name=_("Street"))
    area = models.CharField(max_length=50, blank=True, verbose_name=_("Area/Locality"))
    city = models.CharField(max_length=50, verbose_name=_("City"))
    state = models.CharField(
        max_length=2, choices=INDIAN_STATES, verbose_name=_("State")
    )
    country = models.CharField(
        max_length=2, choices=COUNTRIES, default="IN", verbose_name=_("Country")
    )
    zip_code = models.CharField(
        max_length=6,
        validators=[zip_code_validator],
        verbose_name=_("PIN Code"),
        help_text=_("6-digit postal PIN code"),
    )

    # Status Fields
    is_default = models.BooleanField(default=False, verbose_name=_("Default Address"))
    is_verified = models.BooleanField(default=False, verbose_name=_("Verified"))

    # Timestamps
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ["-is_default", "-created"]
        indexes = [
            models.Index(fields=["customer", "-is_default"]),
            models.Index(fields=["city", "state"]),
            models.Index(fields=["area"]),
            models.Index(fields=["street"]),
        ]
        verbose_name = _("Address")
        verbose_name_plural = _("Addresses")

    def __str__(self):
        parts = [self.door_number, self.street, self.area, self.city, self.zip_code]
        return ", ".join(filter(None, parts))

    def get_absolute_url(self):
        return reverse("Customer_Address_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Customer_Address_update", args=(self.pk,))

    def verify(self):
        """Mark address as verified"""
        self.is_verified = True
        self.save(update_fields=["is_verified"])

    def set_default(self):
        """Set this address as default and unset others"""
        Address.objects.filter(customer=self.customer, is_default=True).update(
            is_default=False
        )
        self.is_default = True
        self.save(update_fields=["is_default"])

    def clean(self):
        """Validate address data"""
        if not any([self.door_number, self.street, self.area]):
            raise ValidationError(
                _("At least one of door number, street, or area must be provided")
            )

    # Backward compatibility properties
    @property
    def doorno(self):
        """Backward compatibility for doorno field"""
        return self.door_number

    @property
    def zipcode(self):
        """Backward compatibility for zipcode field"""
        return self.zip_code

    def save(self, *args, **kwargs):
        """Ensure only one default address per customer"""
        if self.is_default:
            Address.objects.filter(customer=self.customer, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        return super().save(*args, **kwargs)


class Contact(models.Model):
    """
    Customer contact number model with support for multiple numbers per customer.
    Enforces uniqueness per customer/phone/type combination.
    """

    class ContactType(models.TextChoices):
        Home = "H", _("Home")
        Office = "O", _("Office")
        Mobile = "M", _("Mobile")

    # Relationships
    customer = models.ForeignKey(
        "contact.Customer",
        on_delete=models.CASCADE,
        related_name="contactno",
        verbose_name=_("Customer"),
    )

    # Fields
    phone_number = PhoneNumberField(
        verbose_name=_("Phone Number"),
        help_text=_("Enter phone with country code, e.g., +91 9876543210"),
    )
    phone_number_normalized = models.CharField(
        max_length=32,
        blank=True,
        default="",
        editable=False,
        db_index=True,
        verbose_name=_("Phone Number Normalized"),
        help_text=_("Digits-only phone number for fast search"),
    )
    contact_type = models.CharField(
        max_length=1,
        choices=ContactType.choices,
        default=ContactType.Mobile,
        verbose_name=_("Contact Type"),
    )
    is_default = models.BooleanField(default=False, verbose_name=_("Default"))
    is_verified = models.BooleanField(default=False, verbose_name=_("Verified"))

    # Timestamps
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        unique_together = ("customer", "phone_number", "contact_type")
        ordering = ["-is_default", "-created"]
        indexes = [
            models.Index(fields=["customer", "-is_default"]),
        ]
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")

    def __str__(self):
        return f"{self.get_contact_type_display()}: {self.phone_number}"

    def get_absolute_url(self):
        return reverse("Customer_Contact_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Customer_Contact_update", args=(self.pk,))

    def verify(self):
        """Mark contact as verified"""
        self.is_verified = True
        self.save(update_fields=["is_verified"])

    def set_default(self):
        """Set this contact as the default for the customer"""
        Contact.objects.filter(customer=self.customer, is_default=True).exclude(
            pk=self.pk
        ).update(is_default=False)
        self.is_default = True
        self.save(update_fields=["is_default"])

    def clean(self):
        """Validate contact data"""
        if not self.phone_number:
            raise ValidationError({"phone_number": _("Phone number is required")})

    def save(self, *args, **kwargs):
        """Save with default handling"""
        self.clean()
        self.phone_number_normalized = "".join(
            ch for ch in str(self.phone_number or "") if ch.isdigit()
        )
        if self.is_default:
            Contact.objects.filter(customer=self.customer, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)


class Proof(models.Model):
    """
    Customer identity proof model with validation for Indian documents.
    """

    class DocType(models.TextChoices):
        AADHAR = "AA", _("Aadhaar Number")
        DRIVING_LICENSE = "DL", _("Driving License")
        PAN = "PN", _("PAN Card")
        VOTER_ID = "VI", _("Voter ID")
        PASSPORT = "PP", _("Passport")

    # Validators for different document types
    PROOF_VALIDATORS = {
        "AA": RegexValidator(regex=r"^\d{12}$", message=_("Aadhaar must be 12 digits")),
        "PN": RegexValidator(
            regex=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
            message=_("PAN must be in format: ABCDE1234F"),
        ),
        "DL": RegexValidator(
            regex=r"^[A-Z]{2}[0-9]{13}$",
            message=_("Driving License format: TN1234567890123"),
        ),
    }

    # Relationships
    customer = models.ForeignKey(
        "contact.Customer",
        on_delete=models.CASCADE,
        related_name="proofs",
        verbose_name=_("Customer"),
    )

    # Fields
    proof_type = models.CharField(
        max_length=2,
        choices=DocType.choices,
        default=DocType.AADHAR,
        verbose_name=_("Document Type"),
    )
    proof_number = models.CharField(max_length=50, verbose_name=_("Document Number"))
    document = models.FileField(
        upload_to="proofs/", blank=True, null=True, verbose_name=_("Document File")
    )
    is_verified = models.BooleanField(default=False, verbose_name=_("Verified"))

    # Timestamps
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        unique_together = ("customer", "proof_type")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["customer", "proof_type"]),
        ]
        verbose_name = _("Identity Proof")
        verbose_name_plural = _("Identity Proofs")

    def __str__(self):
        return f"{self.get_proof_type_display()}: {self.proof_number}"

    def get_absolute_url(self):
        return reverse("Customer_Proof_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Customer_Proof_update", args=(self.pk,))

    def clean(self):
        """Validate proof number based on type"""
        if self.proof_type in self.PROOF_VALIDATORS:
            validator = self.PROOF_VALIDATORS[self.proof_type]
            try:
                validator(self.proof_number)
            except ValidationError as e:
                raise ValidationError({"proof_number": e.message})

        # Normalize PAN to uppercase
        if self.proof_type == self.DocType.PAN:
            self.proof_number = self.proof_number.upper()

    def save(self, *args, **kwargs):
        """Save with validation"""
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete associated file when proof is deleted"""
        if self.document:
            storage = self.document.storage
            name = self.document.name
            super().delete(*args, **kwargs)
            storage.delete(name)
        else:
            super().delete(*args, **kwargs)

    # Backward compatibility properties
    @property
    def proof_no(self):
        """Backward compatibility for proof_no field"""
        return self.proof_number

    @property
    def doc(self):
        """Backward compatibility for doc field"""
        return self.document
