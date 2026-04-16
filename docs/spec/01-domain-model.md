# Domain Model — Place + Subtypes

## Canonical Entity: Place
The PoC uses a single canonical entity "Place" with a field `place_type` (logical inheritance). Subtypes (restaurant/bar/park/other) are derived and used for filtering and UI.

### Place (canonical fields)
- placeId: string (primary identifier; required)
- cid: string|null
- fid: string|null
- title: string|null
- titleFormatted: string|null
- subTitle: string|null

- categoryName: string|null
- categories: string[] (ordered, derived from categories/0..8 + categoryName)

- address: string|null
- addressFormatted: string|null
- street: string|null
- streetFormatted: string|null
- neighborhood: string|null
- locatedIn: string|null
- city: string|null
- state: string|null
- postalCode: string|null
- countryCode: string|null

- location:
  - lat: number|null
  - lng: number|null

- phone: string|null
- phoneUnformatted: string|null

- url: string|null
- website: string|null
- googleFoodUrl: string|null
- menu: string|null
- reserveTableUrl: string|null

- price: number|null (interpretation: source-provided; do not guess currency)
- rank: number|null
- totalScore: number|null (0–5)
- reviewsCount: number|null
- reviewsDistribution:
  - oneStar: number (default 0)
  - twoStar: number (default 0)
  - threeStar: number (default 0)
  - fourStar: number (default 0)
  - fiveStar: number (default 0)

- isSponsored: boolean (default false)
- businessTime: string|null (source format; parsed by Business Time Parser)

- place_type: enum [restaurant, bar, park, other] (derived)

## Place Type Inference (categories with precedence)
Type inference MUST use both categoryName and categories[], with strict precedence rules:

1) Compute `category_candidates`:
   - First candidate: categoryName (if non-empty)
   - Then candidates: categories/0..8 in numeric order (non-empty)
   - Also ensure categoryName is included in categories[] if not present.

2) Map candidate string -> place_type using a deterministic dictionary (case-insensitive, accent-insensitive).
3) If categoryName maps to a known type, STOP. Otherwise evaluate categories/0..8 in order and pick first mapping.
4) If none matches, set place_type=other.

### Baseline mapping rules (minimum)
- restaurant: contains any of ["restaurant", "restaurante", "steakhouse", "pizza", "pizzaria", "sushi", "churrascaria", "buffet", "cafe", "café", "coffee"]
- bar: contains any of ["bar", "pub", "brewery", "cervejaria", "boteco"]
- park: contains any of ["park", "parque", "garden", "jardim", "praça", "praca"]
- other: default

## Identity Rules
- placeId is the canonical ID. If missing, ingestion fails for that row (log and skip).
- Do not deduplicate unless explicitly specified later.
``