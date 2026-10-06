# Water tankers across India: where they are used, how they are run, and what data exists

Research compiled 6 October 2026 for JalLekha. Companion to `TANKER_PROBLEM_RESEARCH.md` (Hyderabad in
depth) and the earlier notes `jallekha_tanker_problem_research.md` and `jallekha_geographical_research.md`.

**Purpose:** a state-by-state and city-by-city map of tanker use, the type of tanker system each place
runs, the documented failures, and, most important for us, **what data is actually available** there.
The last part decides where JalLekha could be run on real records and where it could not.

---

## 0. How to read this file

| Mark | Meaning |
|---|---|
| **[R]** | I read the full page or document |
| **[S]** | I saw only a search summary or extract; re-check before a slide |
| **[C]** | Carried over from an earlier JalLekha note with its original mark |
| **REAL** | Official record or figure (government data, audit, court order, Parliament answer, or a named official giving a figure) |
| **NEWS** | Established outlet, often quoting officials |
| **CIVIC** | Collected by a civic group, not the government |
| **YEAR?** | The year of the figure could not be confirmed |

This pass ran about 45 web searches. Most results are search summaries ([S]). Government and many news
sites were blocked from this environment, so very little was read in full. **Treat every [S] figure as a
lead to confirm, not a fact to print.** Nothing is estimated; where nothing was found, the file says so.

---

## 1. Summary

1. **Tankers are used in almost every state, in four different systems.**
   - **(A) Booked urban tankers:** a utility sells tankers on request (Hyderabad, Chennai, Bengaluru,
     Pune, Bhopal, parts of Delhi).
   - **(B) Scheduled urban tankers:** a city sends tankers on fixed routes to areas with no pipes
     (Delhi, Hyderabad slums, Nagpur, Ranchi, Faridabad, Jammu, Kohima).
   - **(C) Rural scarcity relief:** the district hires tankers for villages declared short of water
     (Maharashtra, Karnataka, Andhra Pradesh, Rajasthan, Gujarat, Madhya Pradesh, Uttar Pradesh
     Bundelkhand, Tamil Nadu, Bihar, Telangana, West Bengal).
   - **(D) Private markets:** households and societies buy from private operators because no public
     supply reaches them (Bengaluru, Chennai OMR, Mumbai, Thane, Gurugram, Faridabad, Goa, Shillong,
     Lucknow).
2. **The failures repeat across all four:** demand beyond capacity in summer, allocation by order of
   asking or by influence, weak proof of delivery, informal payments, and unregulated private supply.
3. **Public, machine-readable tanker records are rare.**
   - **Hyderabad** is the only government time series of tanker bookings and deliveries by area that
     we found: monthly by section, Jan 2022-Aug 2026, Telangana Open Data Portal.
   - **Delhi** publishes, as PDFs per Assembly Constituency, which tanker serves which fixed point on
     which day (the supply schedule, not deliveries).
   - **Bengaluru** has civic survey data on private tankers (OpenCity, 2015, 2019, 2024).
   - Everywhere else, tanker numbers appear only in press statements or Parliament answers.
4. **The national context data exists and is open.**
   - Census 2011 drinking-water source and location, down to town ward and village.
   - The Jal Jeevan Mission village-level tap dashboard.
   - The CGWB groundwater block categories (2025).
   - NSS 76th round microdata.
   - The Census 2027 houselisting, scheduled for April-September 2026, again asks the main source and
     availability of drinking water; results are not yet published.

---

## 2. National picture and national data sources

