"""Protect append-only evidence; mutable aggregate state remains outside this guard."""
from django.db import migrations


MODELS = (
    "LoanPolicySnapshot", "PawnLoanApprovalSnapshot", "PawnLoanEvent",
    "PawnLoanDisbursalSnapshot", "PawnLoanInterestAccrual", "PawnLoanInterestAccrualLine",
    "PawnLoanRepaymentAllocationLine", "PawnLoanPrincipalClosingLine",
    "PawnLoanRelease", "PawnLoanReleaseItem", "PawnCollateralCustodyEvent",
    "RepaymentScheduleVersion", "RepaymentObligation", "RepaymentScheduleChange",
    "ObligationAllocation",
)


def install(apps, schema_editor):
    q = schema_editor.quote_name
    for name in MODELS:
        model = apps.get_model("loans", name)
        table = q(model._meta.db_table)
        function = q("loans_history_" + model._meta.model_name)
        fields = {f.name for f in model._meta.fields}
        loan_expression = "NEW.loan_id" if "loan" in fields else None
        if loan_expression is None:
            for parent in ("accrual", "loan_event", "release", "collateral_item"):
                if parent in fields:
                    relation = model._meta.get_field(parent)
                    if relation.null:
                        continue
                    target = relation.remote_field.model
                    loan_expression = (
                        f"(SELECT loan_id FROM {q(target._meta.db_table)} "
                        f"WHERE {q(target._meta.pk.column)} = NEW.{q(relation.column)})"
                    )
                    break
        checks = []
        for field in model._meta.fields:
            if not field.is_relation or not field.many_to_one and not field.one_to_one:
                continue
            target = field.remote_field.model
            target_fields = {f.name for f in target._meta.fields}
            if "workspace" not in target_fields:
                continue
            target_table = q(target._meta.db_table)
            column = q(field.column)
            target_pk = q(field.target_field.column)
            conditions = "p.workspace_id = NEW.workspace_id"
            if loan_expression is not None and "loan" in target_fields:
                conditions += f" AND p.loan_id = {loan_expression}"
            checks.append(f"""
  IF NEW.{column} IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM {target_table} p WHERE p.{target_pk} = NEW.{column} AND {conditions}
  ) THEN RAISE EXCEPTION 'Loan evidence reference must belong to its Workspace and loan' USING ERRCODE = '23514'; END IF;
""")
        schema_editor.execute(f"""
CREATE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'Loan evidence is immutable; append compensating evidence' USING ERRCODE = '23514';
  END IF;
{''.join(checks)}
  RETURN NEW;
END; $$;
CREATE TRIGGER loans_history_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON {table}
FOR EACH ROW EXECUTE FUNCTION {function}();
""")


def uninstall(apps, schema_editor):
    q = schema_editor.quote_name
    for name in reversed(MODELS):
        model = apps.get_model("loans", name)
        schema_editor.execute(f"DROP TRIGGER loans_history_evidence_guard ON {q(model._meta.db_table)}")
        schema_editor.execute(f"DROP FUNCTION {q('loans_history_' + model._meta.model_name)}()")


class Migration(migrations.Migration):
    dependencies = [("loans", "0007_monitoring_policy_amendments")]
    operations = [migrations.RunPython(install, uninstall)]
