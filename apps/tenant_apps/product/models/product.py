from django.db import models
from django.shortcuts import reverse
from django.utils.text import slugify
from django_extensions.db.fields import AutoSlugField
from mptt.models import MPTTModel, TreeForeignKey

from ..attributes import get_product_attributes_data, get_variant_attributes_data


ATTRIBUTE_INPUT_TYPE_DROPDOWN = "dropdown"
ATTRIBUTE_INPUT_TYPE_MULTISELECT = "multiselect"
ATTRIBUTE_INPUT_TYPE_CHOICES = (
    (ATTRIBUTE_INPUT_TYPE_DROPDOWN, "Dropdown"),
    (ATTRIBUTE_INPUT_TYPE_MULTISELECT, "Multiselect"),
)


class Category(MPTTModel):
    # gold ,silver ,other
    name = models.CharField(max_length=128, unique=True)
    slug = AutoSlugField(populate_from="name", blank=True)
    description = models.TextField(blank=True)
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    background_image = models.ImageField(
        upload_to="category-backgrounds", blank=True, null=True
    )

    class MPTTMeta:
        order_insertion_by = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_category_detail", args=(self.slug,))

    def get_update_url(self):
        return reverse("product_category_update", args=(self.slug,))


class ProductType(models.Model):
    # ring,bracelet,chain,necklace,harem,dollar,urupudi,coin,kalkas,moppu,mugti,kamal,tops,kassaset,jhapaka,mattal
    name = models.CharField(max_length=128)
    has_variants = models.BooleanField(default=True)
    product_attributes = models.ManyToManyField(
        "Attribute",
        related_name="product_types",
        blank=True,
        through="AttributeProduct",
        through_fields=("product_type", "attribute"),
    )
    variant_attributes = models.ManyToManyField(
        "Attribute",
        related_name="product_variant_types",
        blank=True,
        through="AttributeVariant",
        through_fields=("product_type", "attribute"),
    )

    class Meta:
        app_label = "product"
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_producttype_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("product_producttype_update", args=(self.pk,))

    def __repr__(self):
        class_ = type(self)
        return "<%s.%s(pk=%r, name=%r)>" % (
            class_.__module__,
            class_.__name__,
            self.pk,
            self.name,
        )


class Product(models.Model):
    # tv ring,plate ring,dc chain,gc chain
    product_type = models.ForeignKey(
        ProductType, related_name="products", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField()
    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.CASCADE
    )

    class Meta:
        app_label = "product"
        ordering = ("name",)

    def __iter__(self):
        if not hasattr(self, "__variants"):
            setattr(self, "__variants", self.variants.all())
        return iter(getattr(self, "__variants"))

    def __repr__(self):
        class_ = type(self)
        return "<%s.%s(pk=%r, name=%r)>" % (
            class_.__module__,
            class_.__name__,
            self.pk,
            self.name,
        )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_product_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("product_product_update", args=(self.pk,))

    def is_in_stock(self):
        return any(variant.is_in_stock() for variant in self)

    def get_first_image(self):
        images = list(self.images.all())
        return images[0].image if images else None

    def get_attributes(self):
        return get_product_attributes_data(self)


