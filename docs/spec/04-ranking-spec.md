# Filtering + Ranking Spec (Deterministic, Geo-first)

## Core Rule
Primary retrieval must be deterministic: structured filters + geo distance + openNow + explicit sort preferences.
Semantic similarity must not be used for primary ranking.

## Filtering Precedence (REQUIRED)
When multiple filters are detected, they MUST be applied in this strict order:

1. **Open hours** (if `open_now` detected) - HIGHEST PRIORITY
   - Filter to only open places first (strict phase)
   - If < 5 results, include unknown status places (relaxed phase)
   - Exclude closed places

2. **Proximity** (if `user_location` provided) - SECOND PRIORITY
   - Apply radius escalation: 0.5km → 1km → 2km
   - Filter places within radius
   - Stop when >= 5 results or max radius reached

3. **Classification/Category** (if `categories` detected) - THIRD PRIORITY
   - Filter by category keywords (e.g., "açaí", "sushi", "pizza")
   - Match against categoryName, categories[], and title
   - Use accent-insensitive matching

4. **Other structured filters** (place_type, city, neighborhood, price, min_rating, min_reviews) - FOURTH PRIORITY
   - Apply remaining structured filters

5. **Popularity/Rating** (used in ranking, not filtering) - FIFTH PRIORITY
   - Applied during final ranking/sorting phase
   - Does not filter out candidates, only affects order

**Rationale:** This precedence ensures that:
- User's most important constraint (open hours) is respected first
- Proximity is prioritized over category matching
- Category filtering happens after geo filtering to avoid checking distant places
- Popularity/rating only affects ranking, not eligibility

## Candidate Eligibility
A Place is eligible if it passes all applicable filters in precedence order:

**Note:** Filtering happens in stages per the precedence order above. A place must pass:
1. Open hours filter (if open_now requested) - applied FIRST
2. Proximity filter (if user_location provided) - applied SECOND  
3. Category filter (if categories detected) - applied THIRD
4. Other structured filters:
   - location.lat and location.lng exist (required for geo queries)
   - place_type matches requested types if provided
   - city/neighborhood match if provided (case-insensitive exact/contains)
   - price <= price_max if provided and place has price
   - totalScore >= min_rating if provided and place has totalScore
   - reviewsCount >= min_reviews if provided and place has reviewsCount

**Category Matching:**
- Categories are matched against:
  - `categoryName` field
  - `categories[]` array (categories/0 through categories/8)
  - `title` and `titleFormatted` fields (for cases like "açaí shop" in title)
- Matching is accent-insensitive and case-insensitive
- Uses normalized comparison (NFD normalization, remove accents)

## Radius Strategy (required)
When user_location exists, apply auto escalation:
1) radius = 0.5 km
2) if results < 5 => radius = 1.0 km
3) if results < 5 => radius = 2.0 km
Stop after 2.0 km (max). Return whatever results exist (0..5).

If user explicitly provides a radius, use that instead of auto escalation, but cap at 5 km for PoC unless specified.

## Distance Computation
Use Haversine distance (km). Store computed distanceKm per candidate.

## OpenNow Filtering (required)
If slots.open_now=true:
- Parse businessTime into weekly schedule (see parser notes below).
- Filtering behavior is two-phase to avoid empty results:

Phase A (strict):
- Keep only places that are confidently OPEN now.

If Phase A yields < 5 results, Phase B (relaxed):
- Include places with unknown/unparseable businessTime, but mark `openNowStatus="unknown"`.
- Exclude places confidently CLOSED now.

If open_now is not requested:
- Do not filter by businessTime.

### businessTime parser notes
Because source format may vary, implement a robust parser with these supported patterns:
1) JSON-like weekly structure (e.g., {"Mon":"09:00-18:00", ...})
2) Semicolon-delimited text (e.g., "Mon 09:00-18:00; Tue 09:00-18:00; ...")
3) Single string "Open 24 hours" / "24 horas" => always open
If parsing fails => status unknown.

Timezone:
- Use device/client timezone if provided; otherwise use server local timezone for PoC.

## Lexical Matching (optional but recommended)
After structured filtering, apply lexical scoring for keywords against:
- title/titleFormatted
- categoryName
- categories[]
- neighborhood/city
Lexical scoring is used only to break ties within the deterministic ranking mode.

No embeddings for lexical scoring.

## Sort Modes
Return exactly 5 results (or fewer if not enough eligible).

### sort_preference=distance
Primary: distanceKm ASC
Tie-breakers: totalScore DESC, reviewsCount DESC

### sort_preference=rating
Primary: totalScore DESC
Tie-breakers: reviewsCount DESC, distanceKm ASC (if user_location exists)

### sort_preference=popularity
Primary: reviewsCount DESC
Tie-breakers: totalScore DESC, distanceKm ASC (if user_location exists)

### sort_preference=best_match
Compute a deterministic composite score:
- rating_norm = clamp(totalScore/5, 0..1) (missing => 0)
- pop_norm = log(1+reviewsCount)/log(1+maxReviewsInCandidateSet) (missing => 0)
- dist_norm = clamp(distanceKm / radiusKmUsed, 0..1) (missing => 1)

composite = 0.45*rating_norm + 0.35*pop_norm + 0.20*(1 - dist_norm)

Sort by composite DESC, tie-breakers: distanceKm ASC.

## Sponsored Handling
isSponsored must NOT override ranking.
If needed as tie-breaker only:
- After all other tie-breakers, prefer non-sponsored first (or keep stable). Default: stable (no change).

## Output Fields for UI
Each returned result MUST include:
- placeId, title, categoryName, addressFormatted (or fallback), location, distanceKm,
- totalScore, reviewsCount, price, website/url,
- openNowStatus: "open|closed|unknown" (when open_now requested)