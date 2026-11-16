# Sources: where every fact comes from, and how to check it

Use this file when something in the skill does not match what a server does: a refused option, a missing export, a changed event. WHIP changes fast; the code is the authority, the docs come second, and this skill third.

## Contents
- Official sources
- Repositories, pinned to the commits this skill was built from
- Turning a citation into a link
- When something does not match
- Documentation anchors

## Official sources

| What | Where |
|---|---|
| Documentation (one page, searchable with `/`) | https://whipfx.net/docs/ ; a section: `https://whipfx.net/docs/#<anchor>` |
| The same docs, offline, in every install | `resources/whip_core/docs.html` |
| GitHub organisation | https://github.com/WHIPFX |
| Install recipes (live) | https://raw.githubusercontent.com/WHIPFX/txAdmin-recipe/main/whip-legacy.yaml , https://raw.githubusercontent.com/WHIPFX/txAdmin-recipe/main/whip-enhanced.yaml |
| Every export with its types | https://github.com/WHIPFX/whip_core/tree/main/types (`server.lua`, `client.lua`, `classes.lua`, `events.lua`, `satellite.lua`, `director.lua`) |
| Releases (what changed) | `https://github.com/WHIPFX/<repo>/releases` |
| Community support | the Discord linked on https://whipfx.net |
| FXServer builds (recommended / latest) | https://changelogs-live.fivem.net/api/changelog/versions/win32/server (`linux` for Linux); https://runtime.fivem.net/artifacts/fivem/ |

## Repositories, pinned to the commits this skill was built from

