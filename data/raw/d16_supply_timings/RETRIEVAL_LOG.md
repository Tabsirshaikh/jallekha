# D16 Water Supply Timings (HMWSSB) — Retrieval Log

**Dataset:** HMWSSB Water Supply Timings System & Internet Archive Wayback Machine
**Basis:** REAL (archived schedule from official portal)
**Licence:** Public government web portal (Government of Telangana / HMWSSB)
**Used by:** Scheduled supply validation (A4), need map contextual evidence, RTI planning

## Coverage Summary

- **Sections with data:** 1 / 89 (1.1236%)
- **Total localities with scheduled hours:** 21 (all within S.R. NAGAR section)
- **2025 Tanker bookings covered:** 40,862 / 1,436,768 (2.844%)
- **Ward mapping:** S.R. NAGAR maps to **Ward 98 Ameerpet** (`relation/7857794`)
- **Capture date:** 2024-05-14T21:57:12Z (Wayback Machine snapshot)
- **Live database status (2026-10-06):** 89/89 sections return `alert('No Data Found')` (live database empty)

## Data Sources & Investigation Findings

1. **Live Portal (`bms.hyderabadwater.gov.in/wstl/`):**
   - Main map: `https://bms.hyderabadwater.gov.in/wstl/managerupload/DivisionMap.aspx`
   - Links 11 division pages (`DivISection.aspx` through `DivXVISection.aspx`).
   - Requires browser User-Agent and `Referer: .../DivisionMap.aspx` with session cookies.
   - Defines 89 active sections across JS functions `fun1()`, `fun2()`, etc.
   - Timings page `ViewTimings.aspx?Divisioncode=...&Section=...&Sectioncode=...` returns HTTP 200 with `<script language="javaScript">alert('No Data Found');</script>` for every section.

2. **Internet Archive Wayback Machine:**
   - CDX Query: `https://web.archive.org/cdx/search/cdx?url=https://bms.hyderabadwater.gov.in/wstl/WaterSupplyView/ViewTimings.aspx&matchType=prefix&output=json`
   - Only 1 capture exists with tabular data: S.R. NAGAR (`Divisioncode=6&Section=S.R.NAGAR&Sectioncode=0624`) on 2024-05-14 21:57:12 UTC.
   - Older `hyderabadwater.gov.in` and `.asp` variants yielded no additional captures with data.

3. **Archive.today (`archive.ph`):**
   - Queried section timing URLs; returned no archived snapshots (nginx default placeholder).

4. **Third-Party References:**
   - Community mirrors (e.g., `rajuginni.com/hyderabad-drinking-water`) show fragmented, unverified text snippets; not used as source data.

5. **Outage and Pressure Dashboards:**
   - **Water Supply Outage Dashboard** (`https://erp.hyderabadwater.gov.in/HmwssbOnlineNew/#/OutageDashboard`): Requires employee/consumer ERP authentication. No public API or machine-readable table feed is exposed.
   - **Water Pressure Dashboard** (`https://mdm.hyderabadwater.gov.in/real-time-water-pressure`): Host `65.2.47.226` is unreachable / timed out on ports 80/443.

## Stored Files

| File | Bytes | SHA-256 | Description |
|---|---|---|---|
| `supply_timings.csv` | 7,289 | `81cdc754d4ca1dcbbeaa0c6c5dec3a321f7b8b216c2a1c92a883c2f13776304f` | 21 localities for S.R. Nagar with 24h start/end and hours |
| `raw_pages/division_map.html` | 34,749 | `ef4e9d7417a426c6294a0eb2b3df3a2186212e747f01310a2ea57791a060f913` | Raw captured HTML / gzip |
| `raw_pages/division_map.html.gz` | 9,972 | `effa6070b3fc7dcf39865d23e875f241ee09fc522133143cbb1130575dac95bf` | Raw captured HTML / gzip |
| `raw_pages/sample_live_empty.html` | 8,749 | `12773942c0395044cca27458795645f942a14eca776b561676e155e4d65cbd7f` | Raw captured HTML / gzip |
| `raw_pages/sample_live_empty.html.gz` | 2,892 | `8a076dfdde631f3f60e0408fc98dd15409c02ca2a01fdfe9ac247ac538dcad60` | Raw captured HTML / gzip |
| `raw_pages/sr_nagar_2024-05-14.html` | 35,672 | `f6e6f17308c6e57579d11639b053f87e69f5fbcdf73136a6b010369b68f175b7` | Raw captured HTML / gzip |
| `raw_pages/sr_nagar_2024-05-14.html.gz` | 7,340 | `21ad7992c19212d91298533b37e652ec3b33019cb3d6a679d59d2871141afe0f` | Raw captured HTML / gzip |
