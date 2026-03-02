# Phase 0: Security Foundation - Implementation Checklist

## Overview
This phase establishes the security foundation for the multi-tenant enhancement plan. Must be completed before proceeding to user-facing features.

**Duration:** 2-3 days  
**Priority:** 🔴 CRITICAL  
**Dependencies:** None  
**Blocks:** All other phases

---

## Pre-Implementation Checklist

- [ ] Backup current database
- [ ] Create feature branch: `git checkout -b feature/phase-0-security-foundation`
- [ ] Document current permission checks (baseline)
- [ ] Review existing Role and Permission usage
- [ ] Set up test environment

---

## Task 1: Install and Configure django-guardian (2 hours)

### 1.1 Installation
- [ ] Add `django-guardian==2.4.0` to requirements.txt
- [ ] Run `pip install django-guardian`
- [ ] Add `'guardian'` to `INSTALLED_APPS` in settings
- [ ] Add `'guardian.backends.ObjectPermissionBackend'` to `AUTHENTICATION_BACKENDS`
- [ ] Run migrations: `python manage.py migrate`

### 1.2 Configuration
```python
# django_project/settings/base.py

INSTALLED_APPS = [
    # ... existing apps
    'guardian',
    # ... rest of apps
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',  # Default
    'guardian.backends.ObjectPermissionBackend',  # Guardian
)

# Guardian settings
ANONYMOUS_USER_NAME = None
GUARDIAN_RENDER_403 = True
GUARDIAN_TEMPLATE_403 = '403.html'
```

### 1.3 Verification
- [ ] Test import: `python manage.py shell` → `from guardian.shortcuts import assign_perm`
- [ ] Check migrations applied: `python manage.py showmigrations guardian`
- [ ] Verify backend works: Create test permission assignment

**Files Modified:**
- `requirements.txt`
- `django_project/settings/base.py`

**Testing Command:**
```bash
python manage.py shell
>>> from guardian.shortcuts import assign_perm, get_perms
>>> from apps.orgs.models import Company
>>> from accounts.models import CustomUser
>>> # Test will be run after permission setup
```

---

## Task 2: Define Permission Matrix (3 hours)

### 2.1 Create Permission Matrix Document
- [ ] Create `apps/orgs/docs/PERMISSION_MATRIX.md`
- [ ] Define all permissions across modules
- [ ] Map permissions to roles
- [ ] Document permission hierarchies
- [ ] Add examples for each permission

### 2.2 Create Permissions Configuration File
- [ ] Create `apps/orgs/permissions.py`
- [ ] Define all permission constants
- [ ] Create permission groups by module
- [ ] Add role-to-permission mappings
- [ ] Document permission descriptions

**File to Create:** `apps/orgs/permissions.py`

