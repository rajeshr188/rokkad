#!/usr/bin/env python
"""Test script to validate weight annotations work correctly."""

print("Testing weight annotations in GivenLoan...")

from apps.tenant_apps.girvi.models import GivenLoan
from apps.tenant_apps.girvi.services import LoanMetalWeightService
from django.db.models import Sum

# Test 1: Check if service methods return correct annotations
print("\n1. Testing service methods...")
annotations = LoanMetalWeightService.get_given_loan_weight_annotations()
print(f"   Annotations returned: {list(annotations.keys())}")
if "pure_gold_weight" in annotations:
    print("   ✓ pure_gold_weight annotation exists")
else:
    print("   ✗ pure_gold_weight annotation MISSING")

# Test 2: Check if with_metal_weights() method exists and works
print("\n2. Testing with_metal_weights() method...")
try:
    qs = GivenLoan.objects.all().with_metal_weights()
    print(f"   ✓ with_metal_weights() method works")
    print(f"   Query annotations: {list(qs.query.annotations.keys())}")
except Exception as e:
    print(f"   ✗ with_metal_weights() failed: {e}")

# Test 3: Test aggregation with annotations
print("\n3. Testing aggregation with annotations...")
try:
    # Get unreleased loans
    unreleased = GivenLoan.objects.unreleased()
    print(f"   Unreleased loans count: {unreleased.count()}")

    # Apply annotations
    annotated = unreleased.with_metal_weights()
    print(f"   Annotations: {list(annotated.query.annotations.keys())}")

    # Try aggregation
    result = annotated.aggregate(
        gold=Sum("gold_weight"),
        pure_gold=Sum("pure_gold_weight"),
    )
    print(f"   ✓ Aggregation successful: {result}")
except Exception as e:
    print(f"   ✗ Aggregation failed: {e}")
    import traceback

    traceback.print_exc()

print("\nTest complete!")
