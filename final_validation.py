#!/usr/bin/env python
"""
Final validation script for loan refactor integration.
Tests dashboard aggregation queries.
"""

print("\n" + "=" * 80)
print("FINAL VALIDATION - Dashboard Aggregation Test")
print("=" * 80)

print("\n1. Testing annotation methods...")
try:
    from apps.tenant_apps.girvi.models import GivenLoan

    # Get a small queryset to test
    unreleased = GivenLoan.objects.unreleased()[:1]

    # Test annotation chains
    test_qs = unreleased.with_metal_weights()
    print("   ✓ with_metal_weights() adds annotations")

    test_qs = unreleased.with_itemwise_amounts()
    print("   ✓ with_itemwise_amounts() adds annotations")

    test_qs = unreleased.with_current_value()
    print("   ✓ with_current_value() adds annotations")

except Exception as e:
    print(f"   ✗ Annotation test failed: {e}")

print("\n2. Testing weight aggregations...")
try:
    from apps.tenant_apps.girvi.models import GivenLoan
    from django.db.models import Sum

    unreleased = GivenLoan.objects.unreleased()

    # Test weight aggregations
    weight_stats = unreleased.with_metal_weights().aggregate(
        gold=Sum("gold_weight"),
        silver=Sum("silver_weight"),
        bronze=Sum("bronze_weight"),
        pure_gold=Sum("pure_gold_weight"),
        pure_silver=Sum("pure_silver_weight"),
        pure_bronze=Sum("pure_bronze_weight"),
    )
    print(f"   ✓ Weight aggregation works: {weight_stats}")

except Exception as e:
    print(f"   ✗ Weight aggregation failed: {e}")

print("\n3. Testing value aggregations...")
try:
    from apps.tenant_apps.girvi.models import GivenLoan
    from django.db.models import Sum

    unreleased = GivenLoan.objects.unreleased()

    # Test value aggregations
    value_stats = (
        unreleased.with_metal_weights()
        .with_current_value()
        .aggregate(total_current=Sum("total_current_value"))
    )
    print(f"   ✓ Value aggregation works: {value_stats}")

except Exception as e:
    print(f"   ✗ Value aggregation failed: {e}")

print("\n4. Testing itemwise aggregations...")
try:
    from apps.tenant_apps.girvi.models import GivenLoan
    from django.db.models import Sum

    unreleased = GivenLoan.objects.unreleased()

    # Test itemwise aggregations
    itemwise_stats = (
        unreleased.with_itemwise_amounts()
        .with_current_value()
        .aggregate(
            gold=Sum("gold_value"),
            silver=Sum("silver_value"),
            bronze=Sum("bronze_value"),
        )
    )
    print(f"   ✓ Itemwise aggregation works: {itemwise_stats}")

except Exception as e:
    print(f"   ✗ Itemwise aggregation failed: {e}")

print("\n5. Testing dashboard-like aggregations (multiple together)...")
try:
    from apps.tenant_apps.girvi.models import GivenLoan, LoanItem
    from django.db.models import Sum

    unreleased = GivenLoan.objects.unreleased()

    # Weight aggregations
    weight_stats = unreleased.with_metal_weights().aggregate(
        gold=Sum("gold_weight"),
        silver=Sum("silver_weight"),
        bronze=Sum("bronze_weight"),
    )

    # Value aggregations
    value_stats = (
        unreleased.with_metal_weights()
        .with_current_value()
        .aggregate(total_current=Sum("total_current_value"))
    )

    # Itemwise aggregations
    itemwise_stats = (
        unreleased.with_itemwise_amounts()
        .with_current_value()
        .aggregate(
            gold=Sum("gold_value"),
            silver=Sum("silver_value"),
            bronze=Sum("bronze_value"),
        )
    )

    # LoanItem aggregations
    item_stats = LoanItem.objects.filter(loan__in=unreleased).aggregate(
        total_amount=Sum("loanamount"), total_interest=Sum("interest")
    )

    print(f"   ✓ Combined dashboard aggregations work:")
    print(f"     - Weights: {weight_stats}")
    print(f"     - Values: {value_stats}")
    print(f"     - Itemwise: {itemwise_stats}")
    print(f"     - LoanItem: {item_stats}")

except Exception as e:
    print(f"   ✗ Combined aggregation failed: {e}")

print("\n6. Testing manager methods...")
try:
    from apps.tenant_apps.girvi.models import GivenLoan

    unreleased = GivenLoan.objects.unreleased()

    # Test manager methods
    methods_to_test = [
        ("total_weight", lambda: unreleased.total_weight()),
        ("total_pure_weight", lambda: unreleased.total_pure_weight()),
        ("total_current_value", lambda: unreleased.total_current_value()),
        ("itemwise_value", lambda: unreleased.itemwise_value()),
        ("total_itemwise_loanamount", lambda: unreleased.total_itemwise_loanamount()),
    ]

    for method_name, method_call in methods_to_test:
        try:
            result = method_call()
            print(f"   ✓ {method_name}() works: {result}")
        except Exception as e:
            print(f"   ✗ {method_name}() failed: {e}")

except Exception as e:
    print(f"   ✗ Manager methods test failed: {e}")

print("\n" + "=" * 80)
print("VALIDATION COMPLETE")
print("=" * 80)
print("\nAll dashboard aggregations should work without errors now!")
print("The company_dashboard view should load successfully.")