```python
"""
Permission definitions for the orgs app and multi-tenant system.
This file defines all permissions, their groupings, and role mappings.
"""

from typing import Dict, List, Tuple

# Permission format: (codename, name, description)
PermissionDef = Tuple[str, str, str]

# ============================================================================
# WORKSPACE-LEVEL PERMISSIONS
# ============================================================================

WORKSPACE_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ('workspace_view', 'Can view workspace', 'View workspace details and settings'),
    ('workspace_list', 'Can list workspaces', 'View list of all accessible workspaces'),
    
    # Edit Permissions
    ('workspace_edit', 'Can edit workspace', 'Edit workspace settings and configuration'),
    ('workspace_settings', 'Can manage workspace settings', 'Manage advanced workspace settings'),
    
    # Delete Permissions
    ('workspace_delete', 'Can delete workspace', 'Permanently delete workspace'),
    ('workspace_archive', 'Can archive workspace', 'Soft delete/archive workspace'),
    
    # Transfer Permissions
    ('workspace_transfer', 'Can transfer ownership', 'Transfer workspace ownership to another user'),
]

# ============================================================================
# TEAM MANAGEMENT PERMISSIONS
# ============================================================================

TEAM_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ('team_view', 'Can view team', 'View team members and their roles'),
    ('team_list', 'Can list team members', 'View list of all team members'),
    
    # Invite Permissions
    ('team_invite', 'Can invite members', 'Send invitations to new team members'),
    ('team_invite_admin', 'Can invite admins', 'Send invitations with admin role'),
    
    # Manage Permissions
    ('team_edit', 'Can edit team member', 'Edit team member details'),
    ('team_remove', 'Can remove members', 'Remove members from workspace'),
    ('team_change_role', 'Can change roles', 'Change team member roles'),
    
    # Advanced Permissions
    ('team_view_activity', 'Can view team activity', 'View team member activity logs'),
]

# ============================================================================
# DATA & CONTENT PERMISSIONS
# ============================================================================

DATA_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ('data_view', 'Can view data', 'View all data in workspace'),
    ('data_view_own', 'Can view own data', 'View only own created data'),
    
    # Create Permissions
    ('data_create', 'Can create data', 'Create new data entries'),
    
    # Edit Permissions
    ('data_edit', 'Can edit data', 'Edit any data entry'),
    ('data_edit_own', 'Can edit own data', 'Edit only own created data'),
    
    # Delete Permissions
    ('data_delete', 'Can delete data', 'Delete any data entry'),
    ('data_delete_own', 'Can delete own data', 'Delete only own created data'),
    
    # Export Permissions
    ('data_export', 'Can export data', 'Export data to CSV/Excel/PDF'),
    ('data_export_bulk', 'Can bulk export', 'Export large datasets'),
    
    # Import Permissions
    ('data_import', 'Can import data', 'Import data from CSV/Excel'),
]

# ============================================================================
# BILLING & SUBSCRIPTION PERMISSIONS
# ============================================================================

BILLING_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ('billing_view', 'Can view billing', 'View billing information and invoices'),
    ('billing_history', 'Can view billing history', 'View payment history'),
    
    # Edit Permissions
    ('billing_edit', 'Can edit billing', 'Update payment methods and billing info'),
    ('billing_manage', 'Can manage subscription', 'Change subscription plans'),
    
    # Cancel Permissions
    ('billing_cancel', 'Can cancel subscription', 'Cancel workspace subscription'),
]

# ============================================================================
# REPORTING PERMISSIONS
# ============================================================================

REPORT_PERMISSIONS: List[PermissionDef] = [
    # View Permissions
    ('report_view', 'Can view reports', 'View all reports'),
    ('report_view_basic', 'Can view basic reports', 'View basic reports only'),
    
    # Create Permissions
    ('report_create', 'Can create reports', 'Create custom reports'),
    
    # Export Permissions
    ('report_export', 'Can export reports', 'Export reports to various formats'),
    ('report_schedule', 'Can schedule reports', 'Schedule automated report generation'),
]

# ============================================================================
# FEATURE-SPECIFIC PERMISSIONS (GIRVI MODULE)
# ============================================================================

GIRVI_PERMISSIONS: List[PermissionDef] = [
    # Loan Management
    ('girvi_loan_view', 'Can view loans', 'View loan details'),
    ('girvi_loan_create', 'Can create loans', 'Create new loan entries'),
    ('girvi_loan_edit', 'Can edit loans', 'Edit loan details'),
    ('girvi_loan_delete', 'Can delete loans', 'Delete loan entries'),
    
    # Loan Operations
    ('girvi_loan_approve', 'Can approve loans', 'Approve loan applications'),
    ('girvi_loan_release', 'Can release loans', 'Release completed loans'),
    ('girvi_loan_payment', 'Can record payments', 'Record loan payments'),
    
    # Advanced Features
    ('girvi_loan_bulk', 'Can bulk operations', 'Perform bulk loan operations'),
    ('girvi_report_view', 'Can view loan reports', 'View loan reports and analytics'),
]

# ============================================================================
# FEATURE-SPECIFIC PERMISSIONS (DEA MODULE - Accounting)
# ============================================================================

DEA_PERMISSIONS: List[PermissionDef] = [
    # Journal Entries
    ('dea_entry_view', 'Can view entries', 'View accounting entries'),
    ('dea_entry_create', 'Can create entries', 'Create journal entries'),
    ('dea_entry_edit', 'Can edit entries', 'Edit accounting entries'),
    ('dea_entry_delete', 'Can delete entries', 'Delete accounting entries'),
    
    # Financial Operations
    ('dea_reconciliation', 'Can reconcile accounts', 'Perform account reconciliation'),
    ('dea_close_period', 'Can close periods', 'Close accounting periods'),
    
    # Reports
    ('dea_report_view', 'Can view financial reports', 'View financial reports'),
    ('dea_report_export', 'Can export financial reports', 'Export financial reports'),
]

# ============================================================================
# FEATURE-SPECIFIC PERMISSIONS (SALES MODULE)
# ============================================================================

SALES_PERMISSIONS: List[PermissionDef] = [
    # Invoice Management
    ('sales_invoice_view', 'Can view invoices', 'View sales invoices'),
    ('sales_invoice_create', 'Can create invoices', 'Create sales invoices'),
    ('sales_invoice_edit', 'Can edit invoices', 'Edit sales invoices'),
    ('sales_invoice_delete', 'Can delete invoices', 'Delete sales invoices'),
    
    # Payment Operations
    ('sales_payment_record', 'Can record payments', 'Record sales payments'),
    ('sales_discount_apply', 'Can apply discounts', 'Apply discounts to invoices'),
    
    # Reports
    ('sales_report_view', 'Can view sales reports', 'View sales analytics'),
]

# ============================================================================
# FEATURE-SPECIFIC PERMISSIONS (PURCHASE MODULE)
# ============================================================================

PURCHASE_PERMISSIONS: List[PermissionDef] = [
    # Purchase Management
    ('purchase_order_view', 'Can view purchase orders', 'View purchase orders'),
    ('purchase_order_create', 'Can create purchase orders', 'Create purchase orders'),
    ('purchase_order_edit', 'Can edit purchase orders', 'Edit purchase orders'),
    ('purchase_order_delete', 'Can delete purchase orders', 'Delete purchase orders'),
    
    # Approval
    ('purchase_order_approve', 'Can approve purchases', 'Approve purchase orders'),
    
    # Reports
    ('purchase_report_view', 'Can view purchase reports', 'View purchase analytics'),
]

# ============================================================================
# FEATURE-SPECIFIC PERMISSIONS (CONTACT MODULE)
# ============================================================================

CONTACT_PERMISSIONS: List[PermissionDef] = [
    # Contact Management
    ('contact_view', 'Can view contacts', 'View contact details'),
    ('contact_create', 'Can create contacts', 'Create new contacts'),
    ('contact_edit', 'Can edit contacts', 'Edit contact details'),
    ('contact_delete', 'Can delete contacts', 'Delete contacts'),
    
    # Bulk Operations
    ('contact_import', 'Can import contacts', 'Import contacts from files'),
    ('contact_export', 'Can export contacts', 'Export contacts to files'),
]

# ============================================================================
# ALL PERMISSIONS COMBINED
# ============================================================================

ALL_PERMISSIONS: List[PermissionDef] = (
    WORKSPACE_PERMISSIONS +
    TEAM_PERMISSIONS +
    DATA_PERMISSIONS +
    BILLING_PERMISSIONS +
    REPORT_PERMISSIONS +
    GIRVI_PERMISSIONS +
    DEA_PERMISSIONS +
    SALES_PERMISSIONS +
    PURCHASE_PERMISSIONS +
    CONTACT_PERMISSIONS
)

# ============================================================================
# ROLE DEFINITIONS
# ============================================================================

class RolePermissions:
    """Maps roles to their default permissions"""
    
    OWNER = [
        # Workspace - Full Access
        'workspace_view', 'workspace_list', 'workspace_edit', 'workspace_settings',
        'workspace_delete', 'workspace_archive', 'workspace_transfer',
        
        # Team - Full Access
        'team_view', 'team_list', 'team_invite', 'team_invite_admin',
        'team_edit', 'team_remove', 'team_change_role', 'team_view_activity',
        
        # Data - Full Access
        'data_view', 'data_view_own', 'data_create', 'data_edit', 'data_edit_own',
        'data_delete', 'data_delete_own', 'data_export', 'data_export_bulk', 'data_import',
        
        # Billing - Full Access
        'billing_view', 'billing_history', 'billing_edit', 'billing_manage', 'billing_cancel',
        
        # Reports - Full Access
        'report_view', 'report_view_basic', 'report_create', 'report_export', 'report_schedule',
        
        # Girvi - Full Access
        'girvi_loan_view', 'girvi_loan_create', 'girvi_loan_edit', 'girvi_loan_delete',
        'girvi_loan_approve', 'girvi_loan_release', 'girvi_loan_payment', 'girvi_loan_bulk',
        'girvi_report_view',
        
        # DEA - Full Access
        'dea_entry_view', 'dea_entry_create', 'dea_entry_edit', 'dea_entry_delete',
        'dea_reconciliation', 'dea_close_period', 'dea_report_view', 'dea_report_export',
        
        # Sales - Full Access
        'sales_invoice_view', 'sales_invoice_create', 'sales_invoice_edit', 'sales_invoice_delete',
        'sales_payment_record', 'sales_discount_apply', 'sales_report_view',
        
        # Purchase - Full Access
        'purchase_order_view', 'purchase_order_create', 'purchase_order_edit', 'purchase_order_delete',
        'purchase_order_approve', 'purchase_report_view',
        
        # Contact - Full Access
        'contact_view', 'contact_create', 'contact_edit', 'contact_delete',
        'contact_import', 'contact_export',
    ]
    
    ADMIN = [
        # Workspace - Edit only
        'workspace_view', 'workspace_list', 'workspace_edit', 'workspace_settings',
        
        # Team - Manage but not remove admins
        'team_view', 'team_list', 'team_invite', 'team_edit', 'team_remove', 'team_change_role',
        
        # Data - Full Access
        'data_view', 'data_view_own', 'data_create', 'data_edit', 'data_edit_own',
        'data_delete', 'data_delete_own', 'data_export', 'data_export_bulk', 'data_import',
        
        # Billing - View only
        'billing_view', 'billing_history',
        
        # Reports - Full Access
        'report_view', 'report_view_basic', 'report_create', 'report_export', 'report_schedule',
        
        # Girvi - Full operational access
        'girvi_loan_view', 'girvi_loan_create', 'girvi_loan_edit', 'girvi_loan_delete',
        'girvi_loan_approve', 'girvi_loan_release', 'girvi_loan_payment', 'girvi_loan_bulk',
        'girvi_report_view',
        
        # DEA - Full operational access
        'dea_entry_view', 'dea_entry_create', 'dea_entry_edit', 'dea_entry_delete',
        'dea_reconciliation', 'dea_close_period', 'dea_report_view', 'dea_report_export',
        
        # Sales - Full operational access
        'sales_invoice_view', 'sales_invoice_create', 'sales_invoice_edit', 'sales_invoice_delete',
        'sales_payment_record', 'sales_discount_apply', 'sales_report_view',
        
        # Purchase - Full operational access including approval
        'purchase_order_view', 'purchase_order_create', 'purchase_order_edit', 'purchase_order_delete',
        'purchase_order_approve', 'purchase_report_view',
        
        # Contact - Full Access
        'contact_view', 'contact_create', 'contact_edit', 'contact_delete',
        'contact_import', 'contact_export',
    ]
    
    MEMBER = [
        # Workspace - View only
        'workspace_view', 'workspace_list',
        
        # Team - View only
        'team_view', 'team_list',
        
        # Data - Standard access
        'data_view', 'data_view_own', 'data_create', 'data_edit', 'data_edit_own',
        'data_delete_own',
        
        # Reports - Basic access
        'report_view', 'report_view_basic', 'report_export',
        
        # Girvi - Basic operations
        'girvi_loan_view', 'girvi_loan_create', 'girvi_loan_edit',
        'girvi_loan_payment', 'girvi_report_view',
        
        # DEA - Basic operations
        'dea_entry_view', 'dea_entry_create', 'dea_entry_edit',
        
        # Sales - Basic operations
        'sales_invoice_view', 'sales_invoice_create', 'sales_invoice_edit',
        'sales_payment_record',
        
        # Purchase - View and create only
        'purchase_order_view', 'purchase_order_create',
        
        # Contact - Full Access
        'contact_view', 'contact_create', 'contact_edit',
    ]
    
    VIEWER = [
        # Workspace - View only
        'workspace_view', 'workspace_list',
        
        # Team - View only
        'team_view', 'team_list',
        
        # Data - View only
        'data_view', 'data_view_own',
        
        # Reports - View only
        'report_view', 'report_view_basic',
        
        # All modules - View only
        'girvi_loan_view', 'girvi_report_view',
        'dea_entry_view',
        'sales_invoice_view',
        'purchase_order_view',
        'contact_view',
    ]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_all_permission_codenames() -> List[str]:
    """Get list of all permission codenames"""
    return [perm[0] for perm in ALL_PERMISSIONS]

def get_permissions_for_role(role_name: str) -> List[str]:
    """Get list of permissions for a given role"""
    role_map = {
        'Owner': RolePermissions.OWNER,
        'Admin': RolePermissions.ADMIN,
        'Member': RolePermissions.MEMBER,
        'Viewer': RolePermissions.VIEWER,
    }
    return role_map.get(role_name, [])

def get_permission_display_name(codename: str) -> str:
    """Get display name for a permission codename"""
    for perm in ALL_PERMISSIONS:
        if perm[0] == codename:
            return perm[1]
    return codename

def get_permission_description(codename: str) -> str:
    """Get description for a permission codename"""
    for perm in ALL_PERMISSIONS:
        if perm[0] == codename:
            return perm[2]
    return ""

def get_permissions_by_category() -> Dict[str, List[PermissionDef]]:
    """Get permissions organized by category"""
    return {
        'Workspace': WORKSPACE_PERMISSIONS,
        'Team': TEAM_PERMISSIONS,
        'Data': DATA_PERMISSIONS,
        'Billing': BILLING_PERMISSIONS,
        'Reports': REPORT_PERMISSIONS,
        'Girvi (Loans)': GIRVI_PERMISSIONS,
        'DEA (Accounting)': DEA_PERMISSIONS,
        'Sales': SALES_PERMISSIONS,
        'Purchase': PURCHASE_PERMISSIONS,
        'Contacts': CONTACT_PERMISSIONS,
    }
```

