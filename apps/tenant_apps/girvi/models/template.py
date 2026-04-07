# models.py
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.urls import reverse


class LoanTemplateManager(models.Manager):
    def get_default(self):
        """Get the active default template or None if not found."""
        return self.filter(is_default=True, is_active=True).first()


class LoanTemplate(models.Model):
    class PrintOption(models.TextChoices):
        ORIGINAL_ONLY = "O", "Original Copy Only"
        ORIGINAL_WITH_TERMS = "OT", "Original with Terms on Back"
        DUPLICATE_ONLY = "D", "Duplicate Copy Only"
        DUPLICATE_WITH_FORM = "DF", "Duplicate with Form D3 on Back"
        BOTH_SINGLE_SIDED = "BS", "Both Copies Single Sided"
        BOTH_DOUBLE_SIDED = "BD", "Both Copies Double Sided"
        BOTH_SINGLE_A4 = "BA", "Both on Single A4 Landscape"
        BOTH_DOUBLE_A4 = "BDA", "Both Double Sided on A4 Landscape (2 pages)"

    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100)
    base_template = models.FileField(upload_to="pdf_templates/", null=True, blank=True)
    dup_template = models.FileField(upload_to="pdf_templates/", null=True, blank=True)
    terms_template = models.FileField(upload_to="pdf_templates/", null=True, blank=True)
    form_d3_template = models.FileField(
        upload_to="pdf_templates/", null=True, blank=True
    )
    print_option = models.CharField(
        max_length=3, choices=PrintOption.choices, default=PrintOption.BOTH_SINGLE_SIDED
    )
    # below fields irrelevant for now
    page_width = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Width in centimeters",
    )
    page_height = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Height in centimeters",
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    objects = LoanTemplateManager()

    #     workspace = models.ForeignKey('workspace.Workspace', on_delete=models.CASCADE)

    #     class Meta:
    #         unique_together = ['name', 'workspace']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("girvi:girvi_template_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("girvi:girvi_template_update", args=(self.pk,))

    def get_preview_url(self):
        return reverse("girvi:girvi_template_preview", args=(self.pk,))

    def save(self, *args, **kwargs):
        if self.is_default:
            with transaction.atomic():
                # Unset default flag for all other templates
                LoanTemplate.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def set_default(self):
        self.is_default = True
        self.save()
        return True


class TemplateFrame(models.Model):
    class TemplateType(models.TextChoices):
        ORIGINAL = "O", "Original Copy"
        DUPLICATE = "D", "Duplicate Copy"
        BOTH = "B", "Both Copies"

    FRAME_TYPES = [
        ("license_no", "License Number"),
        ("license_name", "License Name"),
        ("license_address", "License Address"),
        ("license_phone", "License Phone"),
        ("license_propreitor", "License Propreitor"),
        ("logo", "Logo"),
        ("loan_id", "Loan ID"),
        ("loan_qr", "Loan QR Code"),
        ("loan_date", "Date"),
        ("customer_info", "Customer Info"),
        ("customer_name", "Customer Name"),
        ("customer_pic", "Customer Photo"),
        ("loanitem_pic", "Loan Item Photo"),
        ("loan_desc", "Loan Description"),
        ("weight", "Weight"),
        ("pure", "Pure Weight"),
        ("value", "Value"),
        ("address", "Address"),
        ("phone", "Phone Number"),
        ("items_table", "Items Table"),
        ("amount", "Amount"),
        ("amount_words", "Amount in Words"),
        ("label", "Label"),
    ]

    template = models.ForeignKey(LoanTemplate, on_delete=models.CASCADE)
    frame_name = models.CharField(max_length=20, choices=FRAME_TYPES)
    template_type = models.CharField(
        max_length=1,
        choices=TemplateType.choices,
        default=TemplateType.BOTH,
        help_text="Specify if frame appears on original, duplicate or both copies",
    )
    field_type = models.CharField(
        max_length=20,
        choices=[
            ("text", "Text"),
            ("image", "Image"),
            ("table", "Table"),
            ("qr", "QR Code"),
        ],
    )
    x_pos = models.DecimalField(
        max_digits=6, decimal_places=2, help_text="X position in centimeters"
    )
    y_pos = models.DecimalField(
        max_digits=6, decimal_places=2, help_text="Y position in centimeters"
    )
    width = models.DecimalField(
        max_digits=6, decimal_places=2, help_text="Width in centimeters"
    )
    height = models.DecimalField(
        max_digits=6, decimal_places=2, help_text="Height in centimeters"
    )
    font_size = models.PositiveIntegerField(default=12)
    font_name = models.CharField(max_length=50, default="Helvetica")
    show_boundary = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ["template", "frame_name", "template_type"]

    def clean(self):
        """Validate frame geometry against template dimensions."""
        errors = {}

        # Validate frame dimensions are positive
        if self.width <= 0:
            errors["width"] = "Width must be greater than 0 cm."
        if self.height <= 0:
            errors["height"] = "Height must be greater than 0 cm."

        # Validate positions are non-negative
        if self.x_pos < 0:
            errors["x_pos"] = "X position cannot be negative."
        if self.y_pos < 0:
            errors["y_pos"] = "Y position cannot be negative."

        # Validate bounds against template dimensions if template exists
        if self.template and self.template.page_width and self.template.page_height:
            page_width = float(self.template.page_width)
            page_height = float(self.template.page_height)

            if self.x_pos + self.width > page_width:
                errors["x_pos"] = (
                    f"Frame extends beyond page width. X position ({self.x_pos}) "
                    f"+ width ({self.width}) exceeds page width ({page_width})."
                )
            if self.y_pos + self.height > page_height:
                errors["y_pos"] = (
                    f"Frame extends beyond page height. Y position ({self.y_pos}) "
                    f"+ height ({self.height}) exceeds page height ({page_height})."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.template.name} - {self.get_frame_name_display()}"
