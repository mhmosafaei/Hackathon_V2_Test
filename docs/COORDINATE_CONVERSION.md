# Explicit online coordinate conversion

Initial permit extraction remains ONE request and never converts coordinates.
The original spatial_context and quotations remain unchanged. The previous
local PROJ4js transformation has been removed.

`POST /api/coordinates/convert` accepts analysis_id, location_index and optional
force (deliberate Convert Again). The backend uses the active analysis's verified
source point, not client-supplied coordinates. Session/origin checks and an
in-flight guard prevent cross-session and concurrent accidental dispatches.

Only Convert Coordinates invokes this endpoint. It sends location_name,
coordinates_original, coordinate_system, easting and northing to the configured
OPENAI_MODEL (currently gpt-4.1-mini), with strict native JSON-schema output.
The prompt prohibits geocoding, missing-component inference and midpoint guesses.
No extraction, tab switch, Use location or environmental fetch invokes conversion.

Response contract (all fields required; CRS strings and numbers nullable):

```text
source_coordinate_system: string|null
source_coordinate_system_identifier: string|null
source_coordinates: string
wgs84: {latitude: number|null, longitude: number|null}
status: converted | requires_review | failed
confidence: high | medium | low
notes: string
```

Backend requires a completed, non-refused response, valid JSON, exact schema,
preserved source-coordinate string, finite numeric latitude/longitude in legal
bounds and a CRS identifier. Only converted + high confidence unlocks Use location.
Invalid numeric outputs become nullable review results; raw responses are retained
unchanged. These checks do NOT independently prove geodetic accuracy: an online
language-model conversion may be numerically plausible but incorrect. Review the
source CRS/datum and use independently confirmed coordinates for safety-critical work.

One explicit click permits at most one SDK request, with 60-second timeout,
zero retries, 600 output tokens, 4096 input-token ceiling and a persistent
one-request/$0.15 maximum ledger using existing verified pricing. Current
worst-case token reservation is $0.0025984. Unknown pricing blocks dispatch.
Successful/review results are cached per active analysis + original coordinates
+ CRS. Rerenders and location switches do not send requests; deliberate Convert
Again may send a fresh billed request. No background retries occur after failure.

Artifacts are separate under cache/coordinate_conversions/<analysis_id>/<attempt>/:
input.json, response.json, dispatch_ledger.json and conversion.json. Source
analysis and historical reviews are not modified. No rule or WORK authorization
is created. Session clean-start behavior remains: restart clears active state,
but audit artifacts survive.

UI: original coordinates → Convert Coordinates → loading/disabled → derived
WGS84 + model/confidence/notes → Use location → copied environmental form fields
→ explicit Fetch Environmental Data. Multiple source locations keep separate
conversion state; none is selected automatically. Unsupported area/route inputs
require manual confirmed points instead of invented midpoints.

Offline verification: 219 backend tests passed (including 21 coordinate tests),
40 frontend tests passed; production build passed with existing bundle advisory.
No live OpenAI, Copernicus or weather requests were made. Live mathematical
conversion quality remains unverified pending separately authorized acceptance.
