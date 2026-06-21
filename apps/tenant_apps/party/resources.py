from import_export import resources
from import_export.fields import Field
from import_export.widgets import DateTimeWidget

from .models import Party, PartyRole


class PartyResource(resources.ModelResource):
    party_type_display = Field(column_name="party_type_display")
    status_display = Field(column_name="status_display")
    relation_display = Field(column_name="relation_display")
    active_roles = Field(column_name="active_roles")
    legacy_customer_id = Field(column_name="legacy_customer_id")

    created_at = Field(
        attribute="created_at",
        column_name="created_at",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )
    updated_at = Field(
        attribute="updated_at",
        column_name="updated_at",
        widget=DateTimeWidget("%d/%m/%Y, %H:%M:%S"),
    )

    class Meta:
        model = Party
        fields = (
            "id",
            "party_code",
            "display_name",
            "legal_name",
            "party_type",
            "party_type_display",
            "status",
            "status_display",
            "relation_label",
            "relation_name",
            "relation_display",
            "primary_phone",
            "primary_email",
            "tax_pan",
            "gstin",
            "risk_level",
            "credit_hold",
            "active_roles",
            "legacy_customer_id",
            "created_at",
            "updated_at",
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = False
        import_id_fields = ("id",)

    def dehydrate_party_type_display(self, party):
        return party.get_party_type_display()

    def dehydrate_status_display(self, party):
        return party.get_status_display()

    def dehydrate_relation_display(self, party):
        return party.relation_display

    def dehydrate_active_roles(self, party):
        roles = [
            role.role_type.label
            for role in party.roles.all()
            if role.status == PartyRole.RoleStatus.ACTIVE
        ]
        return ", ".join(roles)

    def dehydrate_legacy_customer_id(self, party):
        try:
            return party.legacy_customer_id
        except AttributeError:
            try:
                return party.legacy_customer.pk
            except Exception:
                return ""
