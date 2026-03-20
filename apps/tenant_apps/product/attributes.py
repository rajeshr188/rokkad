def get_product_attributes_data(product):
    """Returns attributes associated with the product,
    as dict of Attribute: AttributeValue values.
    """
    attributes = product.product_type.product_attributes.all()
    attributes_map = {attribute.pk: attribute for attribute in attributes}
    values_map = get_attributes_display_map(product, attributes)
    return {
        attributes_map[attr_pk]: value_obj
        for (attr_pk, value_obj) in values_map.items()
    }


def get_variant_attributes_data(variant):
    """Returns attributes associated with the variant,
    as dict of Attribute: AttributeValue values.
    """
    attributes = variant.product.product_type.variant_attributes.all()
    attributes_map = {attribute.pk: attribute for attribute in attributes}
    values_map = get_attributes_display_map(variant, attributes)
    return {
        attributes_map[attr_pk]: value_obj
        for (attr_pk, value_obj) in values_map.items()
    }


def get_name_from_attributes(variant, attributes):
    """Generates ProductVariant's name based on its attributes."""
    values = get_attributes_display_map(variant, attributes)
    return variant.product.name + "/" + generate_name_from_values(values)


def get_attributes_display_map(obj, attributes):
    """Returns attributes associated with an object,
    as dict of Attribute pk: AttributeValue instance.

    Args:
        attributes: Attribute Iterable
    """
    attributes = list(attributes)
    attr_ids = {attribute.pk for attribute in attributes}
    return _get_normalized_display_map(obj, attr_ids)


def _get_normalized_display_map(obj, attr_ids):
    display_map = {}
    if not getattr(obj, "pk", None):
        return display_map

    assignments = obj.attributes.select_related("assignment__attribute").prefetch_related(
        "values"
    )
    for assigned in assignments:
        attr_id = assigned.assignment.attribute_id
        if attr_id not in attr_ids:
            continue
        values = list(assigned.values.all())
        if not values:
            continue
        values.sort(key=lambda v: ((v.sort_order is None), v.sort_order or 0, v.pk))
        display_map[attr_id] = values[0]
    return display_map


def generate_name_from_values(attributes_dict):
    """Generates name from AttributeValues. Attributes dict is sorted,
    as attributes order should be kept within each save.

    Args:
        attributes_dict: dict of attribute_pk: AttributeValue values
    """
    return "/".join(
        str(attribute_value).strip()
        for attribute_pk, attribute_value in sorted(
            attributes_dict.items(), key=lambda x: x[0]
        )
    )