### 2.3 Update Role Model to Support Permissions
- [ ] Create migration to add default roles
- [ ] Create data migration to populate Role permissions
- [ ] Verify Role.permissions relationship works

**Testing:**
- [ ] Verify all permissions are created
- [ ] Verify roles have correct permissions
- [ ] Test permission query: `Role.objects.get(name='Admin').permissions.all()`

---

## Task 3: Create Audit Logging Model (2 hours)

### 3.1 Create AuditLog Model
- [ ] Create `apps/orgs/audit.py`
- [ ] Define AuditLog model with all required fields
- [ ] Add indexes for performance
- [ ] Create model manager for common queries

**File to Create:** `apps/orgs/audit.py`

```python
"""
Audit logging system for tracking security-sensitive operations.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AuditLogManager(models.Manager):
    """Custom manager for AuditLog with common query methods"""
    
    def for_user(self, user):
        """Get all audit logs for a specific user"""
        return self.filter(user=user)
    
    def for_company(self, company):
        """Get all audit logs for a specific company"""
        return self.filter(company=company)
    
    def for_action(self, action):
        """Get all audit logs for a specific action type"""
        return self.filter(action=action)
    
    def security_events(self):
        """Get security-related events"""
        return self.filter(
            action__in=[
                'LOGIN', 'LOGOUT', 'LOGIN_FAILED',
                'PERMISSION_DENIED', 'UNAUTHORIZED_ACCESS'
            ]
        )
    
    def recent(self, days=7):
        """Get recent audit logs"""
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(timestamp__gte=cutoff)


class AuditLog(models.Model):
    """
    Comprehensive audit logging for security and compliance.
    Tracks all sensitive operations across the application.
    """
    
    # Action types
    ACTION_CHOICES = [
        # Authentication
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('LOGIN_FAILED', 'Login Failed'),
        ('PASSWORD_CHANGE', 'Password Changed'),
        ('PASSWORD_RESET', 'Password Reset'),
        
        # Company/Workspace
        ('COMPANY_CREATE', 'Company Created'),
        ('COMPANY_UPDATE', 'Company Updated'),
        ('COMPANY_DELETE', 'Company Deleted'),
        ('COMPANY_RESTORE', 'Company Restored'),
        
        # Team Management
        ('MEMBER_INVITE', 'Member Invited'),
        ('MEMBER_JOIN', 'Member Joined'),
        ('MEMBER_REMOVE', 'Member Removed'),
        ('MEMBER_ROLE_CHANGE', 'Member Role Changed'),
        
        # Permissions & Security
        ('PERMISSION_GRANT', 'Permission Granted'),
        ('PERMISSION_REVOKE', 'Permission Revoked'),
        ('PERMISSION_DENIED', 'Permission Denied'),
        ('UNAUTHORIZED_ACCESS', 'Unauthorized Access Attempt'),
        
        # Data Operations
        ('DATA_CREATE', 'Data Created'),
        ('DATA_UPDATE', 'Data Updated'),
        ('DATA_DELETE', 'Data Deleted'),
        ('DATA_EXPORT', 'Data Exported'),
        ('DATA_IMPORT', 'Data Imported'),
        
        # Billing
        ('BILLING_UPDATE', 'Billing Updated'),
        ('SUBSCRIPTION_CHANGE', 'Subscription Changed'),
        ('SUBSCRIPTION_CANCEL', 'Subscription Cancelled'),
        ('PAYMENT_SUCCESS', 'Payment Successful'),
        ('PAYMENT_FAILED', 'Payment Failed'),
        
        # Settings
        ('SETTINGS_UPDATE', 'Settings Updated'),
        ('PREFERENCES_UPDATE', 'Preferences Updated'),
        
        # Ownership
        ('OWNERSHIP_TRANSFER', 'Ownership Transferred'),
    ]
    
    # Core fields
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('User'),
        help_text=_('User who performed the action')
    )
    
    company = models.ForeignKey(
        'orgs.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('Company'),
        help_text=_('Company context for the action')
    )
    
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name=_('Action'),
        db_index=True
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Timestamp'),
        db_index=True
    )
    
    # Object tracking (for generic relations)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Content Type')
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Object ID')
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Request metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address')
    )
    user_agent = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('User Agent')
    )
    
    # Details
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Human-readable description of the action')
    )
    
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Data'),
        help_text=_('JSON data with additional context')
    )
    
    # Result
    success = models.BooleanField(
        default=True,
        verbose_name=_('Success'),
        help_text=_('Whether the action was successful')
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message'),
        help_text=_('Error message if action failed')
    )
    
    objects = AuditLogManager()
    
    class Meta:
        verbose_name = _('Audit Log')
        verbose_name_plural = _('Audit Logs')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['company', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} by {self.user} at {self.timestamp}"
    
    @staticmethod
    def log(action, user=None, company=None, description='', data=None, 
            request=None, content_object=None, success=True, error_message=''):
        """
        Convenience method to create audit log entries.
        
        Usage:
            AuditLog.log('COMPANY_CREATE', user=request.user, company=company,
                        description='Created new company', request=request)
        """
        log_data = {
            'action': action,
            'user': user,
            'company': company,
            'description': description,
            'data': data or {},
            'success': success,
            'error_message': error_message,
        }
        
        # Extract request metadata
        if request:
            log_data['ip_address'] = get_client_ip(request)
            log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:255]
        
        # Add generic foreign key if object provided
        if content_object:
            log_data['content_object'] = content_object
        
        return AuditLog.objects.create(**log_data)


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================================================
# DECORATOR FOR AUTOMATIC AUDIT LOGGING
# ============================================================================

from functools import wraps

def audit_log(action, description='', log_args=False):
    """
    Decorator to automatically log function calls.
    
    Usage:
        @audit_log('COMPANY_CREATE', 'Company creation')
        def create_company(request, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            user = None
            company = None
            
            # Try to extract request from args
            for arg in args:
                if hasattr(arg, 'user') and hasattr(arg, 'META'):
                    request = arg
                    user = request.user if request.user.is_authenticated else None
                    if hasattr(user, 'profile') and user.profile.workspace:
                        company = user.profile.workspace
                    break
            
            # Execute the function
            try:
                result = func(*args, **kwargs)
                
                # Log success
                log_data = {}
                if log_args:
                    log_data['args'] = str(args)
                    log_data['kwargs'] = str(kwargs)
                
                AuditLog.log(
                    action=action,
                    user=user,
                    company=company,
                    description=description,
                    data=log_data,
                    request=request,
                    success=True
                )
                
                return result
                
            except Exception as e:
                # Log failure
                AuditLog.log(
                    action=action,
                    user=user,
                    company=company,
                    description=description,
                    request=request,
                    success=False,
                    error_message=str(e)
                )
                raise
        
        return wrapper
    return decorator
```