| Item | What it says | Mark |
|---|---|---|
| NSS 76th round (2018) | Tanker trucks are an "improved" source; public tanker the principal drinking source for 262 sampled households (0.2%) and supplementary for 1,514 (1.4%) (unweighted microdata counts); 9.6% of households spend over 30 minutes a day fetching water (5.7% urban) | [C][S] REAL |
| Parliament answer, Lok Sabha unstarred Q 3426 (13 Dec 2012) | Rural habitations supplied by tanker, as reported by states on 10 Dec 2012: Maharashtra 3,527; Karnataka 202; Haryana 58; Rajasthan 22 | [S] REAL |
| Jal Jeevan Mission | About 15.79 crore rural households (81.57%) had tap connections by 29 Jan 2026. 11 states/UTs reported 100%, including Telangana, Gujarat, Haryana, Punjab, Himachal and Goa. The remaining gap is mainly in Rajasthan, UP, Bihar and Jharkhand. District- and village-wise status is public on the JJM dashboard | [S] REAL |
| A tap is not water | CAG (Tamil Nadu): 83.94% rural tap connections in 2024, but 50% of rural households in the test-checked districts did not get sufficient water | [S] REAL |
| Dynamic Groundwater Resources Assessment 2025 (CGWB with states) | Of 6,762 assessment units (blocks, taluks, mandals), 730 (10.8%) over-exploited and 201 (2.97%) critical. Concentrated in Punjab, Haryana, Delhi, western UP, Rajasthan, Gujarat, Karnataka, Tamil Nadu, Telangana, Andhra Pradesh | [S] REAL |
| Census 2011 houselisting tables (HL/HH series) | Main source of drinking water (tap treated or untreated, well, handpump, tubewell, spring, river, tank, other) and its location (within, near, away from premises), by state, district, sub-district, town, town ward and village | [S] REAL |
| Census 2027 houselisting | April-September 2026, 30 days per state; 33 questions, including main source and availability of drinking water. Maharashtra, Delhi, Rajasthan, Meghalaya, Jharkhand: houselisting 16 May-14 June 2026 | [S] REAL |
| NFHS-5 (2019-21) | Lists tanker truck among improved sources; no tanker-specific percentage was found in the fact sheets | [S] REAL |

**Not found:** an official national count of tanker trips, tanker-dependent households, or private tankers.
The 2012 Parliament answer is the most recent state-wise tanker count from the Centre that we found.

---

## 3. State and city map

Grouped by the four systems in Section 1.

### 3.1 Booked urban tankers (type A)

| City (state) | How it works | Scale and failures | Data available | Mark |
|---|---|---|---|---|
| **Hyderabad (Telangana)** | Book by 155313, app or website; token to nearest filling station; arrival order | 3.19 lakh bookings in May 2026; 63,428 undelivered Jun-Aug 2026; 10-day waits in 2016; "free" slum tankers sold | **Government open data**: monthly bookings and deliveries per section, Jan 2022-Aug 2026 (also mirrored on OpenCity) | [R] REAL (see `TANKER_PROBLEM_RESEARCH.md`) |
| **Chennai (Tamil Nadu)** | CMWSSB "Dial for Water 2.0" online booking; 6 KL and 9 KL for houses, 9-16 KL for multistorey; one booking per 5 days; Rs 475 for 6 KL (domestic) | 900 to 1,050 trips a day (2022); 15-30 day waits in 2019; booking PIN given to the driver; rebooking blocked until the last delivery is confirmed | Only figures in the press; an older "lorry trips" dataset is mentioned in open-data discussions but was not found | [S] NEWS; [C] (P4.md) |
| **Bengaluru (Karnataka)** | BWSSB "Sanchari Cauvery" (from May 2025): app and web booking, GPS, OTP needed before delivery; 4,000 L Rs 660, 6,000 L Rs 740; bulk bookings for apartments are first come, first served | 9 May-19 Sep 2025: East zone 7,680 bookings, South 5,099, North 2,738, West 938. Most supply is still private (type D) | Zone totals in the press only; **civic**: OpenCity private tanker survey data 2015, 2019, 2024 (CC BY-NC-SA) | [S] NEWS; [S] CIVIC |
| **Pune (Maharashtra)** | PMC sells tanker water at filling points (10,000 L for Rs 666 vs private Rs 1,500-1,700) and runs free tankers | PMC free tankers 1,450 trips (15 Jun 2026) to 1,665 (late June); "4.03 lakh rounds" in a fiscal year (date YEAR?); a separate report gives 4.59 lakh trips in Feb 2026 alone, which does not fit the annual figure. Patwardhan Baug: about 50 tankers filled, 18 recorded (alleged); the June 2026 draft SOP is still "first request, first supply" | Press figures only | [S] NEWS |
| **Bhopal (Madhya Pradesh)** | BMC tankers across 21 zones | 72 tankers; demand rose from 100-150 a day (March) to about 300 (April 2025); private tankers Rs 1,000-1,500 | Press only | [S] NEWS |

### 3.2 Scheduled tankers to areas without pipes (type B)