Snapshot of 2026-11-14/15. `main` may be newer: compare before trusting a detail. Line citations use the
pinned commits below; `export-index.md` and `whip-names.json` were regenerated from whip_core
[`59a9cd4`](https://github.com/WHIPFX/whip_core/tree/59a9cd4) (v1.2.0, 2026-11-16).
Changes from 1.0.1 to 1.1.0 that touch the API are folded into the references: `at.aimModels` and the 100 ms
`canInteract` display check (interactions.md), containers opened from their prop's edge (stores-containers-panels.md),
Restore Player Cores (server-ops-devtools.md).
Changes from 1.1.0 to 1.2.0 that touch the API: the character editor as a store (`EditAppearance`,
`GetAppearanceChanges`, `SetPlayerAppearance`) and `RenameCharacter` (players-stats-hud.md, porting-playbooks.md);
`OpenShop` and virtual shops (jobs-shops-properties-doors.md); `SetVehicleCustody`, `TransferVehicle` to an offline
character with `expectedOwner`, `whip_core:vehicle:damageCleared` (vehicles-garages.md, events-and-data.md);
`SetInventoryLocked` (inventory-items.md); `StoreTake`'s metadata filter (stores-containers-panels.md); `PlacePoint`
and the settings page's `place` (ui-nui-camera.md, server-ops-devtools.md); furnisher multi-select. 1.1.1 dropped the
Enhanced NPC netId warning (world-zones-time-npcs.md).

| Repository | What | Pinned commit |
|---|---|---|
| [chameleon_paint](https://github.com/WHIPFX/chameleon_paint) | colour ramps for chameleon paints | [`84b905c`](https://github.com/WHIPFX/chameleon_paint/tree/84b905c7af81b1a24b0b7df702af20b458dbf730) |
| [oxmysql](https://github.com/WHIPFX/oxmysql) | WHIPFX's oxmysql fork (P-001 fix) | [`34788b4`](https://github.com/WHIPFX/oxmysql/tree/34788b4f197080d5533f81e1aa50e37c8e1d4a08) |
| [txAdmin-recipe](https://github.com/WHIPFX/txAdmin-recipe) | the install recipes (Legacy, Enhanced) | [`4b41b9e`](https://github.com/WHIPFX/txAdmin-recipe/tree/4b41b9e5404f4bc7334b337dce285bcc1629d11e) |
| [whip_autos](https://github.com/WHIPFX/whip_autos) | Whiplash tuning | [`380ad29`](https://github.com/WHIPFX/whip_autos/tree/380ad2937626dd178a94df50ee4b10683eb2ab3f) |
| [whip_autos_shop](https://github.com/WHIPFX/whip_autos_shop) | Whiplash shop (tooling) | [`e4ca990`](https://github.com/WHIPFX/whip_autos_shop/tree/e4ca990707b79ac90971826d87ace881cdb6e38a) |
| [whip_chat](https://github.com/WHIPFX/whip_chat) | chat | [`c96b292`](https://github.com/WHIPFX/whip_chat/tree/c96b2920484ccf73bb7a971bf47d77a182155350) |
| [whip_core](https://github.com/WHIPFX/whip_core) | the framework; `types/` = every export stub; `docs.html` = the docs offline; `docs/` = architecture notes and examples | [`d12235f`](https://github.com/WHIPFX/whip_core/tree/d12235f0ff4f679bdda4e3297ac7f8ea22443fd1) |
| [whip_dealership](https://github.com/WHIPFX/whip_dealership) | dealership | [`9fcb0c8`](https://github.com/WHIPFX/whip_dealership/tree/9fcb0c8eddb88b534d97a10add19304bc25e82b0) |
| [whip_fuel](https://github.com/WHIPFX/whip_fuel) | fuel, pumps, jerry can | [`4c940a4`](https://github.com/WHIPFX/whip_fuel/tree/4c940a47cb7ff9d11c85a7510af10524f7acc93e) |
| [whip_graphics](https://github.com/WHIPFX/whip_graphics) | lighting, sky, LED streetlights | [`a12217d`](https://github.com/WHIPFX/whip_graphics/tree/a12217dd7db47788b4c99c0e0c345458d3158b32) |
| [whip_gunny](https://github.com/WHIPFX/whip_gunny) | weapons | [`ec3a1c1`](https://github.com/WHIPFX/whip_gunny/tree/ec3a1c18b5369747f7553dd1963bf0d2dec85336) (v2.0.1) |
| [whip_homes_mirrorpark](https://github.com/WHIPFX/whip_homes_mirrorpark) | Mirror Park homes (interior themes provider) | [`e3c1180`](https://github.com/WHIPFX/whip_homes_mirrorpark/tree/e3c118017fe9641059fed109b8a6a08a1c675493) |
| [whip_loadingscreen](https://github.com/WHIPFX/whip_loadingscreen) | loading screen | [`c9c312d`](https://github.com/WHIPFX/whip_loadingscreen/tree/c9c312d1427afd3439cba14d2c95435e77ce7e78) |
| [whip_media_clothing_female](https://github.com/WHIPFX/whip_media_clothing_female) | media pack (pictures/videos) | [`978c3f3`](https://github.com/WHIPFX/whip_media_clothing_female/tree/978c3f36a64393c8f0a88eadb312dbb97bf66509) |
| [whip_media_clothing_male](https://github.com/WHIPFX/whip_media_clothing_male) | media pack (pictures/videos) | [`c8f2a8e`](https://github.com/WHIPFX/whip_media_clothing_male/tree/c8f2a8ec87d1dd75051f1888211ac89894d97ae9) |
| [whip_media_map](https://github.com/WHIPFX/whip_media_map) | media pack (pictures/videos) | [`779f731`](https://github.com/WHIPFX/whip_media_map/tree/779f73170f0fc4156c5c7b1a704f625577775b6b) |
| [whip_media_previews](https://github.com/WHIPFX/whip_media_previews) | media pack (pictures/videos) | [`a464c73`](https://github.com/WHIPFX/whip_media_previews/tree/a464c7396d3dbe426d89023516d1189ba689d8e7) |
| [whip_media_props](https://github.com/WHIPFX/whip_media_props) | media pack (pictures/videos) | [`802bb14`](https://github.com/WHIPFX/whip_media_props/tree/802bb14114da55c0a2d682c30f74fbe02ad1c667) |
| [whip_phone](https://github.com/WHIPFX/whip_phone) | Duo phone (`docs/MODULES.md`, `docs/FRAMEWORK.md`) | [`b1b8692`](https://github.com/WHIPFX/whip_phone/tree/b1b8692e65fc1f8d4477ce6522c7468f3e82d6d6) |
| [whip_rope](https://github.com/WHIPFX/whip_rope) | physics rope | [`6e74b57`](https://github.com/WHIPFX/whip_rope/tree/6e74b57630ef46c86f7363338c3b68653e6d794c) |
| [whip_test](https://github.com/WHIPFX/whip_test) | automated health tests | [`bfba64b`](https://github.com/WHIPFX/whip_test/tree/bfba64bdee16f3c99917b3e9bddb4f622e4d3cb2) |
| [whip_voice](https://github.com/WHIPFX/whip_voice) | voice (`docs/SETUP.md`, `docs/LINES.md`) | [`436dbfb`](https://github.com/WHIPFX/whip_voice/tree/436dbfbfe36f25a5a12d9ac4755bd321d7bc9f39) |
| [.github](https://github.com/WHIPFX/.github) | contributing, governance, security policy | [`8d107a7`](https://github.com/WHIPFX/.github/tree/8d107a720547d191112dcb602ead5361b8d20a85) |

Upstream, not WHIPFX: [Bob74/bob74_ipl](https://github.com/Bob74/bob74_ipl) (installed by the recipe at tag `2.7.1`).

## Turning a citation into a link

The references cite source as `<repo>/<path>:<line>`, e.g. `whip_core/server/inventory.lua:1019`. Open it:

- as the skill saw it: `https://github.com/WHIPFX/<repo>/blob/<pinned commit>/<path>#L<line>`
  e.g. https://github.com/WHIPFX/whip_core/blob/d12235f0ff4f679bdda4e3297ac7f8ea22443fd1/server/inventory.lua#L1019
- as it is now: `https://github.com/WHIPFX/<repo>/blob/main/<path>` (lines may have moved: search the function name)
- what changed since: `https://github.com/WHIPFX/<repo>/compare/<pinned commit>...main`

Doc citations are anchors (`#guide-secure`, doc section 017): `https://whipfx.net/docs/#guide-secure`, or `docs.html#guide-secure` offline.

## When something does not match

1. Get the facts from the server: the error line (F8 / console), `whipsupport` (version, setup report, recent errors), `/whip` → System → Monitor for refused events, and the `false, why` the call returned.
2. Find the topic in the reference, then follow its citation to the pinned source and to `main` (links above). A different `main` means WHIP changed: trust `main`.
3. Check the stub in `whip_core/types/*.lua` on `main` for the current signature, and the resource's release notes.
4. Check the reference's "Docs vs code" section: known places where the docs and the code disagree.
5. Update the skill: fix the reference, rerun `scripts/export_index.py <whip_core> references/export-index.md`, then `scripts/whip_scan.py --selfcheck references/export-index.md`, and record the new pinned commit here.

## Documentation anchors

Every section of https://whipfx.net/docs/ , in page order.

| Anchor | Section |
|---|---|
| [`#overview`](https://whipfx.net/docs/#overview) | Introduction |
| [`#quickstart`](https://whipfx.net/docs/#quickstart) | Quick Start |
| [`#first-resource`](https://whipfx.net/docs/#first-resource) | Your First Resource |
| [`#first-job`](https://whipfx.net/docs/#first-job) | Your First Job |
| [`#common-calls`](https://whipfx.net/docs/#common-calls) | The calls you'll use |
| [`#coming-from`](https://whipfx.net/docs/#coming-from) | Coming from QBCore, ESX or ox |
| [`#how-whip-thinks`](https://whipfx.net/docs/#how-whip-thinks) | How WHIP works |
| [`#patterns`](https://whipfx.net/docs/#patterns) | Return values |
| [`#patterns-registering`](https://whipfx.net/docs/#patterns-registering) | Registering with WHIP |
| [`#patterns-satellite`](https://whipfx.net/docs/#patterns-satellite) | The satellite helper |
| [`#whip-way`](https://whipfx.net/docs/#whip-way) | The WHIP way |
| [`#glossary`](https://whipfx.net/docs/#glossary) | Glossary |
| [`#what-you-can-change`](https://whipfx.net/docs/#what-you-can-change) | What a resource can change |
| [`#testing`](https://whipfx.net/docs/#testing) | Testing and performance |
| [`#both-platforms`](https://whipfx.net/docs/#both-platforms) | Legacy and Enhanced |
| [`#selling`](https://whipfx.net/docs/#selling) | Selling on WHIP |
| [`#guide-secure`](https://whipfx.net/docs/#guide-secure) | Secure Events |
| [`#secure-events`](https://whipfx.net/docs/#secure-events) | SecureEvent & SecureCallback |
| [`#guide-sentinel`](https://whipfx.net/docs/#guide-sentinel) | Sentinel: Tamper Guard |
| [`#permissions`](https://whipfx.net/docs/#permissions) | Permissions |
| [`#guide-lifecycle`](https://whipfx.net/docs/#guide-lifecycle) | Character Lifecycle |
| [`#player`](https://whipfx.net/docs/#player) | Player |
| [`#client-player`](https://whipfx.net/docs/#client-player) | Player & Status (Client) |
| [`#guide-stats`](https://whipfx.net/docs/#guide-stats) | Stats & Effects |
| [`#server-stats`](https://whipfx.net/docs/#server-stats) | Stats API |
| [`#guide-hud`](https://whipfx.net/docs/#guide-hud) | HUD Framework |
| [`#guide-death`](https://whipfx.net/docs/#guide-death) | Death & Revive |
| [`#guide-escort`](https://whipfx.net/docs/#guide-escort) | Escorting |
| [`#guide-bank`](https://whipfx.net/docs/#guide-bank) | Bank Accounts |
| [`#guide-payments`](https://whipfx.net/docs/#guide-payments) | Charging a Player |
| [`#bank`](https://whipfx.net/docs/#bank) | Bank API |
| [`#guide-inventory`](https://whipfx.net/docs/#guide-inventory) | Inventory |
| [`#item-definitions`](https://whipfx.net/docs/#item-definitions) | Items |
| [`#inventory`](https://whipfx.net/docs/#inventory) | Inventory API |
| [`#client-inventory`](https://whipfx.net/docs/#client-inventory) | Inventory API (client) |
| [`#guide-stores`](https://whipfx.net/docs/#guide-stores) | Stores |
| [`#guide-ground`](https://whipfx.net/docs/#guide-ground) | Ground items |
| [`#guide-containers`](https://whipfx.net/docs/#guide-containers) | Containers |
| [`#store-kinds`](https://whipfx.net/docs/#store-kinds) | Store kinds |
| [`#guide-panels`](https://whipfx.net/docs/#guide-panels) | Panels |
| [`#server-panels`](https://whipfx.net/docs/#server-panels) | Panels API |
| [`#guide-vehicles`](https://whipfx.net/docs/#guide-vehicles) | Vehicles & Keys |
| [`#vehicles`](https://whipfx.net/docs/#vehicles) | Vehicles API |
| [`#client-vehicles`](https://whipfx.net/docs/#client-vehicles) | Client vehicles API |
| [`#vehicle-data-api`](https://whipfx.net/docs/#vehicle-data-api) | Vehicle data & handling API |
| [`#vehicle-stats`](https://whipfx.net/docs/#vehicle-stats) | Vehicle stats API |
| [`#guide-garages`](https://whipfx.net/docs/#guide-garages) | Garages |
| [`#garages-exports`](https://whipfx.net/docs/#garages-exports) | Garages API |
| [`#guide-jobs`](https://whipfx.net/docs/#guide-jobs) | Jobs |
| [`#server-jobs`](https://whipfx.net/docs/#server-jobs) | Jobs API |
| [`#guide-shops`](https://whipfx.net/docs/#guide-shops) | Shops |
| [`#shops`](https://whipfx.net/docs/#shops) | Shops API |
| [`#guide-properties`](https://whipfx.net/docs/#guide-properties) | Properties & Homes |
| [`#housing`](https://whipfx.net/docs/#housing) | Properties API |
| [`#guide-doors`](https://whipfx.net/docs/#guide-doors) | Doors |
| [`#server-doors`](https://whipfx.net/docs/#server-doors) | Doors API |
| [`#guide-zones`](https://whipfx.net/docs/#guide-zones) | Zones |
| [`#server-zones`](https://whipfx.net/docs/#server-zones) | Zones API (server) |
| [`#client-zones`](https://whipfx.net/docs/#client-zones) | Zones API (client) |
| [`#guide-timeweather`](https://whipfx.net/docs/#guide-timeweather) | Time & Weather |
| [`#timeweather`](https://whipfx.net/docs/#timeweather) | Time & Weather API |
| [`#npcs`](https://whipfx.net/docs/#npcs) | NPCs |
| [`#interactions`](https://whipfx.net/docs/#interactions) | Interactions |
| [`#ui-library`](https://whipfx.net/docs/#ui-library) | UI Library |
| [`#guide-controller`](https://whipfx.net/docs/#guide-controller) | Controller support |
| [`#guide-camera`](https://whipfx.net/docs/#guide-camera) | Camera System |
| [`#client-camera`](https://whipfx.net/docs/#client-camera) | Camera API |
| [`#guide-theming`](https://whipfx.net/docs/#guide-theming) | Theming & Skins |
| [`#guide-nui-caps`](https://whipfx.net/docs/#guide-nui-caps) | Browser features and tools |
| [`#guide-dui`](https://whipfx.net/docs/#guide-dui) | Screens in the world (DUI) |
| [`#resource-settings`](https://whipfx.net/docs/#resource-settings) | Settings pages for your resource |
| [`#activity-log`](https://whipfx.net/docs/#activity-log) | Activity Log |
| [`#debug-internal`](https://whipfx.net/docs/#debug-internal) | Debug & internal exports |
| [`#whipcost`](https://whipfx.net/docs/#whipcost) | Timing your loops (WhipCost) |
| [`#dev-pages`](https://whipfx.net/docs/#dev-pages) | Your page in /w |
| [`#guide-weapons`](https://whipfx.net/docs/#guide-weapons) | Weapon System |
| [`#gunny-patterns`](https://whipfx.net/docs/#gunny-patterns) | Learning from gunny |
| [`#gunny-exports`](https://whipfx.net/docs/#gunny-exports) | Gunny API |
| [`#guide-rope`](https://whipfx.net/docs/#guide-rope) | Rope System |
| [`#rope-patterns`](https://whipfx.net/docs/#rope-patterns) | Learning from rope |
| [`#rope-exports`](https://whipfx.net/docs/#rope-exports) | Rope API |
| [`#autos-patterns`](https://whipfx.net/docs/#autos-patterns) | Learning from whip_autos |
| [`#director`](https://whipfx.net/docs/#director) | The Director |
| [`#director-runs`](https://whipfx.net/docs/#director-runs) | Director runs from a script |
| [`#director-cards`](https://whipfx.net/docs/#director-cards) | Director: cards of your own |
| [`#director-tasks-buttons`](https://whipfx.net/docs/#director-tasks-buttons) | Director: tasks and buttons of your own |
| [`#voice`](https://whipfx.net/docs/#voice) | Voice: keys, items, settings |
| [`#voice-setup`](https://whipfx.net/docs/#voice-setup) | Setting up whip_voice |
| [`#voice-lore-calls`](https://whipfx.net/docs/#voice-lore-calls) | Lore phone calls |
| [`#voice-lore-lines`](https://whipfx.net/docs/#voice-lore-lines) | Lore characters speak |
| [`#voice-speakers`](https://whipfx.net/docs/#voice-speakers) | Speakers |
| [`#voice-api`](https://whipfx.net/docs/#voice-api) | Voice for other resources |
| [`#running-whip`](https://whipfx.net/docs/#running-whip) | Running WHIP |
| [`#configuration`](https://whipfx.net/docs/#configuration) | Configuration |
| [`#guide-devtools`](https://whipfx.net/docs/#guide-devtools) | Dev Tools (/w & /whip) |
| [`#guide-playermanager`](https://whipfx.net/docs/#guide-playermanager) | Player Manager |
| [`#guide-banks`](https://whipfx.net/docs/#guide-banks) | Banks |
| [`#building-in-game`](https://whipfx.net/docs/#building-in-game) | Building in Game |
| [`#architecture`](https://whipfx.net/docs/#architecture) | How WHIP is built |
| [`#server-events`](https://whipfx.net/docs/#server-events) | Server Events |
| [`#client-events`](https://whipfx.net/docs/#client-events) | Client Events |
| [`#data-structures`](https://whipfx.net/docs/#data-structures) | Data Structures |
| [`#examples`](https://whipfx.net/docs/#examples) | Examples |
| [`#credits`](https://whipfx.net/docs/#credits) | Credits |
