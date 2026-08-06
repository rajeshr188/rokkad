I traced Girvi’s complete loan-ticket composition path. Its printing flexibility comes from two separate layers:

```text
TemplateFrame positioning
        +
LoanTemplate print_option
        =
Final page sequence
```

## 1. The four uploaded PDFs

Each Girvi `LoanTemplate` can contain:

| Asset | Purpose |
|---|---|
| `base_template` | Original-copy front background |
| `dup_template` | Duplicate-copy front background |
| `terms_template` | Original-copy back page |
| `form_d3_template` | Duplicate-copy back page |

The first two receive positioned loan data. Terms and D3 are normally inserted as complete back pages without positioned loan data.

## 2. How positioned data works

Every `TemplateFrame` defines:

- Field, image, table or QR type
- X and Y in centimetres
- Width and height
- Font and size
- Original, Duplicate or Both applicability

Girvi uses PDF coordinates:

```text
Origin: bottom-left
X: distance from left
Y: distance from bottom
```

The browser preview converts them to top-left CSS coordinates:

```text
top = page_height - y_pos - height
```

Text and tables use `KeepInFrame(mode="shrink")`, so oversized content is reduced to fit its rectangle.

## 3. Original/duplicate frame conditions

Each frame has one of:

```text
O = Original only
D = Duplicate only
B = Both copies
```

When Girvi renders an original, it selects:

```text
Original frames + Both frames
```

When it renders a duplicate:

```text
Duplicate frames + Both frames
```

These are copy-applicability conditions, not general business conditions.

For example:

- A customer signature label can appear only on the original.
- An office-use label can appear only on the duplicate.
- Loan number and amount can appear on both.

## 4. Girvi’s eight print modes

Girvi does not dynamically combine arbitrary pages. It has eight hardcoded composition modes.

| Code | Mode | Final output |
|---|---|---|
| `O` | Original only | 1 × A5 page |
| `OT` | Original + terms | 2 × A5 pages |
| `D` | Duplicate only | 1 × A5 page |
| `DF` | Duplicate + D3 | 2 × A5 pages |
| `BS` | Both single-sided | 2 × A5 pages |
| `BD` | Both double-sided | 4 × A5 pages |
| `BA` | Both on one A4 landscape | 1 × A4 landscape page |
| `BDA` | Both duplex on A4 landscape | 2 × A4 landscape pages |

## 5. Standard A5 modes

### Original only — `O`

```text
A5 page 1
┌─────────────────────────┐
│ Original background     │
│ + Original/Both frames  │
└─────────────────────────┘
```

### Original with terms — `OT`

```text
A5 page 1: Original front + positioned data
A5 page 2: Terms PDF
```

Printed duplex:

```text
Physical sheet
Front: Original
Back:  Terms
```

### Duplicate only — `D`

```text
A5 page 1: Duplicate background + Duplicate/Both frames
```

### Duplicate with D3 — `DF`

```text
A5 page 1: Duplicate front + positioned data
A5 page 2: Form D3
```

Printed duplex:

```text
Physical sheet
Front: Duplicate
Back:  D3
```

### Both single-sided — `BS`

```text
A5 page 1: Original
A5 page 2: Duplicate
```

These are sequential A5 pages. They are not combined side by side.

### Both double-sided — `BD`

With all four assets present:

```text
A5 page 1: Original front
A5 page 2: Terms
A5 page 3: Duplicate front
A5 page 4: Form D3
```

Physical duplex interpretation:

```text
Sheet 1
  Front: Original
  Back:  Terms

Sheet 2
  Front: Duplicate
  Back:  D3
```

## 6. A4 landscape side-by-side mode — `BA`

Girvi creates two half-A4 canvases. Each half is approximately A5 portrait.

```text
A4 landscape page 1

┌──────────────────────┬──────────────────────┐
│ Original A5          │ Duplicate A5         │
│                      │                      │
│ Original + Both      │ Duplicate + Both     │
│ frames               │ frames               │
└──────────────────────┴──────────────────────┘
```

Composition steps:

1. Render original data onto a half-A4 canvas.
2. Merge it over `base_template`.
3. Render duplicate data onto another half-A4 canvas.
4. Merge it over `dup_template`.
5. Place the two resulting A5 pages side by side on one A4 landscape page.

This is intended for printing one A4 sheet and cutting or folding it into two A5 copies.

## 7. A4 landscape duplex mode — `BDA`

The front is identical to `BA`:

```text
A4 landscape page 1 — front

┌──────────────────────┬──────────────────────┐
│ Original front       │ Duplicate front      │
└──────────────────────┴──────────────────────┘
```

The back combines Terms and D3:

```text
A4 landscape page 2 — back

┌──────────────────────┬──────────────────────┐
│ Original terms       │ Form D3              │
└──────────────────────┴──────────────────────┘
```

Physical duplex sheet:

```text
Front-left   → Original ticket
Back-left    → Original terms

Front-right  → Duplicate ticket
Back-right   → Form D3
```

Girvi does not rotate the back page. Correct front/back alignment therefore depends on the printer’s landscape duplex setting—typically the appropriate short-edge/long-edge option for that printer.

## 8. Important missing-asset behaviour

Girvi treats missing assets as warnings rather than blockers.

Examples:

- `O` without an original background prints positioned data on a blank page.
- `D` without a duplicate background prints positioned data on a blank page.
- `OT` produces two pages only when both original and terms PDFs exist. Otherwise it returns only the generated content page.
- `DF` behaves similarly for duplicate and D3.
- `BDA` adds its back A4 page only when both Terms and D3 exist. If either is missing, the entire back landscape page is omitted.

This makes Girvi operationally forgiving, but potentially dangerous: a document can be “ready with warnings” while lacking a legal back page.

## 9. Other architectural observations

- Standard output is always rendered as A5, regardless of the stored `page_width` and `page_height`.
- A4 combination modes are always landscape A4.
- Stored dimensions primarily validate and preview frame geometry.
- Uploaded PDFs are assumed to have appropriate dimensions and usually one relevant page.
- Multi-page uploaded backgrounds can produce surprising results because asset page counts are not strictly normalized.
- Original/Duplicate/Both frames with the same field can overlap if configured carelessly.
- The print-mode composition is hardcoded inside the Girvi renderer.

## What Loans should carry forward

Loans should represent this as an explicit sheet-composition policy instead of only the current three copy modes.

A suitable model would include presets such as:

```text
A5_ORIGINAL
A5_ORIGINAL_TERMS_DUPLEX
A5_DUPLICATE
A5_DUPLICATE_D3_DUPLEX
A5_ORIGINAL_DUPLICATE_SIMPLEX
A5_ORIGINAL_TERMS_DUPLICATE_D3_DUPLEX
A4_LANDSCAPE_SIDE_BY_SIDE
A4_LANDSCAPE_SIDE_BY_SIDE_DUPLEX
```

The crucial distinction is:

```text
Document layout
    = where fields appear within one logical copy

Sheet composition
    = how original, duplicate, terms and D3 pages are arranged for printing
```