class ProductVariant(models.Model):
    sku = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255, unique=True)
    product = models.ForeignKey(
        Product, related_name="variants", on_delete=models.CASCADE
    )
    product_code = models.CharField(max_length=100, unique=True)
    images = models.ManyToManyField("ProductImage", through="VariantImage")

    class Meta:
        app_label = "product"

    def __str__(self):
        return f"{self.name} {self.product_code}"

    def get_attributes(self):
        return get_variant_attributes_data(self)

    def get_bal(self):
        # total = self.stocks.annotate(
        #     total = Sum(
        #         F('stockbalance__Closing_wt')+
        #         F('stockbalance__in_wt')-
        #         F('stockbalance__out_wt')
        #     )
        # )["total"]

        # return total
        pass

    def get_absolute_url(self):
        return reverse("product_productvariant_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("product_productvariant_update", args=(self.pk,))

    def display_product(self, translated=False):
        if translated:
            product = self.product.translated
            variant_display = str(self.translated)
        else:
            variant_display = str(self)
            product = self.product
        product_display = (
            "%s (%s)" % (product, variant_display) if variant_display else str(product)
        )
        return product_display

    def get_first_image(self):
        images = list(self.images.all())
        if images:
            return images[0].image
        return self.product.get_first_image()

    def get_ajax_label(self):
        return "%s, %s" % (self.sku, self.display_product())


class Attribute(models.Model):
    name = models.CharField(max_length=50)
    slug = AutoSlugField(populate_from="name", blank=True)
    input_type = models.CharField(
        max_length=50,
        choices=ATTRIBUTE_INPUT_TYPE_CHOICES,
        default=ATTRIBUTE_INPUT_TYPE_DROPDOWN,
    )
    value_required = models.BooleanField(default=False, blank=True)
    visible_in_storefront = models.BooleanField(default=True, blank=True)
    filterable_in_storefront = models.BooleanField(default=True, blank=True)
    filterable_in_dashboard = models.BooleanField(default=True, blank=True)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_attribute_detail", args=(self.slug,))

    def get_update_url(self):
        return reverse("product_attribute_update", args=(self.slug,))

    def get_formfield_name(self):
        return slugify("attribute-%s" % self.slug, allow_unicode=True)

    def has_values(self):
        return self.values.exists()


class AttributeValue(models.Model):
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=100, default="")
    slug = AutoSlugField(populate_from="name", blank=True)
    sort_order = models.PositiveIntegerField(blank=True, null=True)
    attribute = models.ForeignKey(
        Attribute, related_name="values", on_delete=models.CASCADE
    )

    class Meta:
        ordering = ("-id",)
        unique_together = ("name", "attribute")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_attributevalue_detail", args=(self.slug,))

    def get_update_url(self):
        return reverse("product_attributevalue_update", args=(self.slug,))

    def get_ordering_queryset(self):
        return self.attribute.values.all()


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, related_name="images", on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to="product/", blank=False)

    alt = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ("-id",)
        app_label = "product"

    def get_absolute_url(self):
        return reverse("product_productimage_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("product_productimage_update", args=(self.pk,))

    def get_ordering_queryset(self):
        return self.product.images.all()


class VariantImage(models.Model):
    variant = models.ForeignKey(
        "ProductVariant", related_name="variant_images", on_delete=models.CASCADE
    )
    image = models.ForeignKey(
        ProductImage, related_name="variant_images", on_delete=models.CASCADE
    )

    def get_absolute_url(self):
        return reverse("product_variantimage_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("product_variantimage_update", args=(self.pk,))


class BaseAssignedAttribute(models.Model):
    assignment = None
    values = models.ManyToManyField("AttributeValue")

    class Meta:
        abstract = True

    @property
    def attribute(self):
        return self.assignment.attribute

    @property
    def attribute_pk(self):
        return self.assignment.attribute_id


class AssignedProductAttribute(BaseAssignedAttribute):
    product = models.ForeignKey(
        Product, related_name="attributes", on_delete=models.CASCADE
    )
    assignment = models.ForeignKey(
        "AttributeProduct", on_delete=models.CASCADE, related_name="productassignments"
    )

    class Meta:
        unique_together = (("product", "assignment"),)


class AssignedVariantAttribute(BaseAssignedAttribute):
    variant = models.ForeignKey(
        ProductVariant, related_name="attributes", on_delete=models.CASCADE
    )
    assignment = models.ForeignKey(
        "AttributeVariant", on_delete=models.CASCADE, related_name="variantassignments"
    )

    class Meta:
        unique_together = (("variant", "assignment"),)


class AttributeProduct(models.Model):
    attribute = models.ForeignKey(
        "Attribute", related_name="attributeproduct", on_delete=models.CASCADE
    )
    product_type = models.ForeignKey(
        ProductType, related_name="attributeproduct", on_delete=models.CASCADE
    )
    sort_order = models.PositiveIntegerField(blank=True, null=True)
    assigned_products = models.ManyToManyField(
        Product,
        blank=True,
        through=AssignedProductAttribute,
        through_fields=("assignment", "product"),
        related_name="attributesrelated",
    )

    class Meta:
        unique_together = (("attribute", "product_type"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.product_type.attributeproduct.all()


class AttributeVariant(models.Model):
    attribute = models.ForeignKey(
        "Attribute", related_name="attributevariant", on_delete=models.CASCADE
    )
    product_type = models.ForeignKey(
        ProductType, related_name="attributevariant", on_delete=models.CASCADE
    )
    sort_order = models.PositiveIntegerField(blank=True, null=True)
    assigned_variants = models.ManyToManyField(
        ProductVariant,
        blank=True,
        through=AssignedVariantAttribute,
        through_fields=("assignment", "variant"),
        related_name="attributesrelated",
    )

    class Meta:
        unique_together = (("attribute", "product_type"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.product_type.attributevariant.all()