### 3.2 Create Migration
- [ ] Run `python manage.py makemigrations orgs`
- [ ] Review migration file
- [ ] Run `python manage.py migrate orgs`
- [ ] Verify table created: Check in database

### 3.3 Add Audit Logging to Admin
- [ ] Update `apps/orgs/admin.py` to register AuditLog
- [ ] Add filters for action, user, company, timestamp
- [ ] Make fields read-only
- [ ] Add search capabilities

**Testing:**
- [ ] Create test audit log entry
- [ ] Verify it appears in admin
- [ ] Test filtering and search
- [ ] Test `AuditLog.log()` convenience method

---

## Task 4: Fix Middleware Authorization (3 hours)

### 4.1 Deep Dive: Current Middleware Issues

**Current Flow:**
```
User authenticated → Check workspace → Set tenant → DONE
                                           ↓
                                    NO MEMBERSHIP CHECK!
```

**Attack Scenario:**
```python
# Attacker can do this:
user = User.objects.get(email='attacker@example.com')
victim_company = Company.objects.get(name='victim_company')
user.profile.workspace = victim_company  # No validation!
user.profile.save()

# Next request: Attacker gains full access to victim's data
```

### 4.2 Create New Middleware with Validation
- [ ] Create `apps/orgs/middleware_v2.py` (new file)
- [ ] Implement membership validation
- [ ] Add subscription status check
- [ ] Add audit logging for access attempts
- [ ] Handle edge cases (suspended accounts, expired subscriptions)

