#!/usr/bin/env python
"""
Test script to verify loan refactor integration is complete.
Run with: python manage.py shell < test_refactor_integration.py
"""

print("=" * 80)
print("LOAN REFACTOR INTEGRATION TEST")
print("=" * 80)

# Test 1: Import GivenLoan and TakenLoan
print("\n1. Testing model imports...")
try:
    from apps.tenant_apps.girvi.models import GivenLoan, TakenLoan, LoanItem, Release

    print("   ✓ GivenLoan imported successfully")
    print("   ✓ TakenLoan imported successfully")
    print("   ✓ LoanItem imported successfully")
    print("   ✓ Release imported successfully")
except ImportError as e:
    print(f"   ✗ Import failed: {e}")

# Test 2: Check manager methods exist
print("\n2. Testing manager methods...")
try:
    assert hasattr(GivenLoan.objects, "released"), "released() method missing"
    assert hasattr(GivenLoan.objects, "unreleased"), "unreleased() method missing"
    assert hasattr(
        GivenLoan.objects, "for_table_display"
    ), "for_table_display() method missing"
    assert hasattr(
        GivenLoan.objects, "non_performing_loans_stats"
    ), "non_performing_loans_stats() method missing"
    assert hasattr(
        GivenLoan.objects, "long_dead_loans_stats"
    ), "long_dead_loans_stats() method missing"
    print("   ✓ GivenLoan.objects.released() exists")
    print("   ✓ GivenLoan.objects.unreleased() exists")
    print("   ✓ GivenLoan.objects.for_table_display() exists")
    print("   ✓ GivenLoan.objects.non_performing_loans_stats() exists")
    print("   ✓ GivenLoan.objects.long_dead_loans_stats() exists")
except AssertionError as e:
    print(f"   ✗ Manager method check failed: {e}")

# Test 3: Check TakenLoan manager methods
print("\n3. Testing TakenLoan manager methods...")
try:
    assert hasattr(
        TakenLoan.objects, "non_performing_loans_stats"
    ), "non_performing_loans_stats() method missing"
    assert hasattr(
        TakenLoan.objects, "long_dead_loans_stats"
    ), "long_dead_loans_stats() method missing"
    print("   ✓ TakenLoan.objects.non_performing_loans_stats() exists")
    print("   ✓ TakenLoan.objects.long_dead_loans_stats() exists")
except AssertionError as e:
    print(f"   ✗ TakenLoan manager method check failed: {e}")

# Test 4: Check Release model FK
print("\n4. Testing Release model FK...")
try:
    release_loan_field = Release._meta.get_field("loan")
    related_model = release_loan_field.related_model.__name__
    if related_model == "GivenLoan":
        print(f"   ✓ Release.loan points to {related_model}")
    else:
        print(f"   ✗ Release.loan points to {related_model} (should be GivenLoan)")
except Exception as e:
    print(f"   ✗ Release FK check failed: {e}")

# Test 5: Test queryset methods (if data exists)
print("\n5. Testing queryset methods...")
try:
    unreleased_count = GivenLoan.objects.unreleased().count()
    released_count = GivenLoan.objects.released().count()
    print(f"   ✓ GivenLoan.objects.unreleased() works: {unreleased_count} loans")
    print(f"   ✓ GivenLoan.objects.released() works: {released_count} loans")

    # Test the new methods
    npl_stats = GivenLoan.objects.non_performing_loans_stats()
    print(f"   ✓ non_performing_loans_stats() works: {npl_stats.count()} loans")

    dead_stats = GivenLoan.objects.long_dead_loans_stats(threshold_months=12)
    print(f"   ✓ long_dead_loans_stats() works: {dead_stats.count()} loans")
except Exception as e:
    print(f"   ✗ Queryset method test failed: {e}")

# Test 6: Check LoanItem relationship
print("\n6. Testing LoanItem relationship...")
try:
    from django.db.models import Sum

    # Try to aggregate via LoanItem
    total = LoanItem.objects.filter(loan__in=GivenLoan.objects.unreleased()).aggregate(
        total=Sum("loanamount")
    )
    print(f"   ✓ Can aggregate LoanItem.loanamount: {total}")
except Exception as e:
    print(f"   ✗ LoanItem aggregation failed: {e}")

# Test 7: Check form imports
print("\n7. Testing form imports...")
try:
    from apps.tenant_apps.girvi.forms import LoanForm

    form_fields = LoanForm._meta.fields if hasattr(LoanForm._meta, "fields") else []
    print(f"   ✓ LoanForm imported successfully")
    if form_fields:
        print(f"   ✓ LoanForm fields: {form_fields}")
except Exception as e:
    print(f"   ✗ Form import failed: {e}")

# Test 8: Check filter imports
print("\n8. Testing filter imports...")
try:
    from apps.tenant_apps.girvi.filters import LoanFilter

    print(f"   ✓ LoanFilter imported successfully")
except Exception as e:
    print(f"   ✗ Filter import failed: {e}")

print("\n" + "=" * 80)
print("INTEGRATION TEST COMPLETE")
print("=" * 80)
print("\nIf all tests show ✓, the refactor integration is successful!")
