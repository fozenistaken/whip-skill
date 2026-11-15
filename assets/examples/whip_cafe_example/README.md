# whip_cafe_example

The coffee stand from whip's tutorial, finished: `docs.html` → **Your First Resource** (steps 1 to 7) and **Your First Job** (steps 1 to 4). The code is the tutorial's, line for line, with the coffee's picture added (`html/img/items/mycafe_coffee.webp`, listed under `files` in the manifest).

| File | What it holds |
|---|---|
| `fxmanifest.lua` | The manifest (Your First Resource, step 1) |
| `shared.lua` | Where the counter is and the price (Your First Resource, step 2); a barista's pay (Your First Job, step 3) |
| `server.lua` | The coffee item, drinking it, buying it (Your First Resource, steps 3 to 5); the job and brewing (Your First Job, steps 1 and 3) |
| `client.lua` | The counter: buy, clock on, brew, clock off (Your First Resource, step 6; Your First Job, step 2) |

## Running it

It sits in `whip_core/docs/examples/` so it never starts by itself: FiveM does not look for resources inside another resource's folder.

1. Copy the `whip_cafe_example` folder into your resources folder.
2. In `server.cfg`, below WHIP's `ensure` lines: `ensure whip_cafe_example`. Restart the server.
3. Hire yourself: `/whip` → **Jobs** → *Bean Machine* → **Change** → hire yourself as a Barista.
4. The counter is a step in front of where new characters spawn. Buy a coffee; clock on; brew one (six seconds, then a coffee and $5).

It uses the tutorial's names (`mycafe_coffee`, the `mycafe` job). If you built your own `mycafe` while reading, run one of the two: whichever registers the names first keeps them, and the other is refused (and says so in the console).