| City (state) | How it works | Scale and failures | Data available | Mark |
|---|---|---|---|---|
| **Delhi** | DJB fixed points in unauthorised colonies and JJ clusters, chosen "in consultation with local area representatives"; departmental and hired tankers; GPS; public tracking portal | Summer Action Plan 2026: about 1,030 hired + 191 departmental tankers, about 13,000 points [C]; 1,111 GPS tankers flagged off in April 2025. 2024: Supreme Court asked about the "tanker mafia"; Geeta Colony residents queued and "the tanker ran out of water when we were standing in a queue". CAG (tabled 2026): no GPS on tankers, inequitable zonal supply | **Government PDFs per Assembly Constituency**: tanker registration number, filling point, days of the week, contractor name and phone, JE/AE in charge, fixed-route vs on-demand. Not machine-readable; no delivery records | [S] REAL; [C] |
| **Hyderabad slums** | About 600 "free" trucks (2019); booked by calling the area manager | 14,800 of 2.38 lakh trips went to slums in March 2026; residents report paying drivers | Counted inside the section data; no separate slum list found | [R] NEWS |
| **Nagpur (Maharashtra)** | NMC tankers for "non-network areas"; Orange City Water operator | 36 tankers, 360 trips a day (21 May 2026); OCW 51 tankers, 500 trips a day (9 Jun 2026) | Press only | [S] NEWS |
| **Ranchi (Jharkhand)** | Ranchi Municipal Corporation runs about 70 tankers on a roster with "priority supply to water-scarce areas" | May 2026: Dhurwa, Morabadi, Harmu, Hindpiri, Lower Bazaar largely on RMC tankers | Press only | [S] NEWS |
| **Faridabad (Haryana)** | MCF runs about 20 tankers; over 1,000 private tankers in the city | 300 MLD supply, shortfall up to 120 MLD; Dabua Colony, Jawahar Colony, SGM Nagar, Sanjay Colony, Badkhal perennially short. Sept 2026: Haryana Human Rights Commission ordered free tanker water for about 500 families at Sector 49 (Kalindi Hill) | Press only | [S] NEWS / REAL (commission order as reported) |
| **Indore (Madhya Pradesh)** | IMC tankers to short areas | June 2026: clash over filling a tanker in Azad Nagar, stone-pelting, four injured; Vikas Nagar road blockade alleging water diverted elsewhere. Jan 2026: contaminated piped water in Bhagirathpura killed at least four; tankers sent in | Press only | [S] NEWS |
| **Jammu (J&K)** | Jal Shakti Department and Jammu Municipal Corporation tankers to newly settled areas | CM directed GPS trackers on all tankers (2025); all private filling stations in Jammu division ordered to register within 10 days (June 2026) | Press only | [S] NEWS |
| **Kohima (Nagaland)** | PHE tankers plus private vendors | Piped supply every 2-4 days for a few hours; PHE tanker water at least Rs 500 per 1,000 L, private about Rs 700 per 1,000 L | Press only | [S] NEWS |
| **Shillong (Meghalaya)** | Mostly private tankers at springs and filling points | Meghalaya High Court directed the state to regulate "exorbitant" tanker rates (YEAR?) | Press only | [S] NEWS / REAL (court direction as reported) |
| **Chandigarh** | Municipal tankers to short areas | Summer shortfall of 15-20 MGD against 110 MGD demand (YEAR?) | Press only | [S] NEWS |

### 3.3 Rural scarcity relief (type C)

The common chain, from these reports: the village or gram panchayat asks → the block or taluk office
(BDO, tehsildar) checks → the collector sanctions → tankers are hired, mostly from private owners →
payment from state disaster or scarcity funds. Gram panchayats "neither have the funds nor the
necessary powers" to sanction schemes themselves [S].