**File to Create:** `apps/orgs/middleware_v2.py`

```python
"""
Enhanced WorkspaceMiddleware with security validation.
Replaces the existing middleware with proper authorization checks.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import DisallowedHost, PermissionDenied
from django.db import connection
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django_tenants.utils import get_public_schema_name

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, Membership

logger = logging.getLogger(__name__)


class SecureWorkspaceMiddleware(MiddlewareMixin):
    """
    Enhanced middleware that validates workspace access before setting tenant context.
    
    Security Features:
    1. Validates user membership before granting workspace access
    2. Checks subscription status (if subscriptions app exists)
    3. Logs all access attempts
    4. Handles suspended/deleted companies
    5. Prevents unauthorized tenant context switching
    """
    
    # URLs that don't require workspace validation
    EXEMPT_URLS = [
        '/accounts/',
        '/admin/',
        '/static/',
        '/media/',
        '/__debug__/',
    ]
    
    # URLs that explicitly require workspace
    WORKSPACE_REQUIRED_URLS = [
        '/girvi/',
        '/dea/',
        '/sales/',
        '/purchase/',
        '/contact/',
        '/product/',
        '/rates/',
    ]
    
    def process_request(self, request):
        """Process incoming request and set tenant context securely"""
        
        # Skip for non-authenticated users on exempt URLs
        if not request.user.is_authenticated:
            connection.set_schema_to_public()
            return None
        
        # Check if URL is exempt from workspace requirements
        if self._is_exempt_url(request.path):
            connection.set_schema_to_public()
            return None
        
        # Get user's workspace preference
        workspace = self._get_user_workspace(request.user)
        
        # If no workspace set and URL requires it, redirect to workspace selector
        if not workspace and self._requires_workspace(request.path):
            messages.warning(request, 'Please select a workspace to continue.')
            return HttpResponseRedirect(reverse('orgs_company_list'))
        
        # If workspace is public schema, use public
        if workspace and workspace.schema_name == get_public_schema_name():
            connection.set_schema_to_public()
            request.tenant = workspace
            return None
        
        # Validate workspace access
        if workspace:
            validation_result = self._validate_workspace_access(
                user=request.user,
                workspace=workspace,
                request=request
            )
            
            if validation_result['allowed']:
                # Set tenant context
                connection.set_tenant(workspace)
                request.tenant = workspace
                
                # Log successful access (only for sensitive paths)
                if self._is_sensitive_path(request.path):
                    self._log_access(request, workspace, success=True)
                
                return None
            else:
                # Access denied - log and handle
                self._log_access(request, workspace, success=False, 
                               reason=validation_result['reason'])
                
                # Clear invalid workspace
                request.user.profile.workspace = None
                request.user.profile.save()
                
                # Show error message
                messages.error(request, validation_result['message'])
                return HttpResponseRedirect(reverse('orgs_company_list'))
        
        # Default to public schema
        connection.set_schema_to_public()
        return None
    
    def _get_user_workspace(self, user):
        """Safely get user's workspace"""
        try:
            if hasattr(user, 'profile') and user.profile.workspace:
                return user.profile.workspace
        except Exception as e:
            logger.error(f"Error getting workspace for user {user.id}: {e}")
        return None
    
    def _validate_workspace_access(self, user, workspace, request):
        """
        Comprehensive workspace access validation.
        Returns dict with 'allowed', 'reason', 'message' keys.
        """
        
        # Check 1: Is company deleted/suspended?
        if workspace.is_deleted:
            return {
                'allowed': False,
                'reason': 'COMPANY_DELETED',
                'message': 'This workspace has been deleted.'
            }
        
        # Check 2: Is user a member?
        try:
            membership = Membership.objects.select_related('role').get(
                user=user,
                company=workspace
            )
        except Membership.DoesNotExist:
            logger.warning(
                f"User {user.id} ({user.email}) attempted to access workspace "
                f"{workspace.id} ({workspace.name}) without membership"
            )
            return {
                'allowed': False,
                'reason': 'NO_MEMBERSHIP',
                'message': 'You are not a member of this workspace.'
            }
        
        # Check 3: Is membership active? (if you add this field later)
        # if hasattr(membership, 'is_active') and not membership.is_active:
        #     return {
        #         'allowed': False,
        #         'reason': 'MEMBERSHIP_INACTIVE',
        #         'message': 'Your membership has been deactivated.'
        #     }
        
        # Check 4: Subscription status (if subscriptions app exists)
        if 'apps.subscriptions' in settings.INSTALLED_APPS:
            subscription_check = self._check_subscription(workspace)
            if not subscription_check['allowed']:
                return subscription_check
        
        # All checks passed
        return {
            'allowed': True,
            'reason': 'AUTHORIZED',
            'message': '',
            'membership': membership
        }
    
    def _check_subscription(self, workspace):
        """Check if workspace subscription is active"""
        try:
            from apps.subscriptions.models import Subscription
            
            subscription = Subscription.objects.filter(
                company=workspace
            ).order_by('-created_at').first()
            
            if not subscription:
                return {
                    'allowed': False,
                    'reason': 'NO_SUBSCRIPTION',
                    'message': 'This workspace does not have an active subscription.'
                }
            
            if subscription.is_expired():
                return {
                    'allowed': False,
                    'reason': 'SUBSCRIPTION_EXPIRED',
                    'message': 'This workspace subscription has expired.'
                }
            
            if subscription.is_suspended():
                return {
                    'allowed': False,
                    'reason': 'SUBSCRIPTION_SUSPENDED',
                    'message': 'This workspace subscription has been suspended.'
                }
            
        except ImportError:
            # Subscriptions app not installed, skip check
            pass
        except Exception as e:
            logger.error(f"Error checking subscription for workspace {workspace.id}: {e}")
        
        return {'allowed': True, 'reason': 'SUBSCRIPTION_ACTIVE', 'message': ''}
    
    def _is_exempt_url(self, path):
        """Check if URL is exempt from workspace validation"""
        return any(path.startswith(exempt) for exempt in self.EXEMPT_URLS)
    
    def _requires_workspace(self, path):
        """Check if URL requires workspace context"""
        return any(path.startswith(required) for required in self.WORKSPACE_REQUIRED_URLS)
    
    def _is_sensitive_path(self, path):
        """Check if path is sensitive and should be logged"""
        sensitive_patterns = [
            '/settings/',
            '/billing/',
            '/team/',
            '/company/',
            '/preferences/',
        ]
        return any(pattern in path for pattern in sensitive_patterns)
    
    def _log_access(self, request, workspace, success=True, reason=''):
        """Log workspace access attempt"""
        try:
            action = 'UNAUTHORIZED_ACCESS' if not success else 'WORKSPACE_ACCESS'
            description = f"Access to workspace {workspace.name}"
            if not success:
                description += f" denied: {reason}"
            
            AuditLog.log(
                action=action,
                user=request.user,
                company=workspace,
                description=description,
                request=request,
                success=success,
                data={'path': request.path, 'reason': reason}
            )
        except Exception as e:
            # Don't fail the request if logging fails
            logger.error(f"Failed to log workspace access: {e}")
```

