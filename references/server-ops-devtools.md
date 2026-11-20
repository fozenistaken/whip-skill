# Server operations, configuration and developer tools

Running a WHIP server (database, oxmysql, platform, convars, update checks, setup report), every `whip_core/config.lua` key, the in-game Config page and resource settings pages (`Whip.configPage`, `Whip.onConfigChanged`, `Whip.playerSetting`), the Activity Log, WhipCost, `/w` dev pages and debug tools, Object Viewer options, every console and chat command, ACEs, developer mode, the `/whip` admin panel, Monitor, `GetErrorLog`, and the architecture. Built from doc anchors `#resource-settings`, `#activity-log`, `#debug-internal`, `#whipcost`, `#dev-pages`, `#running-whip`, `#configuration`, `#guide-devtools`, `#building-in-game`, `#architecture`, verified against `whip_core/config.lua`, `shared/config_schema.lua`, `shared/config_guard.lua`, `shared/settings.lua`, `server/settings.lua`, `client/settings.lua`, `client/player_prefs.lua`, `lib/satellite.lua`, `lib/cost.lua`, `server/activity_log.lua`, `server/whipcost.lua`, `tools/whipcost.lua`, `server/devtools_base.lua`, `server/devtools.lua`, `server/commands.lua`, `client/dev_commands.lua`, `tools/core.lua`, `tools/ov_panel.lua`, `server/setup_report.lua`, `server/db_health.lua`, `server/db_guard.lua`, `server/updates.lua`, `shared/platform.lua`, `shared/error_tap.lua`, `server/secure.lua`, `types/server.lua`, `types/client.lua`, `types/satellite.lua`.

## Contents
- Architecture
- Running WHIP: database, oxmysql, downloads, platform
- Convars and server.cfg lines
- Update checks (GetUpdate, GetUpdates)
- The setup report (whipsetup) and every check
- Errors: whiperrors, whipsupport, GetErrorLog
- ACEs, permissions and developer mode
- Console commands
- Chat / F8 commands
- /w quick menu
- Object Viewer options (built-in)
- /whip Admin Panel sections and Monitor
- Building in game (where each tool lives)
- Configuration: how config.lua, the Config page and settings.json work
- Config page (/whip → Settings → Config): every editable entry
- config.lua: every key
- Resource settings pages: Whip.configPage, Whip.onConfigChanged, setting entry fields
- Player settings: Whip.playerSetting, GetPlayerSetting, SetPlayerSetting
- Activity Log: LogActivity, FlushActivityLog, what WHIP logs
- WhipCost (/whipcost)
- Dev pages: RegisterDevPage, RefreshDevPage, RemoveDevPage
- Debug tools: RegisterDebugTool, RemoveDebugTool
- Whip.objectViewerOption / Whip.removeObjectViewerOption
- Other dev/tool exports (HasDevTools, SetDeveloperMode, GetCommandAce, MeasureFrames, GetPlatform, GetGarageHelperStatus)
- Gotchas
- Docs vs code

---

## Architecture

- `whip_core` is the base. Every other WHIP resource depends on it and reaches it only through exports: `dependency 'whip_core'` in `fxmanifest.lua`, then `exports.whip_core:ExportName(...)`. Other WHIP resources work the same (`exports.whip_gunny:GiveWeapon(...)`).
- Layers:

| Layer | Tech | Role |
|---|---|---|
| Database | MariaDB 10.2.3+ / MySQL 8.0.16+ | Characters, items, cars, accounts between restarts |
| Server | Lua 5.4 + oxmysql | Decides everything: every change checked and held in memory, then saved (write-behind) |
| Client | Lua 5.4 + natives | Ped, keys, cars, messages to the screens |
| NUI | HTML/CSS/JS | Screens over the game: inventory, bank, creator, admin tools |
| DUI | HTML/CSS/JS in the world | 3D prompts, `/me` bubbles, NPC conversations, bay outlines, Director marks. One browser per system, created when first needed |

- WHIP needs OneSync. Cars are created by the server, so they stay when their driver leaves.
- whip_core version in this source: `version '1.0.0'`, `whip_updates 'WHIPFX/whip_core'` (`fxmanifest.lua:7,9`). Banner: "whip_core Beta 1.0.0 — public release".
- Shared load order begins: `shared/invoker.lua`, `shared/error_tap.lua`, `config.lua`, `shared/config_guard.lua`, `shared/config_schema.lua`, `shared/settings.lua` (reads `settings.json`, so any file after it sees saved values), `shared/inventory_shape.lua`, `shared/statebags.lua`, ..., `shared/registry.lua`, `shared/platform.lua`, ... (`fxmanifest.lua:12-47`).
- Satellites (your resources) load `shared_script '@whip_core/lib/satellite.lua'` and wrap registrations in `Whip.register(function() ... end)`; whip_core forgets every registration when it restarts and `Whip.register` re-runs them. `Config.DependentResources` (force-restart list) exists only for resources you cannot edit.
- A resource can declare in its fxmanifest: `whip_requires '1.0'` (setup report flags an older whip_core), `whip_updates 'owner/repo'` (update checks), `whip_property_pack` (listed as a property pack).

## Running WHIP: database, oxmysql, downloads, platform