| State | Scale | Failures reported | Data available | Mark |
|---|---|---|---|---|
| **Maharashtra** | 24 May 2024: 3,692 tankers, 2,973 villages, 7,671 hamlets [C]. 26 May 2025 Marathwada: 573 tankers for 370 villages (Chh. Sambhajinagar 273, Jalna 190, Nanded 57, Dharashiv 25, Hingoli 16, Beed 7, Parbhani 3, Latur 2). Early May 2026: 466 tankers (446 private) for 411 villages and 1,194 hamlets in 12 districts | GPS made mandatory, with allegations that units were removed and fitted to motorcycles; a BDO asked a panchayat to resubmit its request for an extra tanker; Latur 2016 Section 144 [C] | District counts released by officials and reported weekly in the press; **no downloadable dataset found** | [S] NEWS quoting officials |
| **Karnataka** | March 2024 (worst drought "in 30-40 years"): 1,920 villages in 1,084 gram panchayats, 149 taluks, 29 districts short of water; 204 tankers in 175 villages; 3,757 private borewells hired; Rs 856 crore released to districts to pay tanker and borewell owners | Dependence on hired private sources | Press only | [S] NEWS quoting the Revenue Minister |
| **Andhra Pradesh** | Plan to supply 1,354 habitations by tanker; tankers proposed for 388 drought mandals and 492 others (YEAR?). March 2024: about half of urban local bodies short of water; Kadapa, Penugonda, Ongole, Hindupur supplied once in three days | — | Press only | [S] NEWS, YEAR? |
| **Rajasthan** | Summer contingency plan for all 41 districts every year (2026: GPS-fitted tankers; complaints on helpline 181 to be resolved within 24 hours). Jaipur 600-700 PHED tankers a day in summer (2023) [C]. PHED tenders for tanker transport by ward and tehsil are public | — | Tender documents public; no trip data found | [S] REAL (plan as reported) |
| **Gujarat** | May 2016: 504 tankers for 891 villages; 1,115 villages declared scarcity-hit. Officials say tanker villages fell from about 4,000 to "very few" after Narmada pipelines (YEAR?) | — | Press only | [S] NEWS |
| **Madhya Pradesh** | "13,000 of 51,000 villages" with critical groundwater, "solely dependent on the transportation of water" (YEAR?). Bundelkhand: Tikamgarh, Chhatarpur | — | Press only | [S] NEWS, YEAR? |
| **Uttar Pradesh (Bundelkhand)** | May 2016: about 1,000 tankers in 11 districts; the state asked the Centre for 10,000 tankers. Mahoba targeted as the first district with 100% piped connections | — | Press only | [S] NEWS |
| **Tamil Nadu** | 2024: Rs 150 crore for water scarcity in about 22 districts, including tanker supply; Ramanathapuram, Sivaganga, Virudhunagar worst hit | CAG: half of rural households in test districts lacked sufficient water despite taps | Press only | [S] NEWS / REAL (CAG) |
| **Bihar** | 2025 PHED summer plan: 475 tankers, 15 water ATMs; tankers where Har Ghar Nal Ka Jal fails. Gaya: tankers "the only source" for two months; families left town (YEAR?) | — | Hand-pump repairs logged on a geo-tagged portal; no tanker data found | [S] NEWS |
| **Telangana (rural)** | Mission Bhagiratha reaches 23,975 villages; 2026 warning that 316 villages (275 Sangareddy, 41 Medak) could lose supply within 45 days if the Manjeera got no inflow; contingency of tankers and borewells | — | Press only | [S] NEWS |
| **West Bengal** | Purulia: PHE departmental tankers on 181-day rate contracts for drought-prone areas (2026-27) | — | Tender documents | [S] REAL (tender) |
| **Uttarakhand** | Jal Sansthan contingency for 526 areas where tankers may be used (old report, 2009-2012); Mussoorie supply 7.67 MLD vs peak demand 14.5 MLD | — | Press only | [S] NEWS, old |
| **Kerala** | Water kiosks of 5,000 L refilled by Kerala Water Authority, one pot per family per day; panchayats blocking city tankers from drawing their water (YEAR?) | — | Press only | [S] NEWS, YEAR? |
| **Himachal Pradesh** | Shimla 2018 crisis: High Court barred tankers for VIP areas. Solan: tenders for tankers to Dharampur and Garkhal drew no bidders (YEAR?) | Allocation by influence | Press only | [S] NEWS |
| **Goa** | About 3,400 private tankers made 1.44 lakh trips to 130 villages in 3.5 years; demand 695 MLD vs supply 633 MLD (YEAR?) | — | Figures appear official (likely an Assembly reply); source document not found | [S] NEWS |

### 3.4 Private-tanker markets (type D)

| City | Scale | Failures | Data | Mark |
|---|---|---|---|---|
| **Bengaluru** | About 3,500 private tankers (March 2024); 110 peripheral villages added in 2007 still waiting for Cauvery connections, paying about Rs 2,000 a month | Prices Rs 500 to Rs 2,000-3,000; only 219 tankers registered three days into a seven-day deadline; 1,732 by 15 March 2024 | OpenCity civic surveys | [S] NEWS; [S] CIVIC |
| **Chennai OMR** | About 400 private tankers, "the sole suppliers" of the southern city | Illegal extraction near Nanmangalam lake despite NGT and High Court orders; strike forced officials to promise to "regularise" extraction (August, YEAR? 2023) | Press only | [S] NEWS |
| **Mumbai** | About 1,800 association tankers, about 350 MLD [C]; June 2026 strike of about 2,100 tankers said to supply about 550 million litres a day; BMC has 18 filling points for private tankers | April 2025 strike; Disaster Management Act used to requisition tankers and wells [C]; Kaula Bandar paid over 40 times the municipal rate; Bombay HC 2014: right to water for non-notified slums | Press only | [S] NEWS |
| **Thane, Diva, Mumbra** | TMC adds tankers to short areas; 72 traditional wells cleaned for Diva and Mumbra (2026) | Diva woman electrocuted drawing water with a pump (May 2024) [C] | Press only | [S] NEWS |
| **Gurugram (Haryana)** | 500 MLD received vs demand above 650 MLD; about 200 societies on the Dwarka Expressway | "Protection money" to tanker operators; about 2 lakh illegal connections | Press only | [S] NEWS |
| **Lucknow (UP)** | Private tankers about Rs 400 per 4,000 L | No formal quality checks; operators rely on washing tanks or bleaching powder | Press only | [S] NEWS |