### 4.3 Update Settings to Use New Middleware
- [ ] Comment out old middleware in settings
- [ ] Add new middleware
- [ ] Document the change
- [ ] Create rollback plan

**File to Modify:** `django_project/settings/base.py`

```python
MIDDLEWARE = [
    # ... existing middleware
    # 'apps.orgs.middleware.WorkspaceMiddleware',  # OLD - REPLACED
    'apps.orgs.middleware_v2.SecureWorkspaceMiddleware',  # NEW - SECURE
    # ... rest of middleware
]
```

### 4.4 Testing
- [ ] Test valid workspace access
- [ ] Test invalid workspace access (non-member)
- [ ] Test deleted company access
- [ ] Test subscription validation (if applicable)
- [ ] Test audit log creation
- [ ] Test redirect to company list when no workspace
- [ ] Test exempt URLs still work

**Test Script:**
```python
# Create test script: apps/orgs/tests/test_secure_middleware.py
# Will create full test suite in testing phase
```

---

## Task 5: Update Decorators with Guardian Support (2 hours)

### 5.1 Create New Permission Decorators
- [ ] Create `apps/orgs/decorators_v2.py`
- [ ] Implement `@permission_required` with Guardian
- [ ] Implement `@object_permission_required`
- [ ] Keep backward compatibility with existing decorators

**File to Create:** `apps/orgs/decorators_v2.py`

