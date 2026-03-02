# Permission Matrix - Rokkad Multi-Tenant System

## Overview

This document defines the complete permission structure for the Rokkad multi-tenant application. It maps **permissions** to **roles** and provides guidance on implementation and usage.

**Document Version:** 1.0  
**Last Updated:** February 27, 2026  
**Status:** Phase 0 - Security Foundation

---

## Table of Contents

1. [Permission Categories](#permission-categories)
2. [Role Definitions](#role-definitions)
3. [Complete Permission Matrix](#complete-permission-matrix)
4. [Permission Hierarchies](#permission-hierarchies)
5. [Implementation Guide](#implementation-guide)
6. [Usage Examples](#usage-examples)

---

## Permission Categories

Permissions are organized into 10 functional categories:

| Category | Prefix | Count | Description |
|----------|--------|-------|-------------|
| **Workspace** | `workspace_` | 7 | Company/workspace management |
| **Team** | `team_` | 8 | Team member management |
| **Data** | `data_` | 10 | Generic data operations |
| **Billing** | `billing_` | 5 | Subscription and billing |
| **Reports** | `report_` | 5 | Report generation and viewing |
| **Girvi** | `girvi_` | 9 | Loan management module |
| **DEA** | `dea_` | 8 | Accounting/journal entries |
| **Sales** | `sales_` | 7 | Sales and invoicing |
| **Purchase** | `purchase_` | 6 | Purchase orders |
| **Contact** | `contact_` | 6 | Contact management |
| **TOTAL** | | **71** | All permissions |

---

## Role Definitions

### Default Roles

```
┌─────────────────────────────────────────────────────────────┐
│                        ROLE HIERARCHY                       │
│                                                             │
│     Owner (71 perms)          - Full control                │
│       ↓                                                     │
│     Admin (55 perms)          - Operations manager          │
│       ↓                                                     │
│     Member (35 perms)         - Standard user               │
│       ↓                                                     │
│     Viewer (16 perms)         - Read-only access            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Role Descriptions

#### 👑 Owner
- **Purpose:** Company founder, ultimate authority
- **Permission Count:** 71 (100% - All permissions)
- **Can:**
  - Delete workspace
  - Transfer ownership
  - Cancel subscription
  - Manage all team members
  - Perform all operations
- **Cannot:** (None - full access)
- **Typical Users:** founder@company.com

#### 🛡️ Admin
- **Purpose:** Operations manager, handles day-to-day management
- **Permission Count:** 55 (77% of all permissions)
- **Can:**
  - Edit workspace settings
  - Invite members (including admins)
  - Change member roles
  - Perform all data operations
  - Approve purchases
  - Close accounting periods
- **Cannot:**
  - Delete workspace
  - Transfer ownership
  - Cancel subscription
  - Edit billing information
- **Typical Users:** manager@company.com, operations@company.com

#### 👤 Member
- **Purpose:** Standard employee, day-to-day operations
- **Permission Count:** 35 (49% of all permissions)
- **Can:**
  - View workspace and team
  - Create and edit own data
  - Process loans (create, edit, payment)
  - Create invoices and purchase orders
  - View reports
- **Cannot:**
  - Edit workspace settings
  - Invite or remove members
  - Delete others' data
  - Approve purchases
  - Export bulk data
  - Close accounting periods
- **Typical Users:** employee@company.com, staff@company.com

#### 👁️ Viewer
- **Purpose:** Read-only observer, auditor, or client
- **Permission Count:** 16 (23% of all permissions)
- **Can:**
  - View workspace details
  - View team members
  - View all data entries
  - View reports
- **Cannot:**
  - Create, edit, or delete anything
  - Export data
  - Invite members
  - Change settings
- **Typical Users:** auditor@company.com, client@company.com

---

## Complete Permission Matrix

### Legend
- ✅ = Permission granted
- ❌ = Permission denied
- 🔒 = Owner only
- 🔑 = Admin+ (Admin and Owner)

---

### 1. WORKSPACE PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `workspace_view` | Can view workspace | ✅ | ✅ | ✅ | ✅ | View workspace details and settings |
| `workspace_list` | Can list workspaces | ✅ | ✅ | ✅ | ✅ | View list of accessible workspaces |
| `workspace_edit` | Can edit workspace | ✅ | ✅ | ❌ | ❌ | Edit workspace settings |
| `workspace_settings` | Can manage settings | ✅ | ✅ | ❌ | ❌ | Manage advanced workspace settings |
| `workspace_delete` | Can delete workspace | ✅🔒 | ❌ | ❌ | ❌ | Permanently delete workspace |
| `workspace_archive` | Can archive workspace | ✅🔒 | ❌ | ❌ | ❌ | Soft delete/archive workspace |
| `workspace_transfer` | Can transfer ownership | ✅🔒 | ❌ | ❌ | ❌ | Transfer ownership to another user |

**Notes:**
- Workspace deletion is irreversible - Owner only
- Transfer ownership requires Owner role
- Settings include theme, logo, preferences

---

### 2. TEAM MANAGEMENT PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `team_view` | Can view team | ✅ | ✅ | ✅ | ✅ | View team members and roles |
| `team_list` | Can list members | ✅ | ✅ | ✅ | ✅ | View full team member list |
| `team_invite` | Can invite members | ✅ | ✅ | ❌ | ❌ | Send invitations to new members |
| `team_invite_admin` | Can invite admins | ✅🔒 | ❌ | ❌ | ❌ | Send invitations with admin role |
| `team_edit` | Can edit member | ✅ | ✅ | ❌ | ❌ | Edit team member details |
| `team_remove` | Can remove members | ✅ | ✅ | ❌ | ❌ | Remove members from workspace |
| `team_change_role` | Can change roles | ✅ | ✅ | ❌ | ❌ | Change team member roles |
| `team_view_activity` | Can view activity | ✅ | ❌ | ❌ | ❌ | View member activity logs |

**Notes:**
- Only Owner can invite or appoint new Admins
- Admins can invite/remove Members and Viewers
- Admins cannot remove other Admins

---

### 3. DATA & CONTENT PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `data_view` | Can view data | ✅ | ✅ | ✅ | ✅ | View all data in workspace |
| `data_view_own` | Can view own data | ✅ | ✅ | ✅ | ✅ | View only own created data |
| `data_create` | Can create data | ✅ | ✅ | ✅ | ❌ | Create new data entries |
| `data_edit` | Can edit data | ✅ | ✅ | ✅ | ❌ | Edit any data entry |
| `data_edit_own` | Can edit own data | ✅ | ✅ | ✅ | ❌ | Edit only own data |
| `data_delete` | Can delete data | ✅ | ✅ | ❌ | ❌ | Delete any data entry |
| `data_delete_own` | Can delete own data | ✅ | ✅ | ✅ | ❌ | Delete only own data |
| `data_export` | Can export data | ✅ | ✅ | ❌ | ❌ | Export data to CSV/Excel/PDF |
| `data_export_bulk` | Can bulk export | ✅ | ✅ | ❌ | ❌ | Export large datasets |
| `data_import` | Can import data | ✅ | ✅ | ❌ | ❌ | Import data from files |

**Notes:**
- "Own" permissions allow users to manage their created content
- Export permissions prevent data leakage
- Members can only delete their own entries

---

### 4. BILLING & SUBSCRIPTION PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `billing_view` | Can view billing | ✅ | ✅ | ❌ | ❌ | View billing info and invoices |
| `billing_history` | Can view history | ✅ | ✅ | ❌ | ❌ | View payment history |
| `billing_edit` | Can edit billing | ✅🔒 | ❌ | ❌ | ❌ | Update payment methods |
| `billing_manage` | Can manage subscription | ✅🔒 | ❌ | ❌ | ❌ | Change subscription plans |
| `billing_cancel` | Can cancel subscription | ✅🔒 | ❌ | ❌ | ❌ | Cancel workspace subscription |

**Notes:**
- Billing management restricted to Owner only
- Admins can view but not modify billing
- Subscription changes may affect workspace access

---

### 5. REPORTING PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `report_view` | Can view reports | ✅ | ✅ | ✅ | ✅ | View all reports |
| `report_view_basic` | Can view basic reports | ✅ | ✅ | ✅ | ✅ | View basic reports only |
| `report_create` | Can create reports | ✅ | ✅ | ❌ | ❌ | Create custom reports |
| `report_export` | Can export reports | ✅ | ✅ | ✅ | ❌ | Export reports to files |
| `report_schedule` | Can schedule reports | ✅ | ✅ | ❌ | ❌ | Schedule automated reports |

**Notes:**
- Members can view and export but not create reports
- Scheduled reports sent via email
- Basic reports = predefined dashboards

---

### 6. GIRVI (LOAN MANAGEMENT) PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `girvi_loan_view` | Can view loans | ✅ | ✅ | ✅ | ✅ | View loan details |
| `girvi_loan_create` | Can create loans | ✅ | ✅ | ✅ | ❌ | Create new loan entries |
| `girvi_loan_edit` | Can edit loans | ✅ | ✅ | ✅ | ❌ | Edit loan details |
| `girvi_loan_delete` | Can delete loans | ✅ | ✅ | ❌ | ❌ | Delete loan entries |
| `girvi_loan_approve` | Can approve loans | ✅ | ✅ | ❌ | ❌ | Approve loan applications |
| `girvi_loan_release` | Can release loans | ✅ | ✅ | ❌ | ❌ | Release completed loans |
| `girvi_loan_payment` | Can record payments | ✅ | ✅ | ✅ | ❌ | Record loan payments |
| `girvi_loan_bulk` | Can bulk operations | ✅ | ✅ | ❌ | ❌ | Bulk loan operations |
| `girvi_report_view` | Can view reports | ✅ | ✅ | ✅ | ✅ | View loan reports |

**Notes:**
- Loan approval requires Admin+
- Members can create and process payments
- Bulk operations for Admin+ only

---

### 7. DEA (ACCOUNTING) PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `dea_entry_view` | Can view entries | ✅ | ✅ | ✅ | ✅ | View accounting entries |
| `dea_entry_create` | Can create entries | ✅ | ✅ | ✅ | ❌ | Create journal entries |
| `dea_entry_edit` | Can edit entries | ✅ | ✅ | ✅ | ❌ | Edit accounting entries |
| `dea_entry_delete` | Can delete entries | ✅ | ✅ | ❌ | ❌ | Delete accounting entries |
| `dea_reconciliation` | Can reconcile | ✅ | ✅ | ❌ | ❌ | Reconcile accounts |
| `dea_close_period` | Can close periods | ✅ | ✅ | ❌ | ❌ | Close accounting periods |
| `dea_report_view` | Can view reports | ✅ | ✅ | ❌ | ✅ | View financial reports |
| `dea_report_export` | Can export reports | ✅ | ✅ | ❌ | ❌ | Export financial reports |

**Notes:**
- Period closure is irreversible - Admin+ only
- Reconciliation requires accounting knowledge
- Members can create daily entries

---

### 8. SALES PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `sales_invoice_view` | Can view invoices | ✅ | ✅ | ✅ | ✅ | View sales invoices |
| `sales_invoice_create` | Can create invoices | ✅ | ✅ | ✅ | ❌ | Create sales invoices |
| `sales_invoice_edit` | Can edit invoices | ✅ | ✅ | ✅ | ❌ | Edit sales invoices |
| `sales_invoice_delete` | Can delete invoices | ✅ | ✅ | ❌ | ❌ | Delete sales invoices |
| `sales_payment_record` | Can record payments | ✅ | ✅ | ✅ | ❌ | Record sales payments |
| `sales_discount_apply` | Can apply discounts | ✅ | ✅ | ❌ | ❌ | Apply discounts to invoices |
| `sales_report_view` | Can view reports | ✅ | ✅ | ❌ | ❌ | View sales analytics |

**Notes:**
- Members can create and edit invoices
- Discounts require Admin+ approval
- Deletion restricted to prevent audit issues

---

### 9. PURCHASE PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `purchase_order_view` | Can view orders | ✅ | ✅ | ✅ | ✅ | View purchase orders |
| `purchase_order_create` | Can create orders | ✅ | ✅ | ✅ | ❌ | Create purchase orders |
| `purchase_order_edit` | Can edit orders | ✅ | ✅ | ❌ | ❌ | Edit purchase orders |
| `purchase_order_delete` | Can delete orders | ✅ | ✅ | ❌ | ❌ | Delete purchase orders |
| `purchase_order_approve` | Can approve orders | ✅ | ✅ | ❌ | ❌ | Approve purchase orders |
| `purchase_report_view` | Can view reports | ✅ | ✅ | ❌ | ❌ | View purchase analytics |

**Notes:**
- Members can only create and view
- Approval workflow for Admin+
- Edit/delete restricted for audit trail

---

### 10. CONTACT PERMISSIONS

| Permission Codename | Name | Owner | Admin | Member | Viewer | Description |
|---------------------|------|:-----:|:-----:|:------:|:------:|-------------|
| `contact_view` | Can view contacts | ✅ | ✅ | ✅ | ✅ | View contact details |
| `contact_create` | Can create contacts | ✅ | ✅ | ✅ | ❌ | Create new contacts |
| `contact_edit` | Can edit contacts | ✅ | ✅ | ✅ | ❌ | Edit contact details |
| `contact_delete` | Can delete contacts | ✅ | ✅ | ❌ | ❌ | Delete contacts |
| `contact_import` | Can import contacts | ✅ | ✅ | ❌ | ❌ | Import from CSV/Excel |
| `contact_export` | Can export contacts | ✅ | ✅ | ❌ | ❌ | Export to CSV/Excel |

**Notes:**
- Members have full CRUD on contacts
- Import/export for Admin+ only
- Contacts shared across workspace

---

## Permission Hierarchies

### Implicit Permission Rules

1. **Owner Inherits All:** Owner always has every permission
2. **Admin > Member > Viewer:** Higher roles inherit lower role permissions (configurable)
3. **Own Data Access:** If user can't edit all data, they can edit own data
4. **View Required for Actions:** Must have `view` permission to have `edit`/`delete`

### Permission Dependencies

```
workspace_delete
    ↓ requires
workspace_edit
    ↓ requires
workspace_view


data_delete
    ↓ requires
data_edit
    ↓ requires
data_view


team_change_role
    ↓ requires
team_edit
    ↓ requires
team_view
```

### Special Rules

1. **Owner Transfer:**
   - Requires `workspace_transfer` permission
   - Creates audit log entry
   - Updates CompanyOwnership model
   - Previous owner becomes Admin

2. **Admin Invitation:**
   - Requires `team_invite_admin` permission
   - Only Owner can promote to Admin
   - Sends invitation email
   - Logs action

3. **Subscription Cancellation:**
   - Requires `billing_cancel` permission
   - Grace period before data deletion
   - Notification sent to all admins
   - Workspace archived, not deleted

---

## Implementation Guide

### 1. In Views (Function-Based)

```python
from apps.orgs.decorators_v2 import permission_required

@permission_required('girvi_loan_create')
def create_loan(request):
    # User has girvi_loan_create permission
    ...
```

### 2. In Views (Class-Based)

```python
from django.contrib.auth.mixins import PermissionRequiredMixin
from apps.orgs.mixins import WorkspacePermissionMixin

class CreateLoanView(WorkspacePermissionMixin, CreateView):
    permission_required = 'girvi_loan_create'
    ...
```

### 3. In Templates

```django
{% if 'data_export' in user_permissions %}
    <a href="{% url 'export_data' %}" class="btn btn-primary">
        Export Data
    </a>
{% else %}
    <span class="btn btn-disabled" title="Requires Export permission">
        Export Data 🔒
    </span>
{% endif %}
```

### 4. Programmatically

```python
from apps.orgs.models import Membership

# Check if user has permission
membership = Membership.objects.get(user=request.user, company=workspace)
has_perm = membership.role.permissions.filter(codename='data_export').exists()

if has_perm:
    # Export data
    ...
```

### 5. Using Guardian (Object-Level)

```python
from guardian.shortcuts import assign_perm, get_perms

# Assign object-level permission
assign_perm('change_customer', user, customer_instance)

# Check object-level permission
perms = get_perms(user, customer_instance)
if 'change_customer' in perms:
    # User can edit this specific customer
    ...
```

---

## Usage Examples

### Example 1: Loan Creation

```python
# View
@permission_required('girvi_loan_create')
@permission_required('contact_view')  # Need to see customers
def create_loan(request):
    if request.method == 'POST':
        # Create loan
        loan = Loan.objects.create(...)
        
        # Log action
        AuditLog.log(
            'DATA_CREATE',
            user=request.user,
            company=request.user.profile.workspace,
            description=f'Created loan {loan.id}',
            content_object=loan,
            request=request
        )
        
        return redirect('loan_detail', loan.id)
    
    return render(request, 'girvi/loan_form.html')
```

### Example 2: Team Invitation

```python
# View - Only Owner can invite Admins
@permission_required('team_invite')
def invite_member(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    
    if request.method == 'POST':
        form = InvitationForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data['role']
            
            # Additional check for Admin invitation
            if role.name == 'Admin':
                membership = Membership.objects.get(
                    user=request.user,
                    company=company
                )
                if membership.role.name != 'Owner':
                    messages.error(request, 'Only Owner can invite Admins')
                    return redirect('company_detail', company_id)
            
            # Create invitation
            invitation = form.save()
            invitation.send_invitation(request)
            
            # Log
            AuditLog.log('MEMBER_INVITE', user=request.user, company=company,
                        description=f'Invited {invitation.email} as {role.name}',
                        request=request)
            
            return redirect('company_detail', company_id)
    
    return render(request, 'invitation_form.html', {'form': form})
```

### Example 3: Conditional UI

```django
<!-- company_detail.html -->
<div class="team-actions">
    {% if 'team_invite' in user_permissions %}
        <a href="{% url 'invite_member' company.id %}" class="btn btn-success">
            <i class="bi bi-person-plus"></i> Invite Member
        </a>
    {% endif %}
    
    {% if 'team_change_role' in user_permissions %}
        <button class="btn btn-warning" data-bs-toggle="modal" data-bs-target="#changeRoleModal">
            <i class="bi bi-shield"></i> Change Roles
        </button>
    {% endif %}
    
    {% if 'workspace_settings' in user_permissions %}
        <a href="{% url 'workspace_settings' %}" class="btn btn-secondary">
            <i class="bi bi-gear"></i> Settings
        </a>
    {% endif %}
</div>
```

### Example 4: Data Export with Permission

```python
@permission_required('data_export')
@audit_log('DATA_EXPORT', 'Exported customer data')
def export_customers(request):
    workspace = request.user.profile.workspace
    
    # Check if bulk export is allowed
    membership = Membership.objects.get(user=request.user, company=workspace)
    can_bulk = membership.role.permissions.filter(
        codename='data_export_bulk'
    ).exists()
    
    if can_bulk:
        customers = Customer.objects.all()  # All customers
    else:
        customers = Customer.objects.filter(
            created_by=request.user
        )  # Only own customers
    
    # Generate CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="customers.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone'])
    for customer in customers:
        writer.writerow([customer.name, customer.email, customer.phone])
    
    return response
```

---

## Permission Testing

### Unit Tests

```python
# apps/orgs/tests/test_permissions.py
from django.test import TestCase
from apps.orgs.models import Company, Role, Membership
from accounts.models import CustomUser

class PermissionMatrixTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Test Company')
        self.owner_role = Role.objects.get(name='Owner')
        self.admin_role = Role.objects.get(name='Admin')
        self.member_role = Role.objects.get(name='Member')
        
        self.owner = CustomUser.objects.create_user(
            email='owner@test.com', password='test123'
        )
        self.admin = CustomUser.objects.create_user(
            email='admin@test.com', password='test123'
        )
        
        Membership.objects.create(
            user=self.owner, company=self.company, role=self.owner_role
        )
        Membership.objects.create(
            user=self.admin, company=self.company, role=self.admin_role
        )
    
    def test_owner_has_all_permissions(self):
        """Owner should have all 71 permissions"""
        membership = Membership.objects.get(user=self.owner, company=self.company)
        perm_count = membership.role.permissions.count()
        self.assertEqual(perm_count, 71)
    
    def test_admin_cannot_delete_workspace(self):
        """Admin should not have workspace_delete permission"""
        membership = Membership.objects.get(user=self.admin, company=self.company)
        has_delete = membership.role.permissions.filter(
            codename='workspace_delete'
        ).exists()
        self.assertFalse(has_delete)
    
    def test_member_can_create_data(self):
        """Member should have data_create permission"""
        member = CustomUser.objects.create_user(
            email='member@test.com', password='test123'
        )
        Membership.objects.create(
            user=member, company=self.company, role=self.member_role
        )
        membership = Membership.objects.get(user=member, company=self.company)
        
        has_create = membership.role.permissions.filter(
            codename='data_create'
        ).exists()
        self.assertTrue(has_create)
```

---

## Migration Path

To implement this permission matrix:

1. ✅ **Install django-guardian:** `pip install django-guardian`
2. ✅ **Run setup command:** `python manage.py setup_permissions`
3. ✅ **Verify roles created:** Check admin panel
4. ✅ **Update views:** Add permission decorators
5. ✅ **Update templates:** Add permission checks
6. ✅ **Test thoroughly:** Run permission test suite

---

## Maintenance & Updates

### Adding New Permissions

1. Add to `apps/orgs/permissions.py` in appropriate category
2. Assign to roles in `RolePermissions` class
3. Run `python manage.py setup_permissions --reset`
4. Update this documentation
5. Communicate to team

### Modifying Roles

1. Update `RolePermissions` class
2. Run setup command
3. Test affected views
4. Update documentation
5. Create migration if schema changes

### Custom Roles

If you need custom roles beyond the 4 defaults:

```python
# Create custom role
accountant_role = Role.objects.create(name='Accountant')

# Assign specific permissions
perms = Permission.objects.filter(codename__startswith='dea_')
accountant_role.permissions.set(perms)

# Assign to user
Membership.objects.create(
    user=user,
    company=company,
    role=accountant_role
)
```

---

## Appendix: Quick Reference

### All Permission Codenames (Alphabetical)

```
billing_cancel
billing_edit
billing_history
billing_manage
billing_view
contact_create
contact_delete
contact_edit
contact_export
contact_import
contact_view
data_create
data_delete
data_delete_own
data_edit
data_edit_own
data_export
data_export_bulk
data_import
data_view
data_view_own
dea_close_period
dea_entry_create
dea_entry_delete
dea_entry_edit
dea_entry_view
dea_reconciliation
dea_report_export
dea_report_view
girvi_loan_approve
girvi_loan_bulk
girvi_loan_create
girvi_loan_delete
girvi_loan_edit
girvi_loan_payment
girvi_loan_release
girvi_loan_view
girvi_report_view
purchase_order_approve
purchase_order_create
purchase_order_delete
purchase_order_edit
purchase_order_view
purchase_report_view
report_create
report_export
report_schedule
report_view
report_view_basic
sales_discount_apply
sales_invoice_create
sales_invoice_delete
sales_invoice_edit
sales_invoice_view
sales_payment_record
sales_report_view
team_change_role
team_edit
team_invite
team_invite_admin
team_list
team_remove
team_view
team_view_activity
workspace_archive
workspace_delete
workspace_edit
workspace_list
workspace_settings
workspace_transfer
workspace_view
```

### Permission Count by Role

| Role | Permission Count | Percentage |
|------|------------------|------------|
| Owner | 71 | 100% |
| Admin | 55 | 77% |
| Member | 35 | 49% |
| Viewer | 16 | 23% |

---

**Document End** | For questions or updates, contact the development team.