---

## 4. Where JalLekha's approach fits, by tanker system

This states what each setting would need, not what JalLekha would achieve there.

| System | Places | What the setting has | What is missing for JalLekha |
|---|---|---|---|
| A. Booked urban tankers | Hyderabad, Chennai, Bengaluru (Sanchari Cauvery), Pune, Bhopal | A booking record per request, a queue, a capacity limit | Outside Hyderabad, no published booking data; only Bengaluru has OTP delivery proof |
| B. Scheduled supply | Delhi, Hyderabad slums, Nagpur, Ranchi, Faridabad, Jammu, Kohima | Fixed points and rosters decided by officials | Delivery records; Delhi has the schedule (PDF) but not what was delivered |
| C. Rural scarcity relief | Maharashtra, Karnataka, AP, Rajasthan, Gujarat, MP, UP, TN, Bihar, Telangana, WB | Village requests, collector sanction, hired private tankers | Village-level request and trip data; only district totals reach the press |
| D. Private markets | Bengaluru, Chennai OMR, Mumbai, Thane, Gurugram, Lucknow, Goa, Shillong | Many sellers, little regulation | No public allocator to work with; registration itself is the first step (Bengaluru 2024, Jammu 2026) |

**The honest pilot claim:** Hyderabad is the only place found where a government publishes tanker
bookings and deliveries by area over several years. Delhi publishes the supply schedule. Bengaluru has
civic survey data. Everything else is press figures. Census 2011, JJM, CGWB and NSS give context for any
state.

---

## 5. Data inventory (what we can actually use)

| Data | Coverage | Level | Format | Licence or access | Use for |
|---|---|---|---|---|---|
| HMWSSB tanker bookings and deliveries | Hyderabad, Jan 2022-Aug 2026 | Section, month | CSV | OGL India (Telangana Open Data Portal; mirror on OpenCity) | Demand, delivery gap, concentration |
| DJB Summer Action Plan per Assembly Constituency | Delhi, 2026 | Fixed point, tanker, weekday | PDF | Public website | Scheduled supply; who serves where |
| OpenCity Bengaluru tanker surveys | Bengaluru 2015, 2019, 2024 | Survey responses | CSV | CC BY-NC-SA (civic) | Private prices and dependence |
| Sanchari Cauvery bookings | Bengaluru, 2025 | Zone totals | Press | — | Scale only |
| Census 2011 houselisting (drinking water source and location) | All India | Town ward, village | XLS/CSV | Public (Census NADA) | Need where pipes are absent |
| Census 2027 houselisting | All India | To be released | — | Not yet published | Future replacement for 2011 |
| JJM dashboard | Rural India | Village | Web dashboard | Public | Which villages lack taps |
| CGWB Dynamic Groundwater Assessment 2025 | All India | Block, taluk, mandal | Report and tables | Public | Groundwater stress |
| India-WRIS / state groundwater wells | All India (states vary; Telangana monthly 2021-2026 already in this repo) | Well, month | Varies | Public | Borewell failure risk |
| NSS 76th round microdata | All India sample, 2018 | Household (sample) | Microdata | MoSPI | Tanker as principal or supplementary source; fetching time |
| Parliament answers | State | State totals | PDF | Public | Official state counts (latest found: Dec 2012) |
| State tanker tenders (Rajasthan PHED, WB PHE, MP, Haryana) | Varies | Tender | PDF | Public | Contract terms, GPS clauses |

---

## 6. Corrections to earlier notes

