Skip to content
 
Search Gists
Search...
All gists
Back to GitHub
@rajeshr188
rajeshr188/gist:3e5c89beb6454484c0f813e960d44ac6
Last active 1 minute ago
Code
Revisions
6
Clone this repository at &lt;script src=&quot;https://gist.github.com/rajeshr188/3e5c89beb6454484c0f813e960d44ac6.js&quot;&gt;&lt;/script&gt;
<script src="https://gist.github.com/rajeshr188/3e5c89beb6454484c0f813e960d44ac6.js"></script>
Jewellery-catalog-schema-inventory-mgmt
gistfile1.txt
# 💍 Jewellery Catalog — Complete Schema Reference
> Full domain architecture adapted from Saleor's product catalog.  
> Covers: Product Catalog · Pricing · Attributes · Media · Collections · Inventory · Lots · Audit Trail

---

## 📋 Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Enums & Choices](#2-enums--choices)
3. [Metal & Purity](#3-metal--purity)
4. [Category Hierarchy](#4-category-hierarchy)
5. [Jewellery Type](#5-jewellery-type)
6. [Jewellery Design](#6-jewellery-design)
7. [Diamond Specification](#7-diamond-specification)
8. [Jewellery Variant](#8-jewellery-variant)
9. [Channel Listings & Pricing](#9-channel-listings--pricing)
10. [Attributes](#10-attributes)
11. [Media](#11-media)
12. [Collections](#12-collections)
13. [Inventory — Lot / Batch](#13-inventory--lot--batch)
14. [Inventory — Unique Stock Item](#14-inventory--unique-stock-item)
15. [Audit Trail](#15-audit-trail)
16. [Pricing Formula](#16-pricing-formula)
17. [Key Design Decisions](#17-key-design-decisions)

---

## 1. Architecture Overview

### Design Philosophy

| Saleor Concept | Jewellery Adaptation | Reason |
|---|---|---|
| `ProductType` | `JewelleryType` | Schema for Ring / Necklace / Bangle |
| `Product` | `JewelleryDesign` | The artistic design, metal-agnostic |
| `ProductVariant` | `JewelleryVariant` | One SKU: 22K Gold Ring, Size 12 |
| `ProductVariantChannelListing` | `JewelleryVariantChannelListing` | Dynamic computed pricing per channel |
| `Attribute` | Domain-typed attributes | Purity, gemstone grade, hallmark |
| `Stock` (integer qty) | `JewelleryStockItem` (1 row = 1 piece) | Each jewellery piece is unique |
| _(none)_ | `JewelleryLot` | Batch/lot from supplier or casting run |
| _(none)_ | `LotEvent` + `StockItemEvent` | Full bidirectional audit trail |

---

### Full Entity Map

```
MetalPurityStandard
(22K Gold / 18K Gold / 925 Silver / 950 Platinum)
     │
     ▼
JewelleryType  (Ring / Necklace / Bangle / Earring / Pendant)
├── allowed_metal_types
├── making_charge defaults
└── certification_required
     │
     ▼
JewelleryDesign  (Master design — metal-agnostic)
├── name, slug, design_code
├── jewellery_type (FK)
├── category (FK → JewelleryCategory, MPTT tree)
├── occasion, gender, style_theme
├── collections (M:M via JewelleryCollectionDesign)
└── translations, SEO, metadata
     │
     ├─────────────────────────────────────────┐
     ▼                                         ▼
JewelleryVariant                         JewelleryMedia
(SKU-level piece)                        (images, 360°, CAD)
├── metal_purity (FK)                          │
├── gross_weight / net_weight                  └── JewelleryVariantMedia (M:M)
├── stone_weight_carats
├── making_charge_type / value
├── wastage_percentage
├── size / size_unit
├── hallmark fields
├── primary_diamond (OneToOne)
├── side_stones (M:M via VariantSideStone)
├── gemstone_type / weight
└── channel_listings (1:M)
     │
     ▼
JewelleryVariantChannelListing
├── metal_spot_price    ← live rate at time of compute
├── metal_value         ← net_weight × spot × purity_factor
├── making_charges
├── wastage
├── stone_value
├── gst
├── price               ← total computed MRP
├── cost_price, prior_price, discounted_price
└── promotion_rules (M:M)

DiamondSpecification
├── carat_weight, cut, color, clarity  (4C grades)
├── GIA / IGI cert number
└── shape, fluorescence, measurements

JewelleryLot  (Batch from supplier / casting)
├── lot_number, lot_type, status
├── supplier, grn_number, purchase_order_ref
├── received_date, warehouse (FK)
├── total weights, assay cert
└── LotEvent (1:M audit log)
     │
     ▼
JewelleryStockItem  (ONE physical piece)
├── variant (FK)
├── lot (FK)
├── warehouse (FK)
├── barcode, rfid_tag, hallmark_number
├── actual_gross_weight, actual_net_weight
├── status (AVAILABLE / RESERVED / SOLD / ...)
├── order_line (OneToOne when sold)
├── checkout_line (FK when in cart)
├── reserved_until
└── StockItemEvent (1:M audit log)
```

---

## 2. Enums & Choices

### MetalTypeChoices
| Value | Display |
|---|---|
| `GOLD` | Gold |
| `SILVER` | Silver |
| `PLATINUM` | Platinum |
| `WHITE_GOLD` | White Gold |
| `ROSE_GOLD` | Rose Gold |

### PurityUnit
| Value | Display | Used For |
|---|---|---|
| `KARAT` | Karat (K) | Gold: 24K, 22K, 18K, 14K |
| `MILLESIMAL` | Millesimal Fineness | Platinum: 950, 900 / Silver: 925, 999 |
| `PERCENT` | Percentage (%) | 99.9% pure silver |

### MakingChargeType
| Value | Display |
|---|---|
| `FLAT_PER_GRAM` | Flat Rate per Gram |
| `PERCENTAGE` | Percentage of Metal Value |
| `FLAT_FIXED` | Fixed Flat Charge |

### OccasionChoices
| Value | Display |
|---|---|
| `WEDDING` | Wedding |
| `ENGAGEMENT` | Engagement |
| `EVERYDAY` | Everyday Wear |
| `FESTIVAL` | Festival |
| `GIFTING` | Gifting |
| `PARTY` | Party / Cocktail |

### GenderChoices
`WOMEN` · `MEN` · `KIDS` · `UNISEX`

### JewelleryTypeKind
`STANDARD` · `BESPOKE` · `ANTIQUE`

### DiamondClarityGrade
`FL` · `IF` · `VVS1` · `VVS2` · `VS1` · `VS2` · `SI1` · `SI2` · `I1`

### DiamondColorGrade
`D` · `E` · `F` · `G` · `H` · `I` · `J`

### DiamondCutGrade
`IDEAL` · `EXCELLENT` · `VERY_GOOD` · `GOOD` · `FAIR`

### MediaAngleTag
`FRONT` · `SIDE` · `TOP` · `WORN` · `VIEW_360` · `CAD_RENDER`

### LotType
| Value | Display |
|---|---|
| `CASTING` | Casting / Manufacturing |
| `PURCHASE` | Supplier Purchase |
| `RETURN` | Customer Return Bulk |
| `TRANSFER` | Warehouse Transfer |
| `OPENING` | Opening Stock Entry |

### LotStatus
| Value | Display |
|---|---|
| `DRAFT` | Draft — being created |
| `GRN_RAISED` | GRN Raised — awaiting inspection |
| `APPROVED` | Quality Approved — items available |
| `PARTIAL` | Partially Sold / Transferred |
| `CLOSED` | Closed — all items accounted for |
| `QUARANTINE` | Quarantine — inspection hold |
| `SCRAPPED` | Scrapped / Melted |

### LotEventType
| Value | Display |
|---|---|
| `CREATED` | Lot Created |
| `GRN_RAISED` | GRN Raised |
| `ITEMS_TAGGED` | Items Barcoded / Tagged |
| `QUALITY_APPROVED` | Quality Approved |
| `QUALITY_REJECTED` | Quality Rejected → Quarantine |
| `TRANSFERRED` | Lot Transferred to Warehouse |
| `PARTIALLY_SOLD` | Some Items Sold |
| `CLOSED` | Lot Closed |
| `SCRAPPED` | Lot Scrapped / Sent for Melting |
| `NOTE_ADDED` | Note Added |

### StockItemStatus
| Value | Display |
|---|---|
| `AVAILABLE` | Available for Sale |
| `RESERVED` | Reserved — In Checkout |
| `SOLD` | Sold |
| `ON_HOLD` | On Hold (display / repair) |
| `IN_TRANSIT` | In Transit |
| `RETURNED` | Returned by Customer |
| `SCRAPPED` | Scrapped / Melted |
| `QUARANTINE` | Under Inspection |
| `LOST` | Lost / Stolen |

### StockItemEventType
| Value | Display |
|---|---|
| `RECEIVED` | Received into Stock |
| `RESERVED` | Reserved for Checkout |
| `RESERVATION_EXPIRED` | Reservation Expired |
| `SOLD` | Sold |
| `RETURNED` | Returned by Customer |
| `TRANSFERRED` | Transferred to Warehouse |
| `PUT_ON_HOLD` | Put On Hold |
| `RELEASED_FROM_HOLD` | Released from Hold |
| `SENT_FOR_REPAIR` | Sent for Repair |
| `REPAIRED` | Returned from Repair |
| `QUARANTINED` | Moved to Quarantine |
| `SCRAPPED` | Scrapped / Melted |
| `WEIGHT_UPDATED` | Weight Re-measured |
| `LOCATION_UPDATED` | Location Changed |
| `MANUAL_ADJUSTMENT` | Manual Adjustment |

---

## 3. Metal & Purity

### MetalPurityStandard
Defines one specific purity level for a metal type.

| Field | Type | Notes |
|---|---|---|
| `metal_type` | CharField | MetalTypeChoices, db_index |
| `purity_value` | DecimalField(7,3) | e.g. 22.000, 18.000, 950.000 |
| `purity_unit` | CharField | PurityUnit |
| `display_label` | CharField(50) | "22K", "950", "925" |
| `slug` | SlugField | unique |
| `description` | TextField | blank |
| `is_hallmarkable` | BooleanField | default=True |

**Mixin:** `ModelWithMetadata`  
**Constraint:** `unique_together = [["metal_type", "purity_value", "purity_unit"]]`  
**Ordering:** `("metal_type", "-purity_value")`  
**Index:** GinIndex on `(metal_type, display_label)`

**Reference Data:**

| metal_type | purity_value | purity_unit | display_label |
|---|---|---|---|
| GOLD | 24.000 | KARAT | 24K |
| GOLD | 22.000 | KARAT | 22K |
| GOLD | 18.000 | KARAT | 18K |
| GOLD | 14.000 | KARAT | 14K |
| WHITE_GOLD | 18.000 | KARAT | 18K White Gold |
| ROSE_GOLD | 18.000 | KARAT | 18K Rose Gold |
| SILVER | 999.000 | MILLESIMAL | 999 |
| SILVER | 925.000 | MILLESIMAL | 925 |
| PLATINUM | 950.000 | MILLESIMAL | 950 |
| PLATINUM | 900.000 | MILLESIMAL | 900 |

---

## 4. Category Hierarchy

### JewelleryCategory
Hierarchical tree using MPTT (Modified Pre-order Tree Traversal).

| Field | Type | Notes |
|---|---|---|
| `name` | CharField(250) | |
| `slug` | SlugField(255) | unique, allow_unicode |
| `description` | SanitizedJSONField | EditorJS rich text |
| `description_plaintext` | TextField | blank, for search |
| `parent` | ForeignKey(self) | null, MPTT parent |
| `background_image` | ImageField | upload_to="jewellery-category-backgrounds" |
| `background_image_alt` | CharField(128) | blank |
| `updated_at` | DateTimeField | auto_now |

**Mixins:** `ModelWithMetadata`, `MPTTModel`, `SeoModel`  
**Managers:** `objects = Manager()`, `tree = TreeManager()`  
**Index:** GinIndex on `(name, slug, description_plaintext)`

**Example Tree:**
```
Rings
├── Engagement Rings
│   ├── Solitaire
│   └── Halo
├── Wedding Bands
└── Fashion Rings
Necklaces
├── Pendants
├── Chains
└── Mangalsutra
Bangles & Bracelets
Earrings
├── Studs
├── Jhumkas
└── Hoops
```

### JewelleryCategoryTranslation
| Field | Type |
|---|---|
| `category` | FK → JewelleryCategory |
| `language_code` | CharField |
| `name` | CharField(128) |
| `description` | SanitizedJSONField |

---

## 5. Jewellery Type

### JewelleryType
Defines the schema/template for a jewellery product category. Controls which metals are allowed and sets making charge defaults.

| Field | Type | Notes |
|---|---|---|
| `name` | CharField(250) | |
| `slug` | SlugField(255) | unique |
| `kind` | CharField | JewelleryTypeKind |
| `is_shipping_required` | BooleanField | default=True |
| `is_customizable` | BooleanField | default=False |
| `allowed_metal_types` | JSONField | list of MetalTypeChoices |
| `making_charge_type` | CharField | MakingChargeType |
| `default_making_rate` | DecimalField(5,2) | % or flat per gram |
| `default_wastage_pct` | DecimalField(5,2) | default=0.00 |
| `tax_class` | FK → TaxClass | SET_NULL |
| `certification_required` | BooleanField | BIS / GIA etc. |

**Mixin:** `ModelWithMetadata`  
**Index:** GinIndex on `(name, slug)`

---

## 6. Jewellery Design

### JewelleryDesign
The master design entity — metal-agnostic. One design ("Floral Ring") can have variants in 22K Gold, 18K White Gold, 950 Platinum.

| Field | Type | Notes |
|---|---|---|
| `jewellery_type` | FK → JewelleryType | CASCADE |
| `name` | CharField(250) | |
| `slug` | SlugField(255) | unique |
| `design_code` | CharField(100) | unique internal reference |
| `description` | SanitizedJSONField | EditorJS |
| `description_plaintext` | TextField | blank |
| `category` | FK → JewelleryCategory | SET_NULL |
| `occasion` | CharField | OccasionChoices |
| `gender` | CharField | GenderChoices |
| `style_theme` | CharField(100) | Floral / Geometric / Vintage |
| `is_customizable` | BooleanField | |
| `is_certified` | BooleanField | |
| `default_variant` | OneToOneField → JewelleryVariant | SET_NULL |
| `rating` | FloatField | null, blank |
| `tax_class` | FK → TaxClass | SET_NULL |
| `search_document` | TextField | denormalized FTS |
| `search_vector` | SearchVectorField | PostgreSQL FTS |
| `search_index_dirty` | BooleanField | db_index, triggers reindex |
| `created_at` | DateTimeField | auto_now_add |
| `updated_at` | DateTimeField | auto_now |

**Mixins:** `SeoModel`, `ModelWithMetadata`, `ModelWithExternalReference`

**Indexes:**
- GinIndex on `search_vector` (full text)
- GinIndex on `search_document` (trigram)
- GinIndex on `(name, slug)` (trigram)
- Index on `(category_id, slug)`
- Index on `(occasion, gender)`

### JewelleryDesignTranslation
| Field | Type |
|---|---|
| `design` | FK → JewelleryDesign |
| `language_code` | CharField |
| `name` | CharField(250) |
| `description` | SanitizedJSONField |

**Constraint:** `unique_together = (("language_code", "design"),)`

### JewelleryDesignChannelListing
Per-channel visibility and availability of a design.

| Field | Type | Notes |
|---|---|---|
| `design` | FK → JewelleryDesign | CASCADE |
| `channel` | FK → Channel | CASCADE |
| `visible_in_listings` | BooleanField | default=False |
| `available_for_purchase_at` | DateTimeField | null, blank |
| `currency` | CharField | |
| `discounted_price_amount` | DecimalField | null, blank |
| `discounted_price` | MoneyField | amount + currency |
| `discounted_price_dirty` | BooleanField | default=False |
| `is_published` | BooleanField | from PublishableModel |
| `published_at` | DateTimeField | from PublishableModel |

**Constraint:** `unique_together = [["design", "channel"]]`

---

## 7. Diamond Specification

### DiamondSpecification
Full GIA/IGI graded diamond specification. Linked to a variant as either the primary/solitaire stone or as side/accent stones.

| Field | Type | Notes |
|---|---|---|
| `carat_weight` | DecimalField(6,3) | min=0.01 |
| `cut_grade` | CharField | DiamondCutGrade |
| `color_grade` | CharField | DiamondColorGrade |
| `clarity_grade` | CharField | DiamondClarityGrade |
| `gia_cert_number` | CharField(50) | unique, nullable |
| `igi_cert_number` | CharField(50) | nullable |
| `cert_image` | ImageField | upload_to="diamond-certs/" |
| `shape` | CharField(50) | Round / Princess / Oval / Marquise / Pear |
| `fluorescence` | CharField(20) | None / Faint / Medium / Strong |
| `depth_pct` | DecimalField(5,2) | nullable |
| `table_pct` | DecimalField(5,2) | nullable |
| `measurements_mm` | CharField(50) | L×W×H |
| `price_per_carat` | DecimalField(12,2) | nullable, reference rate |

**Mixin:** `ModelWithMetadata`

---

## 8. Jewellery Variant

### JewelleryVariant
A specific, purchasable SKU. One JewelleryDesign → many JewelleryVariants distinguished by metal, purity, size, and stones.

**Example:** "Floral Ring" design has variants:
- SKU-001: 22K Gold, 5.2g, Size 12
- SKU-002: 18K White Gold + 0.50ct VVS1 Diamond, Size 12
- SKU-003: 950 Platinum, 6.1g, Size 14

| Field | Type | Notes |
|---|---|---|
| `sku` | CharField(255) | unique, null, blank |
| `name` | CharField(255) | auto-generated or custom |
| `design` | FK → JewelleryDesign | CASCADE, related_name="variants" |
| **— METAL —** | | |
| `metal_purity` | FK → MetalPurityStandard | PROTECT |
| **— WEIGHT —** | | |
| `gross_weight_grams` | DecimalField(8,3) | min=0.001, total incl. stones |
| `net_weight_grams` | DecimalField(8,3) | min=0.001, metal weight only |
| `stone_weight_carats` | DecimalField(8,3) | default=0.000 |
| **— MAKING CHARGES —** | | |
| `making_charge_type` | CharField | MakingChargeType, blank |
| `making_charge_value` | DecimalField(8,2) | flat/gram or % value |
| `wastage_percentage` | DecimalField(5,2) | default=0.00 |
| **— SIZE —** | | |
| `size` | CharField(20) | ring size / chain length |
| `size_unit` | CharField(20) | "inch", "cm", "ring_size_IN" |
| **— HALLMARKING —** | | |
| `is_hallmarked` | BooleanField | |
| `hallmark_number` | CharField(100) | blank |
| `hallmark_centre` | CharField(100) | BIS centre name |
| **— STONES —** | | |
| `primary_diamond` | OneToOneField → DiamondSpecification | SET_NULL, nullable |
| `side_stones` | M2M → DiamondSpecification | through VariantSideStone |
| `gemstone_type` | CharField(100) | Ruby / Emerald / Sapphire / Pearl |
| `gemstone_weight` | DecimalField(7,3) | null, blank |
| **— CUSTOMIZATION —** | | |
| `is_customizable` | BooleanField | |
| `custom_engraving_available` | BooleanField | |
| `lead_time_days` | PositiveIntegerField | default=0 |
| **— INVENTORY —** | | |
| `track_inventory` | BooleanField | default=True |
| `is_preorder` | BooleanField | default=False |
| `preorder_end_date` | DateTimeField | null, blank |
| `preorder_global_threshold` | IntegerField | null, blank |
| `quantity_limit_per_customer` | IntegerField | null, blank, min=1 |
| **— MEDIA —** | | |
| `media` | M2M → JewelleryMedia | through JewelleryVariantMedia |
| `created_at` | DateTimeField | auto_now_add |
| `updated_at` | DateTimeField | auto_now |

**Mixins:** `SortableModel`, `ModelWithMetadata`, `ModelWithExternalReference`

**Indexes:**
- GinIndex on `(name, sku)` (trigram)
- BTreeIndex on `gross_weight_grams`
- Index on `(metal_purity_id, size)`

**Key Methods:**
```python
def get_net_metal_weight(self) -> Decimal:
    """Metal weight after wastage deduction."""
    wastage = self.wastage_percentage / Decimal("100")
    return self.net_weight_grams * (1 - wastage)

def is_preorder_active(self) -> bool:
    return self.is_preorder and (
        self.preorder_end_date is None
        or timezone.now() <= self.preorder_end_date
    )

def get_price(self, channel_listing, promotion_rules=None) -> Money:
    if promotion_rules is None:
        return channel_listing.discounted_price or channel_listing.price
    return calculate_discounted_price_for_rules(
        price=channel_listing.price,
        rules=promotion_rules,
        currency=channel_listing.currency,
    )
```

### VariantSideStone
Through model for accent / side diamonds on a variant.

| Field | Type | Notes |
|---|---|---|
| `variant` | FK → JewelleryVariant | CASCADE |
| `diamond` | FK → DiamondSpecification | CASCADE |
| `quantity` | PositiveIntegerField | default=1 |
| `setting_type` | CharField(50) | Prong / Bezel / Pave / Channel |

**Mixin:** `SortableModel`  
**Constraint:** `unique_together = (("variant", "diamond"),)`

### JewelleryVariantTranslation
| Field | Type |
|---|---|
| `variant` | FK → JewelleryVariant |
| `language_code` | CharField |
| `name` | CharField(255) |

---

## 9. Channel Listings & Pricing

### JewelleryVariantChannelListing

| Field | Type | Notes |
|---|---|---|
| `variant` | FK → JewelleryVariant | CASCADE |
| `channel` | FK → Channel | CASCADE |
| `currency` | CharField | |
| **— METAL COMPONENT —** | | |
| `metal_spot_price_amount` | DecimalField | spot price/gram at last compute |
| `metal_spot_price` | MoneyField | |
| `metal_value_amount` | DecimalField | net_weight × spot × purity_factor |
| `metal_value` | MoneyField | |
| **— MAKING CHARGES —** | | |
| `making_charges_amount` | DecimalField | default=0.00 |
| `making_charges` | MoneyField | |
| **— WASTAGE —** | | |
| `wastage_amount` | DecimalField | default=0.00 |
| `wastage` | MoneyField | |
| **— STONE VALUE —** | | |
| `stone_value_amount` | DecimalField | default=0.00 |
| `stone_value` | MoneyField | |
| **— TAX —** | | |
| `gst_amount` | DecimalField | default=0.00 |
| `gst` | MoneyField | |
| **— FINAL PRICES —** | | |
| `price_amount` | DecimalField | total MRP |
| `price` | MoneyField | |
| `cost_price_amount` | DecimalField | landed cost (internal) |
| `cost_price` | MoneyField | |
| `prior_price_amount` | DecimalField | strikethrough display |
| `prior_price` | MoneyField | |
| `discounted_price_amount` | DecimalField | after promotions |
| `discounted_price` | MoneyField | |
| **— PROMOTIONS —** | | |
| `promotion_rules` | M2M → PromotionRule | through JewelleryVariantListingPromotionRule |
| **— MISC —** | | |
| `preorder_quantity_threshold` | IntegerField | null, blank |
| `price_computed_at` | DateTimeField | auto_now, audit trail |

**Constraint:** `unique_together = [["variant", "channel"]]`
**Indexes:** GinIndex on `(price_amount, channel_id)`, BTreeIndex on `metal_spot_price_amount`

### JewelleryVariantListingPromotionRule

| Field | Type |
|---|---|
| `variant_channel_listing` | FK → JewelleryVariantChannelListing |
| `promotion_rule` | FK → PromotionRule |
| `discount_amount` | DecimalField |
| `discount` | MoneyField |
| `currency` | CharField |

**Constraint:** `unique_together = [["variant_channel_listing", "promotion_rule"]]`

### MetalSpotPriceRecord

Tracks live gold / silver / platinum rates per channel. When updated, a background task recomputes all active `JewelleryVariantChannelListing` prices.

| Field | Type | Notes |
|---|---|---|
| `metal_type` | CharField | MetalTypeChoices, db_index |
| `purity_standard` | FK → MetalPurityStandard | CASCADE |
| `channel` | FK → Channel | CASCADE |
| `currency` | CharField | |
| `price_per_gram` | DecimalField(12,4) | |
| `recorded_at` | DateTimeField | auto_now_add, db_index |
| `source` | CharField(100) | "MCX" / "LBMA" / "manual" |

**Ordering:** `("-recorded_at")`  
**Index:** BTreeIndex on `(metal_type, recorded_at)`


## 10. Attributes

Following Saleor's two-tier attribute system — attributes are assigned at the Type level and values at the Design or Variant level.

### Product-Level Attributes (on JewelleryDesign)

| Attribute Slug | Input Type | Example Values |
|---|---|---|
| `style-theme` | DROPDOWN | Floral, Geometric, Vintage, Temple, Minimalist |
| `occasion` | MULTISELECT | Wedding, Everyday, Festival, Gifting |
| `gender` | DROPDOWN | Women, Men, Unisex, Kids |
| `setting-type` | DROPDOWN | Prong, Bezel, Pave, Channel, Invisible |
| `closure-type` | DROPDOWN | Lobster, Toggle, Box, Push, Spring Ring |
| `collection-series` | DROPDOWN | Bridal 2025, Heritage, Zodiac, Solitaire |
| `inspired-by` | PLAIN_TEXT | "Mughal Art", "South Indian Temple" |
| `certification-body` | MULTISELECT | BIS, GIA, IGI, SGL |

### Variant-Level Attributes (on JewelleryVariant)

| Attribute Slug | Input Type | Variant Selection | Example Values |
|---|---|---|---|
| `metal-type` | DROPDOWN | YES | Gold, Silver, Platinum, White Gold |
| `metal-purity` | DROPDOWN | YES | 22K, 18K, 14K, 950, 925 |
| `ring-size` | DROPDOWN | YES | 10, 11, 12, 13, 14, 15 |
| `chain-length-inch` | DROPDOWN | YES | 16, 18, 20, 22, 24 |
| `bracelet-size-cm` | DROPDOWN | YES | 16cm, 17cm, 18cm, 19cm |
| `finish-type` | DROPDOWN | NO | Matte, Polished, Brushed, Hammered |
| `rhodium-plating` | BOOLEAN | NO | Yes / No |
| `diamond-carat` | NUMERIC | YES | 0.25, 0.50, 0.75, 1.00 |
| `diamond-clarity` | DROPDOWN | YES | VVS1, VVS2, VS1, VS2, SI1 |
| `diamond-color` | DROPDOWN | YES | D, E, F, G, H |
| `diamond-cut` | DROPDOWN | YES | Excellent, Very Good, Good |
| `gemstone-type` | DROPDOWN | YES | Ruby, Emerald, Sapphire, Pearl |

---

## 11. Media

### JewelleryMedia
Extended media model supporting jewellery-specific angle tags and types.

| Field | Type | Notes |
|---|---|---|
| `design` | FK → JewelleryDesign | null, blank |
| `image` | ImageField | upload_to="jewellery/" |
| `alt` | CharField(250) | accessibility |
| `media_type` | CharField | IMAGE / VIDEO / VIEW_360 / CAD |
| `external_url` | CharField(2048) | null, blank |
| `oembed_data` | JSONField | blank, default=dict |
| `angle_tag` | CharField | MediaAngleTag, blank |
| `is_primary` | BooleanField | default=False |

**Mixins:** `SortableModel`, `ModelWithMetadata`
**Ordering:** `("sort_order", "pk")`

### JewelleryVariantMedia
Selectively assigns design-level media to specific variants.

| Field | Type |
|---|---|
| `variant` | FK → JewelleryVariant |
| `media` | FK → JewelleryMedia |

**Constraint:** `unique_together = ("variant", "media")`

---

## 12. Collections

### JewelleryCollection
Curated marketing collections.

| Field | Type | Notes |
|---|---|---|
| `name` | CharField(250) | |
| `slug` | SlugField(255) | unique |
| `designs` | M2M → JewelleryDesign | through JewelleryCollectionDesign |
| `background_image` | ImageField | |
| `background_image_alt` | CharField(128) | |
| `description` | SanitizedJSONField | |

**Mixins:** `SeoModel`, `ModelWithMetadata`
**Index:** GinIndex on `(name, slug)`

**Examples:** "Bridal 2025" · "Diamond Solitaires" · "Gold Under ₹50,000" · "Everyday Silver"

### JewelleryCollectionDesign
Sortable through model for Collection ↔ Design M2M.

| Field | Type |
|---|---|
| `collection` | FK → JewelleryCollection |
| `design` | FK → JewelleryDesign |

**Mixin:** `SortableModel`
**Constraint:** `unique_together = (("collection", "design"),)`

### JewelleryCollectionChannelListing

| Field | Type |
|---|---|
| `collection` | FK → JewelleryCollection |
| `channel` | FK → Channel |
| `is_published` | BooleanField |
| `published_at` | DateTimeField |

**Constraint:** `unique_together = [["collection", "channel"]]`

### JewelleryCollectionTranslation

| Field | Type |
|---|---|
| `collection` | FK → JewelleryCollection |
| `language_code` | CharField |
| `name` | CharField(128) |
| `description` | SanitizedJSONField |

---

## 13. Inventory — Lot / Batch

### JewelleryLot
A batch of jewellery received or produced together. Has its own status lifecycle and transactional methods that cascade to all items.

| Field | Type | Notes |
|---|---|---|
| `id` | UUIDField | primary key |
| `lot_number` | CharField(100) | unique |
| `lot_type` | CharField | LotType, db_index |
| `status` | CharField | LotStatus, db_index, default=DRAFT |
| **— SOURCE —** | | |
| `supplier_name` | CharField(250) | blank |
| `supplier_invoice_ref` | CharField(100) | blank |
| `purchase_order_ref` | CharField(100) | blank |
| `grn_number` | CharField(100) | blank |
| **— RECEIPT —** | | |
| `received_date` | DateField | db_index |
| `warehouse` | FK → Warehouse | PROTECT |
| `metal_purity` | FK → MetalPurityStandard | PROTECT, nullable |
| **— WEIGHTS —** | | |
| `total_gross_weight_grams` | DecimalField(10,3) | default=0.000 |
| `total_net_weight_grams` | DecimalField(10,3) | default=0.000 |
| `expected_item_count` | PositiveIntegerField | default=0 |
| **— ASSAY / QUALITY —** | | |
| `assay_cert_number` | CharField(100) | blank |
| `assay_report` | FileField | upload_to="lot-assay-reports/" |
| `quality_approved` | BooleanField | default=False |
| `quality_approved_by` | CharField(250) | blank |
| `quality_approved_at` | DateTimeField | blank, null |
| **— MISC —** | | |
| `notes` | TextField | blank |
| `created_at` | DateTimeField | auto_now_add |
| `updated_at` | DateTimeField | auto_now |

**Mixin:** `ModelWithMetadata`
**Indexes:** BTreeIndex on `received_date`, BTreeIndex on `(lot_type, status)`, GinIndex on `(lot_number, supplier_name)`

**Computed Properties:**
```python
lot.actual_item_count          # items.count()
lot.available_item_count       # items.filter(status=AVAILABLE).count()
lot.sold_item_count            # items.filter(status=SOLD).count()
lot.actual_total_gross_weight  # Sum of item actual_gross_weight_grams
```

**Lot-Level Transactional Methods:**

| Method | Lot Status Change | Cascades to Items |
|---|---|---|
| `raise_grn(grn_number)` | DRAFT → GRN_RAISED | — |
| `approve_quality(approved_by)` | GRN_RAISED → APPROVED | QUARANTINE/ON_HOLD → AVAILABLE |
| `reject_quality(rejected_by)` | any → QUARANTINE | non-sold → QUARANTINE |
| `transfer_lot(to_warehouse)` | unchanged | AVAILABLE → AVAILABLE (new warehouse) |
| `scrap_lot()` | any → SCRAPPED | non-sold → SCRAPPED |
| `close_lot()` | PARTIAL → CLOSED | — |

### LotEvent
Immutable audit log for every transaction on a JewelleryLot.

| Field | Type | Notes |
|---|---|---|
| `lot` | FK → JewelleryLot | CASCADE, related_name="events" |
| `event_type` | CharField | LotEventType, db_index |
| `from_status` | CharField | LotStatus |
| `to_status` | CharField | LotStatus |
| `from_warehouse` | FK → Warehouse | SET_NULL, nullable |
| `to_warehouse` | FK → Warehouse | SET_NULL, nullable |
| `item_count_snapshot` | PositiveIntegerField | total items at time of event |
| `available_count_snapshot` | PositiveIntegerField | available items at time of event |
| `notes` | TextField | blank |
| `created_by` | CharField(250) | blank |
| `created_at` | DateTimeField | auto_now_add, db_index |

**Ordering:** `("-created_at")`
**Indexes:** Index on `(lot, created_at)`, Index on `(event_type, created_at)`

---

## 14. Inventory — Unique Stock Item

### JewelleryStockItem
Represents ONE unique physical piece of jewellery.
Unlike Saleor's integer-based `Stock` (quantity=10), **each row = one actual item** with its own identity, weight, status, and history.

| Field | Type | Notes |
|---|---|---|
| `id` | UUIDField | primary key |
| `variant` | FK → JewelleryVariant | PROTECT, related_name="stock_items" |
| `lot` | FK → JewelleryLot | SET_NULL, nullable |
| `warehouse` | FK → Warehouse | PROTECT |
| `location_note` | CharField(200) | "Showcase 3 / Shelf B / Vault Row 2" |
| **— IDENTITY —** | | |
| `barcode` | CharField(100) | unique, nullable |
| `rfid_tag` | CharField(100) | unique, nullable |
| `internal_tag` | CharField(100) | blank |
| **— HALLMARKING —** | | |
| `hallmark_number` | CharField(100) | blank |
| `hallmark_centre` | CharField(100) | blank |
| `hallmark_verified_at` | DateTimeField | blank, null |
| **— ACTUAL WEIGHTS —** | | |
| `actual_gross_weight_grams` | DecimalField(8,3) | blank, null, physically weighed |
| `actual_net_weight_grams` | DecimalField(8,3) | blank, null |
| `weight_verified_at` | DateTimeField | blank, null |
| **— STATUS —** | | |
| `status` | CharField | StockItemStatus, db_index, default=AVAILABLE |
| **— ORDER / CHECKOUT —** | | |
| `order_line` | OneToOneField → OrderLine | SET_NULL, nullable — set when sold |
| `checkout_line` | FK → CheckoutLine | SET_NULL, nullable — set when in cart |
| `reserved_until` | DateTimeField | null, blank — checkout hold expiry |
| **— MISC —** | | |
| `notes` | TextField | blank |
| `created_at` | DateTimeField | auto_now_add, db_index |
| `updated_at` | DateTimeField | auto_now |

**Mixin:** `ModelWithMetadata`

**Indexes:**
- Index on `(variant, status)`
- Index on `(warehouse, status)`
- Index on `(lot, status)`
- BTreeIndex on `barcode`
- BTreeIndex on `rfid_tag`
- Index on `(status, reserved_until)`

**Item-Level Transactional Methods:**

| Method | Status Change | Side Effect |
|---|---|---|
| `reserve(checkout_line, until)` | AVAILABLE → RESERVED | Creates `StockItemEvent(RESERVED)` |
| `release_reservation()` | RESERVED → AVAILABLE | Creates `StockItemEvent(RESERVATION_EXPIRED)`, syncs lot |
| `sell(order_line)` | RESERVED → SOLD | Creates `StockItemEvent(SOLD)`, syncs lot to PARTIAL/CLOSED |
| `process_return(order_line)` | SOLD → RETURNED | Creates `StockItemEvent(RETURNED)` |
| `transfer(to_warehouse)` | unchanged | Creates `StockItemEvent(TRANSFERRED)` |

**Availability Queries:**
```python
# Available count for a variant
JewelleryStockItem.objects.filter(
    variant=variant,
    status=StockItemStatus.AVAILABLE
).count()

# All items in a lot
lot.items.all()

# All items in a warehouse by status
JewelleryStockItem.objects.filter(
    warehouse=warehouse,
    status=StockItemStatus.AVAILABLE
)

# Expire stale checkout reservations (background task)
JewelleryStockItem.objects.filter(
    status=StockItemStatus.RESERVED,
    reserved_until__lt=timezone.now()
).update(
    status=StockItemStatus.AVAILABLE,
    checkout_line=None,
    reserved_until=None
)
```

---



## 15. Audit Trail

### StockItemEvent
Immutable audit log for every status change on a JewelleryStockItem.

`triggered_by_lot_event` links back to the LotEvent that caused this item event. If null, the event was triggered by an individual item action.

| Field | Type | Notes |
|---|---|---|
| `item` | FK → JewelleryStockItem | CASCADE, related_name="events" |
| `event_type` | CharField | StockItemEventType, db_index |
| `from_status` | CharField | StockItemStatus |
| `to_status` | CharField | StockItemStatus |
| `from_warehouse` | FK → Warehouse | SET_NULL, nullable |
| `to_warehouse` | FK → Warehouse | SET_NULL, nullable |
| `order_line` | FK → OrderLine | SET_NULL, nullable |
| `triggered_by_lot_event` | FK → LotEvent | SET_NULL, nullable — bidirectional link |
| `notes` | TextField | blank |
| `created_by` | CharField(250) | blank |
| `created_at` | DateTimeField | auto_now_add, db_index |

**Ordering:** `("-created_at")`  
**Indexes:** Index on `(item, created_at)`, Index on `(event_type, created_at)`, Index on `triggered_by_lot_event`

### Bidirectional Traceability

```text
LotEvent (lot.transfer_lot called)
  id = lot_event_42
  event_type = TRANSFERRED
  lot = "CAST-2025-001"
        │
   ┌────┼────┐
   ▼    ▼    ▼
StockItemEvent  StockItemEvent  StockItemEvent
item = Ring-01  item = Ring-02  item = Ring-03
type = TRANSFER type = TRANSFER type = TRANSFER
triggered_by    triggered_by    triggered_by
= lot_event_42  = lot_event_42  = lot_event_42
```
# Forward: all items affected by a lot event
lot_event.triggered_item_events.all()

# Backward: was this item event part of a lot action?
item_event.triggered_by_lot_event


Transaction Coverage

| Transaction | Initiated At | Creates | Cascades To |
|---|---|---|---|
| GRN raised | Lot | LotEvent(GRN_RAISED) | — |
| Quality approved | Lot | LotEvent(QUALITY_APPROVED) | StockItemEvent(RECEIVED) per item |
| Quality rejected | Lot | LotEvent(QUALITY_REJECTED) | StockItemEvent(QUARANTINED) per item |
| Lot transferred | Lot | LotEvent(TRANSFERRED) | StockItemEvent(TRANSFERRED) per item |
| Lot scrapped | Lot | LotEvent(SCRAPPED) | StockItemEvent(SCRAPPED) per item |
| Lot closed | Lot | LotEvent(CLOSED) | — |
| Item reserved | Item | StockItemEvent(RESERVED) | LotEvent(PARTIALLY_SOLD) if first sale |
| Item sold | Item | StockItemEvent(SOLD) | LotEvent(CLOSED) if last item |
| Item returned | Item | StockItemEvent(RETURNED) | — |
| Item transferred individually | Item | StockItemEvent(TRANSFERRED) | — |

---

## 16. Pricing Formula

```text
JewelleryVariantChannelListing.compute_total_price()

Step 1 — Metal Value
  metal_value = net_weight_grams
              × price_per_gram
              × purity_factor

Step 2 — Making Charges
  FLAT_PER_GRAM:  making_charges = making_charge_value × net_weight_grams
  PERCENTAGE:     making_charges = metal_value × (making_charge_value / 100)
  FLAT_FIXED:     making_charges = making_charge_value

Step 3 — Wastage
  wastage = metal_value × (wastage_percentage / 100)

Step 4 — Stone Value
  stone_value = primary_diamond.carat_weight × price_per_carat
              + Σ(side_stone.carat_weight × quantity × price_per_carat)

Step 5 — GST
  subtotal = metal_value + making_charges + wastage + stone_value
  gst = subtotal × gst_rate

Step 6 — Total MRP
  price_amount = metal_value + making_charges + wastage + stone_value + gst
```

Worked example:

**22K Gold Floral Ring: 5.2g gross, 4.8g net, 12% making, 2% wastage, no stones

Gold spot rate        = ₹6,000 / gram
22K purity factor     = 22 / 24 = 0.9167

metal_value           = 4.8 × 6,000 × 0.9167  = ₹26,400.00
making_charges        = 26,400 × 12%           = ₹ 3,168.00
wastage               = 26,400 × 2%            = ₹   528.00
stone_value           = ₹0.00
subtotal              = ₹30,096.00
GST (3%)              = ₹   902.88
────────────────────────────────────
Total MRP             = ₹30,998.88
```

---

## 17. Key Design Decisions

| Decision | Saleor Original | Jewellery Adaptation | Reason |
|---|---|---|---|
| Variant Pricing | Fixed price_amount | Computed from spot rate + weight + making | Metal price fluctuates daily |
| Weight | Single Weight measurement | gross_weight + net_weight + stone_weight | Billing requires breakdown |
| Metal | Generic attribute | First-class MetalPurityStandard FK on variant | Critical for pricing math and compliance |
| Diamonds | Generic attribute values | Dedicated DiamondSpecification with 4C grades | GIA certification, complex grading |
| Media | ProductMedia | Extended with angle_tag, VIEW_360, CAD type | 360° and CAD renders are jewellery-specific |
| Making Charges | Not applicable | Three-mode charge model (flat / pct / fixed) | Domain-specific cost component |
| Live Rates | Not applicable | MetalSpotPriceRecord + price_computed_at | Gold prices change intraday |
| Hallmarking | Not applicable | is_hallmarked, hallmark_number, hallmark_centre | Regulatory compliance (BIS India) |
| Side Stones | Not applicable | VariantSideStone with quantity + setting_type | Multiple accent diamonds per piece |
| Price Breakdown | Single price field | 6-component breakdown stored on listing | Transparent pricing for customer |
| Stock Model | Stock (integer quantity) | JewelleryStockItem (1 row = 1 piece) | Every jewellery item is unique |
| Lot / Batch | Not applicable | JewelleryLot with GRN, assay cert, supplier | Traceability from casting to sale |
| Lot Transactions | Not applicable | LotEvent — lot-level audit log | Bulk operations (transfer, scrap, approve) |
| Item Transactions | Not applicable | StockItemEvent — item-level audit log | Individual sales, returns, repairs |
| Bidirectional Audit | Not applicable | triggered_by_lot_event FK on StockItemEvent | Trace any item event back to a lot action |

```

