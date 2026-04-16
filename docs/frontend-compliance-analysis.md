# Frontend Compliance Analysis

## Summary
The frontend is **partially compliant** but needs updates to match the new PoC API specification (05-openapi.yaml) and UX spec (07-ux-flutter.md).

## Issues Found

### 1. API Request Format Mismatch ❌

**Current Implementation** (`api_service.dart`):
```dart
body['coordinates'] = {
  'lat': latitude,
  'lng': longitude,
};
```

**Required per OpenAPI spec**:
- Should use `userLocation` instead of `coordinates` (legacy)
- Missing `nowIso` field (client current time in ISO-8601)
- Missing `filters` object support (placeType, city, neighborhood, openNow, priceMax, minRating, minReviews)
- Language should be `"pt-BR"` not `"pt"` (or `"en"`)

**Fix Required**: Update `ApiService.sendMessage()` to match new schema.

### 2. API Response Format Mismatch ❌

**Current Implementation**:
```dart
data['places']  // Expects 'places'
data['response']  // Expects 'response'
```

**Required per OpenAPI spec**:
- Response has `results` (not `places`) - array of PlaceResult objects
- Response has `answer` (not `response`) - LLM response text
- Response has `language` - "en" | "pt-BR"
- Response has `debug` - optional debug information
- Legacy fields (`places`, `response`) are still present for backward compatibility, but should migrate

**Fix Required**: Update response parsing to use `results` and `answer`.

### 3. Place Model Mismatch ❌

**Current Place Model** (`models/place.dart`):
```dart
class Place {
  final String name;  // Should be 'title' or 'titleFormatted'
  final String? address;  // Should prefer 'addressFormatted'
  final String? category;  // Should be 'categoryName'
  // Missing: placeId, openNowStatus, distanceKm (in PlaceResult)
}
```

**Required per OpenAPI spec**:
- `PlaceResult` extends `Place` with:
  - `distanceKm: number | null`
  - `openNowStatus: "open" | "closed" | "unknown" | null`
- `Place` should have:
  - `placeId: string` (required)
  - `title: string | null`
  - `titleFormatted: string | null`
  - `categoryName: string | null`
  - `addressFormatted: string | null` (preferred over `address`)
  - `location: LatLng | null`
  - `totalScore: number | null` (not `rating`)
  - `reviewsCount: number | null` (not `reviews_count`)

**Fix Required**: Update Place model to match OpenAPI PlaceResult schema.

### 4. Place Card Missing Spec Requirements ⚠️

**Current Implementation** (`place_card.dart`):
- ✅ Shows title
- ✅ Shows categoryName
- ✅ Shows distance (km or meters)
- ✅ Shows totalScore + reviewsCount
- ✅ Shows address
- ❌ Missing "Open now" badge (open/closed/unknown)
- ❌ Missing action buttons (open website/url in external browser)

**Required per UX spec**:
- "Open now" badge showing open/closed/unknown status (when requested)
- Action buttons to open website/url in external browser

**Fix Required**: Add openNowStatus badge and website/url action buttons.

### 5. Filter Chips Missing ⚠️

**Current Implementation** (`chat_screen.dart`):
- No filter chips visible

**Required per UX spec**:
- Optional filter chips: Restaurant / Bar / Park / Open now

**Fix Required**: Add filter chips UI component.

### 6. Language Code Mismatch ⚠️

**Current Implementation**:
- Uses `'pt'` and `'en'`

**Required per OpenAPI spec**:
- Should use `'pt-BR'` (not `'pt'`) and `'en'`

**Fix Required**: Update language codes throughout frontend.

### 7. Location Handling ✅

**Current Implementation**:
- ✅ Requests location permission
- ✅ Sends userLocation with /chat request when available
- ✅ Handles denied location gracefully

**Status**: Compliant with spec.

### 8. Bilingual UI ✅

**Current Implementation**:
- ✅ UI strings from i18n (EN + pt-BR)
- ✅ Language toggle in app bar
- ✅ Chat language defaults to message language detection

**Status**: Mostly compliant (just needs language code fix: 'pt' → 'pt-BR').

## Required Changes

### Priority 1: Critical (API Compatibility)

1. **Update `ApiService.sendMessage()`**:
   - Change `coordinates` → `userLocation`
   - Add `nowIso` field (current time in ISO-8601)
   - Add `filters` parameter support
   - Change language `'pt'` → `'pt-BR'`

2. **Update response parsing**:
   - Change `data['places']` → `data['results']`
   - Change `data['response']` → `data['answer']`
   - Handle new `language` and `debug` fields

3. **Update Place model**:
   - Match OpenAPI PlaceResult schema
   - Add `placeId`, `openNowStatus`, proper field names

### Priority 2: Important (UX Spec)

4. **Update PlaceCard widget**:
   - Add "Open now" badge (open/closed/unknown)
   - Add website/url action buttons

5. **Add filter chips**:
   - Restaurant / Bar / Park / Open now chips
   - Wire up to `filters` parameter in API call

### Priority 3: Nice to Have

6. **Update language codes**:
   - Change `'pt'` → `'pt-BR'` throughout codebase

## Testing Checklist

After fixes:
- [ ] API request matches OpenAPI spec exactly
- [ ] API response parsing handles new format
- [ ] Place cards show all required fields
- [ ] "Open now" badge displays correctly
- [ ] Filter chips work and send correct filters
- [ ] Location permission flow works
- [ ] Bilingual UI works (pt-BR + en)
- [ ] Website/url buttons open in external browser

## Migration Path

1. **Phase 1**: Update API service to use new format (backward compatible with legacy fields)
2. **Phase 2**: Update Place model and PlaceCard
3. **Phase 3**: Add filter chips
4. **Phase 4**: Remove legacy field support once backend fully migrated