```python
"""
Enhanced permission decorators using django-guardian.
Provides object-level and feature-level permission checking.
"""

import functools
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from guardian.decorators import permission_required as guardian_permission_required
from guardian.shortcuts import get_perms

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, Membership


def permission_required(perm, raise_exception=True, log_denial=True):
    """
    Check if user has specific permission in their current workspace.
    
    Usage:
        @permission_required('data_export')
        def export_data(request):
            ...
    
    Args:
        perm: Permission codename (e.g., 'data_export')
        raise_exception: If True, raises PermissionDenied; if False, returns 403
        log_denial: If True, logs permission denial to audit log
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            workspace = getattr(user.profile, 'workspace', None)
            
            if not workspace:
                if log_denial:
                    AuditLog.log(
                        'PERMISSION_DENIED',
                        user=user,
                        description=f"No workspace set for permission '{perm}'",
                        request=request,
                        success=False
                    )
                if raise_exception:
                    raise PermissionDenied("No workspace selected")
                return HttpResponseForbidden("No workspace selected")
            
            # Get user's membership
            try:
                membership = Membership.objects.select_related('role').get(
                    user=user,
                    company=workspace
                )
            except Membership.DoesNotExist:
                if log_denial:
                    AuditLog.log(
                        'PERMISSION_DENIED',
                        user=user,
                        company=workspace,
                        description=f"No membership for permission '{perm}'",
                        request=request,
                        success=False
                    )
                if raise_exception:
                    raise PermissionDenied("Not a workspace member")
                return HttpResponseForbidden("Not a workspace member")
            
            # Check if role has permission
            has_perm = membership.role.permissions.filter(
                codename=perm
            ).exists()
            
            if not has_perm:
                if log_denial:
                    AuditLog.log(
                        'PERMISSION_DENIED',
                        user=user,
                        company=workspace,
                        description=f"Permission denied: '{perm}'",
                        request=request,
                        success=False,
                        data={'required_permission': perm, 'role': membership.role.name}
                    )
                if raise_exception:
                    raise PermissionDenied(f"Permission '{perm}' required")
                return HttpResponseForbidden(f"Permission '{perm}' required")
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def any_permission_required(perms, raise_exception=True):
    """
    Check if user has ANY of the specified permissions.
    
    Usage:
        @any_permission_required(['data_edit', 'data_create'])
        def create_or_edit_data(request):
            ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            workspace = getattr(user.profile, 'workspace', None)
            
            if not workspace:
                if raise_exception:
                    raise PermissionDenied("No workspace selected")
                return HttpResponseForbidden("No workspace selected")
            
            try:
                membership = Membership.objects.select_related('role').get(
                    user=user,
                    company=workspace
                )
            except Membership.DoesNotExist:
                if raise_exception:
                    raise PermissionDenied("Not a workspace member")
                return HttpResponseForbidden("Not a workspace member")
            
            # Check if role has ANY of the permissions
            has_any_perm = membership.role.permissions.filter(
                codename__in=perms
            ).exists()
            
            if not has_any_perm:
                AuditLog.log(
                    'PERMISSION_DENIED',
                    user=user,
                    company=workspace,
                    description=f"None of required permissions: {perms}",
                    request=request,
                    success=False
                )
                if raise_exception:
                    raise PermissionDenied(f"One of permissions {perms} required")
                return HttpResponseForbidden()
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def object_permission_required(perm, model, pk_url_kwarg='pk', accept_global_perms=True):
    """
    Check object-level permissions using Guardian.
    
    Usage:
        @object_permission_required('change_company', Company, pk_url_kwarg='company_id')
        def update_company(request, company_id):
            ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            # Get object_id from URL kwargs
            object_id = kwargs.get(pk_url_kwarg)
            if not object_id:
                raise Http404(f"Missing {pk_url_kwarg} in URL")
            
            # Get the object
            obj = get_object_or_404(model, pk=object_id)
            
            # Check permission using Guardian
            user_perms = get_perms(request.user, obj)
            
            if perm not in user_perms:
                # Also check global permission from role if accept_global_perms
                if accept_global_perms:
                    workspace = getattr(request.user.profile, 'workspace', None)
                    if workspace:
                        try:
                            membership = Membership.objects.select_related('role').get(
                                user=request.user,
                                company=workspace
                            )
                            has_global = membership.role.permissions.filter(
                                codename=perm
                            ).exists()
                            if has_global:
                                return view_func(request, *args, **kwargs)
                        except Membership.DoesNotExist:
                            pass
                
                # Log denial
                AuditLog.log(
                    'PERMISSION_DENIED',
                    user=request.user,
                    description=f"Object permission denied: '{perm}' on {model.__name__} {object_id}",
                    request=request,
                    success=False,
                    content_object=obj
                )
                
                raise PermissionDenied(f"You don't have permission to {perm} this {model.__name__}")
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


# Backward compatible aliases
@functools.wraps(permission_required)
def role_based_permission(perm):
    """Alias for permission_required for clarity"""
    return permission_required(perm)
```

### 5.2 Document Migration Path
- [ ] Create `DECORATOR_MIGRATION_GUIDE.md`
- [ ] List all views using old decorators
- [ ] Provide migration examples
- [ ] Document breaking changes

---

## Task 6: Create Management Commands (1 hour)

### 6.1 Command to Setup Default Roles and Permissions
- [ ] Create `apps/orgs/management/commands/setup_permissions.py`
- [ ] Implement command to create all permissions
- [ ] Implement command to create default roles
- [ ] Add idempotency (safe to run multiple times)

**File to Create:** `apps/orgs/management/commands/setup_permissions.py`