### Database
- Minimum: MariaDB 10.2.3, MySQL 8.0.16 (`server/db_health.lua:103` `MINIMUM`). Older versions ignore CHECK rules (bank balance cannot go below zero); JSON_EXTRACT needs MariaDB 10.2.3. The setup report shows a FIX line when too old.
- Waiting for the database: whip_core waits for oxmysql to connect; the console says what to check every 30 s; joining players are told the server is still starting.
- No `mysql_connection_string`: whip_core stops and prints the line to add, e.g. `set mysql_connection_string "mysql://user:password@localhost/whip"` above `ensure oxmysql` (`server/db_health.lua:139-141`).
- No SQL to run by hand: whip_core creates its tables on first start and migrates them on the next start after an update (whip_phone does the same for its own tables). A table that cannot be created/read stops the start; players are told the server did not start.
- Database health (`server/db_health.lua`): DOWN only after a DB error followed by `SELECT 1` failing twice (1 s apart), or the heartbeat's `SELECT 1` failing twice. Never because it is slow. While DOWN, every player item action is refused ("Your items are locked: the server can't save right now. Try again in a moment."), clients get `whip_core:client:dbHealth` and lock their screens. UP on the first `SELECT 1` that answers: everything owed is saved, then items unlock.
- DB guard (`server/db_guard.lua`): wraps every awaiting oxmysql call; an unanswered call fails after `ANSWER_MS = 65000` (65 s, above InnoDB's 50 s lock wait). Transactions: `TX_ANSWER_MS = 600000` (10 min). Schema changes (ALTER/CREATE/DROP/OPTIMIZE) are never timed out.
- Stuck saves: a save that fails 5 times in a row is quarantined, retried every minute, never dropped; `whipsaves` lists them and `whipsaves drop <unit>` discards one (last resort, its changes are lost).

### WHIPFX's oxmysql
- The recipe installs WHIPFX's oxmysql: oxmysql 2.14.3 plus one fix: a query made while the database is down errors at once instead of waiting forever. Stock oxmysql works too (then the 65 s guard applies). Get the fix: replace the `oxmysql` folder with the latest release (github.com/WHIPFX/oxmysql/releases) or apply `whip_core/dev/oxmysql-p001.diff`. The setup report detects it by counting 4 `whip P-001 patch` marks in `oxmysql/dist/build.js`.

### First download
- About 510 MB on first join, mostly 5 media packs of up to 145 MB each (packs are capped at 256 MB). A pack re-downloads only when it changes.
- Enhanced cuts off any file after ~2 minutes (players slower than ~1.2 MB/s fail). Quick Start sets `sv_resourceFileDownloadTimeout 600000` (10 min). Legacy has no limit.
- Media packs: `whip_media_clothing_male`, `whip_media_clothing_female` (clothing pictures), `whip_media_props` (`img/props/<model>.webp`), `whip_media_previews` (vehicles `img/vehicles/<model>.webp`, NPCs, tattoos, emotes), `whip_media_map` (map, blip icons, minimap tiles). Start in any order; whip_core reads which exist at its start; restart a pack to push new pictures. A full category continues in a new pack (`whip_media_props_2`); after adding/moving/renaming packs run `node whip_core/dev/assets_index.mjs`.

### Legacy and Enhanced
- Legacy = `FXServer`, Enhanced = `cfx-server`. One WHIP runs on both. A script cannot reliably tell which, so an Enhanced server declares `setr whip_platform enhanced` (must be `setr`: a plain `set` never reached the game on Enhanced). Anything other than `legacy`/`enhanced` reads as legacy with a console warning (`shared/platform.lua:28-31`). The server also calls `SetConvarReplicated('whip_platform', ...)`.
- `GetPlatform()` (both sides) → `'legacy'|'enhanced'`. Internally `GamePlatform.name/.enhanced/.legacy`.
- `/whipplatform` (F8, developer mode) prints what the game read at start and now.
- Model packs come as `<name>` (Legacy) and `<name>_enhanced` (Enhanced); the setup report flags the wrong one.

## Convars and server.cfg lines

| Convar | Default | Effect |
|---|---|---|
| `mysql_connection_string` | — | Required by oxmysql; missing → whip_core halts with the line to add |
| `onesync` / `onesync_enabled` | off | WHIP requires OneSync (setup report FIX) |
| `sv_enforceGameBuild` | — | Legacy: missing → FIX suggesting `3889`; below `3407` → FIX (`setup_report.lua:16-18`) |
| `sv_resourceFileDownloadTimeout` | ~120000 on Enhanced | Raise to `600000` on Enhanced |
| `whip_platform` (setr) | `legacy` | `enhanced` on an Enhanced server |
| `whip_update_check` | `true` | `set whip_update_check false` turns GitHub checks off |
| `whip_inventory_renderer` (setr) | `''` | Resource whose `renderer.js` replaces the inventory drawing layer; wins over `Config.InventoryRenderer` |
| `whip_test_seams` | `false` | `set whip_test_seams true` enables `Config.EnableTestSeams` (whip_test fakes DB failures). Never on live |
| `whip_profiling` (setr, int) | `0` | `setr whip_profiling 1` then restart whip_core: wraps client event/statebag/NUI handlers in profiler scopes (`client/profiling.lua:12`) |

Dev tools from server.cfg: `add_ace identifier.license:xxxx whip.devtools allow`. For panel-granted temporary dev tools (`group.whip_devtools`), server.cfg needs (`server/devtools.lua:994-997`):
```
add_ace group.whip_devtools whip.devtools allow
add_ace resource.whip_core command.add_principal allow
add_ace resource.whip_core command.remove_principal allow
```

## Update checks (GetUpdate, GetUpdates)

- A resource takes part with `whip_updates 'owner/repo'` next to `version` in its fxmanifest (a full `https://github.com/owner/repo(.git)` URL is accepted and trimmed). The latest release's tag is compared with `version` (leading `v` ignored; numeric parts compared, `1.0` = `1.0.0`).
- It reads GitHub **releases**, not tags: a repo with tags but no published release answers 404 and shows "no public release (the repository is private, misspelt, or has none)". Every number counts, so `4.2.6.1` is newer than `4.2.6` (a fork can version above its upstream that way).
- Schedule (`server/updates.lua`): first round 30 s after `whip_core:onReady` with reason `coreStarted`, then hourly; each repository is asked at most once every 12 h (answer kept in server KVP `whip_core:update:<repo>` across restarts). Requests one at a time, 1.5 s apart, with ETag (`If-None-Match`); User-Agent `whip_core-update-check`. Hitting GitHub's 60/h unauthenticated limit pauses all checks until reset.
- Sent: one request per repo to `api.github.com/repos/<repo>/releases/latest`; GitHub sees server IP and repo names only.
- A newer release shows in the console, the setup report (`note Update available: ...`), `whipupdates`, and as a toast to an admin turning developer mode on (once per session).

### GetUpdate(resource?) — SERVER
- `resource` string|nil: default the calling resource (`GetInvokingResource()`).
- Returns `WhipUpdateStatus|nil` (nil when the resource names no repository). Never contacts GitHub; free to call.

### GetUpdates() — SERVER
- Returns `WhipUpdateStatus[]` for every running resource that names a repository.

`WhipUpdateStatus`: `{ resource, repository ('owner/repo'), current (its version)|nil, latest (tag)|nil, url|nil, newer: boolean, checkedAt (os.time)|nil, problem|nil }` (`problem`: private repo, no release, GitHub limit...).
```lua
local u = exports.whip_core:GetUpdate()
if u and u.newer then print(('mycafe %s is out: %s'):format(u.latest, u.url)) end
```

## The setup report (whipsetup) and every check

Printed once per start, 5 s after the last resource start since whip_core became ready (at most 60 s after ready). Lines are `ok`, `FIX` or `note`; footer "Nothing to fix / N to fix, M notes". With zero FIX lines it then prints the "Framework loaded successfully!" banner. `whipsetup` (server console only) prints it again; before ready it says whip_core has not finished starting. A halted start prints its halt instead.

Checks, in order (`server/setup_report.lua:84-283`):
1. OneSync on (`onesync` != off or `onesync_enabled` true) → ok; else FIX (txAdmin Settings → FXServer → OneSync On, or `set onesync on`).
2. Platform: server version string looks Legacy (`v1.0.0.NNNN`) or Enhanced (` bNNN`) but `whip_platform` says the other → FIX `setr whip_platform <x>`.
3. Enhanced → ok. Legacy: no `sv_enforceGameBuild` → FIX (suggests 3889); `< 3407` → FIX; else ok with the build.
4. Database: version too old → FIX "Update the database server"; else ok `Database <ver>, oxmysql <ver> (with whip's patch)`. Unpatched oxmysql → note with the WHIPFX release link.
5. Media packs: missing from resources → FIX; present but not started → FIX (`ensure <name>` or `ensure [assets]`); all fine → ok listing them.
6. Satellites: ok `whip_core <ver> with N satellites: ...` (resources that depend on whip_core, with versions); property packs (resources with `whip_property_pack` metadata) ok; satellites in the folder but not started → note.
7. Update lines (from `Updates.reportLines`): note per newer release; ok "Up to date: N resources checked on GitHub".
8. `whip_requires` in any fxmanifest above the running whip_core version → FIX "update whip_core".
9. Wrong-platform builds: `<name>_enhanced` running on Legacy, or `<name>` running on Enhanced when `<name>_enhanced` exists → FIX.
10. Second loading screen beside `whip_loadingscreen` (any running resource with `loadscreen` metadata) → FIX.
11. Custom inventory UI (`whip_inventory_renderer` convar else `Config.InventoryRenderer`): not running → FIX; no `renderer.js` → FIX; else ok.
12. Voice: whip_voice registered → ok, plus FIX for each other voice running (`pma-voice`, `saltychat`, `tokovoip_script`, `mumble-voip`, `yaca-voice`); only other voice → note (phone calls and radio need whip_voice); none → note.
13. `chat` running beside `whip_chat` → FIX.
14. `spawnmanager` or `basic-gamemode` running → FIX.
15. Other frameworks running (`es_extended`, `qb-core`, `qbx_core`, `ox_core`, `vrp`, `ND_Core`) → FIX.
16. Other inventories (`ox_inventory`, `qb-inventory`, `ps-inventory`, `qs-inventory`, `lj-inventory`) → FIX (register their items with `RegisterItem`).
17. Other targets (`ox_target`, `qb-target`, `qtarget`) → FIX (move to `AddAction`).
18. `Config.EnableTestSeams` true → note.
19. Registry refusals so far (another resource's registration refused) → FIX "Refused for <owner>: <why>", first 8, then "... and N more".

## Errors: whiperrors, whipsupport, GetErrorLog

- `shared/error_tap.lua` keeps the last 200 errors per side (text up to 2000 chars). Kept: errors in whip_core's threads, timeouts, event handlers, NUI callbacks, commands and statebag handlers; SecureEvent/SecureCallback handler errors (filed under the owning resource); whip_core's own caught errors (`[whip_core...] ... ERROR / threw / errored` lines); red `^1` warnings; client page errors (`html/js/error-tap.js`, and satellite pages that load `js/page-tools.js`); satellites' errors via `lib/satellite.lua`. NOT kept: an export's error (its caller gets it). Repeats of the same text within the last few are counted, not duplicated.
- `whiperrors [resource]` — server console only: errors grouped by resource, most first, last 5 lines each with `(xN)` counts. F8 `/whiperrors [resource]` (developer mode) does the same for the client.
- `whipsupport` — server console only: one block to paste for a seller: server version, the setup report, and recent errors by resource (3 lines each), between "copy from here" / "to here" markers.

### GetErrorLog(opts?) — SERVER and CLIENT
- `opts.since` number: only entries with `seq` after an earlier answer's `last`. `opts.max` number (≤200, default 200).
- Returns `{ entries = { { seq, at, side, resource, kind, text, count }, ... }, last, side }`. `kind`: `'error'|'warning'` (server), plus `'page'` (client).

## ACEs, permissions and developer mode

- The one ACE: `whip.devtools`. Used by `/w`, `/whip`, every dev command, admin-only doors/zones, SecureEvent/SecureCallback `ace = 'whip.devtools'`.
- `whip.devtools` alone is not enough: the account must also turn **developer mode** on in `/w`. Until then it is treated as an ordinary player everywhere (`/whip`, dev commands, admin doors and zones, every `HasDevTools` check). `DevTools.aceRefusal` returns `'Developer mode is off: turn it on in /w'` (toast at most every 3 s).
- Developer mode facts (`server/devtools_base.lua`):
  - Off at every join and for everyone after a whip_core restart; a character swap keeps it.
  - On: HUD shows the amber developer mark ("Developer Access Enabled"; hide with `Config.HudDeveloperMark = false`). Each switch printed in the console and logged as `dev_mode_on` / `dev_mode_off` with position and account name.
  - Off (switch, right lost, drop): God Mode, Invisible, Noclip, overlays, open editors and `/whip` all close; the player leaves every tool's live-data audience.
  - If the ACE is lost while on (console, txAdmin), the next live push turns developer mode off and the client gets `whip_core:client:devtoolsRevoked`.
- A player without the ACE who types `/w` or `/whip` gets a console line, once per visit: `add_ace identifier.license:<hex> whip.devtools allow` (copy it, works at once).
- Temporary dev tools ("until the restart"): a permanent admin gives them from the Player Manager; the license is added to principal `group.whip_devtools` (`add_principal`), removed on whip_core stop or by the panel. Temporary admins cannot edit Config settings, cannot grant permissions, cannot kick someone who has dev tools. Permanent admin = `whip.devtools` from server.cfg.
- In-game permissions (`RegisterPermission`/`HasPermission`, table `whip_permissions`, per account): e.g. `director.build`, `director.admin`, `systems.build`. Anyone with `whip.devtools` holds every permission unless the permission says `devtools = false`. A player with a permission that opens a `/whip` section (Director access) gets `/whip` with only that section; `/director` opens the Director for a `director.build` holder.
- Server code: always `exports.whip_core:HasDevTools(source)`, never `IsPlayerAceAllowed(src, 'whip.devtools')` (that ignores developer mode).

## Console commands

Server console (source 0). Unless noted, also usable in game by a player with `whip.devtools` + developer mode (the `devCommand` wrapper, `server/commands.lua:19`; refused players get "That command needs whip.devtools"). `GetCommandAce(name)` returns `'whip.devtools'` for these.

| Command | Where | What |
|---|---|---|
| `whipsetup` | console only | Setup report again |
| `whipsupport` | console only | Version + setup report + errors, for a seller |
| `whiperrors [resource]` | console only (client twin in F8) | Recent server errors by resource |
| `whipupdates` / `whipupdates check` | console only | Every resource with `whip_updates` and its status / ask GitHub now |
| `whipcost [seconds]` | console, or dev player (output to console) | Server half of WhipCost (20 s; 5–120) |
| `whip_players` | console/dev | List active players |
| `whip_pending` | console/dev | Connected players with no character selected |
| `whip_save` | console/dev | Force-save all players |
| `whip_bank <playerId>` | console/dev | A player's bank accounts |
| `whip_giveitem [charId] <item> [amount]` | console/dev | Give an item; no charId = yourself |
| `whip_removeitem <charId> <item> [amount]` | console/dev | Remove an item |
| `whip_inventory <charId>` | console/dev | Show a player's inventory |
| `whip_deposit <playerId> <amount>` | console/dev | Deposit into default account |
| `whipsaves` / `whipsaves drop <unit>` | console/dev | List stuck saves / discard one forever |
| `whip_clearground [radius]` | console/dev | Clear ground items near you (or within radius from console) |
| `whip_clearallground` | console/dev | Clear ALL ground items |
| `whip_spawnground <item> [amount]` | console/dev | Spawn a ground item at your feet |
| `whip_givekey <charId> <vehicleId>` | console/dev | Give a vehicle key |
| `whip_groundcount` | console/dev | Count ground items |
| `whip_revive <charId>` | console/dev | Revive a character |
| `whip_reviveme` | dev | Revive yourself |
| `whip_statebag <serverId>` | console/dev | Print a player's state bag values: `bag` (replicated) vs `truth` (Sentinel ledger) |
| `director ...` | `/director` alone: `director.build`; subcommands: whip.devtools | Director |
| `systems ...` | `systems.build`, only with `Config.Experimental.systemsCreator` | Systems Creator |

## Chat / F8 commands

Developer-mode client commands (`DevCommand`, `client/dev_commands.lua`; refused with "/<name> is a developer tool: turn developer mode on in /w"):

| Command | What |
|---|---|
| `/whipcost [seconds]` | Times WHIP and every resource's WhipCost sections (20 s; 5–120); prints to F8 |
| `/nativecost` | Prices each call the controls loop makes |
| `/paddebug` | Controller chain live: controls down, buttons, what WHIP claimed |
| `/mousedebug` | Measures the player's mouse speed (skill check dot) |
| `/nuicaps` | Prints the browser's capabilities (`GetNuiCaps`) |
| `/whipplatform` | Platform read at start and now (own check, not DevCommand) |
| `/whiperrors [resource]` | This game's error log in F8 |
| `/charedit` | Opens the character editor on yourself |
| `/resetcomposer` | Resets the composer |
| `/whip_inventory_ui [resource\|none]` | Draw this player's inventory with that resource's `renderer.js` until rejoin; `none` = WHIP's; alone = reload current |
| `/copyoutfit [show]` | Copy outfit for Menyoo (checks dev mode itself) |

Other dev tools (open commands; the server re-checks): `/vehpoints` (prompt points on the bike/boat/aircraft you look at), `/radardebug` (minimap tuner), `/radar [part|print]` (radar rects), `/propcheck` (`restart`) (spawn every catalog prop, list failures; run again to stop, resumes next time), `/propprobe` (interior natives at your spot), `/npcdebug` (NPC state over heads), `/prop add <category>` / `/prop remove` (furnisher catalog; server SecureEvents with `ace = 'whip.devtools'`), `/whip_theme [resource|none]` (re-apply theme; server-gated), `/w`, `/whip`, `/director`, `/systems`.

Player commands: `/logout` (to character select, skips the landing screen), `/e <emote>`, `/walk <name>`, `/mood <name>`, `/emotes`, `/me <text>`, `/seats`, `/vehiclehud [on|off]` (hides the dial for that player until reconnect), `/furnish`, `/inventory`; key-binding commands include `+whip_interact`, `+whip_togglelock`, `+whip_ignition_on/off/toggle`, `+tabhotbar`, `whip_radial`, `whip_emote_cancel`, `whip_cyclevoice`, `whip_coords_copy`, `escort_grab`, `escort_release`. Key binding "Whip: Open Admin Panel" is unbound by default (Settings → Key Bindings → FiveM).

### Staff commands added in 1.3.0
- `/tp <x y [z] [heading]>` or `/tp <server id>`, `/tpto <server id>`: to a place or a player, behind a fade, waiting for the ground; a car you drive comes along. Refused for a player in another routing bucket. The Player Manager's Teleport To goes the same way. Each is on the admin's activity log.
- `/tpm`: to your map waypoint, onto the ground there; also Teleport to Waypoint in /w.
- `/vector2`, `/vector3`, `/vector4`, `/heading` (and `/vec`): copy where you stand.
- whip_core's admin commands are sent to staff (holders of `whip.devtools`) as chat suggestions when their character loads. A dev command refused because developer mode is off says so.
- Pending, not in 1.3.0: `/whip_heal <charId>`, `/whip_kill <charId>` and Revive / Heal / Kill in the Player Manager (whip_core PR #76).

## /w quick menu

Arrow keys move, Enter toggles, Esc closes; a tool stays on until switched off (row lit) or acts once. All debug tools draw into one shared pane.

| Entry | Does |
|---|---|
| Developer mode | The switch; while off it is the only row |
| Noclip | Fly, invisible, invincible: WASD, Space/Ctrl, Shift faster. In a vehicle, the vehicle comes along (1.1.0+) |
| Invisible | Nobody sees you; you see yourself at half opacity |
| God Mode | No damage, health kept full |
| Restore Player Cores | Once: revive if down (as `/whip_revive`), then fill health, armour, hunger and thirst (1.1.0; was Restore Health & Armour) |
| Reveal Players | Every player as named blip; within 250 m a tag: character name, charId, account name |
| Kill Me | Once: an ordinary death (Noclip and God Mode off first) |
| Repair Vehicle | Once: repairs the car you are in |
| Coords | X/Y/Z/heading; G copies a `vector4()` |
| Object Viewer | Tags props, peds, vehicles within 20 m; the one you look at opens a card (picture, hash, position, heading, source); G (D-pad left) opens its options |
| Debug | Shows debug tools: Player Stats Debug, Vehicle Stats Debug, Ground Items Debug, plus resources' `RegisterDebugTool` switches |
| Player Stats Debug | Your stats live (ped's reading beside each vital, amber when they disagree), rates, effects, changes; card over players within 40 m |
| Vehicle Stats Debug | Your car's stats, rates, change sources, data; card over WHIP cars within 40 m |
| Ground Items Debug | Piles in your cell and the 8 around: counts, droppers, ages, beam and map mark, grid on the ground |
| Admin Panel | Opens `/whip` |
| Dungeon Mode | World builder on the live world |
| A resource's page | One row per `RegisterDevPage`; Backspace goes back |
| Experimental | Rows for features enabled in Config → Experimental features (Camera Creator, Systems Creator, Combined Settings) |

## Object Viewer options (built-in)

Look at something with Object Viewer on, press G (D-pad left): searchable, grouped list down the right; Esc/B back. White outline = what G would open; blue = the open one.

| Target | Options |
|---|---|
| Anything | Copy details (name, hash, `vector4`). A local-only object of another script has only this |
| Map prop | Make it a Dungeon prop, Change model, Remove for everyone (until restart), or Put back in Dungeon Mode |
| Networked object | Move, Turn invisible, Freeze in place, Swap for a Dungeon prop, Remove |
| Dungeon prop | Move, Change model, Solid, Put the map's one back, Remove; in Dungeon Mode also Duplicate and Fixed Weapon's Fire |
| Ground item | Move, Change item (gun gets new serial), Set how many, Remove. Full admins only; logged on the item log |
| Any prop / ground item | Effects: Smoke, Sparks, Flames (harmless), Steam, Glow (80 server-wide max); Explode (real) |
| Dungeon car | Key settings: where its key is, Locked, Only its key opens it |
| WHIP car (saved) | Return to garage, Change owner, Open in WHIP Admin Menu, Delete from whip database, Fix, Set stat, Explode, Become driver/passenger, Eject all players, Turn invisible, Set invincibility, Freeze, Move, Inspect trunk/glovebox, plus resource options (whip_autos: Open Whiplash) |
| Other car | Remove, Fix, Explode, Make vehicle permanently owned by player (paint, parts, free plate kept), Move |
| Player | Restore health/armour, Revive, Kill, Set on fire, Freeze, Disable combat abilities (both end on leave/char swap), Force escort, Move, Change model, Force open character editor, Force change movement style, Force emote, Adjust stats, Inspect inventory, Open in WHIP Admin Menu, Kick, Ban (1 h–30 days or permanent) |
| Player: Make for them | Spawn a car for them (temporary, key in pocket), Send NPCs after them (1–6 armed, from 25–40 m); until restart/removal |
| NPC | Remove, Kill, Set on fire (fire out after 8 s), Move. WHIP's own NPCs (shopkeepers, Director, lore) have none |
| Dungeon NPC | Attack a player, Follow a player, Calm down, Give a weapon; switches On guard, Invincible, Stay put |

Who: full admins, and Dungeon Masters from Dungeon Mode (not options that outlast a restart, marked Admins only). A Dungeon thing's options are its maker's or any full admin's. Every use is logged on the user's timeline and the target player's. Move uses the furnisher's arrows/rings (R rings, Shift snaps; pad: LS moves, LT/RT down/up, D-pad turns); a player is moved by the server ~10×/s.

## /whip Admin Panel sections and Monitor

Open with `/whip`, the `/w` row, or key "Whip: Open Admin Panel". Esc closes a dialog, then backs out, then closes. Pad: LB/RB step tabs; cursor to top edge fades the panel. Groups: Players, Vehicles, Economy, World, Director, System, Settings.

| Section | Group | Does |
|---|---|---|
| Player Manager | Players | Everyone who joined: characters, stats, vehicles, jobs, bans, notes, timeline; give temporary dev tools |
| Phones | Players | Every number: owner, SIM, contents; change, give SIM, delete, give a number; read-only phone records both ways (block-held texts/calls shown, marked) |
| Vehicles | Vehicles | By plate, model, owner, id. Storage, garage, teleport, owner, keys, eject, lock, stats, freeze, repair, explode, tyres, doors, delete. "Set up a new vehicle" |
| Vehicle Adjustments | Vehicles | Trunk/glovebox size per category or model, or none. Priority: car's own > model > category > config.lua |
| Garages | Vehicles | Create, edit, delete, teleport; move cars between garages |
| Items | Economy | Every item: settings, pictures, give yourself some (config.lua items are edited here) |
| Shops | Economy | Shops, catalogs, prices; link a stocked shop to its container |
| Containers | Economy | Create, edit, delete, open |
| Jobs | Economy | Jobs, roles, hiring, permissions |
| Banks | Economy | Every holder, balance, worth, log |
| Item Log | Economy | Activity log: Everything and Economy tabs |
| Zones | World | Persistent zones, rules, whitelists; in-world Zone Editor |
| Doors | World | Saved doors in folders; in-world Door Editor |
| Ground Items | World | Every world item: search, teleport, blips, delete |
| Properties | World | Every home, problems, fixes; known interiors |
| Time & Weather | World | Time, presets, weather, freeze, blackout, time scale |
| Director | Director | Scenarios, packs, live runs, builders |
| Lore characters | Director | Named people: look, bank name, picture, voice lines |
| Monitor | System | Every SecureEvent and SecureCallback call live, refusals, Sentinel catches. Recorded while closed |
| UI Library | System | Runs every UI component live |
| Config | Settings | whip_core's settings. Permanent admins only |
| A resource's page | Settings | `Whip.configPage` pages, named by `label` |

- Sections with live data push others' edits while you look. Editors that need the game screen suspend the panel and restore it; anything that opens the inventory closes it.
- Monitor internals (`server/secure.lua`): two rings of 500 entries each (accepted, refused), merged by sequence into a ≤1000-entry snapshot on open; per-event registry with calls, rejects, lastCall, effective rate limit. Its own open/close/clear events are raw net events gated with `DevTools.isAllowed` (so viewers do not appear in the feed). With `Config.LogSecureRejections = true` refused SecureEvents and dropped callbacks also print to console (repeats counted per 5 s).
- Dev-tool live data is pushed only to viewers who still hold the ACE (`DevTools.eachViewer`); a demoted admin is dropped.

## Building in game (where each tool lives)

| To | Open |
|---|---|
| Add / change a garage | Vehicles → Garages → + New Garage / a garage → Change |
| Bays | A garage → Change on Bays (a property's: Properties → its Garage) |
| Set up a home | World → Properties → New property, standing inside |
| Building of homes | Register here, or Stamp mode floor to floor |
| Check homes vs interiors | Verify now, Verify…, Quick check |
| Which home am I in | World → Properties → What property am I in? |
| Furnish / storage | A home → Furniture → Manage furniture; Storage → Inspect storage |
| Draw a zone | World → Zones → Open the editor (1/2/3 box, sphere, outline; H scans a room) |
| Lock a door | World → Doors → Open the editor (G saves; E on two doors links a double) |
| Shop | Economy → Shops |
| Stash | Economy → Containers; Use My Position |
| Time and weather | World → Time & Weather |
| Mission / scene | `/whip` → Director, or `/director` |

A map/MLO resource can ship its own doors (`EnsureDoors`) and homes (a `whip_properties.lua` pack) so other servers get them without admin steps.

## Configuration: how config.lua, the Config page and settings.json work

- `whip_core/config.lua` holds defaults, read by server and client. After editing, `ensure whip_core`.
- A syntax slip in config.lua: `shared/config_guard.lua` re-runs the file in a sandbox, prints one framed message naming the line ("whip_core cannot start: config.lua has a mistake"), repeats it 1 s after start, and refuses every `playerConnecting` ("The server could not start: its config.lua has a mistake...").
- Retired keys still present in an old config.lua are named once in yellow with their replacement: `FuelStations`, `FuelPumpProps`, `FuelStationBlipColor`, `FuelStationBlipSprite`, `RefuelLeashRange`, `RefuelPumpRange`, `RefuelVehicleRange`, `VehicleFuelDrainRate`, `VehicleFuelRefillRate`, `VehicleFuelReportInterval`, `VehicleRefuelCostPerUnit` (moved to whip_fuel), `GarageEditorReach` (now `GarageWizardReach`), `HousingEntryPlaceRange`, `HousingInsideRange`, `HousingKeyGrantRange` (now `PropertyKeyGrantRange`), `HousingMaxObjects`, `HousingStreamRange`, `PropSnapImageW/H`, `MenuPedEnabled/Lighting/Offset/Timecycle`, `AccessorySlots`, `PlayerContainers` (now code in `shared/inventory_shape.lua`), `IgnitionKeyItems`, `VehicleModSlots`, `DefaultAccountType`, `DefaultStatuses`.
- In-game Config: `/whip` → Settings → Config, **permanent admins only** (`whip.devtools` from server.cfg with developer mode on; temporary dev tools refused: "Only a permanent admin can change settings"). Pick a group, change values, Apply.
  - Checked as you type; the server re-checks. Apply is all-or-nothing (one refused value saves nothing; the bar names it). Max 200 changes per Apply. Refused while whip_core is still starting.
  - `cross` checks run on the server against the values as they will be after the save.
  - Each row: its config.lua default, Reset, who changed it last. Positions/camera shots: Use where I stand, Place camera (free camera; Enter keeps, Esc cancels), Use my camera. Hero shots: Edit in world.
  - Fixed rows (`Garages`, `Shops`) only seed the database; a button goes to their real editor. Items are edited on Economy → Items.
- Storage: DB table `whip_settings` (`owner` VARCHAR(64), `path` VARCHAR(128), `value` MEDIUMTEXT, `changedBy`, `changedAt`; PK owner+path) and history `whip_settings_log` (`oldValue`, `newValue`, `changedBy`, `at`). Mirrored into `settings.json` (downloaded by players; `sides='both'` values) and `server_settings.json` (server only, never downloaded). Both rewritten from the DB at every start: never edit them. A value equal to the default deletes the row.
- A saved value wins over config.lua until Reset. `apply = 'live'` → in force at once everywhere (server applies and sends `whip_core:client:settingsChanged`); `apply = 'restart'` → saved, in force at whip_core's next start; `'readonly'` → shown only.
- Clients ask for values newer than their `settings.json` with `whip_core:server:settingsHello` at start and again on `whip_core:client:coreReady` (server answers only when ready).
- Another resource cannot read whip_core's `Config`; use the export for the value (e.g. `GetPockets()`).
- whip_core internals hook changes with `Settings.onChange('Path', fn)`.

## Config page (/whip → Settings → Config): every editable entry

Groups (tabs) and entries from `shared/config_schema.lua`. `S` = `sides='server'` (never sent to players). `R` = `apply='restart'`. Anything not listed is config.lua only.

**Characters, money & jobs** (`characters`): `MaxCharacters` int 1–30 · `DefaultCash` int 0–800000 S (cross: must fit one cash stack and pocket weight) · `StartingBalance` int 0–1000000000 S · `MaxExtraAccounts` int 0–100 S · `BlockOwnCharacterTransfers` bool S · `DefaultSpawn` vec4 (world limits x −4000..8000, y −7000..8000, z −200..2000, w 0..360; Use where I stand) · `ShowPlayerNames` enum nearby/always/never S · `PlayerNameRange` number 2–200 m S (shown when nearby) · `JobDefaultRoles` records 1–20, unique `name`, S · `JobDutyOneAtATime` bool S · `JobOneCharacterPerAccount` bool S.

**Joining** (`joining`): `Landing.enabled` bool · `Landing.prompt` string ≤80 nullable · `CharSelect.slots` hero shots (≤30, ≤60 props each; shot 1 required) · `CharSelect.quietBucket` bool · `CharSelect.spawnPicker` bool · `SpawnPoints` records 0–30, unique `id`, S · `ArrivalScenes.enabled` bool · `ArrivalScenes.vehicleRange` 0–2000 m · `ArrivalScenes.nearCarRange` 0–200 m · the four `ArrivalScenes.onFoot/inVehicle/onBike/nearCar` lists (records 0–60: `dict`, `clip`, `cam`, `vehicleClip`, `from` 0–0.95, `to` 0.05–1, `getsIn`, `indoors`; `to` must exceed `from`) · `Creator.spawn` vec4. Weathers used by hero shots must be on `WeatherTypes`.

**Hunger, thirst and breath** (`survival`): `StatOrder` list ≤40 S · `Hunger` bool S · `HungerMinutes` int 1–1440 S · `Thirst` bool S · `ThirstMinutes` int 1–1440 S · `NeedDamage` int 0–50 S · `OxygenSeconds` 1–45 S · `RespawnTime` int 0–600 s · `DeathScreen` bool.

**Inventory** (`inventory`): `EnableInventoryUI` bool · `ContainerSlots.player` int 1–200 R · `MaxWeight.player` 1–1000 kg (cross with cash) · `WeightUnit` enum kg/lb · `AccessoryStrip` bool R · `DropOnFullInventory` bool S · `GroundItemPickupRange` 1.5–10 m · `PlaceItemRange` 1–20 m · `MaxGroundPilesPerDrop` int 1–200 S.

**Items**: `editedIn = 'items'` (Economy → Items).

**Vehicles** (`vehicles`): `DrivingCamera.Enabled` · `DrivingCamera.Default` · `DrivingCamera.Shake` 0–3 · `DrivingCamera.Style` enum consistent/cinematic · `BikeAutoHelmet` · `Seats.NoAutoShuffle` · `VehiclePartPrompts` card (`door/trunk/hood/bike/bicycle/boat.enabled`) · `VehicleTrunkSlots` 1–500 S · `VehicleTrunkMaxWeight` 1–5000 kg S · `VehicleGloveboxSlots` 1–500 S · `MotorbikeGloveboxSlots` 1–500 S · `VehicleGloveboxMaxWeight` 1–1000 kg S · `NpcVehicleLockRange` 0–50 m · `UnlockOnExit` S · `LockpickGame` string ≤64 S · `VehicleDamage.remember` S · `VehicleHud.speedUnit` enum · `VehicleHud.dashSkins` · `GaragePositionHelper.enabled` · `GaragePositionHelper.showRange` 5–100 m · `ExperimentalDriveSync` S.

**Properties** (`properties`): `PropertyMaxObjects` int 1–1000 S R · `PropertyStashProps` map (key = model) · `PropertyStashLimit` int 0–50 S.

**World & gameplay** (`world`): `TimeScale` 0–10 S · `WeatherTypes` list 1–30 (cross) · `WeaponGuard.Enabled` · `WeaponGuard.Allow` list 0–50 · `ThrowKnockdown.Enabled` · `ThrowKnockdown.Npcs` · `ActionMode.Disable` · `IdleCam.Disable` · `InteractPress.enabled` · `ShopTalk.enabled` S · `ShopInteractRange` 1–15 m.

**Emotes, /me and talk** (`emotes`): `Emotes.placeRange` 1–15 m · `Bubbles.range` 5–100 m · `Bubbles.duration` 500–30000 ms · `Bubbles.maxLength` 10–240 · `Bubbles.maxStack` 1–3 R · `Conversations.range` 2–25 m · `Conversations.watcherBubbles` · `Conversations.npcLines` 1–4 · `LoreVoice.Enabled` S · `LoreVoice.Links` list ≤5 S.

**HUD, map & prompts** (`hud`): `HudSkin` enum black/classic · `AimDot` · `MinimapMask` enum `'square'`/`'rounded'`/`false` (game's own) · `MapOptions.onFoot`, `MapOptions.inVehicle` enum (player/on/off) · `Interact3D` card (`theme` keycap/classic, `dark`, `badgePx` 20–200, `labelPx` 20–200) · `InteractVisibleRange` 1–25 m · `InteractActiveRange` 0.5–10 m · `CameraHidesDui` · `Keyboard.Languages` list 1–20 R · `Keyboard.Default` string pattern `^%l%l%l?$`.

**Server** (`server`): `Theme` string ≤64 nullable (resource name) · `HudDeveloperMark` S · `ActivityLogDays` int 1–3650 S R ("Old entries are cleared once, as whip_core starts") · `PlayerManagerSessionWarn` S · `LorePictureLinks` list ≤5 S (each `https://host/...` ending in `/`) · `Sentinel.enabled` S · `Sentinel.autoKick` int 1–50 S, empty = off (`offWhenEmpty`) · `Sentinel.strikesForgetMinutes` 1–1440 S, empty = never.

**Experimental features** (`experimental`): `Experimental.cameraCreator`, `.systemsCreator`, `.combinedSettings` — each asks for confirmation ("An unfinished prototype") before turning on; Apply still required.

## config.lua: every key

Defaults are from `config.lua`. "Page" = editable on the Config page (above). Content tables (`Items`, `Shops`, `Garages`, `JobDefaultRoles`) are read at startup.

### 1. New characters
| Key | Default | Meaning |
|---|---|---|
| `MaxCharacters` | `4` | Characters per account, up to 30; each has a hero shot |
| `DefaultSpawn` | `vector4(-1023.03, -1660.96, 4.62, 44.92)` | New characters' spawn |
| `DefaultCash` | `500` | Cash in pockets (one stack) |
| `StartingBalance` | `1000` | Personal bank balance |
| `DefaultAccountLabel` | `'Personal Account'` | Name of the account made with a character |
| `MaxExtraAccounts` | `5` | Savings/shared accounts per character (personal and job accounts excluded; 0 = none) |
| `BlockOwnCharacterTransfers` | `true` | A player's characters cannot move bank money between each other (cash in world not tracked) |

### 2. Inventory
| Key | Default | Meaning |
|---|---|---|
| `ContainerSlots` | `{ player = 30, accessory = 5 }` | Slots per player container |
| `MaxWeight` | `{ player = 80.0, accessory = 10.0 }` | kg; player includes the strip |
| `WeightUnit` | `'kg'` | Display default (`'kg'`/`'lb'`) until player picks; data is always kg |
| `AccessoryStrip` | `true` | Phone slot 1, Money slot 2, Key slots 3–5 (key in strip goes into ignition automatically). `false`: strip contents move to inventory at next login. Restart |
| `DropOnFullInventory` | `true` | `AddItem` overflow drops at feet; `false`: refused, nothing created. Never destroys |
| `MaxGroundPilesPerDrop` | `50` | Cap on piles per drop |
| `EnableInventoryUI` | `true` | `false`: no WHIP inventory screen; system still runs |

### 3. Items
`Items` table (key → def). Fields: `name`, `desc`, `weight` (kg each), `type` (tooltip category), `stack`, `maxStack`, `usable`, `cooldown` (s), `prop`; optional `metaFields` (`{ key, label, format?, value? }`), `defaultAction`, `contextOptions` (`{ action, label, order, when, require, anywhere, whyNot, icon }`), `image`, `images` (`{ when = {...}, image }`, `{ amount = { below|atLeast = n }, image }`, `{field}`/`{make}` substitution). `when` tests per metadata field: equal, list (one of), `{ above|below|atLeast|atMost }`, `slots = { empty = false }`, `default` for missing. Shipped items: `food`, `drink`, `bandage`, `package`, `id_card`, `cash` (weight 0.0001, maxStack 999999, amount-based images), `vehicle_key`, `lockpick`, `camera`, `hacked_vehicle_key`, `duffle_bag` (25 slots, action `open_duffle`), `wallet` (action `open_wallet`), `armour`, `damage_reducer`. (`jerry_can` is whip_gunny's.)

### 4. Player stats and HUD
| Key | Default | Meaning |
|---|---|---|
| `MinimapMask` | `'rounded'` | `'square'`, `'rounded'`, `'circle'` (comment), or `false` (game's own) |
| `HudSkin` | `'black'` | `'black'` or `'classic'` (not the vehicle dial) |
| `AimDot` | `true` | Dot replaces reticle (not melee/petrol can), red against a wall |
| `HudDeveloperMark` | `true` | Amber developer mark among gauges |
| `CameraHidesDui` | `false` | Camera item also hides WHIP world DUI |
| `MapOptions` | `onFoot='player'`, `inVehicle='player'`, `forceMinimap=false`, `minimap={ fps=60, border=true, northUp=false, centre=false, markerSize=100, markersUpright=true, viewFoot=230, viewSlow=290, viewFast=800, speedFrom=0, speedTo=100, tiltFoot=0, tiltVehicle=38, tiltWithSpeed=false, tiltFast=50 }` | `'player'|'on'|'off'`; `forceMinimap` locks everyone to `minimap` (fps 120/60/45/30/15, border true/'outline'/false) |
| `WeaponGuard` | `{ Enabled = true, Allow = { 'GADGET_PARACHUTE' }, SweepMs = 5000 }` | Strips GTA's native guns (see `PermitNativeWeapon`) |
| `ActionMode` | `{ Disable = true }` | No combat stance |
| `IdleCam` | `{ Disable = true, ResetMs = 10000 }` | No idle cam; driver idle timer reset |
| `DrivingCamera` | `{ Enabled = true, Default = false, Shake = 1.0, Style = 'consistent' }` | Chase cam in Server Settings → Vehicles; Style `'consistent'|'cinematic'` |
| `Controller` | `RadialHoldMs=500, SprintDoubleClickMs=300, SprintOnA=false, VehicleControls=true, VehicleControlsMs=5000, Layout={ dpad_up='phone', dpad_down='radial', dpad_left='engine', dpad_right='inventory', l3='sprint', veh_a='nitrous', foot_b='gunny_reload', lb_a='talk', lb_b='gunny_check_ammo', lb_x='radio', lb_y=false, lb_dpad_up/down/left/right=false }` | Pad layout; each a WHIP action (`radial`, `engine`, `inventory`, `sprint`), a registered action, or `false`. Named action keeps its button while its resource runs |
| `Keyboard` | `{ Languages = { 'en' }, Default = 'en' }` | On-screen keyboard packs in `html/keyboard/`; read at start |
| `Hunger` / `Thirst` | `true` / `true` | Drain, save, gauge, damage under 10% |
| `HungerMinutes` / `ThirstMinutes` | `120` / `90` | Full to empty (1–1440) |
| `NeedDamage` | `1` | Health lost every 10 s while a need ≤10 (health to 200); 0 = none |
| `RespawnTime` | `10` | Seconds before hold-E respawn (`HoldRespawn` extends) |
| `RespawnLocations` | Pillbox `vector4(360.83,-585.28,28.83,250.38)`, Central LS `vector4(341.54,-1395.75,32.51,51.94)`, Mount Zonah `vector4(-449.10,-333.17,34.50,51.93)` | One at random |
| `DeathScreen` | `true` | `false`: draw your own from client event `whip_core:death:screenChanged` |
| `StatOrder` | `{ 'health','armour','hunger','thirst','oxygen' }` | Gauge order; unlisted after |
| `StatHitFlash` | `{ health = 10, armour = 10 }` | % drop that brings gauges back; nil = never |
| `OxygenSeconds` | `20` | Breath under water (≤45) |
| `OxygenRecoverPerSecond` | `6` | Breath back per s (of 100) |
| `OxygenGraceSeconds` | `1` | Seconds at zero before drowning (0–10) |
| `Stats` | `{}` | Your own stats: `type` 'need'/'custom', `default`, `min`, `max`, `persist`, `decay`, `thresholds` (`{ value, below, stat, delta }`), `hud` (`icon` SVG path, `color`) |

### 5. Jobs
| Key | Default | Meaning |
|---|---|---|
| `JobDefaultRoles` | Owner (100; canHire/Fire/Promote/Demote/Manage, bankAccess 'manager'), Manager (50; hire/fire/promote/demote, 'withdraw'), Employee (1; 'view') | Ranks every new job starts with |
| `JobDutyOneAtATime` | `false` | `true`: clocking on clocks off every other job |
| `JobOneCharacterPerAccount` | `true` | One character per account per job |

### 6. Time and weather
`TimeScale` `1.0` (48 real minutes/day) · `StartTime` `{ hour = 12, minute = 0 }` and `StartWeather` `'CLEAR'` (only for a DB that never saved a clock) · `WeatherTypes` `{ 'CLEAR','EXTRASUNNY','CLOUDS','OVERCAST','RAIN','CLEARING','THUNDER','SMOG','FOGGY','XMAS','SNOWLIGHT','BLIZZARD','HALLOWEEN','NEUTRAL' }` · `TimeSyncInterval` `60000` ms.

### 7. Vehicles
| Key | Default | Meaning |
|---|---|---|
| `VehicleHud` | `speedUnit='mph', rpmMax=8, redline=0.87, rpmElectric=20, idleRpm=0.8, idleMeasured=false, rpmByClass={ compacts=7, sedans=7, suvs=6, coupes=7.5, muscle=6.5, sportsclassics=6.5, sports=8, super=9, motorcycles=12, offroad=6, industrial=4, utility=4, vans=5.5, service=4, emergency=6.5, military=4, commercial=4, openwheel=15 }, rpmByModel={}, attitude='ball', flipBank=false, dashSkins=true` | Rev dial; `rpmByModel` wins and follows engine swaps |
| `VehicleStats` | `engine = { default=0, min=0, max=1, persist=false, hud={ icon, color='#3fb950', order=90, iconOnly=true } }` | Stats every car carries; `engine` cannot be replaced. Add with `RegisterVehicleStat` |
| `VehicleStatsTickInterval` | `1` | s between decay checks (restart) |
| `VehicleStatsSaveInterval` | `15` | s between saves of changed stats |
| `VehiclePositionSaveInterval` / `VehiclePositionEpsilon` | `30` / `2.0` | s / metres |
| `VehicleDamage` | `{ remember = true, engineFloor = 100 }` | Keep damage, doors, tyres (not dents) |
| `AtmProps` | `prop_atm_01`, `prop_atm_02`, `prop_atm_03`, `prop_fleeca_atm` | ATM models (no location list) |
| `AtmSearchRange` | `30.0` | |
| `AtmVisibleRange` / `AtmActiveRange` | `3.0` / `1.4` | |
| `AtmBadgeOffset` | per model + `default = { side=-0.10, out=-0.22, up=1.20, yaw=180.0 }` | |
| `AtmMaxDigits` | `9` | |
| `LogVehicleStorage` | `false` | Log every boot/glovebox/ignition open both sides |
| `VehicleLockRange` | `8.0` | L lock range |
| `UnlockOnExit` | `true` | |
| `Seats` | `{ NoAutoShuffle = true }` | |
| `VehicleTrunkRange` | `2.5` | Server gate is this + 3.0 |
| `VehicleStorageKeepRange` | `5.5` | No effect below `VehicleTrunkRange + 3.0` |
| `BikeAutoHelmet` | `false` | |
| `ExperimentalDriveSync` | `false` | Director drives replayed on every client's copy |
| `VehiclePartPrompts` | `trunk`/`hood` `{ enabled=true, drop=0.30, clearance=-0.15, range=1.8, activeRange=1.1, scale=1.32 }`; `door` `{ enabled=true, drop=0.62, rise=0.18, clearance=0.0, inset=0.12, range=1.8, activeRange=1.1, scale=1.32 }`; `bike`/`bicycle` `{ enabled=true, range=1.8, activeRange=1.1, scale=1.32 }`; `boat` `{ enabled=true, range=3.0, activeRange=2.2, scale=1.32 }` | Part prompts |
| `VehiclePartPromptScan` | `15.0` | |
| `VehiclePartOpenAngle` | `70.0` | |
| `VehiclePartHingeTopFrac` | `0.52` | |
| `VehiclePartHinges` | `{}` | `[hash] = { trunk = 'up' }` (down/up/aft/fore/mirror) |
| `VehicleFillers` | `{}` | `[hash] = { side = 'left'|'right'|'rear' }` |
| `VehicleMakeLogos` | `{}` | `['emperor'] = 'emporer'` |
| `NpcVehicleLockRange` | `10.0` | NPC traffic locked within; 0 off |
| `VehicleTrunkSlots` / `VehicleTrunkMaxWeight` | `40` / `200.0` | |
| `VehicleGloveboxSlots` / `VehicleGloveboxMaxWeight` | `10` / `20.0` | |
| `MotorbikeGloveboxSlots` | `1` | Bicycles none |
| `VehicleKeySlots` / `VehicleKeyMaxWeight` | `1` / `1.0` | Ignition |

### 8. Garages
`GarageSpotRadius` `3.5` · `GarageSpotPromptHeight` `1.22` · `GaragePositionHelper` `{ enabled=true, showRange=30.0, onFootRange=10.0, length=5.20, width=2.60, zOffset=0.02, alignDeg=25.0, fadeMs=180, requireStorable=false, idleReleaseMs=60000 }` · `GarageWizardReach` `250.0` (server refuses bay saves further from the admin) · `Garages` seed `legion_square = { name='Public Garage', pos, spawnPos, blipPos, blipSprite=357, blipColor=3, markerType=1, markerSize, markerColor }` (read only on the very first start).

### 9. Shops
`Shops` `{}` (seed; a listed shop is recreated at start whenever no shop has its key; fields `name`, `mode` 'npc'|'infinite'|'stocked', `npcModel` or `prop`, `pos`, `blipSprite`, `blipColor`, `catalog`, `settings.categories`, `settings.layout`) · `ShopBasketSlots` `10` (1–50) · `ShopTalk` `{ enabled=true, batchSeconds=1, keeperDelay=1.2, open, add, change, remove, paid, broke, leave, keeperOpen…keeperLeave }` lines with `{n}`, `{item}`, `{total}`, `{items}`.

### 10. World interaction
| Key | Default |
|---|---|
| `InteractVisibleRange` / `InteractActiveRange` | `5.0` / `2.0` |
| `InteractFocusCone` | `40.0` |
| `InteractFocusConeNear` / `InteractFocusNearWeight` | `100.0` / `0.85` (doors, `focusMode='near'`) |
| `InteractDistWeight` / `InteractCameraWeight` | `0.6` / `0.4` (scoring helper only) |
| `InteractRenderer` | `'world'` (`'nui'` overlay; doors only in world) |
| `Interact3D` | `badgePx=68, labelPx=98, badgeMetres=nil, gap=0.35, fadeMs=100, labelRows=8, cullBehind=true, flashMs=900, depthBias=0.30, stackGap=0.25, stackAlpha=0.45, previewScale=3.4, theme='keycap', dark=false, styles={ subtle, lively }, groupStyles={}` (style fields: badgeScale, labelScale, opacity{seen,inReach,focused}, tint, labelTint, fadeMs, crossfadeMs, slideMs, flash 'blink'/'fade', flashMs, easing/fadeEasing/crossfadeEasing/slideEasing, appear/appearMs, focus, idle, press, base; groups: doors, vehicles, ground_items, garages, containers, properties, conversation, atm, actions) |
| `InteractPress` | `{ enabled = true, maxDistance = 2.5, followHand = true }` |
| `DoorInteractRange` | `3.0` |
| `DoorHandleAlong` / `DoorHandleHeight` | `0.85` / `1.05` |
| `DoorPromptOffsets` | `{}` (`[hash] = { x, y, z }`) |
| `LogSecureRejections` | `true` |
| `PropertyMaxObjects` | `150` |
| `PropertyKeyGrantRange` | `5.0` |
| `PropertyStreamRange` | `60.0` |
| `PropertyFurnitureDistance` | `20.0` (0 = only inside) |
| `PropertyFurnitureRooms` | `4` |
| `PropertySignPlaceRange` | `12.0` |
| `PropertySignPosts` | `whip_forsale_timber`, `whip_forsale_hanging` (`model`, `label`, `panel{x,y,z,w,h}`, `ink`, `accent`, `back`) |
| `PropertyStashProps` | `v_res_tre_wardrobe` (40 slots/150 kg), `v_res_mdchest` (25/80), `v_res_tre_storageunit` (30/120), `prop_ld_int_safe_01` (10/40) |
| `PropertyStashLimit` | `6` |
| `FurnishPlaceRange` | `8.0` |
| `FurnishMoveSteps` / `FurnishTurnSteps` | `{ 0.05, 0.25, 1.0 }` / `{ 15.0, 45.0, 1.0 }` |
| `PropSetMaxProps` | `256` |
| `LorePictureLinks` | `{ 'https://r2.fivemanage.com/' }` |
| `LoreVoice` | `{ Enabled=true, Links={ 'https://r2.fivemanage.com/' }, Range=15, GreetRange=4, ByeRange=10, GreetAgainMinutes=3, ReactAgainSeconds=6, Gestures=true }` |
| `PropClusters` / `PropCategories` | 7 clusters (furniture, fittings, dressing, scenes, everyday, leisure, outside) / categories with glyphs |
| `PropSeeds` | `{}` (`['model'] = 'category'` or `{ category, name }`) |
| `ShopInteractRange` / `ShopStreamRange` | `2.5` / `100.0` |
| `NetworkRange` | `424.0` |
| `DefaultGroundProp` | `'prop_cs_cardbox_01'` |
| `GroundItemPickupRange` / `GroundItemStreamRange` | `2.0` / `100.0` (door lock changes ride the stream range: keep ≥50) |
| `PlaceItemRange` | `10.5` |
| `GiveModeStyle` | `{ walk = 'trash', speed = 'jog' }` |
| `ThrowKnockdown` | `{ Enabled = true, MinSpeed = 8.0, RagdollMs = 2500, Npcs = true }` |
| `ActivityLogDays` | `30` |
| `PlayerManagerSessionWarn` | `false` |
| `ContainerInteractRange` / `ContainerStreamRange` | `2.5` / `100.0` |
| `ContainerPrompt` | `'face'` (`'middle'`/`'side'`/`'face'`) |
| `ContainerDefaultSlots` / `ContainerDefaultWeight` / `ContainerDefaultProp` | `20` / `100.0` / `'prop_cs_cardbox_01'` |
| `Emotes` | `{ cancelKey = 'X', placeRange = 6.0 }` |
| `Bubbles` | `{ range=20.0, duration=5000, maxLength=120, maxStack=3, height=0.3, size=1.0, maxPlayers=6 }` |
| `Conversations` | `{ size=1.0, height=0.375, minSizeFrom=4.0, maxGrow=1.75, margin=0.12, swing=10.0, range=6.0, speakingText, busyText, watcherBubbles=true, npcLines=4, noAnswerHalfText, noAnswerText }` |
| `SkillCheckHoldMs` / `SkillCheckMouseSpeed` | `196` / `1.0` |
| `SkillCheckDifficulty` | `easy { pieces=4, parts=6, widest=3, narrowest=1, msPerPart=650 }`, `medium { 8, 12, 4, 1, 600 }`, `hard { 16, 16, 4, 1, 575 }` |
| `LockpickGame` | `'ring'` (or a `Whip.skillCheckGame` name; falls back to ring) |

### 11. Character select, creator, arrival
- `Landing` `{ enabled=true, camera={ pos, rot, fov=42.0 }, prompt='Press any button to continue', look={ weather='EXTRASUNNY', hour=5, minute=17, frozen=true, priority=1000 }, fadeIn=800, fadeOut=500, streamMs=6000 }` (only on join; `/logout` and restarts skip it).
- `CharSelectFades` `{ fadeOut=500, fadeIn=800, fadeOnPlay=600, fadeOnCreate=900 }` (read at start).
- `CharSelect` `{ slots = { 4 hero shots: camera{pos,rot,fov}, pos vector4, one of scenario/anim{dict,clip}/emote, look, props (≤60) }, quietBucket=true, preloadShots=true, spawnPicker=true }`.
- `SpawnPoints` (server only): `legion` Legion Square, `airport` LSIA, `paleto` Paleto Bay (`{ id, label, pos }`).
- `Creator` `{ spawn=vector4(-1024.39,656.11,156.07,135.34), pose='idle6', look={ weather='CLEAR', hour=20, ... }, fadeOut=800, fadeIn=800, arriveHoldMs=500, settleMs=1200, maxOutfits=20 }` (maxOutfits 1–100).
- `ArrivalScenes` `{ enabled=true, vehicleRange=400.0, nearCarRange=25.0, onFoot={...29 lines}, inVehicle={2}, onBike={1}, nearCar={1} }`; line fields `dict`, `clip`, `cam`, `from`, `to`, `vehicleClip`, `getsIn`, `indoors`, `prop`.

### 12. Performance
`FlushInterval` `1000` ms · `PlayerPositionSaveInterval` `30` s · `PlayerPositionEpsilon` `2.0` m · `StatsTickInterval` `1` · `StatsSyncInterval` `5` · `StatsSetGuardWindow` `2` · `TimeSyncInterval` `60000` · `GroundSyncInterval` `1` · `GroundItemCellSize` `50` (keep well above 25) · `ZonePollInterval` `300` ms · `ZoneVehiclePollInterval` `2000` ms · `ZoneTrackInterval` `1000` ms · `ZoneCheckRange` `200` · `ZoneCellSize` `50`.

### 12b/13. Experimental and advanced
`Experimental` `{ cameraCreator=false, systemsCreator=false, combinedSettings=false }` · `Theme` `nil` (resource with `theme.css`; `/whip_theme` re-applies) · `InventoryRenderer` `nil` (resource with `renderer.js`; convar wins) · `DependentResources` `{}` · `EnableTestSeams` `GetConvar('whip_test_seams','false') == 'true'` · `ShowPlayerNames` `'nearby'` · `PlayerNameRange` `25.0` · `Sentinel` `{ enabled=true, autoKick=3, strikesForgetMinutes=60, logDebounceMs=1000, bootSweep=true, damageModifierClamp={ min=0.05, max=4.0 } }`.

## Resource settings pages: Whip.configPage, Whip.onConfigChanged, setting entry fields

Puts your resource's settings in `/whip` → Settings beside Config. Only permanent admins see/edit it (same rule as Config). Values are saved under the **resource folder name** (`whip_settings.owner`, ≤64 chars): renaming the folder starts from defaults again.

### Whip.configPage(def) — BOTH (from `@whip_core/lib/satellite.lua`)
Call once **at file scope** in a **shared script after `config.lua`** (not inside `Whip.register`; it registers itself through `Whip.register`, so it re-declares on every whip_core start).

| Field | Type | Meaning |
|---|---|---|
| `label` | string | Page name in Settings (≤40 chars, `shared/settings.lua:899`) |
| `settings` | table | Entries in order; each `key` is a path in Config (`'Tuning.EngineSwapPrice'`) |
| `groups` | table\|nil | Instead of `settings`: `{ { label = 'Prices', settings = {...} }, ... }` (optional `id`) |
| `config` | table\|nil | Table the keys are in; default global `Config` |

- Entries are setting entries (below) **without `default`**: each default is taken from the current Config value at call time (before saved values are written in).
- Saved values are written into Config on both sides (server-only `sides='server'` values only on the server) when the page is declared and on every change; tables are changed **in place** so a local reference (`local shop = Config.Shop`) sees new values.
- Values are kept as the check returns them: text trimmed of control chars and surrounding spaces, `int` as integer, `number` as float, `keyKind='hash'` map keys as signed hashes.
- Saved values are re-checked on declaration; one that fails (e.g. you lowered `max`) is dropped with a console line and config.lua's value stands.
- An entry whose default is not data (holds a function) or a `records`/`map` row with an undeclared non-scalar field (a position not declared as a field) is left off the page with a console line.
- An entry whose config.lua default fails its own row's checks is left off (console says why) and your code keeps reading the raw value: **clamp what you read**. The page is refused only when no entry passes.
- The page disappears when your resource stops; saved values stay.
- Returns `boolean`: `false` when `def` is not a table or Config is not loaded (printed). whip_core's refusal reasons are printed later as `settings page refused: <why>`, e.g. `'label: a name for the page, up to 40 letters'`, `'settings: a list of settings (or groups of them)'`, `'group N needs settings'`, `'setting N: key must be a name (letters, digits, _ and .)'`, `'<key> is declared twice'`, `'none of its settings has a default that passes its own check'`, `'whip_core is still starting: declare the page inside Whip.register'`.
- Internals: `__RegisterSettings(def)`, `__GetSetting(key)`, `__GetSettings()`, `__OnSettingChanged(key, fn)` (one hook per key; re-registering replaces). Use the helper, not these.
```lua
-- settings.lua (shared_script, after config.lua)
Whip.configPage({
    label = 'My Cafe',
    groups = {
        { label = 'Prices', settings = {
            { key = 'Prices.coffee', type = 'int', min = 1, max = 500, unit = '$', label = 'Coffee' },
        } },
        { label = 'Counter', settings = {
            { key = 'Counter.coords', type = 'vec3', here = true, label = 'Where it stands' },
            { key = 'Counter.open', type = 'bool', label = 'Open' },
        } },
    },
})
```
whip_autos' `shared/settings.lua` is the reference example.

### Whip.onConfigChanged(path, fn) — BOTH
- `path` string: a path in Config. `fn(value, old, key)`: `key` is the path that changed. Fires for its own path, anything under it, and a change to a table it is inside (a hook on `'Counter.coords'` hearing `'Counter'` gets the whole table; read `Config` when unsure). Also fires when saved values are written in as the page is declared.
- Call at file scope (inside `Whip.register` it would be added again on every whip_core restart; hooks live in your resource and are never removed). `fn` must not wait (errors are caught and printed).
- `apply = 'restart'` entries never call it (read them at start).
```lua
Whip.onConfigChanged('Counter.coords', function()
    local c = Config.Counter.coords
    SetBlipCoords(counterBlip, c.x, c.y, c.z)
end)
```
- Values arrive when whip_core is ready, after your files load: code that reads Config at file scope sees config.lua first; rebuild derived data in `onConfigChanged`.

### Setting entry fields (`#registersettings`)
Used by `Whip.configPage` entries and items' own `settings`.

| Field | Type | Meaning / rule |
|---|---|---|
| `key` | string | `^[%a_][%w_%.]*$`, ≤64, unique on the page. Dots make paths: a callback on `prices` hears `prices.coffee` |
| `type` | string | `'int'`, `'number'`, `'bool'`, `'string'`, `'enum'`, `'vec3'`, `'vec4'`, `'list'`, `'records'`, `'map'`, `'record'` |
| `default` | any | Value until changed (items give it; configPage takes config.lua's). Must pass the entry's checks or the row is dropped |
| `label` / `help` | string | Row name (defaults to key) / line under it |
| `shownWhen` | `{ path, equals }` | Show the row (or card) only while that setting equals the value |
| `min` / `max` / `step` | number | int/number range and arrow step |
| `unit` | string | `'$'` prefixes; anything else suffixes (`'m'`, `'ms'`) |
| `options` | table | enum: `{ { value = 'slow', label = 'Slow' }, ... }` (each needs `value`) |
| `maxLen` / `minLen` | number | string length in UTF-8 characters; `minLen` default 1 |
| `pattern` / `patternWhy` | string | Lua pattern the whole trimmed text must match (use `^…$`) / message |
| `nullable` / `emptyLabel` | bool / string | Empty box = `nil`; label for it (default `'none'`) |
| `offWhenEmpty` | bool | int/number/string: empty = `false` ("off") |
| `apply` | string | `'live'` (default), `'restart'`, `'readonly'` |
| `why` | string | Reason shown for restart/readonly rows |
| `sides` | string | `'both'` (default) or `'server'` (never sent to players; admins still see it) |
| `cross` | `function(get)` | Server-side when this setting is in a save; `get(key)` = value as it will be saved. Return `true` or `false, 'why'`. Put it on both entries of a two-setting rule |
| `here` / `limits` / `axisLabels` | bool / table / table | vec3/vec4: "Use where I stand"; `{ x = { min, max }, ... }` |
| `place` | bool / table | vec3/vec4 (whip_core 1.2.0+): a Place button; the panel steps aside and the point is placed in the world with `PlacePoint` (ui-nui-camera.md). `{ model = 's_f_y_shop_mid', ped = true }` picks the ghost. Comes back as an edit waiting for Apply. An empty optional position reads 'none' |
| `item` | table | list: entry shape without key; must be `int`, `number`, `string` or `enum` (edited as one comma-separated line). For positions use `records` with a `vec3` field |
| `fields` | table | records / map rows / record: field entries with `key` (`'permissions.canHire'` may reach inside the row); fields not listed are kept as-is. A `record` field cannot itself be a `record` |
| `widget` / `marker` | string / table | `widget = 'mapPoints'`: records with a vec3 and a string field shown as draggable map icons; `marker = { sprite = 361, colour = 1, name = 'Gas Station' }` |
| `each` | table | map of single values: value shape (`{ type = 'string', maxLen = 20 }`) |
| `minItems` / `maxItems` | number | list/records count (map: `maxItems` only). Equal = fixed rows |
| `unique` | string | records: field no two rows share |
| `keyKind` / `keyPattern` / `keyWhy` / `keyLabel` | | map: `'hash'` (model name or number → signed 32-bit hash, as `GetEntityModel`), `'number'` (digit key → integer), else names checked against `keyPattern` |
| `record` type | | One card of `fields`, each saved as its own setting `'<key>.<field>'`, defaults from the card's `default` table; `cross`/`sides`/`apply`/`why`/`shownWhen` inherited from the card unless the field sets its own |

Declaration-time errors (from `badEntry`): unknown type; a list/records/record without `item`/`fields`, enum without `options`; non-number `min/max/step/maxLen/minItems/maxItems`; uncompilable `pattern`/`keyPattern`; map without `each` or `fields`; nesting deeper than 6.

Check failure messages (shown to the admin): `'needs a value'`, `'must be on or off'`, `'must be a number'`, `'must be a whole number'`, `'must be at least N'`, `'must be at most N'`, `'must be text'`, `'cannot be empty'`, `'is longer than N characters'`, `patternWhy` or `'has characters it cannot have'`, `'is not one of the choices'`, `'must be a position'`, `'<axis> must be between a and b'`, `'must be a list'`, `'needs at least N entries'`, `'must be a list of rows'`, `'rows i and j have the same X'`, `'must be a table of rows'`, `'"k" is there twice'`, `'cannot be changed here'` (readonly).

## Player settings: Whip.playerSetting, GetPlayerSetting, SetPlayerSetting

A per-player choice (volume, units, show/hide) as a row on the pause menu's Server Settings page. Your resource stores the value itself (own KVP on the player's PC); the page calls `get`/`set`. The row goes when your resource stops and returns on whip_core restart.

### Whip.playerSetting(def) — CLIENT (from `lib/satellite.lua`)
Call at file scope; it registers inside `Whip.register` itself. Returns `false` (printed) when `def` lacks `key`, `get` or `set`, or on the server; refusal reasons from whip_core are printed as `player setting <key> refused: <why>`.

| Field | Type | Rule |
|---|---|---|
| `key` | string | `^[%w_%.%-]+$`, 1–64; unique; start with your resource name (`'mycafe.sounds'`). Cannot be one of whip_core's own keys |
| `label` | string | Required (cut to 60) |
| `type` | string | `'toggle'` (true/false), `'choice'` (one of options), `'slider'` (number) |
| `get` | function | Returns current value |
| `set` | function | `set(value)` stores it; page keeps nothing |
| `default` | any | **Required**: a plain value the type takes; what "Reset this page to server defaults" restores. A function default is refused |
| `group` | string? | Tab: `'Controller'`, `'Vehicles'`, `'Map & HUD'`, `'Chat & voice'` (also whip's `'Minimap'`) or your own (cut to 30). Default `'Other'` |
| `help` | string? | One line (cut to 240) |
| `options` | table? | choice: `{ { value, label }, ... }`, at least 2 (labels cut to 40) |
| `min`, `max`, `step`, `unit` | number?, string? | slider: `min < max` required, `step` > 0 (default 1), unit cut to 12 |

Refusal reasons: `'key must be letters, digits, dots, dashes or underscores (1-64)'`, `'type must be toggle, choice or slider'`, `'label is required'`, `'a choice needs at least two options, each { value, label }'`, `'a slider needs min < max and a step over 0'`, `'a resource\'s setting needs get and set (its value stays yours)'`, `'<key> is one of whip_core\'s own'`, `'a resource\'s setting needs a default: a plain value its type takes (Reset puts it back)'`.
```lua
local sounds = GetResourceKvpInt('sounds') ~= 2   -- unset reads 0 = on
Whip.playerSetting({
    key = 'mycafe.sounds', group = 'Map & HUD', type = 'toggle', default = true,
    label = 'Café sounds', help = 'The till and the coffee machine.',
    get = function() return sounds end,
    set = function(on) sounds = on; SetResourceKvpInt('sounds', on and 1 or 2) end,
})
```

### GetPlayerSetting(key) — CLIENT
- Returns the value in force on this PC: a server-forced value (greyed row "Disabled by server admin"), else the player's choice, else the default. Reads whip_core's own rows too. `nil` for an unknown key.
```lua
local unit = exports.whip_core:GetPlayerSetting('dial.speedUnit')   -- 'mph' or 'kmh'
```

### SetPlayerSetting(key, value) — CLIENT
- Changes a row as the page does (for your own screen showing the same setting). A resource's row goes through its `set`. Slider values are clamped and snapped to step.
- Returns `true`, or `false, reason`: `'no such setting'`, `'Disabled by server admin'`, `'not a value this setting takes'`, or the `set` error text.
```lua
local ok, why = exports.whip_core:SetPlayerSetting('voice.callVolume', 75)   -- whip_voice's row
```

whip_core's own keys (stored in KVP `whip_core:prefs`): `dial.speedUnit`, `dial.style`, `dial.horizon`, `drive.camera`, `drive.cameraStyle`, `inv.weightUnit`, `keyboard.language`, `keyboard.predict`, `map.onFoot`, `map.inVehicle`, `map.background`, `map.border`, `map.fps`, `mm.northUp`, `mm.centre`, `mm.markerSize`, `mm.markersUpright`, `mm.viewFoot`, `mm.viewSlow`, `mm.viewFast`, `mm.speedFrom`, `mm.speedTo`, `mm.tiltFoot`, `mm.tiltVehicle`, `mm.tiltWithSpeed`, `mm.tiltFast`, `pad.cursorSpeed`, `pad.doubleClickMs`, `pad.lookSpeed`, `pad.moveSpeed`, `pad.radialHoldMs`, `pad.sprintOnA`, `pad.vehicleControls`, `pad.vehicleControlsKeys`, `prompts.dark`, `prompts.shape`, `prompts.stash`. Tab order: Controller, Vehicles, Map & HUD, Minimap, Chat & voice, then others.

## Activity Log: LogActivity, FlushActivityLog, what WHIP logs

Two timelines from one table `activity_log` (`id`, `ts`, `charId`, `event` VARCHAR(32), `itemKey`, `itemUid` VARCHAR(24), `amount` INT, `detail` VARCHAR(191), `x`, `y`, `z`, `hostKey`, `hostUid`): per character, and per item instance (uid).
- Item identity: the first time an instance crosses a logged point, a `uid` (`'<hex os.time>-<hex counter>'`) is stamped into `metadata.uid` and a `first_seen` row written; the uid then travels with the item through every move, give, drop, ground row and pickup. A stack split keeps the uid on both halves; a merge absorbs into the surviving stack.
- Rows save in the same transaction as the change they describe (per-action log unit); rows outside any action go in a shared unit with the next save pass. Final save flushes them (step 60).
- Retention: `Config.ActivityLogDays` (default 30, page 1–3650, restart). Pruned once at start, in chunks of 10000 (max 500 chunks).
- Client-paced notes (`inv_open`, `inv_close`, `interaction`) are capped at 60 per character per minute.
- Events WHIP writes include: `login`, `logout`, `died`, `inv_open`, `inv_close`, `moved`, `organised`, `merged`, `gave`, `received`, `dropped`, `picked_up`, `threw`, `placed`, `used`, `destroyed`, `opened_container`, `interaction`, `ctx_<action>`, `first_seen`, `gained`, `lost` (items entering/leaving the game: shops, admin gives, satellite AddItem/RemoveItem, ATM cash, pumps), `lockpick_fail`, `lockpick_door`, `vehicle_enter`, `vehicle_claimed`, `vehicle_plate`, `property_bought`, `renamed`, `identity_notice`, `bank_admin`, `bank_system`, `payment_unpaid`, `refund_failed`, `withdraw_undo_short`, `dungeon_mode`, `dev_mode_on`, `dev_mode_off`; Object Viewer uses are logged on user and target timelines.
- Reasons: the `reason` your resource passes to `AddItem`, `PayPlayer`, etc. is logged as `'<reason> · by <resource>'` (reason sanitised to 120 chars; the resource name is appended because the reason is the caller's claim).

### Item Log (/whip → Economy → Item Log)
- Everything tab: every item event newest first; filters by person, item, what happened, when (up to `ActivityLogDays`), minimum amount. Click a person, an item's whole life, or a place to teleport.
- Economy tab: one item at a time: how many exist now, in/out by reason, who holds/gained most. Items inside other items and a resource's own storage are not counted.
- Rows without an item (logins, dev tool use) appear on the person's timeline in the Player Manager.

### LogActivity(source, event, opts?) — SERVER, WAITS
| Param | Type | Meaning |
|---|---|---|
| `source` | number | Whose timeline (charId of the loaded character; nil charId if none) |
| `event` | string | Required, short (stored ≤32 chars) |
| `opts.detail` | string? | Free text (stored ≤191) |
| `opts.slotData` | table? | An **address**: `{ kind = 'player', id = source, sub = 'player', slot = 4 }`, the `addr` from a use handler or `FindItem`, or any store's address. Also writes the row to that item's history and mints its uid if it has none (saved with the item) |

- Returns `true`, or `false, reason`: `'event name required'`, `'opts is { detail?, slotData? }'`, the address resolution error, `'Invalid slot'`, `'Empty slot'`, or for a `{ container, slot }` table: `"name the slot with an address: { kind = 'player', id = source, sub = 'player', slot = n }"`.
- A slot-shaped copy (`{ item, amount, metadata }`, e.g. from `GetItemAt`) is accepted: its existing uid is used; no uid is minted (a uid on a copy belongs to nothing).
```lua
exports.whip_core:LogActivity(source, 'whiplash_entered', { detail = 'Bay 3' })
exports.whip_core:LogActivity(source, 'lockpick_used', { detail = 'garage door', slotData = addr })
```

### FlushActivityLog() — SERVER, WAITS
- Writes every owed row now (waits for an in-flight write). Only for tests and ops. Returns `boolean`: `false` if the DB refused (rows kept and retried).

## WhipCost (/whipcost)

Times your loops on players' PCs (and server) without a profiler's overhead.

### WhipCost.start() / WhipCost.stop(name, started) — CLIENT and SERVER
- Load `client_script '@whip_core/lib/cost.lua'` and/or `server_script '@whip_core/lib/cost.lua'`.
- `start()` returns `number|nil` (nil while `/whipcost` is not running; `WhipCost.on` is the flag). `stop(name, started)` returns nothing, at once when `started` is nil. `name` is the table line, as `'area: what'`.
- Never `Wait()` between start and stop: on the client a run that spanned a frame is left out; on the server there is no frame check, so the wait would be timed.
- Client clock: `GetNetworkTimeAccurate` (whole ms; sums over many runs). Server clock: `os.clock()` CPU time.
```lua
CreateThread(function()
    while true do
        local cost = WhipCost.start()
        drawCafeMarkers()
        WhipCost.stop('mycafe: markers', cost)
        Wait(0)
    end
end)
```

### Running it
- Client: developer mode on, `/whipcost` (20 s) or `/whipcost 60` (clamped 5–120). Play normally; the table prints in F8, most expensive first.
  - Columns: **us a frame** (share of every frame — read this), us a run, runs a second, KB a second (garbage made). Under 100 runs → marked "rough". Nested sections count in both.
  - Then MEMORY BY RESOURCE (every resource loading `lib/satellite.lua` or `lib/cost.lua`: the climb you see in resmon), EVERY LOOP by thread start function, calls into whip_core and how often (one per frame from another resource costs both sides every frame), and NOT COUNTED remainder.
  - Collectors pause during the run (exact memory). A resource making over 32 MB gets its collector back and its figure stops; afterwards collectors catch up (small hitch possible).
- Server: console `whipcost [seconds]` (or a dev player; output in the server console): columns resource, section, runs/s, us/run, ms/s (1000 = one core). Time only, no memory. Internal events: `whip_core:cost:serverStarted`, `whip_core:cost:serverStopped`, `whip_core:cost:serverReported`.

## Dev pages: RegisterDevPage, RefreshDevPage, RemoveDevPage

Pages show only to a developer with developer mode on. The menu only reads rows: re-check anything a row does on the server with `exports.whip_core:HasDevTools(source)`.

### RegisterDevPage(id, def) — CLIENT
Declare inside `Whip.register` (whip_core forgets every page on restart). Same id again replaces yours. Goes when your resource stops. `/w` reopens on the page it was closed on with Escape. Stored as `'<resource>:<id>'` (another resource's same id is a different page).

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `^[%w_%-]+$`, ≤48 |
| `label` | string | Row in `/w` and the page title (≤40) |
| `desc` | string\|nil | Line under the list while your row is picked (≤300) |
| `rows` | function | Returns a list of rows, or a view `{ title, back, select, rows }`. Called on open, after every pick, and on `RefreshDevPage` |
| `onSelect` | `function(rowId)` | Must not wait: start a thread, then `RefreshDevPage` |
| `onBack` | function\|nil | The way back from a level that returned `back` |
| `onOpen` / `onClose` | function\|nil | Page came on / left the screen |

View: `title` (default the label), `back` (name of the level above; the way back calls `onBack`), `select` (row id picked first), `rows`.

| Row field | Type | Meaning |
|---|---|---|
| `id` | string\|number | Passed to `onSelect`; every row except a note needs one |
| `label` | string | Text |
| `kind` | string\|nil | `'run'` (default), `'toggle'` (lit by `active`), `'open'` (chevron into a level), `'note'` (never picked) |
| `active` | boolean\|nil | Toggle state |
| `desc` | string\|nil | Line under the list while picked |
| `close` | boolean\|nil | Close the menu after `onSelect` |
| `icon` | string\|nil | A prompt glyph name (`'target'`, `'car'`...); unknown draws nothing |
| `sep` | string | Group header instead of a row: `{ sep = 'Playback' }` |

Returns `true`, or `false, why`: `'the id must be letters, digits, _ or - (48 at most)'`, `'the page must be a table'`, `'label (the row in /w and the page title) must be a string'`, `'rows (a function answering the page\'s rows) is required'`, `'onSelect (a function run when a row is picked) is required'`, `'<onBack|onOpen|onClose> must be a function'`.
```lua
local open, level = false, 'top'
Whip.register(function()
    Whip.core:RegisterDevPage('cafe', {
        label = 'Café',
        rows = function()
            if level == 'menu' then
                return { title = 'Menu', back = 'Café', rows = { { id = 'coffee', label = 'Coffee' } } }
            end
            return { rows = {
                { id = 'open', label = 'Open', kind = 'toggle', active = open },
                { id = 'restock', label = 'Restock', desc = 'Fills every shelf.' },
                { id = 'menu', label = 'Menu', kind = 'open' },
            } }
        end,
        onSelect = function(rowId)
            if rowId == 'open' then open = not open
            elseif rowId == 'menu' then level = 'menu'
            else TriggerServerEvent('mycafe:devAction', rowId) end   -- server checks HasDevTools
        end,
        onBack = function() level = 'top' end,
    })
end)
```

### RefreshDevPage(id) — CLIENT
- Your rows changed without a pick: if the page is on screen, `rows` is called again keeping the same row picked; otherwise free. Returns `true` or `false, 'no page of yours has that id'`.

### RemoveDevPage(id) — CLIENT
- Removes your page while your resource runs. Returns `true` or `false, 'no page of yours has that id'`.

## Debug tools: RegisterDebugTool, RemoveDebugTool

### RegisterDebugTool(id, def) — CLIENT
- A switch among `/w`'s debug tools, visible while the Debug row is on, after WHIP's own, sorted by label. Turning it on checks with the server like any dev tool. Same id replaces (keeps on/off state). Declare in `Whip.register`; goes when your resource stops.
- `id` `^[%w_%-]+$` ≤48. `def.label` string ≤40; `def.desc` string? (≤300); `def.onToggle(on)` function, required; also called with `false` when Debug or developer mode goes off. Return `false` to stay off (an error also leaves it off, printed).
- Returns `true` or `false, why` (`'the id must be letters, digits, _ or - (48 at most)'`, `'the tool must be a table'`, `'label (its row in /w) must be a string'`, `'onToggle (a function run when it is switched) is required'`).
```lua
exports.whip_core:RegisterDebugTool('mine', {
    label = 'My Debug', desc = 'What my overlay shows.',
    onToggle = function(on) ShowMyOverlay(on) end,
})
```

### RemoveDebugTool(id) — CLIENT
- Removes it; one that is on is **not** switched off (your job). Returns `true` or `false, 'no debug tool of yours has that id'`.

## Whip.objectViewerOption / Whip.removeObjectViewerOption

### Whip.objectViewerOption(id, def) — CLIENT (from `lib/satellite.lua`)
Adds/changes an option in the Object Viewer's G list. Call at file scope (it registers via `Whip.register`). `select` runs in its own thread (may wait); the list has closed.

| Field | Type | Rule |
|---|---|---|
| `id` | string | `'<namespace>.<name>'`: `^[%a][%w_]*%.[%a][%w_]*$`, ≤64 |
| `label` | string | Required, ≤48 |
| `kinds` | string[] | Non-empty; any of `vehicle`, `player`, `npc`, `object` |
| `whip` | boolean? | `true`: only WHIP's own (saved car, player); `false`: only the game's; nil: both. Must be boolean or nil |
| `group` | string? | Heading ≤24; default your resource name |
| `tint` | string? | `blue`, `teal`, `green`, `amber`, `red`, `violet`, `slate` (default; unknown → slate) |
| `hint` | string? | Line under the list (≤160) |
| `select` | function | `select(target)`; `target = { kind, entity, netId, whip, vehicleId, serverId, model, name, coords = { x, y, z, heading } }` |

- Returns `true`, or `false` when invalid (reason printed: `'an option\'s id is "<your namespace>.<name>", like autos.whiplash'`, `'<id>: it needs a label (48 letters at most)'`, `'<id>: kinds is a list of: vehicle, player, npc, object'`, `'<id>: "x" is not a kind ...'`, `'<id>: whip is true, false or left out'`).
- Shown to anyone with dev tools on and to a Dungeon Master in Dungeon Mode: check on the server (`HasDevTools(source)` or the needed permission).
- `Whip.removeObjectViewerOption(id)` removes one (also automatic on resource stop).
```lua
Whip.objectViewerOption('mycafe.refuel', {
    label = 'Fill the tank', group = 'My cafe', tint = 'amber', kinds = { 'vehicle' }, whip = true,
    select = function(target) TriggerServerEvent('mycafe:server:refuel', target.vehicleId) end,
})
```

## Other dev/tool exports

### HasDevTools(source) — SERVER
- `true` only with `whip.devtools` **and** developer mode on. `source == 0` (console) → `true`. Use instead of `IsPlayerAceAllowed`. A SecureEvent/SecureCallback with `ace = 'whip.devtools'` already gets this check.

### HasDevTools() — CLIENT
- Is developer mode on for this player (for what a client tool shows; the server's check is authoritative).

### SetDeveloperMode(source, on) — SERVER
- Toggles developer mode as the `/w` switch does, for tools acting for a player (whip_devlink keeps it on across restarts). On only for an account with `whip.devtools`. Logged with the invoking resource as the reason. Returns `true` or `false, 'You do not have dev tools'`.

### GetCommandAce(name) — SERVER
- `'whip.devtools'` for whip_core's in-game admin commands (`whip_giveitem`, `whip_revive`, ...), else `nil`. For chat suggestion filtering (whip_chat).

### MeasureFrames(opts?) — CLIENT, WAITS
- `opts.seconds` 1–30 (default 5). Returns `{ seconds, frames, fps, fpsWorst1, medianMs, worstMs, over33, over50 }`.

### GetPlatform() — BOTH
- `'legacy'|'enhanced'`.

### GetGarageHelperStatus() — CLIENT (internal test hook; do not build on it)
- Returns `{ enabled (Config.GaragePositionHelper.enabled), duiActive, drawing (visible bay outlines), driving (in a driver's seat), qualifies (driven vehicle passes requireStorable) }`.

---

## Gotchas
1. `whip.devtools` without developer mode is an ordinary player everywhere. Server code must call `exports.whip_core:HasDevTools(source)`; `IsPlayerAceAllowed(src, 'whip.devtools')` skips developer mode. `HasDevTools(0)` is `true`.
2. Developer mode is off at every join and after every whip_core restart; anything a tool relies on must survive it turning off (your `RegisterDebugTool` `onToggle(false)` is called then).
3. Config page and resource settings pages are permanent-admin only: panel-granted temporary dev tools cannot change settings.
4. A saved Config value beats config.lua until Reset is pressed. Editing config.lua has no visible effect for a key someone changed in game. Never edit `settings.json` / `server_settings.json`: rebuilt from the DB at every start.
5. `apply = 'restart'` settings (`ContainerSlots.player`, `AccessoryStrip`, `PropertyMaxObjects`, `Bubbles.maxStack`, `Keyboard.Languages`, `ActivityLogDays`) are saved at once but take effect only at whip_core's next start; `onConfigChanged` is not called for them.
6. `Whip.configPage` must be in a shared script after config.lua, at file scope; values follow the resource **folder name** (renaming the folder resets to defaults). `label` is limited to 40 characters.
7. Code that reads Config at file scope sees config.lua values first; saved values arrive when whip_core is ready. Rebuild derived data in `Whip.onConfigChanged` (file scope, never inside `Whip.register`, which would stack hooks).
8. An entry whose config.lua default fails its own check (e.g. above `max`) is silently left off the page (console line) and your code keeps the raw value: clamp what you read.
9. A `records`/`map` row field holding a position must be declared in `fields`, or the whole entry is left off; functions in Config values cannot go on a page.
10. `sides = 'server'` values exist only in the server's Config; client code reading the same Config key keeps config.lua's value.
11. `Whip.playerSetting` needs a plain `default` (functions are refused) plus `get` and `set`; it is client-only and returns false on the server.
12. `LogActivity` `slotData` must be an address (`{ kind, id, sub, slot }`); a `{ container, slot }` table is refused, and a copied slot without a uid gets no uid.
13. Never `Wait()` between `WhipCost.start()` and `stop()`; on the server a wait is silently timed.
14. Dev page `rows`/`onSelect` and debug tool callbacks must not yield; dev pages and debug tools vanish on whip_core restart unless declared in `Whip.register`.
15. `/w` rows, debug tools and Object Viewer options are client UI only: every server action they trigger must re-check `HasDevTools(source)` (Object Viewer options are also visible to Dungeon Masters).
16. `whipsetup`, `whipsupport`, `whiperrors`, `whipupdates` only work in the server console (silently ignored from a player).
17. Enhanced servers must use `setr whip_platform enhanced` (not `set`) and should raise `sv_resourceFileDownloadTimeout` for the ~510 MB first download.
18. Running another framework, inventory, target, voice, `chat` beside `whip_chat`, `spawnmanager` or `basic-gamemode` is a setup-report FIX: they fight WHIP.
19. A config.lua syntax error halts whip_core and refuses every join; the message names the line (the slip is often on the line above).

## Docs vs code
1. `config.lua:863`, `config.lua:1071`, `config.lua:1077` and `types/client.lua:984` mention `/garagehelper`, `/interactrenderer` and `/i3d`, but no such commands are registered anywhere in whip_core (only `client/interact.lua:1024` has a comment). Treat them as non-existent.
2. Docs (#configuration) list `MinimapMask` values `'square'`, `'rounded'` or `'circle'`; the Config page enum offers `'square'`, `'rounded'` and `false` (game's own) (`shared/config_schema.lua:705-708`). `'circle'` is only reachable by editing config.lua (`config.lua:321`).
3. Docs `DrivingCamera` lists `Enabled`, `Default`, `Shake`; code also has `Style = 'consistent'|'cinematic'` (`config.lua:400`, schema `shared/config_schema.lua:517`).
4. Docs Controller defaults omit `foot_b = 'gunny_reload'` (`config.lua:433`).
5. Docs "Every 12 hours whip_core asks GitHub": code runs a check loop hourly (first 30 s after ready) and asks each repository only when its last answer is older than 12 h (`server/updates.lua:25-26,251-260`).
6. Docs list `whipcost [seconds]` as a console command; the server command also accepts an in-game player with dev tools + developer mode (output still to the server console) (`server/whipcost.lua:41-43`).
7. `Whip.configPage` docs give no length for `label`; code refuses labels over 40 characters (`shared/settings.lua:899`). Dev page/debug tool ids are capped at 48 characters (`tools/core.lua:677,812`), not stated in the docs.
8. `LogActivity` docs: event "short"; code truncates `event` to 32 and `detail` to 191 characters (`server/activity_log.lua:126-131`).
9. Docs #configuration lists `Conversations` fields without `minSizeFrom`, `maxGrow`, `noAnswerHalfText`, `noAnswerText` (`config.lua:1441-1460`), and `Sentinel` without `logDebounceMs`, `bootSweep`, `damageModifierClamp` (`config.lua:1821-1825`).
10. `HudDeveloperMark` is `sides = 'server'` on the Config page (`shared/config_schema.lua:768`) although it affects every player's HUD (the server applies it via stats).
