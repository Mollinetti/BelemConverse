# Flutter Web Chat UX Spec (WebView Container)

## Screens
1) Chat Screen
- Message list (user + assistant)
- Input box + send
- Optional filter chips: Restaurant / Bar / Park / Open now
- Location permission flow

2) Results Cards (in assistant message)
Each result card displays:
- title
- categoryName
- distance (km or meters)
- totalScore + reviewsCount
- address (addressFormatted preferred)
- "Open now" badge (open/closed/unknown when requested)
- action buttons: open website/url (external browser)

## Location Handling
- On first use, request location permission.
- If denied, app still works but geo queries will ask user to enable location or type a neighborhood/city.
- Send userLocation with each /chat request when available.

## Bilingual UI
- UI strings pulled from i18n map (EN + pt-BR).
- Chat language defaults to message language detection unless user changes.
``