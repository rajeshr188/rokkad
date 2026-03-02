from rest_framework import serializers

from . import models


class CustomerSerializer(serializers.ModelSerializer):
    loan_set = serializers.StringRelatedField(many=True)

    class Meta:
        model = models.Customer
        fields = (
            "id",
            "name",
            "created",
            "last_updated",
            "area",
            "type",
            "relatedas",
            "relatedto",
            "active",
            "gender",
            "religion",
            "loan_set",
        )


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Address
        fields = [
            "area",
            "created",
            "door_number",
            "zip_code",
            "last_updated",
            "street",
            "Customer",
        ]


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Contact
        fields = [
            "created",
            "contact_type",
            "number",
            "last_updated",
            "Customer",
        ]


class ProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Proof
        fields = [
            "proof_type",
            "created",
            "proof_number",
            "document",
            "last_updated",
            "Customer",
        ]
