# Golden Queries & Expected Behavior

## Notes
- Each query should be tested with a fixed userLocation.
- Expected results list can be placeIds OR titles depending on dataset.
- The key acceptance is: radius escalation, openNow filtering, deterministic ranking, 5 results.

## Test Location Sets (examples)
- L1: {"lat": -1.4500, "lng": -48.4900}
- L2: {"lat": -1.4300, "lng": -48.4600}

## Golden Queries (EN)
Q1: "Closest restaurants open now"
- loc: L1
- plan: place_type=restaurant, open_now=true, sort=distance, radius=auto 0.5/1/2
- expect: <=5 results, all open or unknown only if strict yields <5

Q2: "Best rated sushi near me open now"
- loc: L1
- plan: category includes sushi, open_now=true, sort=rating (distance tie-break)
- expect: <=5, rating desc

Q3: "Popular bars within 1km"
- loc: L1
- plan: place_type=bar, sort=popularity, radius override=1km
- expect: reviewsCount desc

## Golden Queries (pt-BR)
P1: "Restaurantes mais próximos abertos agora"
- loc: L1
- plan: restaurant + open_now + distance sort

P2: "Melhores cafés perto de mim"
- loc: L2
- plan: restaurant (or other) via category mapping for café + rating sort; open_now not required unless asked

P3: "Parque perto de mim aberto agora"
- loc: L1
- plan: park + open_now + distance sort

## Acceptance Criteria (for each query)
- Produces a Query Plan JSON per spec.
- Applies radius escalation 0.5km then 1km then 2km until results >=5 or max radius reached.
- Returns exactly up to 5 results.
- Ranking follows sort mode.
- LLM response only references returned places.