| Earlier claim | Correction |
|---|---|
| "Hyderabad is the only city that publishes every tanker booking" (draft pitch line) | It publishes monthly totals per section, not every booking. It is the only government booking-and-delivery series by area that we found. Delhi publishes schedules; Bengaluru has civic surveys |
| Gurugram Sectors 92 and 95: "over 10,000 families" | Source says 7 societies, about 10,000 residents |
| Bengaluru "20% of population" and "80 wards" on tankers; Beed, Ashti, Georai and Baramati figures; Marathwada "45%" | Still not found; do not use |
| UP "1,000 tankers" and Gujarat "504 tankers" | These are **2016** figures, not current |

---

## 7. Open questions

- A downloadable Maharashtra tanker report (district or village level); officials release weekly counts, but no file was found.
- Whether CMWSSB (Chennai) or BWSSB (Bengaluru) publish booking data anywhere.
- The exact year and source of the Goa (1.44 lakh trips), AP (1,354 habitations), MP (13,000 villages) and Kerala kiosk figures.
- A more recent Parliament answer with state-wise tanker counts than December 2012.
- When Census 2027 houselisting tables will be released.
- Delhi delivery records (GPS logs, trip completions); only the schedule is public.

---

## 8. Limits

- About 45 searches in one sitting; almost all results are search summaries ([S]). Government sites
  (`cag.gov.in`, `delhijalboard.delhi.gov.in` PDFs, `hyderabadwater.gov.in`) could not be opened directly
  from this environment.
- The list is what search found, not a census of every city. Smaller towns are under-represented; large
  cities and recent years are over-represented.
- Several figures carry no confirmed year (marked YEAR?).
- Press figures quote officials but are not the official documents.

---

## 9. Sources

**National**
- Lok Sabha unstarred question 3426 (13 Dec 2012), tanker-supplied habitations: https://eparlib.nic.in/bitstream/123456789/632929/1/133144.pdf (identified via search; confirm the number)
- Lok Sabha unstarred question 700 (17 Sep 2020): https://cms.neva.gov.in/NeVA/LS/FileStructure/AssemblyFiles/17/4/20200917/Unstarred/700.pdf
- Jal Jeevan Mission progress, News On Air (Dec 2025): https://www.newsonair.gov.in/over-15-crore-households-provided-tap-water-connection-under-jal-jeevan-mission/ ; dashboard: https://jaljeevanmission.gov.in
- Dynamic Groundwater Resources Assessment 2025 summary: https://visionias.in/current-affairs/news-today/2025-12-30/environment/ministry-of-jal-shakti-releases-dynamic-groundwater-resource-assessment-report-2025
- Census 2011 houselisting tables (NADA): https://censusindia.gov.in/nada/index.php/catalog/8447
- Census 2027 houselisting, News On Air (23 Jan 2026): https://www.newsonair.gov.in/government-notifies-questions-to-be-posed-to-citizens-for-first-phase-of-census-starting-april-1/ ; PIB document: https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/may/doc202651861301.pdf
- NSS 76 microdata: https://www.microdata.gov.in/NADA43/index.php/catalog/153 ; time to fetch, Down To Earth: https://www.downtoearth.org.in/news/water/4-out-of-10-rural-households-travel-every-day-for-drinking-water-67935
- CAG Tamil Nadu JJM finding, Deccan Chronicle: https://www.deccanchronicle.com/amp/southern-states/tamil-nadu/tn-achieves-84-tap-connections-in-rural-areas-but-half-lack-adequate-water-cag-1985970

