from rest_framework import serializers

from . import models


class CustomerSerializer(serializers.ModelSerializer):
    loan_set = serializers.SerializerMethodField()

    def get_loan_set(self, obj):
        """Backward-compatible API field backed by GivenLoan.loans_received."""
        return [str(loan) for loan in obj.loans_received.all()]

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
