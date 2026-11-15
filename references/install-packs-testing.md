# Installing WHIP, its asset packs, oxmysql fork and the test suite

Covers the txAdmin recipes, the setup report, WHIPFX's oxmysql fork, the five `whip_media_*` packs, `whip_graphics`, `whip_homes_mirrorpark`, the Legacy/Enhanced asset layout, `whip_test` (suite, endurance, load test, kit) and the WHIPFX org policies. Built from doc anchors `#quickstart`, `#quickstart-cfg`, `#updating`, `#running-whip`, `#oxmysql-patch`, `#first-download`, `#update-checks`, `#testing`, `#measuring`, `#both-platforms`, the media-pack part of the dev-tools guide, and source: `txAdmin-recipe/*`, `oxmysql/*`, `whip_media_*/*`, `whip_graphics/*`, `whip_homes_mirrorpark/*`, `whip_test/*`, `.github/*`, plus `whip_core/server/{setup_report,db_guard,clothing_pictures,prop_catalog,vehicle_catalog}.lua`, `whip_core/shared/{assets,assets_index}.lua`, `whip_core/dev/{assets_index.mjs,clothing_pictures.js,oxmysql-p001.diff}`.

## Contents

- Release model and versions
- txAdmin recipes
- server.cfg the recipes write
- Legacy vs Enhanced recipe differences
- First run, admins, updating
- The setup report (whipsetup, whiperrors, whipsupport)
- oxmysql: the WHIPFX fork
- Media packs: common contract
- WhipAssets: how whip_core finds media
- whip_media_clothing_male / whip_media_clothing_female
- whip_media_props
- whip_media_previews
- whip_media_map
- Paths the server writes into
- whip_graphics
- whip_homes_mirrorpark
- Legacy/Enhanced asset layout (stream_enhanced, git hook)
- whip_test: the automated suite
- whip_test: sections and modules
- whip_test: endurance run (/testlong)
- whip_test: load test (/testload)
- whip_test: kit for your own resource's tests
- whip_test: demo panels and the Sentinel tamper seam
- Testing and measuring tools in whip_core (docs cross-reference)
- WHIPFX org policies (.github)
- Gotchas
- Docs vs code

## Release model and versions

> **The recipe changes with every release: read the live YAML (`scripts/install_whip.py --dry-run` lists it).**
> On 2026-11-15 the live recipe already differed from the table below. whip_core was at `v1.0.1`. whip_gunny
> (v2.0.0, 4 parts), the five media packs (v1.0.0, 1 to 4 parts each) and whip_homes_mirrorpark (v1.0.0, 3 parts)
> came as **release zips** (`<repo>-N.zip`, each 40 MiB or less, made by `tools/release_zips.py`). They are
> fetched with `download_file` and `unzip`, because GitHub builds `download_github` zips on request, too slowly
> for txAdmin's 150 s limit. That recipe had 62 tasks, 13 of them `download_github`. The table below is the
> earlier list, kept for its destinations and notes.

- A WHIP release = the set of git tags named in the txAdmin recipe. Each resource is released as a `v<version>` tag matching its `fxmanifest.lua` `version`; tags are never moved or deleted, a correction is a new version (`.github/GOVERNANCE.md`).
- Both YAML files carry the same tag list; the header says "change both together".
- Recipe `version: 1.0.0`, `author: WHIPFX`, `$engine: 3`, `$onesync: on`.

| Resource | Tag in recipe | Destination |
|---|---|---|
| whip_core | v1.0.0 | `./resources/whip_core` |
| whip_autos | v1.0.0 | `./resources/whip_autos` |
| whip_autos_shop | v1.0.0 | `./resources/whip_autos_shop` |
| whip_chat | v1.1.0 | `./resources/whip_chat` |
| whip_dealership | v1.0.0 | `./resources/whip_dealership` |
| whip_fuel | v1.0.0 | `./resources/whip_fuel` |
| whip_gunny | v2.0.0 (timeoutSeconds 900) | `./resources/whip_gunny` |
| whip_loadingscreen | v1.6.2 | `./resources/whip_loadingscreen` |
| whip_phone | v1.1.0 | `./resources/whip_phone` |
| whip_rope | v1.0.0 | `./resources/whip_rope` |
| whip_voice | v1.0.0 | `./resources/whip_voice` |
| whip_media_clothing_male | v1.0.0 (900) | `./resources/[assets]/[media]/whip_media_clothing_male` |
| whip_media_clothing_female | v1.0.0 (900) | `./resources/[assets]/[media]/whip_media_clothing_female` |
| whip_media_props | v1.0.0 (900) | `./resources/[assets]/[media]/whip_media_props` |
| whip_media_previews | v1.0.0 (900) | `./resources/[assets]/[media]/whip_media_previews` |
| whip_media_map | v1.0.0 | `./resources/[assets]/[media]/whip_media_map` |
| whip_homes_mirrorpark | v1.0.0 (900) | `./resources/[assets]/whip_homes_mirrorpark` |
| whip_graphics | v2.1.0 | `./resources/[assets]/whip_graphics` |
| chameleon_paint (`WHIPFX/chameleon_paint`) | v2.0.0 | `./resources/[assets]/chameleon_paint` |
| bob74_ipl (`Bob74/bob74_ipl`, upstream, not WHIPFX) | 2.7.1 (no `v`) | `./resources/[assets]/bob74_ipl` |
| oxmysql (WHIPFX fork, release zip) | v2.14.3-whip.1 | unzipped into `./resources/[ox]` |

- `whip_test` is NOT in the recipe (install by hand on a test server only).
- chameleon_paint is WildBrick142's work under its own terms, not part of WHIP, "must never be sold"; whip_autos' Chameleon paints need its colour ramps. bob74_ipl is Bob74's (MIT): fills map holes, loads GTA Online interiors. Neither is WHIP code.

## txAdmin recipes

Recipe URLs (txAdmin setup page → **Remote URL Template**):

| Game | URL |
|---|---|
| FiveM Legacy (FXServer, artifact 38435+) | `https://raw.githubusercontent.com/WHIPFX/txAdmin-recipe/main/whip-legacy.yaml` |
| GTA V Enhanced (cfx-server) | `https://raw.githubusercontent.com/WHIPFX/txAdmin-recipe/main/whip-enhanced.yaml` |

Requirements (README, `#quickstart`):
- txAdmin; Legacy artifact 38435 or newer (Legacy YAML: `$minFxVersion: 38435`; comment: `sv_enforceSteamAuth` alone needs 38004). Enhanced YAML has no `$minFxVersion`.
- MariaDB 10.2.3+ or MySQL 8.0.16+ (older versions ignore the CHECK rules that stop a bank balance going negative), and a DB user that can create databases.
- ~1 GB disk; downloads ~830 MB from GitHub (recipe `description`).
- ≥10 Mbit/s to GitHub: txAdmin's default per-download limit is 150 s and the largest download (whip_media_clothing_female) is ~145 MB.
- GitHub API: each `download_github` is one API call; unauthenticated limit 60/hour; the recipe makes 20.
- Voice ports open inbound like 30120: UDP 7882-7893 and TCP 7881 (whip_voice runs its own voice server on the same machine; on Windows first start asks to allow `livekit-server.exe` through the firewall, or run `resources/whip_voice/service/Open voice ports.bat`).
- Installs as a NEW server only: the recipe builds resources, database and `server.cfg`; it cannot be added to an existing server.

Task order (identical in both YAMLs; 25 tasks):
1. 20 × `download_github` (table above), each `src`/`ref`/`dest`; six carry `timeoutSeconds: 900` (whip_gunny, clothing male, clothing female, props, previews, mirrorpark).
2. `download_file` `https://github.com/WHIPFX/oxmysql/releases/download/v2.14.3-whip.1/oxmysql.zip` → `./tmp/oxmysql.zip` (the release build, not source).
3. `unzip` `./tmp/oxmysql.zip` → `./resources/[ox]` (the zip contains an `oxmysql/` folder, so it lands at `resources/[ox]/oxmysql`).
4. `remove_path` `./tmp`.
5. `connect_database`: empty database. No SQL file: whip_core creates every table on first start and migrates on later starts.
6. `write_file` `./server.cfg` (below). txAdmin fills `{{svLicense}}`, `{{maxClients}}`, `{{serverEndpoints}}`, `{{dbConnectionString}}`, `{{addPrincipalsMaster}}` when the deploy finishes.

The user enters the server licence key (portal.cfx.re) and DB login; txAdmin turns on OneSync (`$onesync: on`) and puts the txAdmin master account in `group.admin` via `{{addPrincipalsMaster}}`.

## server.cfg the recipes write

Common to both, in order:

```cfg
sv_licenseKey "{{svLicense}}"
sv_maxclients {{maxClients}}
{{serverEndpoints}}
set mysql_connection_string "{{dbConnectionString}}"
# platform lines differ here (next section)
sv_scriptHookAllowed 0
set sv_enforceSteamAuth true            # players need Steam linked to their Cfx.re account
ensure oxmysql
ensure whip_core
ensure whip_autos
ensure whip_autos_shop
ensure whip_chat
ensure whip_dealership
ensure whip_fuel
ensure whip_gunny
ensure whip_loadingscreen
ensure whip_phone
ensure whip_rope
add_unsafe_child_process_permission whip_voice   # FXServer lets a resource start a program only with this
ensure whip_voice
ensure [assets]    # the media packs, the map packs and bob74_ipl
# Your own resources go below, each after WHIP: ensure mycafe
add_ace group.admin command allow
add_ace group.admin command.quit deny
add_ace group.admin whip.devtools allow
{{addPrincipalsMaster}}
```

