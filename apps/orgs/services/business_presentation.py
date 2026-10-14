"""Business display/workflow restoration, separate from control-plane authority."""
from django.core.exceptions import PermissionDenied, ValidationError
from apps.orgs.access import resolve_workspace_access
from apps.tenancy.context import current_workspace_id
from apps.subscriptions.access_policy import require_business_write


def restore_business_presentation(*, workspace, actor, values, load_file, save_file):
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied('Business presentation requires the explicit destination Workspace.')
    resolve_workspace_access(actor=actor,workspace=workspace).require('workspace.settings.manage')
    require_business_write(workspace)
    if type(values) is not dict or set(values) != {'source_name','theme','logo','loan_workflow'} or values['loan_workflow'] not in {'SIMPLE','EXTENDED'}:
        raise ValidationError('Unsupported business presentation settings.')
    workspace.theme=values['theme']
    workspace.loan_workflow=values['loan_workflow']
    if values['logo']:
        save_file(workspace.logo,load_file(values['logo']))
    workspace.full_clean()
    workspace.save(update_fields=['theme','loan_workflow','logo'])
