# whip_voice and the voice system

Covers WHIP's 3D voice chat resource `whip_voice` (built-in LiveKit voice server, items, settings, voice lines, voice bots, world voices, sound recipes), whip_core's voice-system registry (`RegisterVoiceSystem`, `GetVoiceSystem`, `Whip.voice`, `Whip.voiceSystem`, HUD voice exports) and the lore voice features built on it (`LoreSay`, lore phone calls, Director speakers, `CheckPicture`). Built from doc anchors `#voice`, `#voice-setup`, `#voice-setup-own`, `#voice-lore-calls`, `#voice-lore-lines`, `#voice-speakers`, `#voice-api`, `#voice-api-sounds`, verified against `whip_voice/` (fxmanifest, config.lua, docs/SETUP.md, docs/LINES.md, server/*.lua, server/builtin.js, client/*.lua, shared/sound_blocks.lua, service/voicebot/bot.mjs) and `whip_core/server/voice_system.lua`, `whip_core/client/voice_system.lua`, `whip_core/client/stats.lua`, `whip_core/lib/satellite.lua`, `whip_core/types/*.lua`, `whip_core/server/director/lore_voice.lua`, `whip_core/server/director/speakers.lua`, `whip_phone/server/lore.lua`, `whip_phone/server/calls.lua`.

## Contents
- Architecture
- Installation and server.cfg
- Convars
- The built-in voice server (first start, bin, logs, restarts)
- Your own voice server, and running the voice bot yourself
- Player controls, commands and per-player settings
- Items: megaphone, radio, speaker
- config.lua reference
- How hearing is decided (server rules)
- whip_core: the voice-system registry and HUD exports
- Lines API (whip_voice server exports)
- Sound recipes and blocks
- Voice bots API
- World voices API
- Other whip_voice exports and events
- Lore phone calls
- Lore characters speaking (LoreSay, Config.LoreVoice)
- Director speakers (Play on Speakers / Stop Speakers cards)
- CheckPicture
- Internal net events, callbacks and state
- Diagnostics: /voicecheck, /voicestatus, /voicedebug and the problem messages
- Writing your own voice system
- Gotchas
- Docs vs code

## Architecture

- Each player's game sends its microphone to a voice server (LiveKit). The FiveM server never carries audio; it only decides who may hear whom (server-authoritative). A modified game cannot listen in on calls, radio frequencies or out-of-range players.
- The voice server is either **built in** (no `whip_voice_url` convar: `server/builtin.js` downloads LiveKit and runs it on the same machine as a child process) or **your own** (`whip_voice_url` set: LiveKit Cloud or LiveKit elsewhere).
- Built-in mode: players' games are told to connect to `wss://whip-voice.invalid` (`server/builtin.lua:25`); `html/js/relay.js` intercepts that and carries the signalling through the FiveM connection (`whip_voice:server:sig` / `whip_voice:client:sig`, handled in `server/builtin.js`). Only the media goes to the voice ports. No domain or certificate needed.
- Room: one per start of whip_voice, named `whipvoice-<8 random hex>`, created with `empty_timeout = 600`, `departure_timeout = 60`; older `whipvoice-*` rooms are deleted at start (`server/main.lua:17-41`). A built-in server that restarts gets a fresh room; all players get `whip_voice:client:reconnect`.
- Server tick: the who-hears-whom pass runs 4×/s (`server/hearing.lua:29` `TICK_MS = 250`); results go to each player as allow/hear lists.
- **One voice system per server** (whip_core registry). whip_voice registers itself as `label = 'whip_voice (advanced)'`, features `{ lines = true, speaker = true, pickup = true, quality = true, sounds = 'full' }`. If another voice resource registered first, whip_voice prints `NOT STARTED: <why>` and stays off (no items, no tokens).
- Everything that uses voice (whip_phone calls, the radio, the megaphone, HUD voice light, lore characters, Director speakers, your resource) goes through it. Other resources must call it via `Whip.voice(...)` (from `@whip_core/lib/satellite.lua`), never `exports.whip_voice` by name.
- Load order (fxmanifest): shared `@whip_core/lib/satellite.lua`, `config.lua`, `shared/sound_blocks.lua`; server builtin.lua, builtin.js, token.lua, voice_server.lua, players.lua, audibility.lua, hearing.lua, lines.lua, lines_api.lua, bots.lua, items.lua, megaphone.lua, radio.lua, speakers.lua, check.lua, main.lua; client acoustics.lua, ways.lua, environment.lua, main.lua, megaphone.lua, radio.lua, walkie.lua, speakers.lua, debug.lua. `ui_page 'html/index.html'`, `nui_callback_strict_mode 'true'`, `dependency 'whip_core'`, `whip_requires '1.0'`, `whip_updates 'WHIPFX/whip_voice'`, `lua54 'yes'`, version `1.0.0`.
- `stream/prop_megaphone_01.ydr` replaces GTA's megaphone model everywhere (the "HUSH PA-30").
- `bin/` (downloads) and `service/` are never sent to players.
- Licence: LGPL-3.0; downloaded LiveKit server Apache 2.0; bundled livekit-client (Apache 2.0) and three.js r170 (MIT).

## Installation and server.cfg

Requirements: whip_core; FXServer 64-bit Windows or Linux, FiveM Legacy artifact 38435+ or GTA V Enhanced; voice ports open inbound; FiveM's own voice off.

```cfg
set mumble_disableServer true                     # Legacy only; turns off FiveM's Mumble (no effect on Enhanced)
add_unsafe_child_process_permission whip_voice    # above ensure whip_voice; required for the built-in server
ensure whip_voice                                 # after ensure whip_core
```

- `add_unsafe_child_process_permission whip_voice` lets the resource spawn LiveKit, the voice bot (Node), Windows `tar` and PowerShell (unpacking, reading the firewall). Without it the console prints the line to add. Not needed with your own voice server.
- FiveM's own voice must be off. Legacy: `set mumble_disableServer true` (WHIP's Legacy recipe writes it). Enhanced: off unless `voice_internal` or `voice_external_connect` is in server.cfg (both set `sv_voiceChat`); leave them out. `sv_mumble` alone does not count. whip_voice checks at every start (red console line) and `/voicecheck` fails (`server/check.lua:45-61`; platform from convar `whip_platform`, default `legacy`).
- Remove pma-voice / mumble-voip when using whip_voice (whip_core docs migration table).

Voice ports (inbound):

| Port | Use |
|---|---|
| UDP 7882-7893 | voices |
| TCP 7881 | voices when a player's network blocks UDP |

- Windows Firewall: click Allow for `livekit-server.exe` (tick Public on a server), or run `whip_voice\service\Open voice ports.bat` (asks for admin; also removes a Block rule created by clicking Cancel). Custom ports: `"Open voice ports.bat" -Udp 7982-7993 -Tcp 7981`. If FXServer itself runs as administrator, whip_voice opens the ports at start itself. No restart needed after opening.
- Host firewall (OVH, Hetzner Cloud, AWS security groups, Azure, GCP): allow like 30120. Router: forward. Linux ufw: `ufw allow 7882:7893/udp`, `ufw allow 7881/tcp`.
- Signalling never uses these ports (goes through the FiveM connection). Rented hosting that can't open ports: use your own voice server elsewhere.

## Convars

All server-side, plain `set` (never `setr`/`sets` for secrets), before `ensure whip_voice`.

| Convar | Default | Meaning |
|---|---|---|
| `whip_voice_udp` | `7882-7893` | UDP port or range for voices (built-in) |
| `whip_voice_tcp` | `7881` | TCP fallback port (built-in) |
| `whip_voice_ip` | found by asking the internet | public IPv4 players send voices to; must be dotted IPv4 or the start fails (`builtin.js:129`) |
| `whip_voice_api` | `http://127.0.0.1:7880` | where the voice server's API/signalling listens (built-in: this machine only); with your own server, where FiveM reaches its API |
| `whip_voice_bot` | `true` | `false`: built-in mode does not install/run the voice bot (no lore calls/lines/speakers) |
| `whip_voicebot_url` | `http://127.0.0.1:7899` | where the voice bot listens |
| `whip_voicebot_token` | `''` | shared secret with a self-run bot (own-server mode only; built-in generates its own) |
| `whip_voice_url` | `''` | set = your own voice server (`wss://` with valid certificate); built-in stays off |
| `whip_voice_key` / `whip_voice_secret` | `''` | LiveKit API key pair for your own server |
| `whip_platform` | `legacy` | read by the FiveM-voice check (`enhanced` checks `sv_voiceChat`) |

Two FXServers on one machine need separate ports for the second: e.g. `whip_voice_udp "7982-7993"`, `whip_voice_tcp "7981"`, `whip_voice_api "http://127.0.0.1:7980"`, `whip_voicebot_url "http://127.0.0.1:7999"`.

The client also reads `GetConvar('whip_voice_secret')` during `/voicecheck` to detect a leaked secret (`client/main.lua:411`): if set with `setr`, the check reports "players can read whip_voice_secret".

## The built-in voice server

- First start: downloads LiveKit **1.13.7** (~20 MB) into `whip_voice/bin`, verifies SHA-256 against the pinned checksum (`builtin.js:55-58`), starts it with **new random keys every start** (key `whip<12 hex>`, never written to disk; passed to Lua by local event `whip_voice:builtin:state`).
- Then, in the background, the voice bot: its own Node.js **22.19.0** plus npm packages (~100 MB total, checksummed) into `bin/voicebot/app`; reinstalled when whip_voice's copy changes (stamp file `.whip-stamp`). Voice works meanwhile. Needs HTTPS to github.com, nodejs.org, registry.npmjs.org.
- Console lines: `built-in voice server: downloading LiveKit 1.13.7 ...`, `... is running. Players' games send voices to UDP 7882-7893 ...`, `voice room whipvoice-xxxxxxxx open`, `voice bot: running (lore characters can phone players)`.
- Phases (`VoiceBuiltin.state.phase`): `off`, `starting`, `downloading`, `ready`, `restarting`, `failed`; bot phases include `off`, `installing`, `ready`.
- A child that stops by itself is restarted; after **five stops in a row** it is left stopped (`builtin.js:356-518`). Logs: `whip_voice/bin/logs/livekit.log`, `voicebot-install.log`, bot log; each rotated at 10 MB (old kept as `.old`).
- Replacing the whip_voice folder on update deletes `bin`, so the next start downloads again.
- If the bot restarts, every voice bot is removed with `onDone('failed')`; if LiveKit restarts, a new room opens and bots are removed with `'failed'`.
- The built-in bot gets `Config.VoiceBot` (maxCalls, audioLinks, maxSeconds, maxMB) written into its config.json at start (`server/builtin.lua:121-127`; `maxMB` clamped 0.1–64). Restart whip_voice after changing them.

## Your own voice server, and running the voice bot yourself

```cfg
set whip_voice_url    "wss://your-project.livekit.cloud"
set whip_voice_key    "API..."
set whip_voice_secret "..."
set whip_voice_api    "https://your-project.livekit.cloud"
```

- Players connect directly, so `whip_voice_url` must be `wss://` with a valid certificate. A self-hosted HTTPS front must pass everything to LiveKit port 7880 with WebSockets.
- `setr`/`sets` for the secret sends it to every client: rotate the key pair if that happened.
- The voice bot is then yours (it must run on the FiveM machine, as it reads `@resource/...` files from disk):
  1. Install Node.js 22; copy `whip_voice/service/voicebot` elsewhere; `npm ci --omit=dev`.
  2. `config.json` beside `bot.mjs`: `{ "listen": "127.0.0.1:7899", "token": "<24+ random chars>" }`. Optional: `maxCalls` (30; 1–200), `audioLinks` (`["https://r2.fivemanage.com/"]`), `maxSeconds` (120; 1–600), `maxBytes` (15 MB; 64 KB–64 MB), `musicSeconds` (600; ≤1200), `musicBytes` (40 MB; ≤100 MB). `listen` must be on 127.0.0.1 or the bot refuses to start (`bot.mjs:81-84`).
  3. `node bot.mjs`, kept running (NSSM / systemd).
  4. server.cfg: `set whip_voicebot_token "<same token>"`, plus `whip_voicebot_url` if not the default.
- Bot HTTP API (Bearer token): `GET /health` → `{ ok, version, calls, max }`; `POST /calls`; `POST /calls/:id/allow`; `POST /calls/:id/play`; `POST /calls/:id/stop`; `GET /calls/:id` → `{ state, playedMs, duration }`; `DELETE /calls/:id`. Over `maxCalls` it answers 429 (`busy`). Bot version in this source: `1.5.0` (`bot.mjs:58`).
- Never share `whip_voice_secret`, `whip_voicebot_token` or the bot's config.json.

## Player controls, commands and per-player settings

| Key mapping (FiveM binding) | Label | Default | Notes |
|---|---|---|---|
| `+whip_voice_talk` | `Voice: push to talk` | `N` (`Config.PushToTalkKey`) | blue HUD circle |
| `+whip_voice_radio` | `Voice: radio push to talk` | `CAPITAL` (`Config.Radio.PushToTalkKey`) | only while the radio is on; orange HUD; people nearby still hear you |
| `whip_cyclevoice` (whip_core) | `Cycle Voice Range` | `Z` | whisper/normal/shout; ignored unless `IsGameInputFree()` |
| pad action `talk` | `Talk (hold)` | LB + A (`slot = 'lb_a'`) | registered with `RegisterPadAction`, `menus = true` |
| pad action `radio` | `Radio (hold)` | LB + X (`slot = 'lb_x'`) | same |

- Push-to-talk is not gated by `IsGameInputFree` (works while aiming/placing); FiveM blocks bindings while a text box has focus. The mic stays open 200 ms after release (`TAIL_MS`). Dying (unless `Config.DeadCanTalk`) or logging out stops talking on both keys.
- Players rebind in Settings > Key Bindings > FiveM; controller combos on the pause menu's Controller screen.
- First join: FiveM asks for microphone permission; its prompt takes the mouse only while the F8 console is open (F8, Allow, close F8). Until then they hear but cannot talk; after 15 s whip_voice tells them how; `/voicecheck` lists them as "can hear but not talk".

Commands:

| Command | Side | Gate | Does |
|---|---|---|---|
| `/voicecheck` / `voicecheck` | server (`Whip.command`, `dev = true, whileDead = true`) | server console, or `whip.devtools` with developer mode on | full diagnosis (see Diagnostics) |
| `/voicestatus` / `voicestatus` | server (`dev = true, whileDead = true`) | same | voice server state, bot state, API address, room, each connected player (joined, mic live/off, range, voices picked up) |
| `/voicevolume [0-200]` | client `RegisterCommand` | everyone | sets how loud other players are (100 normal, 0 mutes); no argument shows the current value. Chat suggestion added on `whip_core:player:loaded` |
| `/voicedebug` | client | `whip_core:devtools:checkAccess` callback | toggles an overlay of each voice's path (muffled by what, heard from which doorway) and the doors/windows of your building |
| `/lorecall <recording> [loreKey]` | whip_phone server (`dev = true, console = false`) | dev tools on | see Lore phone calls |

Per-player settings (pause menu > Settings > Server, group `Chat & voice`, via `Whip.playerSetting`; values kept in client KVP on the player's PC):

| Setting key | Label | Type / range | Default | KVP |
|---|---|---|---|---|
| `voice.volume` | Voice volume | slider 0–200 step 5 % | 100 | `whip_voice:volume` (same as `/voicevolume`) |
| `voice.callVolume` | Phone call volume | slider 0–100 step 5 % | 100 | `whip_voice:callVolume`; applies to every line except the radio; whip_phone's Settings > Sounds > Call volume reads/writes it via Get/SetPlayerSetting |
| `voice.radioVolume` | Radio volume | slider 0–100 step 10 % | 80 | `whip_voice:radioVolume` (also the radio's knob) |
| `voice.noiseSuppression` | Background noise suppression | toggle | `Config.Quality.noiseSuppression` | `whip_voice:noiseSuppression` (`on`/`off`, deleted when equal to the server default); change applies at once with a moment's silence |

Also KVP `whip_voice:radioFreq`: last frequency used (shown while the radio is off).

## Items: megaphone, radio, speaker

Registered with `core:RegisterItem` inside `Whip.register` (again on every whip_core restart). The keys belong to "the voice system": a replacement voice resource registers the same keys; whip lets the first registrant own a key. Pictures `html/img/items/megaphone.png`, `radio.png`, `speaker.webp`. Give like any item: `Whip.core:AddItem(source, 'radio', 1)`.

| Key | name | weight | type | stack | usable | prop (dropped) |
|---|---|---|---|---|---|---|
| `megaphone` | Megaphone | 1.2 | tool | false | true | `prop_megaphone_01` |
| `radio` | Radio | 0.4 | tool | false | true | `prop_cs_walkie_talkie` |
| `speaker` | Speaker | 6.0 | tool | false | true | `Config.Speaker.model` (`ba_prop_battle_club_speaker_small`) |

All three use handlers return `false` (item kept).

### Megaphone
- Use toggles up/down (`core:RegisterUseHandler('megaphone')`). Up: server sets `Megaphone.on[src]`, range × `Config.Megaphone.rangeMultiplier` (6), effect `'megaphone'` (bullhorn) sent with hear lists; client plays whip_core emote `megaphone` (upper body, can walk).
- Goes down: used again; emote ends any other way (X, entering a car, drawing a weapon, a fall; client polls every 250 ms and sends `whip_voice:server:megaphoneDown`); emote refused at start; last megaphone leaves pockets (`whip_core:item:removed` with `count <= 0`); died; logout; drop; whip_voice stopping.
- A closed car takes `Config.Megaphone.carMuffle` (4 dB) off a megaphone voice instead of `Config.Muffle.car` (9); each in a different car takes 1.8× this.

### Radio (walkie-talkie)
- Use opens the 3D radio (bottom right) via `whip_voice:client:walkie` `{ on, freq, speaker, min, max }`. Right knob: power (click) and volume (drag/scroll); middle knob: channel 100–999 = frequency; side bar: push to talk; grey top button: speaker. Esc (or pad B/Start) puts it away; it keeps working. Player stands still while it is open (controls blocked).
- Controller while open: D-pad up/down channel (held runs, 10 at a time after a while), left/right volume, A power, RB held talk, X speaker, Y key beeps on/off, B/Start close. LB + X still talks.
- Each frequency is a shared line `radio:<freq>` (track `radio`, `sameWorld = true`, `pickup = false`, `minMembers = 1`, `quality = { clear = Config.Radio.clearWithin, range = Config.Radio.maxRange }`, `speakerRange = Config.Radio.speakerRange`, recipe `{ radio(static, distortion), beeps }`), made by the first radio tuned in and gone with the last (`server/radio.lua:30-44`).
- Server checks: turning on needs `HasItem(src, 'radio')` (else `'You have no radio'`); frequency must be an integer in range (else `'That is not a frequency'`). The SecureEvent `whip_voice:server:radio` uses an `id` param (integer only, never rounded) and is **not** `whileDead`: while down a player cannot open, change or talk on it, but a radio left on stays on and keeps playing (speaker too). Any refusal re-sends the true state (`whip_voice:client:radioState`).
- Speaker (`whip_voice:server:radioSpeaker`): only while on (`'The radio is off'`); the radio's received audio plays from the holder's position for people within `speakerRange` (8 m); not louder for the holder; someone on the same frequency hears it only on their own radio, never twice. One way: no pickup.
- Off when the last radio leaves pockets or on logout (not on death).
- Range: clear to 500 m, breaking up with static/garble to silence at 1500 m; only the same routing bucket.
- Emotes: `Config.Radio.holdEmote = 'walkie'` while the radio is on screen; `talkEmote = 'radio'` (hand to shoulder mic) while talking, unless already in another emote; `''` disables either.

### Speaker
- Use: checks per-character limit (`Config.Speaker.maxPerPlayer`, 3: `'You have 3 speakers out already'`) and server limit (`maxPlaced`, 64: `'There are too many speakers out'`), then runs whip_core's `PlaceObject(model, { label = 'Speaker', vehicles = true })` (wheel turns, arrows raise; ground, table, car roof/bed). A pending use expires after 300 s (`'Use the speaker again'`).
- Placement checks (`server/speakers.lua:207-246`): spot within 12 m of the player; on a car: car exists and is a vehicle, within 17 m, offset ≤ 6 m from the car's origin; the exact same item (by slot address and `metadata.uid`) still there; then `StoreTake` + `SavePlayer` before the speaker is recorded (never duplicated).
- Shown to everyone as a whip_core prop set `speaker:<id>` (`ShowPropSet`, `drawDistance = Config.Speaker.drawDistance`, 300, max 500); on a car it is attached and rides it.
- A prompt on its back (anyone within 3.5 m server-side may use it): Song link (dialog), Play, Stop (1.2 s fade), Volume (0–200 %), Range (5 to `maxRange` m, 300 max), Pick up. Server event `whip_voice:server:speaker` with `what` ∈ `link`, `play`, `stop`, `volume`, `range`, `pickup`.
- Song link rules (`Speakers.linkProblem`): ≤255 chars; must start with an entry of `Config.Speaker.links` (default `https://r2.fivemanage.com/`); rest `[%w%-%._/]+`, no `..`; `.mp3`, `.ogg` or `.wav`. Messages: `Give it a song's link`, `A song is an .mp3, .ogg or .wav link`, `Only links starting with ... are played`.
- Plays as a whip_voice world voice with `music = true`, on a loop (needs voice bot 1.5.0+).
- Item metadata carries the setup: `speakerLink`, `speakerVolume`, `speakerRange` (restored when put down again).
- Persistence: server KVP `whip_voice_speakers`. On restart every speaker out goes back to the character who placed it via `GiveOnLogin` (pockets now, or next login; at their feet if full); one with no findable owner is dropped as a ground item where it last was. A speaker whose car is gone for 10 s drops as a ground item at the car's last position.

## config.lua reference

`whip_voice/config.lua` is a shared script (sent to clients): never put secrets in it.

| Key | Default | Meaning |
|---|---|---|
| `Config.PushToTalkKey` | `'N'` | default talk key |
| `Config.Ranges.whisper / normal / shout` | 3.0 / 8.0 / 20.0 | metres; fade smoothly to silence at the edge |
| `Config.FullVolumeWithin` | 1.0 | full volume within this; never more than 15 % of a range |
| `Config.SideSeparation` | 6 | dB quieter in the far ear on top of 3D (0 = 3D only, 12 strong) |
| `Config.DeadCanTalk` | false | downed players always hear; talk only if true |
| `Config.MaxVoices` | 100 | most voices one listener is connected to (nearest); `Audibility.CAP` |
| `Config.Megaphone.rangeMultiplier` | 6 | |
| `Config.Megaphone.carMuffle` | 4 | dB |
| `Config.Radio.PushToTalkKey` | `'CAPITAL'` | |
| `Config.Radio.clearWithin` / `maxRange` | 500 / 1500 | metres |
| `Config.Radio.minFrequency` / `maxFrequency` | 100 / 999 | |
| `Config.Radio.bitrateKbps` | 24 | |
| `Config.Radio.holdEmote` / `talkEmote` | `'walkie'` / `'radio'` | `''` for none |
| `Config.Radio.staticVolume` | 0.06 | 0–1 |
| `Config.Radio.distortion` | 1.0 | 0–1.5 |
| `Config.Radio.speakerRange` | 8 | metres |
| `Config.Radio.uiSounds` | true | key/power beeps (talk and roger beeps stay) |
| `Config.Speaker.model` | `'ba_prop_battle_club_speaker_small'` | |
| `Config.Speaker.links` | `{ 'https://r2.fivemanage.com/' }` | only links it plays |
| `Config.Speaker.volume` / `range` | 100 / 30 | new speaker defaults |
| `Config.Speaker.maxRange` | 300 | max 300 (code falls back to 100 if unset) |
| `Config.Speaker.drawDistance` | 300 | max 500 |
| `Config.Speaker.maxPerPlayer` / `maxPlaced` | 3 / 64 | per character / server |
| `Config.Environment.rooms / walls / cars / water / echo` | true | each effect switchable |
| `Config.Environment.headphone3D` | true | false = plain panning |
| `Config.Muffle.doorway / door / window / wall / around / car` | 3 / 12 / 12 / 14 / 6 / 9 | dB |
| `Config.Quality.bitrateKbps` | 64 | |
| `Config.Quality.noiseSuppression` | true | default only; players can override |
| `Config.Quality.autoGain` | false | |
| `Config.Quality.echoCancellation` | false | |
| `Config.Quality.packetLossProtection` | false | FEC/redundancy, ~20 ms delay |
| `Config.Quality.silentWhenQuiet` | false | send nothing while the key is up; first word ~20-40 ms late |
| `Config.CrowdQuality` | `{ { listeners = 40, bitrateKbps = 40 }, { listeners = 80, bitrateKbps = 24 } }` | lower bitrate for widely heard voices; recovers 5 listeners below the line (`Audibility.CROWD_BACK`); delete lines to disable |
| `Config.VoiceBot.WaitSeconds` | 5 | a bot request past maxCalls waits this long, retrying every 500 ms |
| `Config.VoiceBot.maxCalls` | 30 | built-in bot only |
| `Config.VoiceBot.audioLinks` | `{ 'https://r2.fivemanage.com/' }` | sites recordings may come from; `@resource` files always work |
| `Config.VoiceBot.maxSeconds` / `maxMB` | 120 / 15 | |

Outdoor bending: a post ~1 dB, a corner just passed 2–4 dB, a right angle `around` (6), more for a U-turn; each corner adds its own; distance fade is separate.

## How hearing is decided (server rules)

From `server/audibility.lua`, `server/hearing.lua`, `server/players.lua`:
- A listener hears a speaker when: same routing bucket, not the same player, speaker can speak (mic live; alive unless `DeadCanTalk`; character loaded), and within the speaker's range + margin. Range = `Config.Ranges[range]` × megaphone multiplier while up.
- `MARGIN = 15` m connected ahead of the range (plus 1 s of closing speed for fast cars); let go after `HOLD_MS = 3000` past range + margin. The audible fade to the exact range is done on the listener's machine, so a modified client could hear up to 15 m past range.
- At most `Config.MaxVoices` nearest speakers; in a crowd over the cap a connected voice keeps its place unless a newcomer is 3 m closer (`STAY`).
- Down/up comes only from whip_core's server events `whip_core:player:died` / `revived` (not the client-writable state bag).
- Logout keeps the LiveKit connection (character screen is another bucket) but the player hears/is heard by no one until a character loads, and is removed from every line (`'logout'`).
- Range key: client fires `whip_voice:server:setRange` on whip_core's local `whip_core:voice:rangeChanged`; server accepts only `whisper`/`normal`/`shout`.
- Player token: 120 s TTL, may publish only a microphone, no data; can subscribe only to voices whose owner allows them (every voice starts allowing nobody).

## whip_core: the voice-system registry and HUD exports

### RegisterVoiceSystem(info) — SERVER (whip_core)
- `info.label` string (≤60 chars; default the resource name). `info.features` table: `lines`, `speaker`, `pickup`, `quality` (booleans; anything but `true` = false), `sounds` (`'full'` or `'basic'`; anything else = `'basic'`).
- Caller is the registering resource (`Registry.caller()`). Call inside `Whip.register` so it re-registers when whip_core restarts. Released when the resource stops.
- Returns `true`, or `false, '<res> is already the voice system: run one voice resource, not both'` (another live one holds it), or `false, 'RegisterVoiceSystem takes { label = ..., features = { ... } }'`.
- On change, broadcasts net event `whip_core:client:voiceSystem` (view or `false`); also sent to each player on character load.
- A voice system must: implement the line exports with the same arguments (as far as its features allow), register the `radio` and `megaphone` items, turn `whip_core:voice:rangeChanged` into metres, and light the HUD with `SetVoiceTalking`.

```lua
Whip.register(function()
    local ok, why = exports.whip_core:RegisterVoiceSystem({ label = 'my_voice',
        features = { lines = true, speaker = true, pickup = false, quality = false, sounds = 'basic' } })
    if not ok then print('voice stays off: ' .. why) return end
end)
```

### GetVoiceSystem() — BOTH (whip_core)
- Returns `{ resource, label, features = { lines, speaker, pickup, quality, sounds } }` (a copy), or `false` when none runs. Server: false if the holder is no longer alive in the Registry. Client: false unless `GetResourceState(resource) == 'started'`.
- Client local event `whip_core:voice:systemChanged` payload `{ resource, label, features }` (all nil when none). Fired when the server announces a different resource and on `onClientResourceStop` of the current one.

### Whip.voiceSystem() — BOTH (satellite)
- `Whip.call('GetVoiceSystem')`, then returns the table only if `resource` is a string and started; else `false`.

### Whip.voice(name, ...) — BOTH (satellite)
- Calls `exports[<voice resource>][name](...)` under `pcall`. Returns the export's first two results, or `false, 'no voice system is running'`, or `false, '<res>: <error>'` if it threw.
- The export sees **your** resource as `GetInvokingResource()`, so lines/bots/sounds you create are owned by you.
- Use from the server: all line/bot/world-voice exports are server exports. whip_voice's only client export is `HearsEntity`.

```lua
local lineId, why = Whip.voice('OpenLine', { members = { visitor, guard } })
if not lineId then return false, why end
```

### HUD and range exports (whip_core client, `client/stats.lua`)
- `SetVoiceTalking(talking, mode?)` — CLIENT. `mode = 'radio'` shows an orange gauge with a walkie icon; else blue mic. Held by the calling resource; cleared if it stops.
- `GetVoiceLevel()` — CLIENT. 20 (whisper), 50 (normal), 100 (shout).
- `GetVoiceName()` — CLIENT. `'Whisper'`, `'Normal'`, `'Shout'`.
- Local event `whip_core:voice:rangeChanged` `{ index = 1|2|3, name, level }` when Z is pressed. Without a voice system the bar is display-only.

## Lines API (whip_voice server exports)

A line = a set of players who hear each other anywhere, through a recipe. Every export returns its value or `true`, or `false, why`; never `nil`. Call through `Whip.voice(name, ...)`. Exports read `GetInvokingResource()` first; calls from no resource return `false, 'call it from another resource'`. Only the owning resource may touch a line (`'that line is not yours'`); unknown/closed ids give `'no such line (closed?)'`.

Line behaviour:
- `track = 'voice'` carries the normal talk key; `'radio'` the radio key. People around members still hear them normally.
- Members hear the others in both ears, through the recipe, at their own call volume (radio lines: radio volume).
- On speaker: the line also plays from that member's device in 3D for people near (walls, doors, distance apply), within `speakerRange`; not louder for the owner. A modified game can be connected up to 3 m further, held 1 s (`margin = 3, hold = 1000` for other resources' lines; whip_voice's radio uses 15 m / 3000 ms).
- `pickup = true`: on speaker, people near the device are heard on the line, only within their own voice range of the device and never beyond `speakerRange`, quieter with distance, by the nearest device if near two.
- Muted: the line hears neither the member nor anyone near their device.
- Downed members stay and hear but cannot talk (`DeadCanTalk`); a downed member's device on speaker keeps playing.
- Across routing buckets unless `sameWorld = true`. Without `quality` a line is clear at any distance.
- Two lines between the same two players on the same track: heard once, through the line already in use (or the oldest).
- Members persist through a reconnect (hear nothing meanwhile). They leave by themselves on disconnect (`'left'`) or logout (`'logout'`).
- Limits: 32 members per line, 500 open lines per resource.
- Callbacks run in their own thread, only while the owner is still started; errors are printed and swallowed.
- When the owner stops, its lines close silently (no callbacks) and its sounds are removed. When whip_voice restarts, every line is gone: handle `onResourceStop`/`onResourceStart` for `'whip_voice'`.

### OpenLine(spec) — SERVER
| Field | Type | Default | Notes |
|---|---|---|---|
| `members` | number[] | `{}` | server ids; each must have a whip character loaded (`GetPlayer`), else `'member X is not a player with a character loaded'`; max 32 |
| `track` | `'voice'`/`'radio'` | `'voice'` | else `"track is 'voice' or 'radio'"` |
| `recipe` | table or string | plain voice | block list, or a `RegisterSound` name (yours short, anyone's full `'<res>:<name>'`); errors prefixed `'recipe: '` |
| `speakerRange` | number | 8 | clamped 1–30 |
| `pickup` | boolean | false | |
| `quality` | `{ clear, range }` | none | both numbers, else `'quality is { clear = metres, range = metres }'`; clear 0–100000, range 1–100000, range forced > clear |
| `sameWorld` | boolean | false | |
| `minMembers` | number | 2 | clamped 1–64, floored; checked only when a member leaves |
| `onEnd(lineId, why)` | function | | closed by itself: `'empty'`. Not called on `CloseLine` or owner stop |
| `onLeave(lineId, src, why)` | function | | `'left'`, `'logout'`, `'removed'` (a voice bot leaving passes its own reason, e.g. `'done'`) |

Returns: line id string (`'<8 hex>-<n>'`, unique per whip_voice start), or `false, why` (`'a line is a table: { members, recipe, ... }'`, `'members is a list of server ids'`, `'onEnd is a function'`, `'at most 32 members'`, `'at most 500 lines open at once'`).

```lua
local lineId, why = Whip.voice('OpenLine', {
    members = { caller, callee }, pickup = true, minMembers = 2,
    recipe = { { 'band', low = 300, high = 3400 }, { 'compress', threshold = -24, ratio = 4 } },
    onEnd = function(id, reason) print(('call %s over: %s'):format(id, reason)) end,
})
```

### CloseLine(lineId) — SERVER
Everyone lets go at once; voice bots on it are removed (`onDone('lineClosed')`). Already closed: `true`. No `onEnd`.

### AddLineMember(lineId, src) / RemoveLineMember(lineId, src) — SERVER
- Add: must have a character loaded (`'not a player with a character loaded'`), max 32 (`'at most 32 members'`). Adding an existing member returns `true`. On a closed line: `false, 'no such line (closed?)'` (a `minMembers = 1` line closes with its last member: open a new one).
- Remove: not a member returns `true`. Otherwise `onLeave(..., 'removed')`, and `onEnd('empty')` if members < `minMembers`.

### SetLineSpeaker(lineId, src, on) / SetLineMuted(lineId, src, on) — SERVER
`on == true` only. Not a member: `false, 'not on that line'`. Speaker-off and mute-on take effect immediately.

### SetLineRecipe(lineId, recipe) — SERVER
New recipe (list or sound name); every listener rebuilds in place. `false, 'recipe: <why>'` on a bad recipe.

### GetLine(lineId) — SERVER
`{ id, track, members = { [src] = { speaker, muted } }, pickup, sameWorld, speakerRange, minMembers }`. Bot members appear keyed `'bot:<n>'`.

### RegisterSound(name, recipe) — SERVER
`name` matches `^[%w_%-]+$`, ≤32 chars (else `"a sound's name is letters, digits, - and _"`). Returns the full name `'<your_resource>:<name>'`. Re-registering replaces. Removed when your resource stops.

### IsVoiceReady(src) — SERVER
`true` when joined to the room with a live microphone; else `false, 'not connected to voice'` or `false, 'no microphone'`.

```lua
Whip.voice('SetLineSpeaker', lineId, callee, true)
Whip.voice('SetLineMuted', lineId, caller, true)
Whip.voice('CloseLine', lineId)
```

Dispatch example: `OpenLine({ track = 'radio', minMembers = 1, recipe = { { 'radio', static = 0 }, { 'beeps' } } })`, then `AddLineMember` as officers clock on, `RemoveLineMember` as they clock off.

whip_phone's calls use: `members = { caller, callee }, track = 'voice', pickup = true, minMembers = 2, recipe = Config.CallSound, speakerRange = Config.SpeakerRange or 8` (`whip_phone/server/calls.lua:131`).

## Sound recipes and blocks

- A recipe is a list of blocks in order. Each block is `{ 'name', key = value }` or `{ type = 'name', ... }`. Data only; validated on the server (`Lines.checkRecipe`) and again in the page (`html/js/fx.js`).
- Missing setting → default; number out of range → clamped; non-number → refused (`'block N (name): key is a number'`); word not in the list → refused (`'... key is one of a, b'`); unknown block → `'block N: there is no block called X'`; non-table block → `'block N is not a table'`.
- Limits (`SoundLimits`): 24 blocks; 4 "source" blocks (`noise`, `breakup`, `radio`, `hum`, `chorus`, `vibrato`, `tremolo`, `ringmod`, `reverb`); data depth 8. Every line ends in a safety limiter.
- Single source of truth: `whip_voice/shared/sound_blocks.lua`, `{ min, max, default }` or word list (first = default).

| Block | Settings `{min, max, default}` |
|---|---|
| `gain` | `db` -60..24, 0 |
| `lowpass` | `hz` 20..20000, 3000; `q` 0.1..30, 0.7 |
| `highpass` | `hz` 20..20000, 300; `q` 0.1..30, 0.7 |
| `bandpass` | `hz` 20..20000, 1200; `q` 0.1..30, 0.7 |
| `notch` | `hz` 20..20000, 1000; `q` 0.1..30, 0.7 |
| `peak` | `hz` 20..20000, 1500; `q` 0.1..30, 1; `db` -30..30, 0 |
| `lowshelf` | `hz` 20..20000, 250; `db` -30..30, 0 |
| `highshelf` | `hz` 20..20000, 4000; `db` -30..30, 0 |
| `band` | `low` 20..20000, 300; `high` 20..20000, 3400; `q` 0.1..30, 0.7 |
| `drive` | `k` 1..50, 2.5; `oversample` `none`/`2x`/`4x` (raises quiet sound too: follow with `gain`) |
| `crush` | `steps` 2..256, 32 |
| `compress` | `threshold` -100..0, -24; `knee` 0..40, 6; `ratio` 1..20, 4; `attack` 0..1, 0.003; `release` 0..1, 0.12 |
| `noise` | `kind` `white`/`pink`/`brown`; `level` 0..0.3, 0.02; `hz` 20..20000, 2500; `q` 0.1..30, 0.7 (only while talking) |
| `breakup` | `static` 0..1, 0.06 (drops out with the line's `quality`) |
| `beeps` | `up` 0..5000, 1250; `down` 0..5000, 1900; `down2` 0..5000, 1450 (0 = that beep off); `level` 0..0.2, 0.05 (one beep on start, two on stop) |
| `pan` | `to` -1..1, 0 |
| `hum` | `hz` 20..400, 50; `level` 0..0.3, 0.02 (only while talking) |
| `echo` | `time` 0.02..2, 0.25 s; `feedback` 0..0.9, 0.35; `mix` 0..1, 0.3 |
| `chorus` | `rate` 0.05..8, 1.2; `depth` 0..0.02, 0.004; `mix` 0..1, 0.5 |
| `vibrato` | `rate` 0.1..12, 5; `depth` 0..0.01, 0.002 |
| `tremolo` | `rate` 0.1..20, 5; `depth` 0..1, 0.5 |
| `ringmod` | `hz` 1..2000, 50; `mix` 0..1, 1 |
| `reverb` | `size` 0.1..4, 1.2 s; `mix` 0..1, 0.25 (one per line, only while talking) |
| `radio` | `static` 0..1, 0.06; `distortion` 0..1.5, 1 (whip_voice's walkie, breaks up with `quality`) |

A voice system with `features.sounds = 'basic'` plays at most a phone or radio filter; check `Whip.voiceSystem().features` before relying on exotic blocks.

## Voice bots API

A voice bot = a recording heard on one of your lines as one more voice (e.g. a lore character on a call). It only talks: never hears the line, nobody near anyone hears it except through a member's device. Requires the voice bot service. Keys are `'bot:<n>'`. Owner-only (`'that voice bot is not yours'`; unknown: `'no such voice bot (gone?)'`). Removed (no `onDone`) when the owner stops; all removed when whip_voice stops.

### CreateVoiceBot({ name, audio }) — SERVER, WAITS
- `name` string (≤80 chars, default `'Caller'`). `audio`: a link starting with one of the bot's `audioLinks` (Fivemanage by default), or `'@resource/path/file.ogg'` from a started resource (mp3/ogg/wav; resource name `[%w_%-%.]+`, path `[%w%-%._/]+`, no `..`; ≤255 chars). Resource files are read by the bot from disk as `file:<full path>`; do **not** list them in `files {}`.
- Joins the room and fetches/validates the recording now. Past `maxCalls` retries every 500 ms up to `Config.VoiceBot.WaitSeconds`.
- Returns `botKey, durationMs`, or `false, why`: `'voice is still starting'`, `'every voice bot line is in use'`, `'only mp3, ogg and wav files are played'`, `'the resource X is not started'`, `'a resource\'s recording is "@resource/folder/file.ogg"'`, `'audio is a recording\'s link, or "@resource/file.ogg"'`, the bot's own refusal text (e.g. `only links starting with ... are accepted`, over 120 s / 15 MB, not readable), or "not running" reasons.
- Bot recordings: mp3, ogg (Vorbis or Opus) or wav; m4a/FLAC refused (`not a recording this can read`).

### PutVoiceBotOnLine(botKey, lineId) — SERVER
Line must be yours (`'no such line of yours'`). Counts as a member for `minMembers`. Already on another line: `'it is on another line'`.

### PlayVoiceBot(botKey, onDone) — SERVER, WAITS
- Returns `durationMs` or `false, why`. The bot waits up to 3 s for an allowed listener to subscribe, then plays.
- `onDone(botKey, why)`: `'done'`, `'removed'`, `'lineClosed'`, `'failed'`. When it finishes, the bot is removed and leaves the line, which may then close: `onDone` and the line's `onEnd` fire at the same moment in no set order.
- If the play request fails the bot is removed with `'failed'` (onDone is called) and the export returns `false, why`.

### RemoveVoiceBot(botKey) — SERVER
`true` (also when already gone). Calls `onDone('removed')` if set.

### VoiceBotStatus() — SERVER, WAITS
The bot's `/health`: `{ ok, version, calls, max }`, or `false, why`.

Guidance: create the bot before you need it (before the phone rings), put it on the line when answered, then play. Max 30 bots at once including world voices.

## World voices API

A world voice plays recordings from entities or fixed spots, heard like a player's voice (range, walls, doorways, cars, mouth moving on peds). Used by lore characters, Director speakers and the speaker item. Owner-only; removed when the owner stops. Same `audio` rules as `CreateVoiceBot`. `onDone(key, reason)`: `'done'`, `'stopped'`, `'cut'`, `'removed'`, `'failed'`.

A place (`at`) is one of:

| Form | Meaning |
|---|---|
| `{ netId = n }` | an entity (must exist now), followed as it moves |
| `{ netId = n, offset = vector3(x,y,z), model = 'prop_speaker_06' }` | a spot in the entity's frame, ≤10 m from it; with `model`, sound comes out of that object riding there |
| `{ coords = vector3(x,y,z), model = 'prop_speaker_06' }` | a fixed spot; with `model`, each client finds its own copy of that object there so its walls/room are used |

`at` may be a list of up to 32 places: one sound heard from every place in step; levels add by power (two equal speakers +3 dB). Errors: `'at is { netId = n, offset?, model? }, { coords = vector3, model? }, or a list of them'`, `'no entity with that netId'`, `'offset is a vector3 within 10 m of the entity'`, `'coords is a vector3 (x, y, z)'`, `'at most 32 places'`, `'place N: ...'`. `model` is a name (≤64 chars) or hash.

### CreateWorldVoice({ name, at, range, bucket, music }) — SERVER, WAITS
`range` 2–300 m (default 12); `bucket` routing bucket for fixed spots (default 0; entities use their own); `music = true` = heard as music (arrives late by distance at the speed of sound, Doppler on moving sources (~1.5 semitones at 110 km/h), air absorbs treble with distance, more echo far off outdoors, two paths round corners). Returns `key` or `false, why`. Silent while none of its places exist on the server (after respawning an NPC, call `MoveWorldVoice`).

### PlayWorldVoice(key, audio, onDone?, opts?) — SERVER, WAITS
- Plays a recording, cutting off one already playing (its `onDone('cut')`). Returns `durationMs` or `false, why`.
- `opts.loop = true` until `StopWorldVoice`; `opts.music = true` uses the bot's music limits (`musicSeconds`/`musicBytes`, 10 min / 40 MB) instead of a line's 2 min / 15 MB; `opts.fadeIn` ms from silence (0–30000).
- A bot that is on a line (not a world voice): `'that voice bot is on a line, not in the world (PlayVoiceBot)'`.

### StopWorldVoice(key, fadeMs?) — SERVER, WAITS
Stops, faded over `fadeMs` (0–30000, done by the bot so everyone hears the same fade). `onDone('stopped')`. Nothing playing: `true`. Bot older than 1.5.0: `false, 'the voice bot is older than 1.5.0 and cannot stop a recording: run the voice setup again'`.

### SetWorldVoiceSound(key, recipe | false) — SERVER
A recipe (same validation as lines) or `false`/nil for its plain sound. A megaphone up overrides it.

### MoveWorldVoice(key, at) — SERVER
New places; keeps range, megaphone, sound, bucket.

### SetWorldVoiceRange(key, range, fullWithin?) — SERVER
`range` must be a number (`'range is a number of metres'`), clamped 2–300. `fullWithin` >0 and ≤ range, else the usual (~1 m).

### SetWorldVoiceMegaphone(key, on) — SERVER
Range × `Config.Megaphone.rangeMultiplier`, bullhorn sound while up.

### SetWorldVoiceRadio(key, frequency | false) — SERVER
Puts it on the radio frequency's shared line (integer 100–999: `'a frequency is a whole number'` / `'a frequency is a whole number from 100 to 999'`), or off with `false`/nil. Heard by players on that frequency in its bucket, breaking up with distance from its entity; people near still hear it in the world.

### RemoveWorldVoice(key) — SERVER
`true` (also when gone). Current `onDone('removed')`.

```lua
CreateThread(function()   -- these exports wait
    local v = Whip.voice('CreateWorldVoice', { name = 'Dispatch', at = { netId = NetworkGetNetworkIdFromEntity(ped) }, range = 8 })
    if not v then return end
    Whip.voice('SetWorldVoiceRadio', v, 100)
    Whip.voice('PlayWorldVoice', v, '@my_story/audio/all_units.ogg')
end)
```

Songs, loops, fades and `StopWorldVoice` need voice bot 1.5.0+.

## Other whip_voice exports and events

### GetPlayerRadio(source) — SERVER
The integer frequency the player's radio is on, or `false` when off.

### HearsEntity(netId) — CLIENT
`hears, talking`: whether this client hears the world voice of that entity, and whether sound is coming out of it now. Used by whip_core's speech bubbles to hold a lore line's subtitle until audio starts.

### Local client event `whip_voice:entityTalking` (netId, on)
Fired when a heard world voice's entity starts/stops producing sound.

## Lore phone calls

A lore character (Director named NPC) phones a player and a recording plays into the call (whip_phone + whip_voice + voice bot).
- Recording: mp3, ogg or wav, ≤2 min (`maxSeconds` 120) and ≤15 MB (`maxMB`). Either a Fivemanage link (tick Retention Exempt on upload) or `@my_story/audio/irwin_intro.ogg` in an ensured resource (not in `files {}`). Other sites: add to `Config.VoiceBot.audioLinks` (own server: the bot's config.json).
- `/lorecall <recording> [loreKey]` (whip_phone, in game only, dev tools on): first lore character unless a key is given; you need a phone with a SIM on you. Chat replies: `Heard it all: the voice bot works.`, `You hung up before it finished.`, `You declined it.`, `Nobody answered.`, `It was called off.`, `You are already on a call.`, `You need a phone with a SIM on you.`, `It could not call: <why>`.
- `LorePhones.call` (whip_phone) creates the bot via `Whip.voice('CreateVoiceBot')` before ringing; a down player counts as busy; outcome callback values `'answered'`, `'hungup'`, `'declined'`, `'missed'`, `'failed'`, `'cancelled'`; immediate `'busy'`/`'nophone'`. No voice system: `"lore characters' calls need whip_voice and its voice bot"`.
- Director Phone Call card (green Lore group): From (lore character; empty = scenario's own), Recording, To (players). Outcomes: Heard it all, Hung up early, Declined · Missed, Busy · No phone, Didn't work. Several players each get their own call; the card follows the best outcome. In a Test it rings only you.
- Caller picture: Lore characters > Edit picture (Fivemanage link, framed); shown on the call screen, Contacts, Messages, Recents. Accepted sites: `Config.LorePictureLinks` (`/whip` > Settings > Config > Server "Picture links accepted").

## Lore characters speaking (LoreSay, Config.LoreVoice)

Lines (keys): `hello`, `goodbye`, `positive`, `negative`, `bumped`, `hitByCar`, `aimedAt`, `gunfire`, `carStolen`. Each line has variants (≤50 per line, ≤200 total, subtitle ≤160 chars) taken in turn, never the same twice running; a line with no variant isn't said. Variants are set in `/whip` > Director > Lore characters > Audio tab. **Voice-line recordings must be links** starting with `Config.LoreVoice.Links` (mp3/ogg/wav, ≤255 chars); `@resource` paths are not accepted there (`lore_voice.lua:76-93`). The NPC must be in the world (a scenario NPC whose Lore character picker names it). Subtitles show over its head as each player starts hearing the line (at once for players too far to hear).

`Config.LoreVoice` (whip_core config.lua; clamps from `lore_voice.lua:51-63`):

| Key | Default | Clamp | Meaning |
|---|---|---|---|
| `Enabled` | true | | off: `'lore voice lines are switched off (Config.LoreVoice.Enabled)'` |
| `Links` | `{ 'https://r2.fivemanage.com/' }` | must match `^https://host/...` | accepted recording link starts |
| `Range` | 15 | 2–50 | metres its voice carries |
| `GreetRange` | 4 | 1–15 | Hello when a player comes this close |
| `ByeRange` | 10 | 2–50 | Goodbye when a greeted player goes this far |
| `GreetAgainMinutes` | 3 | 0–120 | |
| `ReactAgainSeconds` | 6 | 1–600 | same reaction again only after this |
| `Gestures` | true | | hand gestures while talking |

Internals: the NPC's world voice joins the room when a player is within 40 m, leaves 30 s after nobody is; at least 2.5 s between self-triggered lines; reaction reports must come from within 60 m; queue up to 3, stale after 20 s. A reaction cuts in on whatever it was saying. Settings page: `/whip` > Settings > Config > Emotes, /me and talk ("Lore characters speak", "Voice line links accepted").

### LoreSay(key, line, opts?) — SERVER, WAITS (whip_core)
- `opts.near` server id: its NPC nearest that player; else `opts.npcId`; else the first alive.
- `opts.wait = true`: return once said. `opts.busy`: `'skip'`, `'queue'`, `'cut'` (overrides the line's If talking). `opts.bonus`: 0–250 m extra full-volume reach and subtitle distance (waits 1 s first so newly reached players hear from the start; next line back to normal). `opts.megaphone = true`. `opts.radio`: integer frequency to say it on too (non-integer refused; one whip_voice refuses is said out loud only, with no radio in hand, named in the console). Megaphone/radio last for that line only; radio needs voice bot from whip_voice 1.4.0+.
- Returns `true`, `true, 'queued'`, or `false, why`: `'No lore character called X'`, `'it has no NPC in the world now'`, `'no line "X"'`, `'<name> has no <Label> line'`, `'already talking (this line is set to skip then)'`, `'whip_voice is not running'`, no voice bot; with `wait`, also whip_voice stopped or the NPC gone.
- Call from a thread or handler (it waits while the recording is fetched).

```lua
local ok, why = exports.whip_core:LoreSay('irwin', 'positive', { near = source })
```

Director cards: **Lore Says** (Who, Line, Wait; done/failed) and **Play Custom Voice Line** (Who, Recording link, optional Subtitle, If it is already talking: say it after (default) / cut in / skip, Wait; Said / Could not / Took too long). Both have Bonus range (0–250 m), Through a megaphone, and On the radio: `No` / `On the player's frequency` (via `GetPlayerRadio` of the player the card acts for; off → out loud only, logged) / `On a frequency` (100–999 whole number).

## Director speakers (Play on Speakers / Stop Speakers cards)

- Any prop placed on the Director World tab (+ Prop) can be a speaker; same Group lets one card name them all. Attached to a car/NPC, it plays from it as it moves.
- Play on Speakers (World group): Speakers (props or a group, up to 32), Song link (Fivemanage; mp3/ogg/wav, ≤10 min), Loop, Volume 0–200 %, Heard up to 5–300 m (default 40 in code), Full volume within, Speaker sound 0–100 % (cheap-speaker colouring), Tone (Bass/Mids/Treble ±12 dB), Fade in (s), Wait until it has played (Loop off). Outcomes Done / Could not / Took too long.
- Implemented as one `CreateWorldVoice({ name = 'Speakers', at = places, range, bucket = run.bucket, music = true })` + `SetWorldVoiceRange` + `SetWorldVoiceSound` (`whip_core/server/director/speakers.lua:155-200`). One song per speaker at a time: a new one stops the old. Stop Speakers fades out 0–30 s. Every song a run plays stops when the run ends. Needs voice bot 1.5.0+.

## CheckPicture(url, frame) — SERVER (whip_core)

Checks a profile picture as WHIP takes one (used by whip_phone's contact card). Link must start with `Config.LorePictureLinks`; empty link = no picture. `frame = { x, y, z }`: x, y 0–100 (centre), z zoom 1–3; cleaned (x/y rounded to 0.1, z to 0.01); `{50, 50, 1}` becomes nil. Returns `true, frame|nil` or `false, why`.

## Internal net events, callbacks and state

Client → server (all `core:SecureEvent` registered in `Whip.register`, only while whip_voice is the voice system):

| Event | Params | Rate (ms) / burst | whileDead |
|---|---|---|---|
| `whip_voice:server:state` | `joined` bool, `speaking` bool | 250 / 6 | yes |
| `whip_voice:server:setRange` | `range` enum whisper/normal/shout | 150 / 6 | yes |
| `whip_voice:server:megaphoneDown` | — | 250 / 4 | yes |
| `whip_voice:server:radio` | `on` bool, `freq` id min..max | 150 / 8 | no |
| `whip_voice:server:radioSpeaker` | `on` bool | 250 / 4 | no |
| `whip_voice:server:probe` | nonce id, transport enum udp/tcp/relay/none/unknown, rtt int 0–60000, secretSeen bool, joined bool, why string ≤160 | 500 / 3 | yes |
| `whip_voice:server:placeSpeaker` | x,y (±20000), z (-500..3000), rx,ry,rz (±360), net int 0–65535, ox,oy,oz (±10), orx,ory,orz | 500 / 2 | no |
| `whip_voice:server:speaker` | id, what enum, value string ≤255 | 250 / 4 | no |
| `whip_voice:server:sig` | sock, op, data (plain `onNet` in builtin.js; LiveKit validates) | — | — |

SecureCallbacks: `whip_voice:token` (2000 / 3, whileDead) → `{ url, token }` or `false, why` (`'Voice is unavailable: ...'`, `'They left'`, `'Voice is not set up on this server (whip_voice_key / whip_voice_secret)'`); `whip_voice:speakers` (2000 / 3, whileDead) → speaker views.

Server → client: `whip_voice:client:reconnect`, `:hear` `{ add = {...}, remove = {...} }`, `:allow` (ids, kbps, radioIds), `:line` `{ open, close, add, remove, q, via, level }`, `:megaphone` (on), `:radioState` `{ on, freq, speaker }`, `:walkie` `{ on, freq, speaker, min, max }`, `:probe` (nonce), `:sig`, `:placeSpeaker` (model), `:speakers` (list of `{ id, model, coords, rot, net, offset, carRot, song, playing, volume, range }`).

Server-local: `whip_voice:builtin:state`, `whip_voice:builtin:start`, `whip_voice:builtin:firewall`. whip_voice listens to whip_core's `whip_core:player:loaded`, `:logout`, `:died`, `:revived`, `whip_core:item:removed` (`{ source, item, count }`, count = remaining).

Server KVP: `whip_voice_speakers`. Client KVPs listed under player settings.

## Diagnostics: /voicecheck, /voicestatus, /voicedebug and the problem messages

`/voicecheck` checks top to bottom (an early failure often causes later ones): (1) whip_voice is the voice system and FiveM's own voice is off; (2) the voice server: built-in running and Windows Firewall letting voices in, or the three own-server lines and the key accepted; (3) own server: `https://<voice address>` reachable with a valid certificate; (4) every player probed (4 s): UDP (good), TCP (UDP blocked), relay/none, microphone, and whether their game can read `whip_voice_secret`; (5) the voice bot set up, running, accepting the token. Ends with `Everything checked is right.` or `N thing(s) to fix`.

| Message | Meaning / fix |
|---|---|
| FXServer lets a resource start programs only when server.cfg allows it | add `add_unsafe_child_process_permission whip_voice` above ensure, restart |
| Windows Firewall BLOCKS the voice server | someone clicked Cancel: run `Open voice ports.bat` |
| Windows Firewall: the voice ports are not open yet / does not let voices in | Allow, or `Open voice ports.bat` |
| all players connect over TCP | UDP 7882-7893 blocked: host firewall + Windows Firewall |
| (everyone) is not connected to voice | ports shut |
| some players connect over TCP | their network; nothing on your side |
| something already answers on 127.0.0.1:7880 | another program/another FXServer's whip_voice: change ports |
| does not match its published checksum / answered 403 / could not unpack | download cut/changed or no HTTPS to github.com (nodejs.org, registry.npmjs.org for the bot): restart whip_voice |
| the voice server stopped five times in a row | see `bin/logs/livekit.log`; often a port in use |
| the voice bot: its packages could not be installed | see `bin/logs/voicebot-install.log` |
| *name* is the voice system, so whip_voice is off | another voice resource started first: remove its ensure |
| FiveM's own voice (Mumble) is on | add `set mumble_disableServer true` |
| FiveM's own voice is on (server.cfg has voice_internal ...) | remove those lines (Enhanced) |
| can hear but not talk | player must allow the mic (F8 open), or allow in FiveM settings and reconnect |
| only links starting with ... are accepted | use Fivemanage, `@resource/...`, or extend `Config.VoiceBot.audioLinks` |
| there is no ... / cannot be read | wrong `@resource` path |
| not a recording this can read | not mp3/ogg/wav |
| the voice server is not answering / did not answer | own server: wrong `whip_voice_api` or down |
| `https://...` cannot be reached / is not the voice server | bad certificate or proxy not passing to 7880 with WebSockets |
| refused our key | wrong key/secret pair |
| players can read whip_voice_secret | set with `setr`/`sets`: use `set`, rotate the key |
| no voice bot answers | none running (own-server mode) |
| the voice bot refused whip_voicebot_token / has no whip_voicebot_token line | token mismatch with config.json |

## Writing your own voice system

- Register with `RegisterVoiceSystem` in `Whip.register`; only one runs, the first wins.
- Export the line calls with the same signatures (`OpenLine`, `CloseLine`, `AddLineMember`, `RemoveLineMember`, `SetLineSpeaker`, `SetLineMuted`, `SetLineRecipe`, `GetLine`, `RegisterSound`, `IsVoiceReady`) to the extent of your declared features; honour `GetInvokingResource()` as the owner.
- Register `radio` and `megaphone` items (same keys), listen to `whip_core:voice:rangeChanged`, call `SetVoiceTalking(talking, mode?)`.
- whip_test's voice items test accepts `whip_voice` or `whip_voice_simple` as the running voice system (`whip_test/server/tests/70_voice_items.lua:29`); `whip_voice_simple` is not in this source set.

## Gotchas

1. Never call `exports.whip_voice:*` from your resource; use `Whip.voice(name, ...)`. Direct calls still work only while whip_voice is the voice system; a server may run another.
2. `Whip.voice` returns only the first two results of an export.
3. `CloseLine` never fires `onEnd`, and owner stop fires no callbacks. Only self-closure (`'empty'`) fires `onEnd`.
4. `minMembers` is only checked when someone leaves: `OpenLine` with fewer members than `minMembers` stays open until the first leave.
5. A `minMembers = 1` line closes when its last member leaves; later `AddLineMember` returns `false, 'no such line (closed?)'`.
6. Line members must have a whip character loaded at add time; not being connected to voice yet is fine.
7. Bot-, world-voice- and status-exports WAIT (HTTP to the bot): call them in a thread or handler, never at file scope.
8. `@resource/...` recordings are read from disk by the bot on the server; do not add them to `files {}` (players would download them). The resource must be started.
9. Lore voice lines (Audio tab, LoreSay) accept only links from `Config.LoreVoice.Links`; `@resource` recordings work for phone calls, bots and world voices but not for lore voice lines.
10. A world voice is silent while none of its places exists on the server; after respawning an NPC call `MoveWorldVoice`.
11. `PlayVoiceBot`'s `onDone('done')` and the line's `onEnd('empty')` arrive together in no set order.
12. `config.lua` is shared to clients: secrets belong in server.cfg with plain `set`.
13. The radio SecureEvents are not `whileDead`: a downed player can't change the radio, but a radio already on stays on and they still hear.
14. Built-in mode regenerates keys each start and opens a new room; all lines and bots are lost when whip_voice or its voice server restarts (bots get `'failed'` on voice-server/bot restart, nothing on whip_voice restart).
15. Updating whip_voice by replacing its folder deletes `bin`; the next start re-downloads LiveKit and the bot.
16. `IsVoiceReady` requires a live microphone, not just a connection.
17. Z (range) is ignored while a text input has focus (`IsGameInputFree`); push-to-talk is not.

## Docs vs code

- `#voice-setup-own` says `whip_voice\service\Setup voice server.bat` installs LiveKit, Caddy and the bot as services; no such file exists in `whip_voice/service/` (only `Open voice ports.bat`, `firewall.ps1`, `voicebot/`).
- `#voice-api` describes `IsVoiceReady` as "connected to voice"; code also requires a live microphone and returns `'no microphone'` (`server/lines_api.lua:250-255`). LINES.md matches the code.
- `#voice-api` documents `onLeave` reasons `'left'`, `'logout'`, `'removed'`; a voice bot leaving a line passes its own reason (`'done'`, `'failed'`, `'lineClosed'`, `'removed'`) and world voices leaving a radio line pass `'off'` (`server/bots.lua:276`, `:448`; `server/radio.lua:62`).
- fxmanifest and `server/megaphone.lua` comments say the megaphone gives "3x the range"; `Config.Megaphone.rangeMultiplier` is 6 and docs say 6 (`fxmanifest.lua:30`).
- `/voicecheck`'s header comment says it is for admins with the `command` permission; the actual gate is `Whip.command(..., { dev = true })` (console, or whip.devtools with developer mode) (`server/check.lua:3`, `:308`). Docs say developer mode, matching code.
- `Config.Speaker.maxRange` fallback in code is 100 when unset (`server/speakers.lua:32`); config ships 300, docs say "up to 300".
- `voicebot/package.json` says version 1.0.0; the bot reports `VERSION = '1.5.0'` (`bot.mjs:58`), which is what `VoiceBotStatus().version` and the "1.5.0 or newer" checks mean.
