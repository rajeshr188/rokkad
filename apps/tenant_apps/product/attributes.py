def get_product_attributes_data(product):
    """Returns attributes associated with the product,
    as dict of Attribute: AttributeValue values.
    """
    attributes = product.product_type.product_attributes.all()
    print(f"attributes: {attributes}")
    attributes_map = {attribute.pk: attribute for attribute in attributes}
    print(f"attributes_map: {attributes_map}")
    values_map = get_attributes_display_map(product, attributes)
    print(f"values_map: {values_map}")
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
    as dict of Attribute: AttributeValue values.

    Args:
        attributes: Attribute Iterable
    """
    display_map = {}
    print(f"obj: {obj},attributes: {attributes}")
    for attribute in attributes:
        value = obj.attributes.get(str(attribute.pk))
        print(f"value: {value}")
        if value:
            choices = {str(a.pk): a for a in attribute.values.all()}
            print(f"choices: {choices}")
            display_map[attribute.pk] = choices[value]
    print(f"display_map: {display_map}")
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
