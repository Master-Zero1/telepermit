# Telescript facts: single source of truth

## Verified (the only Telescript claims allowed in code comments, README, UI text, blog, video)
- Announced 1994 by General Magic.
- Agents "go" to "places" under permits and authorities.
- A permit capped lifetime, size and total spend ("allowance", counted in teleclicks). The engine destroyed an agent the instant it exceeded a limit.
- Identity carried an unforgeable cryptographic authority.
- A place inspected an arriving agent's identity, permit and class, then refused it, or admitted it only after imposing a permit.
- Agents interacted only inside the same place.

## Author's interpretation (always label it "interpretation")
- It died with its ecosystem (flopped devices, AT&T shut PersonaLink, its only place, in 1996, slow modems), not because permits failed.

## Our design choices (never present as Telescript behaviour)
- Step limit and the allowed-actions list; Ed25519 as the signature mechanism; pre-flight limit checks; denied actions refused and logged without killing; imposed permit = component-wise minimum; REFUSE when counters already exceed a ceiling; tool costs; the "size" cap is NOT implemented.

## Rules
- Do not add any other Telescript fact. If unsure, write "unverified" or leave it out.
- No General Magic or AT&T logos, screenshots or trademarks anywhere.