**Booked and scheduled urban tankers**
- Hyderabad: see `TANKER_PROBLEM_RESEARCH.md`; OpenCity mirror: https://data.opencity.in/dataset/hyderabad-water-supply-through-tankers-data
- Delhi tanker schedule page: https://delhijalboard.delhi.gov.in/jalboard/schedule-water-tankers ; Summer Action Plan 2026: https://delhijalboard.delhi.gov.in/sites/default/files/inline-files/sap_2026_1.pdf ; example AC file: https://delhijalboard.delhi.gov.in/sites/default/files/inline-files/ac_51_kalka.pdf
- Delhi 2024: Geeta Colony queues (LatestLY/ANI): https://www.latestly.com/agency-news/india-news-delhi-water-crisis-geeta-colony-residents-forced-to-fill-water-from-tankers-express-outrage-6032771.html/amp ; Supreme Court, Deccan Herald: https://www.deccanherald.com/amp/story/india%2Fdelhi%2Fwhat-action-have-you-taken-against-tanker-mafia-sc-asks-delhi-govt-on-water-crisis-3063257 ; GPS tankers, Tribune: https://www.tribuneindia.com/news/delhi/cm-flags-off-1111-gps-enabled-water-tankers
- Chennai Dial for Water: https://housing.com/news/a-thorough-guide-to-chennai-metro-water-booking ; trips per day, DT Next: https://www.dtnext.in/news/chennai/city-has-enough-drinking-water-till-october-777549
- Bengaluru Sanchari Cauvery zone bookings, Deccan Herald: https://www.deccanherald.com/amp/story/india%2Fkarnataka%2Fbengaluru%2Fbig-turnout-in-east-bengaluru-for-cauvery-water-scheme-against-tanker-mafia-3744728 ; OpenCity tanker data: https://data.opencity.in/dataset/bengaluru-tanker-water-data
- Pune: Punekar News (tanker trips): https://punekarnews.in/pune-struggles-with-water-scarcity-150-160-tankers-deployed-daily-to-meet-demand-4-03-lakh-rounds-of-tankers-recorded-in-last-fiscal ; April 2026: https://www.punekarnews.in/?p=234037 ; Patwardhan Baug: https://www.punekarnews.in/?p=233897
- Bhopal, Free Press Journal: https://www.freepressjournal.in/bhopal/bhopal-bmcs-water-tanker-demand-sees-50-spike-in-april
- Nagpur, The Hitavada: https://www.thehitavada.com/Encyc/2026/5/21/while-24x7-dream-falters-nmc-executes-360-tanker-trips-daily-within-city.html ; https://www.thehitavada.com/Encyc/2026/6/9/ocws-tankers-log-500-trips-per-day-to-provide-drinking-water-across-city.html
- Ranchi, webindia123 (24 May 2026): https://news.webindia123.com/news/Articles/India/20260524/4453877.html ; UNI: https://www.uniindia.com/ranchi-municipal-corporation-reviews-summer-water-supply-preparedness/east/news/3768197.html
- Faridabad, Tribune: https://m.tribuneindia.com/news/haryana/summer-scarcity-pvt-water-suppliers-hike-rates-by-20-608294 ; UNI (HSHRC order): https://test.uniindia.com/news/north/20-years-without-govt-water/3965721.html
- Indore: Amar Ujala (17 Jun 2026): https://www.amarujala.com/madhya-pradesh/indore/indore-two-groups-clashed-over-the-issue-of-filling-water-vehicle-windows-were-smashed-following-stone-pelti-2026-06-17 ; Business Standard (Bhagirathpura): https://www.business-standard.com/india-news/indore-water-contamination-residents-no-longer-trust-water-supply-126010200038_1.html
- Jammu, Kashmir Reader (15 Jun 2026): https://kashmirreader.com/2026/06/15/private-water-filling-stations-across-jammu-must-register-in-10-days-govt/
- Kohima, Eastern Mirror: https://www.easternmirrornagaland.com/private-water-suppliers-are-kohimas-lifeline ; Shillong, India Water Portal: https://www.indiawaterportal.org/groundwater/tankers-in-the-abode-of-clouds-shillongs-growing-water-crisis ; Meghalaya HC, Legal Vidhiya: https://legalvidhiya.com/water-rates-charged-by-private-tankers-in-shillong-exorbitant-state-must-rein-them-in-meghalaya-high-court/?amp=1
- Chandigarh, Tribune: https://www.tribuneindia.com/news/chandigarh/summer-brings-back-fear-of-water-scarcity-in-chandigarh/amp

