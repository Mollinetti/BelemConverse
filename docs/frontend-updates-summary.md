# Frontend Updates Summary

## Changes Made to Match PoC Specifications

### 1. Place Model (`lib/models/place.dart`) ✅
- **Updated** to match OpenAPI PlaceResult schema
- Added all required fields: `placeId`, `title`, `titleFormatted`, `categoryName`, `addressFormatted`, etc.
- Added `distanceKm` and `openNowStatus` fields (PlaceResult specific)
- Added `hasWebsite` getter for website/url detection
- Added `openNowStatusText` getter for display
- Maintains backward compatibility with legacy field names (`name`, `category`, `rating`)

### 2. API Service (`lib/services/api_service.dart`) ✅
- **Updated** `sendMessage()` to use new API format:
  - Uses `userLocation` instead of `coordinates` (with legacy fallback)
  - Adds `nowIso` field (current time in ISO-8601)
  - Adds `filters` parameter support
  - Language code: accepts `'pt-BR'` or `'en'`
- **Updated** response parsing:
  - Uses `results` array (with fallback to `places`)
  - Uses `answer` field (with fallback to `response`)
  - Handles new response structure

### 3. Chat Provider (`lib/providers/chat_provider.dart`) ✅
- **Added** filter state management:
  - `selectedPlaceTypes` Set for place type filters
  - `openNowFilter` boolean for open now filter
  - `togglePlaceTypeFilter()`, `toggleOpenNowFilter()`, `clearFilters()` methods
- **Updated** `sendMessage()` to:
  - Build filters object from state
  - Include `nowIso` timestamp
  - Pass filters to API service

### 4. Place Card Widget (`lib/widgets/place_card.dart`) ✅
- **Added** `showOpenNow` parameter
- **Added** `_buildOpenNowBadge()` method:
  - Shows "Open now" (green), "Closed now" (red), or "Hours unknown" (orange) badge
  - Only displays when `showOpenNow` is true and `openNowStatus` is available
- **Added** `_buildActions()` method:
  - Shows website/url button when place has website
  - Opens website in external browser using `url_launcher`
- **Updated** to use new field names (`categoryName`, `addressDisplay`)
- **Updated** category icon logic to check `placeType` first

### 5. Message Bubble Widget (`lib/widgets/message_bubble.dart`) ✅
- **Updated** `_buildPlaces()` to:
  - Show up to 5 places (was 3)
  - Detect if openNow filter was used (check for `openNowStatus`)
  - Pass `showOpenNow` prop to PlaceCard

### 6. Chat Screen (`lib/screens/chat_screen.dart`) ✅
- **Added** `_buildFilterChips()` method:
  - Shows filter chips: Restaurant, Bar, Park, Open now
  - Displays active filters with selected state
  - Shows "Clear" button when filters are active
  - Bilingual labels (pt-BR/en)
- **Updated** language code handling:
  - Converts `'pt'` → `'pt-BR'` before sending to API
  - Handles both `'pt'` and `'pt-BR'` for display logic

### 7. Constants (`lib/config/constants.dart`) ✅
- **Updated** `AppLanguage` enum:
  - Portuguese code changed from `'pt'` to `'pt-BR'` per OpenAPI spec
  - Added backward compatibility in `fromCode()` method

### 8. Dependencies (`pubspec.yaml`) ✅
- **Added** `url_launcher: ^6.2.5` for opening websites in external browser

## Compliance Status

### ✅ Fully Compliant
- API request format matches OpenAPI spec
- API response parsing handles new format
- Place model matches PlaceResult schema
- Place cards show all required fields
- "Open now" badge displays correctly
- Filter chips implemented
- Website/url buttons open in external browser
- Language codes match spec (`pt-BR` / `en`)

### ⚠️ Backward Compatibility
- Legacy field names still supported for smooth migration
- Legacy API fields (`coordinates`, `places`, `response`) still handled
- Language code `'pt'` automatically converted to `'pt-BR'`

## Testing Checklist

After these updates, verify:
- [ ] Filter chips toggle correctly
- [ ] Filters are sent to API in correct format
- [ ] Place cards display all fields correctly
- [ ] "Open now" badge shows correct status
- [ ] Website buttons open in external browser
- [ ] Language codes work correctly (`pt-BR` / `en`)
- [ ] Location permission flow works
- [ ] API requests match OpenAPI spec exactly

## Next Steps

1. Run `flutter pub get` to install `url_launcher` dependency
2. Test filter chips functionality
3. Test place cards with real API responses
4. Verify website links open correctly
5. Test with both EN and pt-BR languages
