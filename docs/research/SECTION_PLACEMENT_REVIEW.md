# Missing section location review, 2026-10-07

Branch: `feat/place-missing-sections`. Basis: DERIVED. New output:
`data/derived/crosswalk/section_placement_reviewed.csv`. It contains all 45 source identities,
verbatim logged candidate coordinates and reasons. UNPLACED coordinates are blank.
These are named locality points or automatic landmark proxies, **not official section
offices or boundaries**. Existing crosswalk, weights, map, source data, APIs and UI are unchanged.

| Final status | Sections | 2025 bookings |
|---|---:|---:|
| ACCEPT_AUTO | 22 | 66,374 |
| ACCEPT_REVIEWED | 5 | 24,543 |
| UNPLACED | 18 | 26,647 |
| Total cohort | 45 | 117,564 |

Accepted candidates cover 90,917 bookings (77.33% of the missing-location cohort,
6.33% of city bookings). This is candidate coverage; the map has not been rebuilt.

## Sources referred to in CSV reasons

- Logged `section_placement_candidates.csv`, `section_placement_best.csv`, raw Nominatim
  and Overpass JSONs in `data/raw/geography/`; existing `section_to_ward_2016.csv` for division
  neighbours. Existing division limits and 1.5 km same-place grouping are ASSUMED.
- **S1:** [News9, reported HMWSSB February 17, 2025 shutdown](https://www.news9live.com/city/hyderabad/hyderabad-water-supply-cut-on-february-17-for-24-hours-affected-areas-list-2821249):
  Bhagat Singh Nagar and Adarsh Nagar are listed in division 12, Vajpayee Nagar in division 13,
  Bachupally in division 22. The names do not distinguish homonyms or locate a section office.
- **S2:** [Munsif, reported HMWSSB February 1, 2025 shutdown](https://munsifdaily.com/hyderabad-water-supply-to-be-disrupted/):
  Boduppal, Chengicherla and Peerzadiguda are listed in division 19, supporting the eastern cluster.
- **S3:** [Telangana Today, Malkajgiri infrastructure report](https://telanganatoday.com/major-infrastructure-projects-underway-in-malkajgiri-under-marri-rajasekhar-reddy):
  identifies a Vajpayee Nagar/Neredmet railway-crossing project, corroborating the mismatch of
  the logged Quthbullapur childcare hit. It supplies no replacement coordinate.

Notice evidence is secondary reporting of HMWSSB statements. No original GIS notice or
official section coordinates were found. These reports are not direct boundary proof.

## Review decisions

| Section | Decision |
|---|---|
| BACHUPALLY (PD 7), division 22 | ACCEPT_REVIEWED, suburb `node/2002214372`, 17.541055 / 78.363548. S1 and Nizampet/Bollaram support the locality. Alternatives are college/apartment POIs; apartment coordinates duplicate existing Gandimaisamma. |
| PEERJADIGUDA (DIV 19) | ACCEPT_REVIEWED, suburb `node/2942962635`, 17.3945 / 78.592525. S2 supports the locality; alternatives are a clinic and road bus stop. |
| CHENGICHERLA, division 19 | ACCEPT_REVIEWED, village `node/5390598303`, 17.432934 / 78.606609. S2 supports the locality; alternatives are highway entrance bus stops. |
| THUKKUGUDA, division 18 | ACCEPT_REVIEWED, village `node/4309199246`, 17.209043 / 78.476782, south of Jalpally. Within the existing wide-division distance limit; competing health-post coordinates are in Langar Houz. No notice uniquely locates this section. |
| SHAMSHABAD, division 18 | ACCEPT_REVIEWED, village `node/245640121`, 17.261144 / 78.393194, south of Kismathpur. Other hits are cemetery/temple/shop POIs. No notice uniquely locates this section. |
| MARUTHINAGAR (DIV 10) | UNPLACED: two plausible neighbourhoods, Chaitanyapuri and Champapet. No distinguishing evidence. |
| Bhagatsingh Nagar, division 12 | UNPLACED: Chintal and KPHB candidates both pass the division check; S1 cannot distinguish them. |
| MYSARAM, division 8 | UNPLACED: two clinic POIs; no locality point or distinguishing evidence. |
| VAJPAYEE NAGAR, division 13 | UNPLACED: sole Quthbullapur childcare hit does not establish the Neredmet locality. |
| VAISHALINAGAR (DIV 10) | UNPLACED: sole hit is a Madinaguda apartment 24.09 km from the division centre. |
| ADARSHNAGAR, division 12 | UNPLACED: all homonyms fail the existing distance rule; S1 supplies no coordinate. |

ACCEPT_AUTO preserves the earlier 22 candidates without upgrading their status. Several are
landmarks: Doyens school, Suchitra sports pitch, Vigyanpuri college, Tappa Chabutra road,
Pedda Amberpet childcare, Thoomkunta bus stop, Sanatnagar station and lake/reserve hits.
They are **automatic proxies, not independently validated centres**. Downstream consumers
must retain this distinction and review unsuitable proxies before constructing service areas.
Even ACCEPT_REVIEWED establishes a named locality only. Twelve NOT_FOUND rows remain unplaced;
no new search answer or coordinate was invented. The full unresolved list is in the CSV.

| Still UNPLACED | 2025 bookings |
|---|---:|
| THATTIKHANA | 13,543 |
| MARUTHINAGAR (DIV 10) | 5,354 |
| VAJPAYEE NAGAR | 1,895 |
| VAISHALINAGAR (DIV 10) | 1,723 |
| BOATS CLUB | 1,304 |
| HINDI NAGAR | 926 |
| GODE-KI-KABAR | 615 |
| ADARSHNAGAR | 557 |
| Bhagatsingh Nagar | 546 |
| M.R.G.FILTERS | 71 |
| ADIBATLA (PD 1) | 40 |
| TURKAYAMJAL (PD 1) | 29 |
| MISRIGUNJ | 17 |
| MYSARAM | 16 |
| GUNDLAPOCHAMPALLY (PD 7) | 7 |
| PATANCHERU PIPELINE | 2 |
| 40 MLD STP ATTAPUR | 1 |
| KONDAPAKA | 1 |

Validation: four artifact tests failed before the output existed, then passed. They check
complete unique identities, verbatim candidate coordinates, raw OSM provenance for reviewed
points and blank coordinates for unresolved cases. Existing tracked data is unchanged.
Full lint, 200 frontend tests, translation checks and all task data verifiers pass.
Full backend suite: 1,025 passed, one failed. The failure is the existing shortage CSV
reproducibility check: station assignments changed after the forecast refresh; 42 saved
capacity/reason rows differ on rebuild, although all risk categories remain unchanged.
No existing forecast or shortage data is changed by this data-only review.