**Rural scarcity relief**
- Marathwada 26 May 2025, PTI via The Week: https://www.theweek.in/wire-updates/national/2025/05/27/bes17-mh-rains-marathwada.html ; Maharashtra May 2026, UNI: https://test.uniindia.com/411-villages-1-194-hamlets-in-maharashtra-depend-on-water-tankers-amid-rising-summer-heat/west/news/3835603.html ; May 2024, Outlook: https://www.outlookindia.com/amp/story/national/water-stock-in-maharashtra-dams-dips-to-23-pc-over-3600-tankers-pressed-into-service
- Maharashtra panchayat proposals, Janata Weekly: https://janataweekly.org/is-maharashtra-playing-politics-with-drought/ ; GPS, Udayavani: https://english.udayavani.com/article/state-govt-makes-gps-mandatory-for-all-water-tankers/615099
- Karnataka 2024, Deccan Herald: https://www.deccanherald.com/amp/story/india%2Fkarnataka%2Frs-856-crore-released-to-districts-to-address-water-woes-minister-2918523
- Andhra Pradesh, Deccan Chronicle: https://deccanchronicle.com/nation/current-affairs/234-habitations-in-ap-getting-water-through-tankers-890883 ; The Hindu via PressReader (30 Mar 2024): https://www.pressreader.com/india/the-hindu-visakhapatnam-9WWH/20240330/281573770703275
- Rajasthan 2026 plan, Social News XYZ (IANS): https://www.socialnews.xyz/2026/03/14/ensure-no-water-scarcity-during-summer-rajasthan-cm-tells-officials/ ; Business Standard (2024): https://www.business-standard.com/india-news/rajasthan-government-preps-drinking-water-action-plan-for-summers-124041100602_1.html
- Gujarat 2016, Business Standard (PTI): https://business-standard.com/amp/article/pti-stories/guj-121-more-villages-declared-scarcity-hit-total-at-1-115-116051101549_1.html
- Madhya Pradesh, The Statesman (2026): https://www.thestatesman.com/cities/madhya-pradesh-water-crisis-heatwave-2026-jal-jeevan-mission-bjp-congress-1503600170.html
- Uttar Pradesh 2016, Business Standard: https://www.business-standard.com/article/current-affairs/up-countering-drought-with-free-food-packets-hand-pumps-116051200794_1.html
- Tamil Nadu 2024, Deccan Herald: https://www.deccanherald.com/amp/story/india%2Ftamil-nadu%2Ftamil-nadu-allots-rs-150-crore-to-handle-water-scarcity-in-summer-2998092
- Bihar 2025, Patna Press: https://patnapress.com/bihar-steps-up-summer-water-crisis-preparations-with-major-repair-drive-and-tanker-supply-plan/ ; Gaya, Down To Earth: https://www.downtoearth.org.in/amp/story/water/bihar-staring-at-water-crisis-in-summer-months-with-groundwater-levels-declining-76174
- Telangana 2026, Telangana Today: https://telanganatoday.com/singur-will-not-be-able-to-supply-drinking-water-after-45-days-to-316-villages-in-sangareddy-and-medak-se-mission-bagiratha
- West Bengal Purulia tender: https://www.publicservicesmap.in/tenders/07-ee-pmd-phed-of-2026-2027-sl1--wb-2026-phed-1031226-1
- Uttarakhand, India Environment Portal: https://indiaenvironmentportal.org.in/news-clippings/mussoorie-nainital-not-far-from-shimla-like-crisis-say-residents-experts
- Kerala, The News Minute: https://www.thenewsminute.com/kerala/temperatures-rise-ernakulam-gears-possible-drought-conditions-97856
- Himachal: Tribune (HC 2018): https://m.tribuneindia.com/news/archive/himachal/hc-all-equal-no-tanker-for-vips-597189 ; Solan: https://www.tribuneindia.com/news/himachal/himachal-a-surplus-water-state-yet-solan-grapples-with-severe-scarcity-631211/amp
- Goa, Herald Goa: https://www.heraldgoa.in/?p=443254

**Private markets**
- Bengaluru registration, The Week: https://www.theweek.in/news/india/2024/03/04/karnataka-dk-shivakumar-wants-bengaluru-private-tankers-to-finish-registration-before-march-7.amp.html ; 110 villages, Deccan Herald: https://www.deccanherald.com/amp/story/india%2Fkarnataka%2Fbengaluru%2Fthree-years-on-wait-for-cauvery-water-continues-in-110-villages-around-bengaluru-1130736.html
- Chennai OMR, The News Minute: https://www.thenewsminute.com/amp/story/tamil-nadu/chennai-it-corridor-choked-tanker-lorries-line-tap-groundwater-illegally-181335
- Mumbai June 2026 strike, UNI: https://test.uniindia.com/news/west/agitation-maha-mum-water-tank-strike/3870427.html ; Kaula Bandar, Citizen Matters: https://citizenmatters.in/bmc-water-for-all-policy-promises-greater-access-to-water-can-it-deliver/
- Thane, Free Press Journal: https://www.freepressjournal.in/mumbai/thane-municipal-corporation-cracks-down-on-water-wastage-mandates-stp-compliance-launches-mass-conservation-drive
- Gurugram, Tribune: https://www.tribuneindia.com/news/haryana/200-societies-along-dwarka-e-way-suffer-at-the-hands-of-tanker-mafia-634420/amp
- Lucknow, Kolkata, Delhi, Down To Earth tanker economy series: https://www.downtoearth.org.in/amp/story/water/tanker-economy-revealed-severe-water-crisis-in-multiple-cities-including-delhi-lucknow-kolkata