```python
"""
Management command to setup default roles and permissions.
Run after installing django-guardian: python manage.py setup_permissions
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.orgs.models import Company, Role
from apps.orgs.permissions import ALL_PERMISSIONS, get_permissions_for_role


class Command(BaseCommand):
    help = 'Setup default roles and permissions for the application'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing roles and recreate them',
        )
    
    def handle(self, *args, **options):
        reset = options['reset']
        
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Setting up permissions and roles'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        with transaction.atomic():
            # Step 1: Create content type for Company (used for permissions)
            company_ct = ContentType.objects.get_for_model(Company)
            
            # Step 2: Create all permissions
            self.stdout.write('\n📝 Creating permissions...')
            created_perms = self.create_permissions(company_ct)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {created_perms} permissions'))
            
            # Step 3: Reset roles if requested
            if reset:
                self.stdout.write('\n🗑️  Deleting existing roles...')
                deleted = Role.objects.all().delete()[0]
                self.stdout.write(self.style.WARNING(f'✓ Deleted {deleted} roles'))
            
            # Step 4: Create default roles
            self.stdout.write('\n👥 Creating default roles...')
            self.create_default_roles()
            self.stdout.write(self.style.SUCCESS('✓ Created default roles'))
            
            # Step 5: Summary
            self.print_summary()
            
        self.stdout.write(self.style.SUCCESS('\n✅ Setup complete!'))
    
    def create_permissions(self, content_type):
        """Create all custom permissions"""
        created = 0
        
        for codename, name, description in ALL_PERMISSIONS:
            perm, created_now = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name}
            )
            if created_now:
                created += 1
                self.stdout.write(f'  + {codename}: {name}')
        
        return created
    
    def create_default_roles(self):
        """Create default roles with permissions"""
        default_roles = ['Owner', 'Admin', 'Member', 'Viewer']
        
        for role_name in default_roles:
            role, created = Role.objects.get_or_create(name=role_name)
            
            # Get permissions for this role
            perm_codenames = get_permissions_for_role(role_name)
            
            # Assign permissions
            perms = Permission.objects.filter(codename__in=perm_codenames)
            role.permissions.set(perms)
            
            status = '✨ Created' if created else '♻️  Updated'
            self.stdout.write(f'  {status} {role_name}: {perms.count()} permissions')
    
    def print_summary(self):
        """Print summary of created roles and permissions"""
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*70)
        
        total_permissions = Permission.objects.filter(
            codename__in=[p[0] for p in ALL_PERMISSIONS]
        ).count()
        self.stdout.write(f'\nTotal Permissions: {total_permissions}')
        
        self.stdout.write('\nRoles:')
        for role in Role.objects.all().order_by('name'):
            perm_count = role.permissions.count()
            self.stdout.write(f'  • {role.name}: {perm_count} permissions')
        
        self.stdout.write('\n' + '='*70)
```

### 6.2 Command to Audit User Permissions
- [ ] Create `apps/orgs/management/commands/audit_permissions.py`
- [ ] Show permissions for each user/role
- [ ] Generate permission report

---

## Task 7: Update Admin Interface (1 hour)

### 7.1 Register AuditLog in Admin
- [ ] Update `apps/orgs/admin.py`
- [ ] Add read-only fields
- [ ] Add filters and search
- [ ] Customize list display

### 7.2 Enhance Role Admin
- [ ] Show permissions in admin
- [ ] Add permission filters
- [ ] Add inline permission display

**Update:** `apps/orgs/admin.py`

---

## Post-Implementation Checklist

### Testing
- [ ] Run all existing tests: `python manage.py test`
- [ ] Create new test suite for permissions
- [ ] Test middleware with various scenarios
- [ ] Test audit logging
- [ ] Manual testing of permission checks

### Documentation
- [ ] Update CHANGELOG with Phase 0 changes
- [ ] Document new decorators
- [ ] Document audit logging usage
- [ ] Update README with setup instructions

### Code Quality
- [ ] Run linting: `flake8` or `pylint`
- [ ] Check for security issues: `bandit`
- [ ] Review all changed files
- [ ] Ensure no sensitive data in logs

### Deployment Preparation
- [ ] Create migration plan document
- [ ] Test migrations on staging
- [ ] Prepare rollback scripts
- [ ] Update deployment documentation

### Communication
- [ ] Notify team of changes
- [ ] Schedule code review
- [ ] Plan testing session
- [ ] Update project board

---

## Success Criteria

Phase 0 is complete when:

1. ✅ Django-guardian installed and configured
2. ✅ All permissions defined and created in database
3. ✅ Default roles (Owner, Admin, Member, Viewer) created with permissions
4. ✅ AuditLog model created and logging works
5. ✅ Middleware validates membership before granting access
6. ✅ Old security vulnerabilities fixed
7. ✅ All tests passing
8. ✅ Documentation complete

---

## Rollback Plan

If issues arise:

1. **Revert Middleware:**
   ```python
   # In settings.py
   MIDDLEWARE = [
       'apps.orgs.middleware.WorkspaceMiddleware',  # OLD
       # 'apps.orgs.middleware_v2.SecureWorkspaceMiddleware',  # NEW
   ]
   ```

2. **Keep guardian installed** - it's backward compatible

3. **Rollback migrations:**
   ```bash
   python manage.py migrate orgs <previous_migration_number>
   ```

4. **Remove audit logging calls** (if causing issues)

---

## Estimated Timeline

| Task | Time | Priority |
|------|------|----------|
| 1. Install django-guardian | 2h | 🔴 P0 |
| 2. Define permission matrix | 3h | 🔴 P0 |
| 3. Create audit logging | 2h | 🟡 P1 |
| 4. Fix middleware | 3h | 🔴 P0 |
| 5. Update decorators | 2h | 🔴 P0 |
| 6. Management commands | 1h | 🟡 P1 |
| 7. Admin interface | 1h | 🟢 P2 |
| **Total** | **14h** | **~2 days** |

---

## Next Phase

After Phase 0 completion, proceed to **Phase 1: Core Auth Implementation** which includes:
- Updating all views with new permission decorators
- Creating permission context processor
- Object-level permission assignments
- Comprehensive testing

**Ready to begin implementation? Start with Task 1!** 🚀