Ensure-order rules:
- Only `oxmysql` must precede whip_core; user resources go after WHIP's lines.
- Media packs start in any order, before or after whip_core (they are under `ensure [assets]`, after whip_core). whip_homes_mirrorpark README asks for `ensure [assets]` after `ensure whip_core`.
- `add_unsafe_child_process_permission whip_voice` must come before `ensure whip_voice`.
- `whip.devtools` is the ACE behind `/w` and `/whip`; `command allow` lets group.admin run restricted commands (needed by e.g. whip_test's `/testload`).

## Legacy vs Enhanced recipe differences

| Item | whip-legacy.yaml | whip-enhanced.yaml |
|---|---|---|
| `name` | `WHIP` | `WHIP (Enhanced)` |
| `$minFxVersion` | `38435` | absent |
| Game build | `sv_enforceGameBuild 3889` | absent |
| Platform convar | absent (unset = legacy) | `setr whip_platform enhanced` (setr so clients get it) |
| Download timeout | absent (Legacy has no limit) | `set sv_resourceFileDownloadTimeout 600000` (Enhanced cuts a file at ~2 min; this gives 10 min) |
| Mumble | `set mumble_disableServer true` | absent |
| Stock chat | absent | `stop chat # We have our own :)` (under a `## Resources List` heading) |
| Pools | none | `increase_pool_size` block (below) |

Enhanced `increase_pool_size` lines (active ones): `MaxExtraVehicleModelInfos 500`, `Decorator 400` (max 900), `StaticBounds 10000`, `"Dummy Object" 5000`, `DwdStore 5000`, `InteriorInst 350` (max 450), `MaxExtraPedModelInfos 1000`, `MaxExtraWeaponModelInfos 1000`, `MetaDataStore 2850`, `NavMeshes 1000`, `fwDynamicArchetypeComponent 50000`. Commented out (expand automatically or unused): FragmentStore, CWeaponComponentInfo, DrawableStore, InteriorProxy, MapDataStore, MapTypesStore, MaxBaseModelInfos, MaxCompEntityModelInfos, MaxMloInstances, MaxMloModelInfos, MaxPedModelInfos, MaxTimeModelInfos, MaxVehicleModelInfos, MaxWeaponModelInfos, TxdStore.

Resource code is identical on both games; asset resources ship `stream/` (Legacy) and `stream_enhanced/` (Enhanced). The setup report flags a missing/low `sv_enforceGameBuild` on Legacy (min 3407, suggests 3889; `whip_core/server/setup_report.lua:16-18`) and a server whose version string looks like the other platform.

## First run, admins, updating

First run:
1. Console prints the **WHIP setup** report ~5 s after the last resource started; lines marked FIX say what to change; with nothing to fix, `Framework loaded successfully!` follows. `whipsetup` (server console) prints it again.
2. Join (Steam must be linked), make a character (appearance editor opens).
3. F2 = inventory, `/w` = quick tools, `/whip` = admin panel.
4. To make someone else an admin: have them type `/w`; the console prints the `add_ace` line to add.
- Full docs: `resources/whip_core/docs.html` (works offline).

Updating a resource: read its release notes → stop server → replace the folder with the release's "Source code (zip)" → start; whip_core migrates tables on next start. Before replacing, copy out what the server saved inside resource folders:

| Saved in | What |
|---|---|
| `whip_core/pack_exports` | Director packs / property packs you exported |
| `whip_media_props/img/props`, `whip_media_previews/img/vehicles` | "Pictures taken in game" (see Docs vs code: no live tool writes them in this release) |
| `whip_autos/engines.json` | Engine list, if you ran `/whiplashengines` |
| any `whip_media_*` | Pictures you added by hand |

Update checks: every 12 h whip_core asks `api.github.com` for each resource whose fxmanifest has `whip_updates '<owner>/<repo>'` (all media packs, whip_graphics, whip_homes_mirrorpark, whip_test declare one). `whipupdates` lists, `whipupdates check` re-checks; `set whip_update_check false` turns it off (`#update-checks`).

A first join downloads ~510 MB, mostly the 5 media packs (each ≤145 MB as downloaded); a pack downloads again only when it changes (`#first-download`).

## The setup report (whipsetup, whiperrors, whipsupport)

`whip_core/server/setup_report.lua`. Printed once per start, `SETTLE_MS` = 5000 ms after the last `whip_core:onReady`, capped at `CAP_MS` = 60000 ms after whip_core was ready (line 13), so packs ensured after whip_core are not reported missing. Each line is `ok`, `FIX` or `note`; footer "Nothing to fix" / "N to fix", note count.

| Check | Result |
|---|---|
| OneSync (`onesync` ≠ off or `onesync_enabled` true) | ok / FIX |
| Server version string looks Legacy (`v1.0.0.N`) or Enhanced (` bN`) but `whip_platform` says the other | FIX: `setr whip_platform <x>` |
| Enhanced | ok "GTA V Enhanced (whip_platform enhanced)" |
| Legacy: no `sv_enforceGameBuild` / below 3407 / OK | FIX (suggests 3889) / FIX / ok |
| Database problem (DbHealth, e.g. too old) | FIX |
| Database + oxmysql version, "(with whip's patch)" when ≥4 `whip P-001 patch` marks in `oxmysql/dist/build.js` (lines 65-77) | ok; note when unpatched |
| Media packs (`WhipAssets.resources()`): missing from resources folder / present but not started / all running | FIX / FIX / ok "Pictures and videos: …" |
| Satellites (resources depending on whip_core) with versions; property packs (`whip_property_pack` metadata); satellites present but not started | ok / ok / note |
| Newer releases (`Updates.reportLines`) | lines from updates.lua |
| Any resource's `whip_requires '<ver>'` above whip_core's version | FIX |
| `<name>_enhanced` running on Legacy, or `<name>` running on Enhanced when `<name>_enhanced` exists | FIX |
| Second resource with `loadscreen` metadata beside whip_loadingscreen | FIX |
| Custom inventory UI (`whip_inventory_renderer` convar / `Config.InventoryRenderer`) not running or without `renderer.js` | FIX |
| Voice: whip voice system + another (pma-voice, saltychat, tokovoip_script, mumble-voip, yaca-voice) | FIX; none at all → note |
| `chat` running beside `whip_chat` | FIX |
| `spawnmanager`, `basic-gamemode` running | FIX |
| Other framework (es_extended, qb-core, qbx_core, ox_core, vrp, ND_Core) | FIX |
| Other inventory (ox_inventory, qb-inventory, ps-inventory, qs-inventory, lj-inventory) | FIX |
| Other target (ox_target, qb-target, qtarget) | FIX |
| `Config.EnableTestSeams == true` | note "A test server only" |
| Registry refusals (first 8, then "… and N more") | FIX |

Console commands (all `source == 0` only, registered restricted):
- `whipsetup` — reprint report; before whip_core finished starting prints "whip_core has not finished starting" (line 328).
- `whiperrors [resource]` — server error log grouped by resource, 5 latest lines each (line 375).
- `whipsupport` — one paste-able block: server version, setup report, 3 latest errors per resource (line 382).

## oxmysql: the WHIPFX fork

Repo `github.com/WHIPFX/oxmysql`; release `v2.14.3-whip.1`, asset `oxmysql.zip`. Base: upstream overextended/oxmysql **2.14.3** (`package.json` `"version": "2.14.3"`). Licence unchanged: LGPL-3.0-or-later.

### What differs from upstream (provable from this clone)

The clone has ONE commit (`34788b4 docs: the fork note for server owners`) holding the whole tree, so there is no upstream history to diff against. Differences shown by markers and files:

| Difference | Where |
|---|---|
| P-001 fix: the `getConnection()` call is wrapped in `try { conn = await getConnection(...) } catch (err) { return logError(invokingResource, cb, isPromise, err, ...) }` | `src/database/rawQuery.ts:32`, `rawExecute.ts:37`, `rawTransaction.ts:34`, `startTransaction.ts:27` |
| Marker comment `//! whip P-001 patch (WHIPFX): …` on each of the four; `//!` comments survive bundling because `build.js:69` sets esbuild `legalComments: 'inline'` (inferred purpose: the setup report counts them in `dist/build.js`) | same lines |
| New unit test `tests/unit/database/connectionUnavailable.test.ts` ("WHIPFX P-001"): with the connection factory throwing `ECONNREFUSED`, rawQuery/rawExecute/rawTransaction/startTransaction each call back `(null, error)` and none rejects; startTransaction never runs the caller's function | tests |
| README fork note prepended (rest of README is upstream's; upstream download links in it are WITHOUT the fix) | `README.md` |

Everything else is stated to be upstream's ("Everything else is upstream's", README). Not provable here; unmarked items such as `patches/mysql2@3.24.5.patch` (bind `undefined` → `null` instead of throwing) and `patches/named-placeholders@1.1.6.patch` carry no WHIP marker and are referenced from `package.json` `patchedDependencies` (inferred: upstream's own patches). `package.json` `bugs`/`repository`, `CONTRIBUTING.md` (CLA with Overextended) and `NOTICE.md` are upstream's unchanged.

### The bug P-001 fixes

When the pool cannot hand out a connection (DB down/restarting), upstream's `await using connection = await getConnection()` throws outside any try/catch → unawaited rejected promise → caller never answered; a Lua `MySQL.*.await` waits forever; Node prints an unhandled rejection (`whip_core/dev/oxmysql-p001.diff` header). With the fix the error goes through `logError` like a bad query.

How `logError` answers (`src/logger/index.ts:56`): fires `TriggerEvent('oxmysql:error', { query, parameters, message, err, resource })`; then if `cb && isPromise` it calls `cb(null, output)`; otherwise only `console.error(output)`. Consequences:
- `MySQL.<method>.await(...)` and `exports.oxmysql:<method>_async`/`<method>Sync` (promise paths): answered at once with an error → Lua `error`.
- Plain callback form `MySQL.query(q, p, cb)`: callback is NOT called on error unless the calling resource declares `mysql_option 'return_callback_errors'` in its fxmanifest (`lib/MySQL.lua` reads `mysql_option` metadata and passes it as `isPromise`).

### How whip_core uses/detects it

- Detection: `oxmysqlPatched()` loads `oxmysql/dist/build.js` and counts the literal `whip P-001 patch`; ≥4 → "(with whip's patch)" (`whip_core/server/setup_report.lua:67`). Otherwise a note: "while the database is down a query can wait for ever (whip gives up on it after 65 s)".
- Backstop for stock oxmysql: `whip_core/server/db_guard.lua`, loaded right after `@oxmysql/lib/MySQL.lua` in whip_core's fxmanifest. Wraps `.await` of `scalar, single, query, insert, update, prepare, transaction, rawExecute` (line 74). Unanswered after `ANSWER_MS` = 65000 (line 19; above InnoDB's 50 s lock wait) → error "the database did not answer this <method> within 65 s"; `transaction` gets `TX_ANSWER_MS` = 600000 (line 26); schema changes (`ALTER/CREATE/DROP/OPTIMIZE`) are never guarded. A late answer prints `a <method> answered N s after it was given up as lost`. Calls `DbHealth.suspect` on failure.
- Hand patching stock oxmysql: apply `whip_core/dev/oxmysql-p001.diff` (not loaded by any manifest). An oxmysql update replaces `dist/build.js` and drops a hand patch.
- Stock oxmysql works; only the 65 s backstop differs.

### oxmysql convars and commands (upstream behaviour, read from this source)

| Convar | Default | Meaning |
|---|---|---|
| `mysql_connection_string` | `''` → env `DB_CONNECTION` → `mysql://root@localhost` | URI (`mysql://user:pass@host:port/db?opt=v`) or `key=value;` string (aliases: host/hostname/ip/server/data source/addr/address, user/user id/username/uid, pwd/pass, db). Read once at start |
| `mysql_debug` | `false` | `'false'`, a JSON array of resource names, or anything else unparsable = true |
| `mysql_ui` | `false` | enables the query UI |
| `mysql_slow_query_warning` | `200` (ms) | |
| `mysql_log_size` | `100` (10000 when debug on) | per-resource log array cap |
| `mysql_transaction_isolation_level` | `2` | 1 REPEATABLE READ, 2 READ COMMITTED, 3 READ UNCOMMITTED, 4 SERIALIZABLE; other → READ COMMITTED |
| `mysql_versioncheck` | `1` | 0 disables the GitHub check (`src/update/index.ts`) |
| `mysql_resultset_warning` | `1000` | rows before an oversized-result warning |
| `mysql_logger_service` | `''` | logger module (e.g. fivemanage) |
| `FIVEMANAGE_LOGS_API_KEY` | `''` | for `logger/fivemanage.js` |

Connection defaults (`src/config.ts`): `connectTimeout: 60000`, `supportBigNumbers: true`, `jsonStrings: true`, own named-placeholder conversion (connection option `namedPlaceholders=false` disables it), `dateStrings`/`flags`/`ssl` JSON-parsed, flag `CONNECT_WITH_DB` added when a database is named. Console command `oxmysql_debug add|remove <resource>` (server console only). Lua API from `@oxmysql/lib/MySQL.lua`: `MySQL.scalar/single/query/insert/update/prepare/transaction/rawExecute` (each callable with a callback and `.await`), `MySQL.startTransaction(cb)`, `MySQL.ready(cb)` / `MySQL.ready.await()`, `MySQL.Sync.*`/`MySQL.Async.*` aliases (fetchAll, fetchScalar, fetchSingle, insert, execute, transaction, prepare, store). Provides `mysql-async` and `ghmattimysql`.

## Media packs: common contract

Five resources hold everything whip_core shows that is big and rarely changes. Reason: a client downloads a resource's packed files again in full whenever anything in it changes; whip_core changes often. One pack per category, each ≤256 MB (stream/ excluded from the cap). Kept out of whip_core "so its updates stay small".

Every pack:
- `fx_version 'cerulean'`, `game 'gta5'`, `lua54 'yes'`, `author 'Whippy'`, `version '1.0.0'`, `whip_updates 'WHIPFX/<name>'`.
- `whip_media_pack 'yes'` — how whip_core's DEV tools (`dev/assets_dirs.js`, `dev/assets_index.mjs`) find packs anywhere in the resources tree (beside whip_core or in `[category]` folders at any depth). The runtime does NOT read this metadata; it uses the generated index (next section).
- `server_script 'server.lua'` — byte-identical in all five packs; server only, not downloaded. Exports below.
- `files { ... }` one line per folder (a `*` in a folder name matches nothing).
- Install: `resources/[assets]/[media]/<pack>` + `ensure [assets]`. Start in any order relative to whip_core. Restarting a pack never touches gameplay; restart it to send new pictures to players.
- Licence: the pictures/videos/map are Rockstar material (not covered by WHIP's LGPL); `fxmanifest.lua`, `server.lua` (and the .bat / `.githooks/`) are LGPL-3.0.
- Missing/not started → setup report FIX lines.

### SavePicture(kind, name, data) — SERVER (each pack)

`whip_media_props/server.lua:43`. Writes a picture into this pack (FXServer lets a resource write only inside its own folder).

| Param | Type | Meaning |
|---|---|---|
| kind | `'props'` \| `'vehicles'` | folder: `img/props/` or `img/vehicles/` |
| name | string | model name; 1-80 chars, `^[%w_%-]+$`; lower-cased |
| data | string | WebP bytes: `>12` bytes, starts `RIFF`, bytes 9-12 `WEBP` |

Returns `true`, or `false, why`: `'only whip_core saves pictures here'` (caller is not `whip_core`, `GetInvokingResource()` check, line 29), `'unknown kind of picture: <kind>'`, `'not a model name: <name>'`, `'not a WebP'`, `'disk write failed'`. Path: `<kind folder><name lower>.webp` via `SaveResourceFile`.

### RemovePicture(kind, name) — SERVER (each pack)

Same validation (`server.lua:60`). Tries `os.remove('@<res>/<path>')`, then `os.remove(GetResourcePath(res)..'/'..path)`; if both fail, writes an empty file. Returns `true, true` (gone), `true, false` (0-byte file left; counts as no picture everywhere), or `false, why`.

Only whip_core may call either. No code in whip_core 1.0.0 calls them (see Docs vs code).

## WhipAssets: how whip_core finds media

`whip_core/shared/assets.lua` (shared, both sides) + generated `shared/assets_index.lua` (Lua) and `html/js/assets-index.js` (NUI, `whipAssetUrl`). whip_core never hard-codes a pack name; it asks by path.

`WhipAssets.chunks` (generated; `{ resource, dir, from? }`):

| Area (`dir`) | Pack |
|---|---|
| `img/clothing/male` | whip_media_clothing_male |
| `img/clothing/female` | whip_media_clothing_female |
| `img/props` | whip_media_props |
| `img/vehicles`, `img/peds`, `img/tattoos`, `video/emotes` | whip_media_previews |
| `img/blips`, `map`, `stream`, `stream_enhanced` | whip_media_map |

Functions (globals, not exports):
- `WhipAssets.resourceFor(path)` → pack name or nil. Path is lower-cased, leading `/` stripped; longest matching `dir` wins; for an area split over several packs, the last chunk whose `from` ≤ the file name.
- `WhipAssets.url(path)` → `'https://cfx-nui-<pack>/<path>'` or nil. Example: `img/props/prop_bench_01a.webp` → `https://cfx-nui-whip_media_props/img/props/prop_bench_01a.webp`.
- `WhipAssets.resources()` → pack names in index order (deduped).
- `WhipAssets.isAsset(name)` → boolean.

Splitting a category: when a pack outgrows 256 MB the area continues in `<pack>_2` (e.g. `whip_media_props_2`); each pack holds one sorted run of names (a-m, n-z), `from` = first name of the run; interleaved names break it. After adding, moving or renaming packs run `node whip_core/dev/assets_index.mjs` (rewrites both index files, prints each pack's size, warns past 256 MB). New pictures in an existing folder need nothing.

Readers in whip_core:
- Props: `PropCatalog.syncImages()` (`whip_core/server/prop_catalog.lua:229`) at boot after load/seed: for each catalog model opens `<GetResourcePath(pack)>/img/props/<model>.webp` (open + seek, never read; `Wait(0)` every 500 opens), non-empty = picture; updates `prop_catalog.hasImage` in chunks. If the props pack folder is missing, flags are left untouched with a WARNING. Works whether or not the pack has started (reads the folder via `GetResourcePath`, state ≠ `missing`).
- Vehicles: `findPictures()` (`whip_core/server/vehicle_catalog.lua:101`) at each start sets `row.hasImage` from `img/vehicles/<model>.webp` (non-empty). No pack → WARNING "no car has a picture and the dealership has nothing to sell". Old DB columns from the retired in-game picture tool (`hasImage`, `imageW`, `imageH`, `status`, `capturedBy`, `captureNote`, `generatedAt`) are unread. Image URL: `WhipAssets.url('img/vehicles/<model>.webp')`; the "no picture" stand-in `missing.png` stays in whip_core.
- Clothing: see next section.
- Client appearance editor forgets its clothing-picture cache on `onClientResourceStart` of any media pack (`whip_core/client/appearance.lua`).

## whip_media_clothing_male / whip_media_clothing_female

- Male: 17,500 WebP (~175 MB on disk). Female: 18,913 WebP (~192 MB on disk; the recipe's largest download, ~145 MB). One picture per item and colour, 256 px WebP, quality 80, freemode bodies only (`mp_m_freemode_01`, `mp_f_freemode_01`).
- Layout: `img/clothing/<body>/<slot>/<body>_<slot no.>_<collection>_<item 3 digits>_<colour 2 digits>.webp`, e.g. `img/clothing/male/11_tops/male_11_mp_m_vinewood_004_00.webp`, `male_11_base_000_00.webp`. Props use `prop<slot>`: `male_prop0_base_000_00.webp`. The ped's first collection is called `base`. Collection = GTA's DLC collection name (`GetPedCollectionNameFromDrawable`/`...FromProp`), item = local index (`GetPedCollectionLocalIndexFromDrawable`).
- Slot folders (17 per body; male counts): `00_head` 46, `01_masks` 1608, `02_hair` 185, `03_arms_gloves` 1182, `04_pants` 1570, `05_bags` 842, `06_shoes` 1420, `07_accessories` 640, `08_undershirts` 2014, `09_vests_armour` 201, `10_decals` 327, `11_tops` 4650, `p0_hats` 1891, `p1_glasses` 557, `p2_ears` 125, `p6_watches` 176, `p7_bracelets` 66.
- Add-on clothing has no picture; the editor shows its number.
- Which items have a picture is NOT in the packs: `whip_core/data/clothing-pictures.json` (`{ files, made, found = { male|female = { components = { ['11'] = { base = '0-15,17,…', <collection> = '0-30' } }, props = {...} } } }`), written by `whip_core/dev/clothing_pictures.js`. whip_core reads it on its own start and on any media pack's start (`whip_core/server/clothing_pictures.lua:21,45`). The editor hides apparel/accessory items without a picture. No list → console WARNING and every item shows. `data/` is not in whip_core's `files` (players never download it).
- Callback serving the list: `SecureCallback('whip_core:appearance:clothingPictures', { requirePlayer = false, params = { { 'body', 'enum', { 'male', 'female' } } } })` → the body's table, or `false, 'No clothing pictures'` (line 51).
- After adding/removing/renaming pictures in either pack: double-click `Rebuild clothing picture list.bat` (male pack only; needs Node.js; looks for `whip_core\dev\clothing_pictures.js` one, two and three folders up), then restart both clothing packs and whip_core. `.gitattributes`: `*.bat text eol=crlf`.

## whip_media_props

- 14,637 WebP (~148 MB): `img/props/<model>.webp`, 256 px, quality 80. Furniture catalog, prop pickers, object viewer, Director world picker.
- Add: drop `img/props/<model>.webp`, restart the pack (players get it) and whip_core (it re-checks which props have a picture at start).
- Overflow pack: `whip_media_props_2` with a later run of names.

## whip_media_previews

| Folder | Count | Naming | Shown in |
|---|---|---|---|
| `img/vehicles` | 930 | `<model>.webp` | garages, `/whip` panel, dealership, furnisher |
| `img/peds` | 881 | `<model>.webp` | Director world builder (NPCs tab); glyph until present |
| `img/tattoos` | 1,492 | `<overlay name lower>.webp` (male/female share) | character editor tattoos (3D Clanker's flash cards), one per `whip_core/shared/tattoo_list.lua` entry |
| `video/emotes/{Dances,Emotes,PropEmotes,Walks}` | 110 / 445 / 306 / 135 = 996 WebM | named by `video` field in `whip_core/shared/emote_list.lua` | emote menu previews |

- ~125 MB. A new emote folder needs its own `files` line. A new vehicle picture also needs a whip_core restart; a new car needs a line in `whip_core/server/vehicle_catalog_list.lua`.

## whip_media_map

| Path | What | Sent to players |
|---|---|---|
| `map/whip-map3d.js` | 3D Clanker's 3D map (pause menu and `/whip` panel), drawn by `whip_core/html/js/map3d/map3d.js` | yes (`files`) |
| `img/blips/<sprite id>.webp` | 927 blip icons (≤64 px), from FiveM's docs via `whip_core/dev/map_tiles/blip_icons.js` | yes |
| `stream/whipmap_<row>_<col>.ytd`, `stream_enhanced/…` | 6 dark HUD radar tiles (rows 0-2, cols 0-1), swapped for `minimap_sea_*` by `whip_core/client/hud_skin.lua`; made by `dev/map_tiles/minimap_tiles.js` | streamed (never in `files`) |
| `map/gtav-map.js`, `map/whip/{z}/{x}-{y}.webp` (z 0-5, 1,365 tiles) | old 2D map (Regynate's traced shapes): source for baking the radar tiles | no |

~26 MB. Also carries `.githooks/` (stream → stream_enhanced converter).

## Paths the server writes into

| Path | Writer | Notes |
|---|---|---|
| `<pack>/img/props/<model>.webp`, `<pack>/img/vehicles/<model>.webp` | media pack `SavePicture`/`RemovePicture` (whip_core only) | no caller in whip_core 1.0.0 |
| `whip_core/data/clothing-pictures.json` | `dev/clothing_pictures.js` (Node, by hand) | |
| `whip_core/shared/assets_index.lua`, `whip_core/html/js/assets-index.js` | `dev/assets_index.mjs` (Node, by hand) | |
| `whip_core/pack_exports/<key>.director.json` (+ manifest), `whip_core/pack_exports/<file>` | Director export, property-pack export (`SaveResourceFile`) | copy out before updating whip_core |
| `whip_autos/engines.json` | `/whiplashengines` | |
| mirrorpark: none on disk; client KVPs `wh_glass_mode_dev`, `wh_budget_homes_dev`, `wh_budget_rooms_dev`, `wh_budget_portals_dev` | dev commands | per player |

## whip_graphics

LED streetlights and WHIP's colour grade ("the look"). Version 2.1.0. Does NOT use whip_core. `[assets]` folder, `ensure [assets]`. ~4.2 MB.

Contents:
- `stream/` (79 files) for Legacy: 9 `.yft` (`prop_streetlight_01, 01b, 03, 03c, 03d, 04`, `prop_traffic_01a, 01b, 01d`: stock poles, flat LED heads, warm white 255,227,166; housing on the arm bone, LED face on the glass bone, so a shot lamp loses only its lit face; LED faces lit 128×256 / shot 64×128 since 2.0.4), 28 `m25_2_distlodlights_medium*.ymap` (distant LOD glow recoloured; `m25_2_` is build 3889's active set, replacing build 3407's `vw_`), 42 `*_critical_*.ymap` (placements with their own LightEffect, recoloured and moved to the LED face).
- `stream_enhanced/` (78 files): hand-made, models converted gen8→gen9 with CodeWalker, map data regenerated from Enhanced 1.0.1158; lacks `hei_kt1_rd_critical_0.ymap` (Legacy-only). `.enhanced-manual` marks it so the git hook leaves it alone.
- `data/whippy_led_timecycle.xml` (modifiers `whippy_look`, `whippy_day`, `whippy_night`, `whippy_night_plain`) and `data/whippy_led_look_snapshots.xml` (357 snapshot modifiers `whippy_look_<group>_NNN`, ~380 KB); both `files` + `data_file 'TIMECYCLEMOD_FILE'`, loaded on both games.
- Client scripts: `client/look_data.lua` (Legacy keyframes, `LookData`), `client/look_snap.lua` (Enhanced snapshot list, `LookSnap`), `client/look_legacy.lua` (returns early unless legacy), `client/look_enhanced.lua` (returns early unless enhanced). `look_data.lua`, `look_snap.lua`, both XMLs are generated (`work/lookdev/build_look*.py`, not in repo); do not hand-edit.

Platform selection: client reads `GetConvar('whip_platform', 'legacy')`, lower-cased; `enhanced` → Enhanced look. An Enhanced server MUST `setr whip_platform enhanced` (setr, so clients see it), or the Legacy look runs on Enhanced.

How the look works:
- Extra timecycle slot, strength 1.0, re-evaluated every 1000 ms:
  - Legacy: `whippy_look` rewritten live with `SetTimecycleModifierVar` from game hour (linear between keys, wraps at midnight) and weather group; plus `dir_shadow_cascade0_scale = 10` (sun-shadow box).
  - Enhanced: picks the snapshot covering the hour for the weather group (last snapshot with start ≤ hour) and `SetExtraTimecycleModifier`s it (FiveM's live-edit natives are unconfirmed on Enhanced). Each switch moves values ≤5% of their daily range.
- Main slot: `whippy_day` / `whippy_night` cross-faded by strength: day 07:00-19:00, night 21:00-05:00, smoothstep through stock at 06:00 and 20:00; Halloween weather uses `whippy_night_plain` (keeps the green moon). Checked every 250 ms; if another script's modifier is on the main slot it steps aside and returns within 250 ms once free. Strength set only on change.
- Weather groups: EXTRASUNNY/CLEAR/CLOUDS/CLEARING/NEUTRAL → `clear` (grade 1, ambient, fog, glow); SMOG → `smog` (grade 1, ambient, glow, no fog); OVERCAST/RAIN/THUNDER/FOGGY → `grey` (grade 0.5 only); XMAS/SNOWLIGHT/BLIZZARD → `snow` (grade 0.3); HALLOWEEN → `halloween` (off). Unknown weather → `grey`; unknown hash → EXTRASUNNY. Uses `GetNextWeatherTypeHashName()`.
- Visual settings while on (restored on stop / toggle off): `Tonemapping.bright.filmic.A = 0.20`, `Tonemapping.bright.filmic.W = 5.0`, `misc.coronas.intensityScaleGlobal = 0.9`, `misc.coronas.sizeScaleGlobal = 1.1`. On Enhanced only if `SetVisualSettingFloat`/`GetVisualSettingFloat` exist (pcall'd). Night glow needs Post FX High+.

Command (client, unrestricted): `/ledambient` — toggles the whole look (both slots + visual settings) for the local player; prints `[whip_graphics] look ON|OFF` (`[whip_graphics_enhanced]` on Enhanced). No exports, no events, no server script.

Conflicts: overrides those nine models; do not run with another mod changing the same streetlights; replaces the retired `whippy_streetlight_03` resource.

## whip_homes_mirrorpark

Every Mirror Park house as a walk-in home: 71 homes in 16 designs, 25 walk-in site garages, 8 interior looks. Version 1.0.0 (code `VERSION = '0.12.0'`). Requires whip_core (properties). `this_is_a_map 'yes'`. ~102 MB. Install in `resources/[assets]`, ensured by `ensure [assets]` after whip_core.

What it streams (`stream/` and `stream_enhanced/`, 632 files each: 391 `.ydr`, 121 `.ymap`, 70 `.ybn`, 40 `.ytyp`, 9 `.ytd`, `_manifest.ymf`):
- Owns the area's stock overrides (`hei_id2_21*` maps, regional collision, night-window LODs, occluders); conflicts with any other map changing these houses; do not run the retired `whippy_test_bungalow`.
- Driveway car generators removed from its maps; driveway scenario points blocked client-side with vehicles-only scenario blocking areas (street parking untouched).
- `data_file 'DLC_ITYP_REQUEST'` for 16 `*_types.ytyp`, 16 `*_int.ytyp`, 6 variant interiors (`mp_d10v1/v2`, `mp_d11v1`, `mp_h2v1`, `mp_h3v1`, `wh_bngv1`: windows facing site garages walled), `mp_site_garages_types.ytyp`, `mp_site_garages_int.ytyp` (all referenced under `stream/`; none in `files`).
- `data_file 'GTXD_PARENTING_DATA' 'gtxd.meta'`: `wh_theme_1..7` texture dictionaries parented to `wh_bng_textures` (each theme txd holds only its 4 textures).
- `data_file 'INTERIOR_PROXY_ORDER_FILE' 'interiorproxies.meta'`: reserves proxy slots 5000-5070 for the 71 homes and 5071-5095 for the 25 garages so FiveM deletes them on disconnect (no dead copies after reconnect).
- `files { 'interiorproxies.meta', 'gtxd.meta' }`.

Using it: the pack does NOT create properties. In-game: `/whip → World → Properties → New property`, standing inside the house. Then the home's sign and admin page offer the 8 looks (owner or anyone who may furnish).

Interior themes contract (`whip_interior_themes 'v1'` in fxmanifest; whip_core `server/property_themes.lua` finds it, matches property placement to a home by archetype or `designArchetype` within 2.0 m, stores the choice in the property's `theme` column, pushes the whole table when either resource starts and each change as made).

Themes (`id`, `key`, `name`, walls, trim, skirting, floor, floorName): 0 original/Original `#b2a899` (honey oak), 1 charcoal/Charcoal `#424244`, 2 navy/Navy `#2a364a`, 3 forest/Forest `#2e4036`, 4 oxblood/Oxblood `#5c2a2a`, 5 slate/Slate `#48525a`, 6 espresso/Espresso `#48362c`, 7 midnight/Midnight `#222224`. Entity sets `wh_theme_0..7`.

### GetThemes() — SERVER
Returns a copy: `{ { id, key, name, walls, trim, skirting, floor, floorName }, ... }` (colours `#rrggbb`; floor = the oak's mid tone).

### GetHomes() — SERVER
Returns a copy: `{ { key, archetype, designArchetype, position = vector3 (MLO instance origin), heading = degrees }, ... }` (71 rows). Keys like `mp_d01_p01`, `mp_h3`, `wh_bng_p04`. `archetype` is the variant MLO for `mp_d10_p01..p03`, `mp_d11_p02`, `mp_h2`, `mp_h3_p03`, `wh_bng_p04`.

### GetHomeTheme(key) — SERVER
Returns theme id (0 when unset) or nil for an unknown home.

### SetHomeTheme(key, id) — SERVER
`id` integer 0-7. Returns `true` or `false, 'unknown home <key>' | 'unknown theme <id>'`. Publishes `GlobalState.whMpThemes`.

### SetAllThemes(map) — SERVER
`map = { [homeKey] = themeId }`; replaces the whole table (left out = 0). Returns `true, count` (non-zero entries) or `false, 'expected { [home key] = theme id }' | 'unknown home <k>' | 'unknown theme <v> for <k>'` (all-or-nothing).

State: `GlobalState.whMpThemes = { [home] = id }` (theme 0 omitted). Survives a restart of this resource (valid entries re-read at start). Clients apply only after the table arrives; after 10 s without it, homes load Original.

### GetHomeAt(coords?) — CLIENT
`coords` default = player ped position. Returns `homeKey, interiorId` for a loaded home whose interior contains the point (within 50 m of origin), else nil.

### GetHomeTheme(key) — CLIENT
The theme this client wants for the home (includes a local `wh_theme` preview), or nil.

Client events fired (local `TriggerEvent`): `whip_core:interiorRefreshed` (interiorId) after each theme refresh (whip_core rebuilds furniture); `whip_homes_mirrorpark:themeApplied` (homeKey, interiorId, theme, wasInside, refreshed). Listens to `whip_core:property:furnishStateChanged` and polls `exports.whip_core:GetInteriorFurnishState(id)` (every ≤250 ms; a `pending` longer than 12 s stops holding the windows) — window "reveal gate" opens when interior ready + themed + furniture done.

Interior loader (client): FiveM's scene graph caps 256 interior rooms / 800 portals for everything loaded; the 71 placement maps total 669 rooms / 1,777 portals, so only the nearest homes load. Defaults `MAX_HOMES 8`, `ROOM_BUDGET 64`, `PORTAL_BUDGET 224`; wanted within 60 m of the walls (`LOAD_ON`), kept to +10 m; no new loads while the player moves faster than 8.3 m/s.

Convars (client-read):
- `whip_platform` — `enhanced` enables the client garage-door wake-up (on Legacy FiveM's own patch does it).
- `wh_loader` — `ipl` (default; RemoveIpl/RequestIpl by budget) or `static` (never touches placement maps; enforces budget with DisableInterior; needs `GetInteriorAtCoordsWithTypehash` + `GetInteriorLocationAndNamehash`, else falls back to ipl). Set with `setr wh_loader static`.

Commands:
- Server, restricted (console/ACE): `wh_theme_set <home> <id>`, `wh_theme_list` (testing without whip_core; whip_core's next SetAllThemes overwrites).
- Client dev commands (F8), refused unless `exports.whip_core:HasDevTools()` is true (WHIP developer mode on via `/w`, needs `whip.devtools`); without whip_core they stay off: `wh_garage_doors on|off`, `wh_reveal` (log load→reveal steps), `wh_unload` (forced unload toggle, ipl mode), `wh_glass [native|fade [far near]]` (window mode, saved), `wh_xray` (hide matte plugs locally), `wh_debug` (overlay), `wh_budget <homes> <rooms> <portals>` (saved per player), `wh_ground [watch]`, `wh_stairs`, `wh_theme [<home|here> <0-7|off>]` (local preview), `wh_home_check`, `wh_bungalow_check`.

Doors: not registered by this pack; whip_core's door system owns them.

## Legacy/Enhanced asset layout (stream_enhanced, git hook)

- FiveM on Enhanced streams `stream_enhanced/` INSTEAD OF `stream/` when it exists; Legacy streams `stream/` (`#both-platforms`; `.githooks/enhanced_assets.py`). Ship both for any models/maps/props.
- Packs with models: whip_graphics (hand-made `stream_enhanced`, `.enhanced-manual`), whip_homes_mirrorpark and whip_media_map (`stream_enhanced` generated).
- `.githooks/enhanced_assets.py` (identical in whip_graphics, whip_homes_mirrorpark, whip_media_map), run by `.githooks/pre-commit`: converts staged `stream/` changes with Alchemist (`git config alchemist.cli <path to AlchemistCli.exe>`, `git config core.hooksPath .githooks`) and stages results. Commands `hook`, `sync RESOURCE...` (`sync .` for repo root), `check`. Skips resources with `.enhanced-skip`, `.enhanced-manual`, a sibling `<name>_enhanced`, `.fxap` (escrow), or only `stream_enhanced/`. Flags drawables (`.ydr/.ydd/.yft`) with >127 geometries: Enhanced crashes streaming one (Legacy and Alchemist accept them); split the model.
- Alternative layout the setup report understands: a separate `<name>_enhanced` resource; running the wrong one for the platform is a FIX.
- NUI pages wider than 8192 px are refused by `CreateDui` on Enhanced; NPCs made before any character loads can lose their network id (`#both-platforms`). `exports.whip_core:GetPlatform()` → `'legacy'|'enhanced'` on either side.

## whip_test: the automated suite

Resource `whip_test` 1.0.0, `dependency 'whip_core'`, `whip_requires '1.0'`, needs oxmysql (`@oxmysql/lib/MySQL.lua`) and whip_core of the same release. TEST SERVERS ONLY: a run gives/takes items, money and cars on the tester's character, creates test doors/containers/vehicles; the load test deliberately strains the server. Not in the recipe; put in `resources` and `ensure whip_test` from the console when needed. It also declares `whip_interior_themes 'v1'` (stand-in theme provider for module 69, exports in `server/tests/69_property_themes.lua`) and includes `@whip_core/lib/satellite.lua`.

Prerequisites for `/test`:
1. `set whip_test_seams true` in server.cfg → whip_core `Config.EnableTestSeams = GetConvar('whip_test_seams', 'false') == 'true'` (`whip_core/config.lua:1800`). Without it the run refuses: "Config.EnableTestSeams is not true in whip_core — the suite cannot run without it." (`whip_test/server/runner.lua:1503`). Setup report shows a note while seams are on.
2. Tester has ACE `whip.devtools` AND developer mode on (`/w`): checked with `exports.whip_core:HasDevTools(src)`; falls back to bare `IsPlayerAceAllowed(src, 'whip.devtools')` only if whip_core is not running (`runner.lua:1451`). Refusal: "You need whip.devtools, with developer mode on (/w)."
3. Tester alive ("You are dead. Respawn or get revived, then run /test again.").
4. No run, endurance run or load test already in progress.
5. In-game only (console → "Use this in-game.").

Commands (all in-game):

| Command | Does |
|---|---|
| `/test` | Opens the NUI menu: a card per section with server test count, last result (passed/failed/skipped, partial, "ago"; memory only) |
| `/test all` | Full suite |
| `/test <section id>` | One section (ids below); unknown id lists the valid ones |
| `/teststop` | Request stop: the current test finishes, loops end at the next flag check and clean up from there; during the client phase sends the (partial) report at once |
| `/testlong` | Endurance run (below) |
| `/testload [dial=value …]` / `/testload help` | Load test (below) |
| `/testloadstop` | Stop a load test; works from the server console |
| `/testloadclean [confirm]` | Count / delete load-test leftovers (console allowed) |

`/test`, `/teststop`, `/testlong` and the demo panels are registered unrestricted and gated in code; `/testload`, `/testloadclean`, `/testloadstop` are registered restricted (also need `command.<name>` ACE; the recipe's `add_ace group.admin command allow` covers it). `/testloadstop` checks the bare ACE, not developer mode.

Run flow (`StartRun`, `runner.lua:1481`):
1. Reset harness switches (`__TestSetDbFaultMode(nil)`, `__TestFailNextQuery(nil)`, `__TestPauseFlushThread(false)`), take `__TestHarnessState` baseline.
2. Snapshot the tester's inventory (aborts if unreadable); restored at the end. Typed accessory slot 4 becomes a bandage-only "Medkit" slot for the run (`RegisterAccessorySlot{ slot = 4, accepts = 'bandage', label = 'Medkit', tag = 'whip_test:strip:<time>:<n>' }`), released (`ReleaseTag`) afterwards.
3. Close all UI, leave vehicle, empty the tester's inventory.
4. Server phase: modules sorted by `order` (file number); per module `setup(source, ctx)` → each test `fn(source, ctx)` (50 ms gap) → `teardown(ctx, source)` (always runs, even after setup failure) → leak check.
5. Client phase: `whip_test:runClientTests` to the tester; client must answer within `CLIENT_PHASE_MS` = 180000 ms or a `CLIENT PHASE TIMED OUT` row is added (`runner.lua:1270`).
6. Report: cleanup, remove the run's own activity-log rows from the tester's timeline, NUI report, server event `whip_test:runFinished` (source, report).

Result rules:
- A test that finishes with zero assertions FAILS: "no assertion ran — this test cannot fail as written" (`runner.lua:1128`).
- `skip(reason)` records SKIPPED (not pass). Setup skip/failure emits one row per test (`SETUP SKIPPED: <name>` / `SETUP FAILED: <name>`) so totals stay honest.
- Meta rows (`TEARDOWN`, `LEAKED STATE`, `CLIENT PHASE TIMED OUT`) count as failures but not as tests.
- Leak check after each module: open panels (closed via `ClosePanel`), open store views (`__TestReleaseViews`), armed DB/raw-query faults, paused flush thread, changed player/container durability, rate-limit bypass left on, phantom players, tester flagged dead, items left in the tester's inventory. Each is reported as `LEAKED STATE` against the module that leaked, then cleared.
- Totals check: "⚠ expected N server results, got M — modules were lost"; client "⚠ expected N client results"; on full runs, each missing client module order prints "⚠ no client test module with order N — did its file fail to load?".

Output format:
- Chat lines with prefix `[TEST]`: `✓ <category> > <test> (<ms>ms)`, `- <category> > <test> (skipped: <reason>)`, `✗ <category> > <test>: <error>`, `✗ <category> > SETUP FAILED|TEARDOWN FAILED|LEAKED STATE: …`; footer `ALL N TESTS PASSED (Xs)` or `P passed F failed S skipped (Xs)`.
- NUI report (`whip_test:showReport`, NUI focus on): title `whip_core Test Report — Full Suite` or `… — <section label>`; summary counts, time, `PARTIAL (stopped)`; categories grouped, expanded when failing, `passed/total` and PASS/FAIL badge; each row icon ✓/−/✗, name, side (server|client), duration, error text. Buttons: Copy Failures (plain text: header line, then `[SKIPPED — ]<category>: <name> [<side> <ms>ms]` + indented error), back to menu; Escape closes.
- Report object (also the `runFinished` payload): `{ results = { { category, name, passed, skipped?, error?, duration, side, meta? } }, passed, failed, skipped, totalTime, partial, title }`.

Server assertion globals available to modules: `assertEqual, assertNotEqual, assertType, assertNotNil, assertNil, assertTrue, assertFalse, assertGt, assertGte, assertOk(value, err, label), assertLastReject(eventName, expectedReason|nil, label)` (reads `__TestLastReject`), `assertDbScalar`, `assertDbRowCount` (flushes first), `skip(reason)`, `waitFor(fn, ms)`, `DbQuery`, `FlushPersistence`, client drivers `ClientExecWait`, `ClientCallback`, `ClientOpenContainer`, `ClientEnterVehicle`, etc. `DB_ERROR = 'Could not save that (database error)'` mirrors whip_core's reason. Client runner mirrors the asserts.

Exports (server):

### StartTestRun(source, sectionId?) — SERVER
`sectionId`: `'all'`/nil = full suite, or a section id. Same gates as `/test`. Returns `true` or `false, why` (`'No such player.'`, `'The tester needs whip.devtools with developer mode on (/w).'`, `'No section called "<id>".'`, plus StartRun refusals: `'Tests are already running.'`, `'The endurance test is running.'`, `'The load test is running.'`, `'Config.EnableTestSeams is not true in whip_core.'`, `'The tester is dead.'`, `"Could not read the tester's inventory."`). Report arrives as server event `whip_test:runFinished` (source, report).

### GetTestSections() — SERVER
`{ { id, label }, ... }` for built-in and external sections.

### IsRunning() — SERVER
`true` while a suite or endurance run is going.

### RegisterTestModule(mod) — SERVER
`mod = { category, tests = { { name, fn } }, setup?, teardown?, order? (default 1000) }`. Returns `true` or `false, why` (`'a test module is { category = "...", tests = { { name = "...", fn = function(source) end } } }'`, `'test <i> needs a name and fn'`). Same owner+category replaces; the owner's modules and card are removed when it stops. Use via the kit.

### MakeStranger() / DisposeStranger(userId) — SERVER
Throwaway account + character in the DB for tests needing another person: `charId, userId` or nil when seams are off. `DisposeStranger` removes both, returns true.

## whip_test: sections and modules

Sections (`whip_test/shared/sections.lua`; `/test <id>`): `player`, `inventory`, `containers`, `panels`, `saving`, `vehicles`, `money`, `jobs`, `world`, `emotes`, `voice`, `director`, `interaction`, `security`; plus `other` (modules in no section) and one card per external resource (id = resource name, or `res_<name>` on collision).

Server modules (file → category, ≈ test count by `name =` lines):

| Section | Modules |
|---|---|
| player | 01 Player (9), 35 Player API (15), 33 Appearance (5, saveAppearance shape sanitizer), 39 Stats & Effects (25), 73 Player Flags (4) |
| inventory | 02 Inventory (30), 09 Item Registration (13), 17 Item Use (10, RegisterUseHandler), 23 Moves (11, real event path), 24 Placement (12, conjure/destroy primitives), 25 StoreMove (31, storeMove + `addr` param type), 31 Place Item (6, placing mode, `placed` flag), 36 Store Kinds (13, RegisterStoreKind), 26 Admin Inventory (7), 43 Inventory API (31), 44 Menu & Shift-Click (19, Split/Destroy outside pockets) |
| containers | 07 Containers (27, create→open→place→take→close→delete), 06 Ground Items (13), 27 Ground Drop (6, CreateGroundItem both call shapes) |
| panels | 13 Panel (OpenPanel API) (7), 19 Panels (8, OpenPanel/ClosePanel/onClose), 21 Panel Contract (8, onValidate), 30 Panel Item (15, RegisterPanelItem) |
| saving | 16 Persistence (16, DB round-trip), 28 Incremental Save (14), 29 Write-Behind (29), 20 Failure Paths (6, DB says no), 32 Activity Log (9, uid stamp, two timelines) |
| vehicles | 05 Vehicles (36, create→spawn→key→lock→fuel→trunk→store→delete), 37 Vehicle Data (46, data, stats, ownership transfer), 75 Vehicle Damage (5) |
| money | 03 Bank (27), 18 Bank Access (8, Grant/RevokeBankAccess, GetPlayerJob), 47 Payments (11, ChargePlayer/RefundPlayer), 08 Shops (15), 40 Shop Economy (23, catalogs, shelf prices, stock) |
| jobs | 04 Jobs (44) |
| world | 12 Time & Weather (8), 14 Zones (Server) (24), 15 Doors (Server) (28), 50 World API (19), 61 Managed Doors (9), 60 Property Math (6), 62 Properties (13), 63 Property Packs (7), 64 Property Admin (10), 65 Property Wizard (9), 66 Property Garage (8), 67 Property Scale (6), 68 Property Stashes (10), 69 Property Themes (9) |
| voice | 70 Voice Items (5, megaphone, radio; whip_voice or whip_voice_simple) |
| director | 74 Director API (8), 76 Check (12), 77 Flow (18), 78 Endings (11), 79 Live Runs (6), 80 Player Cards (9), 81 World Things (8), 82 Goals (8), 83 Conversations (11), 84 Fail Conditions (7), 85 NPC Tasks (22), 86 Car & Prop Tasks (17), 87 Security (5), 88 Fixed Weapons (5) |
| interaction | 48 UI From The Server (18), 51 Runtime Points (6, points & NPCs) |
| security | 10 SecureEvent (18, SecureEvent/SecureCallback), 11 Callbacks (3), 38 Sentinel (14, statebag tamper watch), 34 API Contract (9, types file vs real exports), 42 Audit 2 Fixes (9), 46 Registry & Security (20), 72 Permissions (5) |
| other | 89 Retired Items (5, RetireItem) — listed in no section |

Client modules (`Client: <name>`, orders 1-20, no 5): Player (4), Inventory (8), UI Library (10), Interactions (18), Vehicles (11), Jobs (4), Stats (3), Camera (6), Time (3), Callbacks (4), Zones (30), Doors (4), Garage Helper (3), Registry (5), Emotes (7), Voice (2), Dev Pages (3), Clean Screen (3), Objectives (4). Sections: Client: Player/Stats → player; Inventory → inventory; Vehicles/Garage Helper → vehicles; Jobs → jobs; Time/Zones/Doors/Camera → world; Emotes → emotes; Voice → voice; Interactions/UI Library/Dev Pages/Clean Screen/Objectives → interaction; Callbacks/Registry → security.

## whip_test: endurance run (/testlong)

Gates: in-game, dev access, nothing else running. Snapshots the inventory. Loops 1 tick/s until `/teststop`; HUD update every 5 s (elapsed, cycles, errors, RAM MB, delta MB, per-system cycles/errors/avg ms).

| System | Every N ticks | Does |
|---|---|---|
| Inventory | 3 | `AddItem(source,'food',3,nil,{reason='_endurance',noDrop=true})` then `RemoveItem` |
| Ground | 5 | `CreateGroundItem('food',1,…)`, `GetGroundItemsNearby(…,50)`, `DeleteGroundItem` |
| Bank | 5 | creates `_endurance_account` once (`CreateBankAccount(source, '_endurance_account', { type = 'personal' })`), `BankDeposit`/`BankWithdraw` 100 with `source` as actor |
| Callback | 2 | `GetPlayer`, `GetItemCount(source,'food')` type check |
| Container | 8 | `CreateContainer{ name='_endurance_ctr', slots=5, maxWeight=20.0 }`, `GetContainer`, `DeleteContainer` |
| Vehicle | 10 | `GetVehiclesOf(source)`; toggles and restores the first car's lock via `SetVehicleLocked` |

On stop: endurance account drained and closed with its transaction rows (`DisposeTestAccount`), inventory restored, report: one row per system (`<name> (<cycles> cycles, avg <ms>ms)`, fails on any error with the last one) plus "RAM stability (delta: X MB)" failing at ≥50 MB growth (`runner.lua:1967`).

## whip_test: load test (/testload)

Purpose: what whip costs at ~200 players without players. Cannot measure OneSync sync, bandwidth, or client frame time. Needs test seams (phantoms come from `__TestPhantoms`; with seams off "none created — is Config.EnableTestSeams true?").

Dials (`/testload name=value …`, unspecified = default, values clamped to `[0, max]`, unknown keys reported):

| Dial | Default | Max | Loads |
|---|---|---|---|
| `players` | 200 | 512 | phantom entries in Players + Stats cache |
| `announce` | 0 | 1 | 1: each phantom fires `whip_core:player:loaded` (phantom = true) so satellites work too |
| `vehicles` | 50 | 300 | server-spawned cars 1200 m away |
| `items` | 300 | 2000 | ground items (near the operator on purpose) |
| `stats` | 6 | 40 | extra decaying stats (multiplies per-player tick) |
| `doors` | 20 | 200 | doors toggled one per 100 ms tick |
| `containers` | 20 | 200 | stocked containers (write-behind flush) |
| `events` | 20 | 100 | events/s fired by the operator's client through real SecureEvent (FiveM's net-event limiter can kick you) |
| `dbrows` | 200 | 512 | rows per DB burst into table `whip_loadtest_rows` (created/dropped by the run) |
| `dbevery` | 60 | 600 | seconds between bursts (60 = Config.SaveInterval) |
| `churn` | 20 | 200 | objects recycled per second round-robin (items, containers, doors, vehicles) |

Run: calibrates the tick baseline (worst of 15 × `Wait(100)`), then every 100 ms measures drift; aborts if drift > `DRIFT_ABORT_MS` = 2500 ms. Renews `__TestRateLimitBypass(true)` every 3000 ms while events > 0 (whip_core TTL 10 s, so a crashed run restores rate limiting by itself). Panel update every 500 ms: counts, door toggles, churned, DB sent/done/failed/peak in-flight, DB latency p50/p95/p99/max, bursts, events sent, drift, worst drift, RAM MB. Output also printed as `[whip_test:load] …` in the server console and `[load]` in chat.

Stop (`LoadTestStop`): bypass off first, phantoms 0, unregister stats, delete vehicles/items/doors/containers, drop the table; triggered by `/testloadstop`, drift guard, operator disconnect, resource stop.

`/testloadclean`: counts (and with `confirm` deletes) ground items whose metadata contains `_loadtest`, ground items with scalar (bare number/string) metadata (breaks whip_core's ground loader), vehicles with `vehData._loadtest` (deleted one by one through whip_core), doors labelled `_loadtest_door_%`, containers named `_loadtest_ctr_%` (contents first). Afterwards restart whip_core (caches still hold removed rows).

## whip_test: kit for your own resource's tests

`server_script '@whip_test/lib/kit.lua'` (test server only). Register inside `Whip.registerWith('whip_test', function() … end)` so it re-registers when whip_test restarts.

```lua
Whip.registerWith('whip_test', function()
    WhipTest.module({ category = 'My Café', tests = {
        { name = 'a coffee costs $5', fn = function(source)
            local ok, why = exports.whip_core:ChargePlayer(source, 5, { method = 'cash' })
            WhipTest.assertOk(ok, why, 'charged')
        end },
    } })
end)
```

- `WhipTest.module({ category, order?, setup?(source), teardown?(ctx, source), tests = { { name, fn(source) } } })` → `true` or `false, why`. Card named after your resource; `/test <resource>` runs it.
- Asserts: `assertEqual(actual, expected, label)`, `assertTrue`, `assertFalse`, `assertNil`, `assertNotNil`, `assertOk(value, err, label)` (fails on nil/false with the reason). `WhipTest.skip(reason)`, `WhipTest.waitFor(fn, timeoutMs = 5000)` → truthy value or nil, `WhipTest.makeStranger()`, `WhipTest.disposeStranger(userId)`.
- Each wrapped test returns its assertion count; zero assertions = fail. `ctx` arrives as a copy across the resource boundary: keep state in your own locals.

## whip_test: demo panels and the Sentinel tamper seam

- Demo panel commands (dev only, in-game): `/testpanel` (6-slot "Test Panel"), `/testpanelro` (4-slot read-only), `/dumpster`, `/lootcrate`, `/medkit`, `/evidence`, `/vendingmachine`, `/toolbox`, `/dropoff`, `/safebox`, `/trashcan`, `/showcase`; each opens an `OpenPanel` example.
- `/sn_tamper <key> <value>` (client, not in README): writes whip's watched statebag keys from the client like a cheat menu, to prove the Sentinel (e.g. `isDead true`, `damageModifier 0.01`, `charId nil`, `whipVehicleId 999999` while driving). Values parse as nil/true/false/number/string. Exists only while whip_test runs.

## Testing and measuring tools in whip_core (docs cross-reference)

From `#testing`, `#measuring`, `#export-costs` (details in the dev-tools reference):
- Inventory screen without the game: `node whip_core/dev/inventory-preview/preview.js my_inventory_ui`.
- Director: `TestDirectorCard(type, props, { player = source })`, `TestDirectorScenario`.
- Second player: pass `{ charId = n }` for another character of yours; two FiveM clients on one PC; turn off `Config.BlockOwnCharacterTransfers` on a test server to move money between them.
- `/w` → Kill Me, Restore Health & Armour, Repair Vehicle; `/whip` → System → Monitor (SecureEvent calls, refusal reasons, handler time); `whiperrors` / `GetErrorLog`.
- Cost: `/whipcost` (client, developer mode), `WhipCost.start()`/`WhipCost.stop('label', t)` via `@whip_core/lib/cost.lua`, `MeasureFrames({ seconds })`, server console `whipcost [seconds]`, `profiler record 500` + `profiler view` with `setr whip_profiling 1`.

## WHIPFX org policies (.github)

`SRC_DIR/.github` (commit `8d107a7`): applies to every WHIP repo.
- Contributing: one repo per resource; issues state resource, version, Legacy/Enhanced, repro; security issues only via private reporting. PRs: fork, branch from `main`, one change per PR (issue first for large features), test on a recipe-installed server, no new LuaLS warnings (whip_core `types/` describes the API), conventional commits (`fix:`, `feat:`, `chore:`, `docs:`), PR against `main` with what changed and how tested; rebase not merge. Contributions are under the repo's licence; no third-party assets/code unless licensed; state third-party origins.
- Governance: roles Owner (org owner), Maintainer (maintain on every repo: review/merge, releases, issues), Triage, Contributor. Every change to `main` in a code repo via PR with one approval from a maintainer/owner other than the author, all conversations resolved, linear history; owners may merge their own PRs without approval; no direct pushes. Recipe changes get the most care. Tags `v<version>` matching fxmanifest, never moved/deleted. Disputes: owners decide.
- Security: report via the repo's **Security > Report a vulnerability**; include resource, version, impact, repro. Only the latest release of each resource as installed by the current recipe gets fixes. In scope: anything a client can send that the server trusts wrongly, admin/permission checks, the recipe and its downloads, whip_voice's installer and services. Out of scope: FiveM, txAdmin, GTA V, upstream oxmysql, owners' own changes/settings.

## Gotchas

1. The recipe only builds a NEW server; it cannot be layered onto an existing one. Migrating = new server + port your resources (`ensure` them after WHIP's lines).
2. Enhanced without `setr whip_platform enhanced` (must be `setr`, not `set`) runs Legacy code paths on clients: whip_graphics' Legacy look, mirrorpark's garage-door wake-up off; the setup report flags the mismatch.
3. Enhanced cuts any single file download at ~2 min; without `set sv_resourceFileDownloadTimeout 600000` slow players never finish the media packs.
4. `ensure [assets]` starts the media packs, map packs, chameleon_paint and bob74_ipl together; putting the packs elsewhere is fine as long as they are started (missing/stopped → FIX lines and blank pictures).
5. Updating a media pack by replacing its folder wipes pictures you added; copy them out first. Same for `whip_core/pack_exports` and `whip_autos/engines.json`.
6. New clothing pictures are invisible in the editor until `Rebuild clothing picture list.bat` rewrote `whip_core/data/clothing-pictures.json` AND whip_core restarted (the list lives in whip_core, not the pack); updating whip_core overwrites that JSON with the shipped one.
7. New prop/vehicle pictures need a pack restart (players get the file) AND a whip_core restart (picture flags are read from disk only at start). An empty file counts as no picture.
8. If the props pack folder is missing at whip_core start, picture flags are left as they were (not zeroed); vehicles get no pictures at all and the dealership has nothing to sell.
9. Moving pictures between packs or adding `whip_media_props_2` requires `node whip_core/dev/assets_index.mjs`; otherwise `WhipAssets.resourceFor` still points at the old pack. A split area must be one sorted name run per pack.
10. P-001 answers only promise/await callers. Plain-callback oxmysql calls still get no callback on a DB-down error unless the resource sets `mysql_option 'return_callback_errors'`; they only log.
11. oxmysql's version check still queries `overextended/oxmysql` releases; following its "update available" link installs upstream without P-001 (the setup report then shows the unpatched note). Get updates from `WHIPFX/oxmysql` releases.
12. Hand-patching stock oxmysql (`whip_core/dev/oxmysql-p001.diff`) is lost on any oxmysql update (it replaces `dist/build.js`).
13. whip_core's db_guard gives a stuck `transaction` 10 minutes, not 65 s; schema-change queries are never cut off.
14. whip_test must never run on a live server: `whip_test_seams true` enables DB-failure injection, phantoms and rate-limit bypass seams; `/sn_tamper` is a working cheat while whip_test is started.
15. `/test` needs developer mode ON, not just the ACE; a dead tester or an open UI fails the start or many tests.
16. Full-suite runs always print "⚠ no client test module with order 5": there is no client test 05 (files jump 04 → 06).
17. `Retired Items` (module 89) is in no section, so it only appears on the "Other" card; the `interaction` section lists a category `Interaction Points` that no module registers.
18. `/testload help` lists only 8 dials; `announce`, `dbevery` and `churn` exist but are not shown.
19. `/testload` with `events` > ~20/s can get the operator kicked by FiveM's reliable-event limiter (not bypassable).
20. After `/testloadclean confirm` restart whip_core: its caches still hold the deleted rows.
21. `/testload*` are restricted commands: a tester with only `whip.devtools` (no `command` ACE) cannot run them.
22. mirrorpark homes do nothing until each is made a property in `/whip → World → Properties → New property` while standing inside; themes need whip_core and are all-or-nothing in `SetAllThemes`.
23. mirrorpark's `wh_*` F8 tools are refused without WHIP developer mode; `wh_budget` and `wh_glass` settings persist per player in KVP.
24. whip_graphics steps aside while another script holds the main timecycle slot; a camera filter that clears the slot shows stock lighting for up to 250 ms.
25. Drawables with >127 geometries crash Enhanced when streamed; the git hook only warns, split them.
26. The txAdmin download of a big pack can exceed txAdmin's 150 s default; the recipe sets `timeoutSeconds: 900` on six tasks, yet the README still asks for 10 Mbit/s.

## Docs vs code

- Quickstart `server.cfg` (`#quickstart-cfg`) omits lines the recipe writes: `ensure whip_dealership`, `sv_maxclients`, `{{serverEndpoints}}`, `sv_scriptHookAllowed 0`, `add_ace group.admin command allow`, `add_ace group.admin command.quit deny`, Legacy `set mumble_disableServer true`, Enhanced `stop chat` and the pool sizes (`txAdmin-recipe/whip-legacy.yaml`, `whip-enhanced.yaml` write_file task). Docs show a literal `add_principal identifier.fivem:…`; the recipe uses `{{addPrincipalsMaster}}`.
- Docs/README say the two recipes "differ only in server.cfg"; the YAML headers also differ (`name`, Legacy-only `$minFxVersion: 38435`), and the README's list of differences omits `mumble_disableServer` (Legacy) and `stop chat` (Enhanced).
- Quickstart says stock `chat` "isn't installed"; the Enhanced recipe still runs `stop chat` (Enhanced cfx-server presumably ships it; inferred).
- oxmysql README: "every query call … answers its caller with an error at once". Code answers via callback only when `isPromise` is true (`oxmysql/src/logger/index.ts:56`); plain callbacks are not called. whip_core's own comment agrees (`whip_core/server/director/store.lua:689`).
- `whip_core/server/db_guard.lua:4-6` describes the upstream bug as oxmysql 2.12.0 and lists `rawQuery and rawTransaction`; the fork patches four functions (also rawExecute, startTransaction) at 2.14.3.
- Recipe README and Quickstart tell owners to copy out "pictures taken in game" from `whip_media_props/img/props` and `whip_media_previews/img/vehicles`, and the props/previews fxmanifest comments credit `/propsnap` and "the Vehicle Snapshot tool"; but `/propsnap` is gone (`whip_core/shared/config_guard.lua:57`), the vehicle picture tool is "retired" (`whip_core/server/vehicle_catalog.lua:13-15`), and nothing in whip_core calls the packs' `SavePicture`/`RemovePicture` exports.
- whip_homes_mirrorpark fxmanifest comment says stream/ and stream_enhanced/ "hold the same 629 file names"; both hold 632.
- Docs `#guide-properties` (Interior themes) say theme ids are 0-255; whip_homes_mirrorpark accepts 0-7 only (`whip_homes_mirrorpark/server.lua` `validTheme`: `id < #THEMES`), and whip_core caps providers at 64 themes (`whip_core/server/property_themes.lua` `MAX_THEMES = 64`).
- whip_test README says to `ensure whip_test` from the console; `client/sn_tamper.lua` comment says whip_test "is never ensured" (meaning: only started by hand on a test server).
- whip_test is not covered by the docs (`#testing` lists no `/test`); only `EnableTestSeams` / `set whip_test_seams true` appears (`#configuration`).
- Docs `#first-download` "5 media packs of up to 145 MB each" is the download size; on-disk the female clothing pack is ~192 MB and male ~175 MB (cap enforced by `dev/assets_index.mjs` is 256 MB).
