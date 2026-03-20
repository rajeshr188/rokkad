from django.contrib.auth import get_user_model
from django_tenants.test.cases import TenantTestCase

from .forms import ProductForm, ProductVariantForm
from .models import (
	AssignedProductAttribute,
	AssignedVariantAttribute,
	Attribute,
	AttributeValue,
	Category,
	Product,
	ProductType,
	ProductVariant,
)


User = get_user_model()


class NormalizedAttributesRegressionTests(TenantTestCase):
	@classmethod
	def setup_tenant(cls, tenant):
		user = User.objects.create_user(
			username="tenant_test_owner",
			email="tenant_test_owner@example.com",
			password="testpass123",
		)
		tenant.name = "tenant-test-company"
		tenant.owner = user
		tenant.creator = user

	def setUp(self):
		self.category = Category.objects.create(name="Cat-Attr-Reg")
		self.product_type = ProductType.objects.create(
			name="Type-Attr-Reg", has_variants=True
		)

		self.product_attribute = Attribute.objects.create(name="Metal")
		self.product_attribute_value = AttributeValue.objects.create(
			name="Gold", value="Gold", attribute=self.product_attribute
		)
		self.product_type.product_attributes.add(self.product_attribute)

		self.variant_attribute = Attribute.objects.create(name="Color")
		self.variant_attribute_value = AttributeValue.objects.create(
			name="Yellow", value="Yellow", attribute=self.variant_attribute
		)
		self.product_type.variant_attributes.add(self.variant_attribute)

	def test_product_form_creates_normalized_assignment(self):
		product = Product(product_type=self.product_type)
		field_name = self.product_attribute.get_formfield_name()
		form = ProductForm(
			data={
				"description": "Regression product",
				"category": self.category.pk,
				field_name: self.product_attribute_value.pk,
			},
			instance=product,
		)

		self.assertTrue(form.is_valid(), form.errors)
		saved_product = form.save()

		self.assertEqual(saved_product.get_attributes()[self.product_attribute], self.product_attribute_value)
		assigned = AssignedProductAttribute.objects.get(product=saved_product)
		self.assertEqual(
			list(assigned.values.values_list("pk", flat=True)),
			[self.product_attribute_value.pk],
		)

	def test_variant_form_creates_normalized_assignment(self):
		product = Product.objects.create(
			product_type=self.product_type,
			name="Base Product",
			description="desc",
			category=self.category,
		)
		variant = ProductVariant(
			product=product,
			sku="SKU-ATTR-REG",
			product_code="PC-ATTR-REG",
			name="Variant Seed",
		)
		field_name = self.variant_attribute.get_formfield_name()
		form = ProductVariantForm(
			data={
				"name": "Variant Final",
				field_name: self.variant_attribute_value.pk,
			},
			instance=variant,
		)

		self.assertTrue(form.is_valid(), form.errors)
		saved_variant = form.save()

		self.assertEqual(
			saved_variant.get_attributes()[self.variant_attribute],
			self.variant_attribute_value,
		)
		assigned = AssignedVariantAttribute.objects.get(variant=saved_variant)
		self.assertEqual(
			list(assigned.values.values_list("pk", flat=True)),
			[self.variant_attribute_value.pk],
		)

	def test_variant_attribute_update_replaces_previous_value(self):
		second_value = AttributeValue.objects.create(
			name="Green", value="Green", attribute=self.variant_attribute
		)
		product = Product.objects.create(
			product_type=self.product_type,
			name="Base Product 2",
			description="desc",
			category=self.category,
		)
		variant = ProductVariant.objects.create(
			product=product,
			sku="SKU-ATTR-UPD",
			product_code="PC-ATTR-UPD",
			name="Variant Update",
		)

		first_field_name = self.variant_attribute.get_formfield_name()
		first_form = ProductVariantForm(
			data={"name": "Variant Update", first_field_name: self.variant_attribute_value.pk},
			instance=variant,
		)
		self.assertTrue(first_form.is_valid(), first_form.errors)
		first_form.save()

		second_form = ProductVariantForm(
			data={"name": "Variant Update", first_field_name: second_value.pk},
			instance=variant,
		)
		self.assertTrue(second_form.is_valid(), second_form.errors)
		saved_variant = second_form.save()

		assigned = AssignedVariantAttribute.objects.get(variant=saved_variant)
		self.assertEqual(
			list(assigned.values.values_list("pk", flat=True)),
			[second_value.pk],
		)
