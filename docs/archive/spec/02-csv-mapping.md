# CSV Mapping & Normalization

## Input Columns (as provided)
address, adressFormatted, categories/0..8, categoryName, cid, city, countryCode, fid, IsSponsored,
googleFoodUrl, locatedIn, location/lat, location/lng, menu, neighborhood, phone, phoneUnformatted,
placeId, postalCode, price, rank, reserveTableUrl, reviewsCount,
reviewsDistribution/fiveStar, reviewsDistribution/fourStar, reviewsDistribution/oneStar,
reviewsDistribution/threeStar, reviewsDistribution/twoStar,
state, street, streetFormatted, subTitle, title, titleFormatted, totalScore, url, website, businessTime

NOTE: Column "adressFormatted" is misspelled in source and MUST be mapped to addressFormatted.

## Mapping
- address -> address
- adressFormatted -> addressFormatted
- categories/0..8 -> categories[] (in order; keep non-empty)
- categoryName -> categoryName
- cid -> cid
- fid -> fid
- city -> city
- state -> state
- countryCode -> countryCode
- locatedIn -> locatedIn
- neighborhood -> neighborhood
- postalCode -> postalCode
- street -> street
- streetFormatted -> streetFormatted

- location/lat -> location.lat
- location/lng -> location.lng

- phone -> phone
- phoneUnformatted -> phoneUnformatted

- title -> title
- titleFormatted -> titleFormatted
- subTitle -> subTitle

- url -> url
- website -> website
- googleFoodUrl -> googleFoodUrl
- menu -> menu
- reserveTableUrl -> reserveTableUrl

- price -> price
- rank -> rank
- totalScore -> totalScore
- reviewsCount -> reviewsCount

- reviewsDistribution/oneStar -> reviewsDistribution.oneStar (int default 0)
- reviewsDistribution/twoStar -> reviewsDistribution.twoStar (int default 0)
- reviewsDistribution/threeStar -> reviewsDistribution.threeStar (int default 0)
- reviewsDistribution/fourStar -> reviewsDistribution.fourStar (int default 0)
- reviewsDistribution/fiveStar -> reviewsDistribution.fiveStar (int default 0)

- IsSponsored -> isSponsored (boolean default false)
- businessTime -> businessTime

- placeId -> placeId (required)

## Normalization Rules
- Trim whitespace on all strings.
- Empty string => null.
- Numbers:
  - lat/lng, totalScore, price, rank parsed as float (or int where appropriate); invalid => null.
  - review counts parsed as int; invalid => null (or 0 for distribution fields).
- isSponsored parsing:
  - true values: ["true","TRUE","1","yes","YES","sim","SIM"]
  - false values: ["false","FALSE","0","no","NO","nao","não","NAO","NÃO",""]
- address selection:
  - For display: prefer addressFormatted if present, else address.
- categories[]:
  - Build from categories/0..8 non-empty.
  - Ensure categoryName is included in categories[] if not already present.
- place_type:
  - computed after categories[] building, per domain model.

## Output Artifact (PoC)
Ingestion outputs:
1) canonical_places.jsonl — one JSON Place per line
2) ingestion_report.json — counts, skipped rows, parse errors
``