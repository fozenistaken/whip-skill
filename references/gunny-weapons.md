# whip_gunny: weapons, magazines, calibers, attachments, packs

What whip_gunny (WHIP's weapon system, v2.0.1) does, its data model, every export and event, its item names, and how it uses whip_core. It also covers whip_core's weapon catalog and weapon guard. Built from doc anchors `#guide-weapons`, `#gunny-bench`, `#gunny-items`, `#gunny-give-take`, `#gunny-each-shot`, `#gunny-hud`, `#gunny-packs`, `#gunny-debug`, `#gunny-wont-reload`, `#gunny-patterns`, `#gunny-files`, `#gunny-exports`, `#giveweapon`, `#givemagazine`, `#gunny-client`, `#getdrawnweapon` and `#gunny-events`. Checked against the whole `whip_gunny/` repo and `whip_core/shared/weapon_catalog.lua`, `shared/gta_weapons.lua`, `shared/gta_weapon_models.lua`, `client/weapon_guard.lua`, `lib/satellite.lua` and `types/*.lua`.

## Contents
- Install, manifest and load order
- Data model (metadata shapes)
- Items: calibers, weapons, magazines, attachments
- Adding weapons in gunny's files
- Item settings (/whip Items page)
- Server exports: GiveWeapon, GiveMagazine
- Pack exports (both sides): RegisterWeapon, RegisterMagazine, Gunny.register
- Client exports
- Events (public)
- Internal net events, callbacks and their schemas
- Behaviour: draw, holster, shooting, reload, loading magazines, magazine slot, throwables, jerry can, vehicles
- The weapon bench
- Controls, commands, key mappings, pad actions, control blocks
- Recipes (give/take back, every shot, HUD, no-weapons zone)
- How gunny uses whip_core (API map)
- whip_core weapon catalog (Whip.weapons) and GTA weapon list
- whip_core weapon guard (PermitNativeWeapon)
- Debugging and troubleshooting
- Learning from gunny: WHIP patterns
- Gotchas
- Docs vs code

---

## Install, manifest and load order

- Ships with WHIP and is installed by the txAdmin recipe. To install by hand, add `ensure whip_gunny` after `ensure whip_core`. It needs no SQL; its items appear under /whip → Economy → Items.
- A resource that calls gunny adds `dependency 'whip_gunny'`. A **weapon pack** needs no dependency (see Pack exports).
- fxmanifest: `fx_version 'cerulean'`, `lua54 'yes'`, `version '2.0.0'`, `dependency 'whip_core'`, `whip_requires '1.0'` (the setup report flags an older whip_core), `whip_updates 'WHIPFX/whip_gunny'` (whip_core checks that repo's releases), `ui_page 'html/index.html'` and `nui_callback_strict_mode 'true'` (only gunny's own page may call its NUI callbacks).
- Shared load order: `@whip_core/lib/satellite.lua` (first), `config.lua`, `items/calibers.lua`, `items/weapons.lua`, `items/magazines.lua`, `items/attachments.lua`, `shared/catalog.lua`, `shared/packs.lua`, `shared/whip_weapons.lua`.
- Server order: `main`, `items`, `weapons`, `magpanel`, `magazines`, `reload`, `shooting`, `throwables`, `attachments`, `debug`, `ledger`.
- Client order: `main`, `ammo` (the only writer of ped ammo, so it loads before the others), `weapons`, `reload`, `shooting`, `throwables`, `vehicle`, `magazines`, `attachments`, `debug`.
- `data_file`s:
  - `DLC_ITYP_REQUEST`: `stream/whippy_mag_round.ytyp`, `stream/whip_ammo_props.ytyp` (one ammo box per ammo item, `whip_ammobox_<caliber>`) and `stream/whip_gun_props.ytyp` (`whip_gunprop_*` thrown and dropped gun props with collision).
  - `CLIP_SETS_FILE`: `data/whip_shotgun_clip_sets.xml`.
  - In this order, components before the weapons that list them: `WEAPONCOMPONENTSINFO_FILE`, `WEAPON_METADATA_FILE`, `WEAPON_ANIMATIONS_FILE`, `PED_PERSONALITY_FILE`, `WEAPONINFO_FILE`. This set covers `whip_*.meta` and again `whip_heavypistol_*.meta`.
  - `WEAPONINFO_FILE_PATCH`: `whip_patch_pumpshotgun_mk2.meta` and `whip_patch_combatshotgun.meta`. Both patch Rockstar's own guns to reload shell by shell at 0.5 speed; the Mk II takes the combat shotgun's 6-shell clip.
  - `AUDIO_WAVEPACK 'audiodirectory'` and `AUDIO_SOUNDDATA 'data/whippy_gunny_sounds.dat'`. The data_file names the `.rel` without `.54.rel`.
- `files{}` lists `lib/pack.lua` (so packs' clients can load it), the html, `html/img/items/*.webp|*.png` and the metas. It deliberately lists **no `stream/` files**: on GTA V Enhanced, which streams `stream_enhanced/`, a listed `stream/` file is packed into the resource and gunny fails to start ("Failed to generate cache for set: resource.rpf").
- `stream/` and `stream_enhanced/` (Enhanced) hold the models. `.githooks/enhanced_assets.py` keeps `stream_enhanced/` in step with `stream/`. Sources are in `anim_src/`, `audio_src/` and `props_src/`.
- Add-on guns: every weapon gunny remodels is an **add-on** `WEAPON_WHIP_*` with its own models `w_<type>_whip_<name>`, so Rockstar's originals stay stock for NPCs, police and other scripts. A resource cannot change a base weapon's animation entry. There are 15 of them: HEAVYPISTOL, REVOLVER, REVOLVER_MK2, DOUBLEACTION, NAVYREVOLVER, ASSAULTRIFLE, PUMPSHOTGUN, SAWNOFFSHOTGUN, SNIPERRIFLE, BAT, DAGGER, GOLFCLUB, HATCHET, KNIFE and MACHETE. Add-on components: `COMPONENT_WHIP_ASSAULTRIFLE_CLIP_01/02`, `COMPONENT_WHIP_NAVYREVOLVER_CLIP_01` and `COMPONENT_WHIP_HEAVYPISTOL_CLIP_01/02`.

## Data model (metadata shapes)

gunny owns the rules and whip_core owns the data, which lives in item metadata.

| Item kind | Metadata | Notes |
|---|---|---|
| Gun with magazines | `{ serial, attachments = { [slot] = attachmentItem }, attachmentMeta = { [slot] = {...} }, magazine = { item, ammo, serial, ...rest of the magazine's metadata incl. uid } }` | `magazine` is nil when empty. |
| Gun with no magazine (`magless`) | `{ serial, attachments, attachmentMeta, ammo = n }` | The rounds are loose in the gun. |
| Magazine | `{ serial, ammo }` (+ `uid` once logged) | Stays a separate item when out of a gun. |
| Melee | `{ serial }` | No card rows. The serial identifies the drawn weapon. |
| Jerry can | `{ serial, fuel = 0..100 }` | A new can is empty (`fuel = 0`). |
| Throwable | none | Stacks merge. The drawn one is known by its slot and item. |
| Ammo (`ammo_*`) | none | A stack of loose rounds, `type='ammo'`, `maxStack 999`. |
| Attachment | its own metadata (uid) | When fitted, it is copied into the gun's `attachmentMeta[slot]` and handed back on removal. Older guns may carry `attachmentUids[slot]`, which comes back as `{ uid }`. |

Telling a gun from the rest (verified 2026-11-18, `server/items.lua`): guns, magazines and throwables all register with `type = 'weapon'`. A gun is the one whose metadata has a `serial` and an `attachments` table; a magazine has `{ serial, ammo }`, melee `{ serial }` only. For a definition-level filter: guns are `stack = false` and carry no `fuelCapacity` (the jerry can), but magazines pass that filter too, so check the metadata in the handler.

- Serial: 12 characters from `A–Z0–9` (`GunnyNewSerial`, `server/main.lua:210`). It is stamped by `RegisterItemDefaultMetadata` for every gun, magazine, melee weapon and jerry can as it is made. A magazine without one gets one as it goes into a gun (`GunnyMagazineIn`).
- A magazine put into a gun is stored **whole** inside the gun (`meta.magazine`) and comes out exactly as it went in, with the remaining rounds. While it is inside, `FindItemByMetadata('serial', magSerial)` finds nothing, because the search is not nested.
- Item `type`: guns, melee, throwables, the jerry can, magazines and attachments are `'weapon'`; rounds are `'ammo'`. Guns, magazines and attachments: `stack=false`, `maxStack=1`, `usable=false`.

## Items

### Calibers (`items/calibers.lua`, `Config.Calibers`): 24 ammo items
Fields: `ammoItem` (item key), `ammoWeight` (kg per round, default 0.01), `label` (the item is called "`<label>` Round", desc "`<label>` ammunition") and `prop` (ammo-box model `whip_ammobox_*`). A weapon's or magazine's `caliber` names the key on the left.

| caliber key | ammoItem | kg | | caliber key | ammoItem | kg |
|---|---|---|---|---|---|---|
| `9mm` | `ammo_9mm` | .007 | | `.44 Magnum` | `ammo_44mag` | .025 |
| `.45 ACP` | `ammo_45acp` | .014 | | `.36 Navy` | `ammo_36navy` | .008 |
| `.50 AE` | `ammo_50ae` | .022 | | `.22 LR` | `ammo_22lr` | .003 |
| `5.56x45` | `ammo_556` | .012 | | `Musket Ball` | `ammo_musket` | .035 |
| `7.62x39` | `ammo_762x39` | .016 | | `Flare` | `ammo_flare` | .06 |
| `7.62x51` | `ammo_762x51` | .025 | | `Taser Cartridge` | `ammo_taser` | .03 |
| `.308 Win` | `ammo_308` | .025 | | `Energy Cell` | `ammo_energycell` | .01 |
| `.50 BMG` | `ammo_50bmg` | .115 | | `Railgun Slug` | `ammo_railgun` | .25 |
| `12 Gauge` | `ammo_12gauge` | .040 | | `Rocket` | `ammo_rocket` | 2.2 |
| `.357 Magnum` | `ammo_357` | .016 | | `Homing Rocket` | `ammo_homingrocket` | 3.0 |
| `40mm Grenade` | `ammo_40mm` | .23 | | `Firework` | `ammo_firework` | .5 |
| `Minigun Round` | `ammo_minigun` | .025 | | `EMP Round` | `ammo_emp` | .25 |

### Weapons (`items/weapons.lua`, `Config.Weapons`): 102 items
Fields:
- Every weapon: `weight` (default 2.0 for a gun, 1.0 melee, 0.5 throwable, 3.0 jerry can), `description`, `label`, `hash` (a GTA weapon hash in backticks; **required**), `prop` (ground model).
- A gun with magazines: `caliber`, `compatibleMags` (list), `defaultClipComponent` (the GTA clip shown when the magazine has no `component`), `reloadTime` (ms; also the minimum reload time in a seat).
- A magless gun: `caliber`, `reloadTime`, `magless = true`, `internalCapacity`, and optionally `loopedReload = true` (shell at a time; needs `UseLoopedReloadAnim` plus `reload_loop` clips in its weapon meta).
- Other kinds: `melee = true`; `fuelCan = true` + `fuelCapacity`; `throwable = true` + `maxStack` (default 25).

The kind comes from the flags: `Config.KindOf` returns `'fuelCan'`, then `'throwable'`, then `'melee'`, and anything else is `'gun'`.

**Guns with magazines (46).** Columns: item, hash, caliber, magazines, reload ms.
| item | hash | cal | mags | ms |
|---|---|---|---|---|
| gunny_pistol | WEAPON_PISTOL | 9mm | mag_pistol, _extended | 1000 |
| gunny_pistol_mk2 | WEAPON_PISTOL_MK2 | 9mm | mag_pistol_mk2, _extended | 1000 |
| gunny_combatpistol | WEAPON_COMBATPISTOL | 9mm | mag_combatpistol, _extended | 1000 |
| gunny_appistol | WEAPON_APPISTOL | 9mm | mag_appistol, _extended | 1100 |
| gunny_pistol50 | WEAPON_PISTOL50 | .50 AE | mag_pistol50, _extended | 1200 |
| gunny_snspistol | WEAPON_SNSPISTOL | 9mm | mag_snspistol, _extended | 900 |
| gunny_snspistol_mk2 | WEAPON_SNSPISTOL_MK2 | 9mm | mag_snspistol_mk2, _extended | 900 |
| gunny_heavypistol | WEAPON_WHIP_HEAVYPISTOL | .45 ACP | mag_heavypistol, _extended | 1100 |
| gunny_vintagepistol | WEAPON_VINTAGEPISTOL | 9mm | mag_vintagepistol, _extended | 1100 |
| gunny_ceramicpistol | WEAPON_CERAMICPISTOL | 9mm | mag_ceramicpistol, _extended | 1000 |
| gunny_gadgetpistol ("Perico Pistol") | WEAPON_GADGETPISTOL | 9mm | mag_gadgetpistol | 1000 |
| gunny_smg | WEAPON_SMG | 9mm | mag_smg, _extended, _drum | 2000 |
| gunny_smg_mk2 | WEAPON_SMG_MK2 | 9mm | mag_smg_mk2, _extended | 2000 |
| gunny_microsmg | WEAPON_MICROSMG | 9mm | mag_microsmg, _extended | 1800 |
| gunny_minismg | WEAPON_MINISMG | 9mm | mag_minismg, _extended | 1700 |
| gunny_assaultsmg | WEAPON_ASSAULTSMG | 9mm | mag_assaultsmg, _extended | 2100 |
| gunny_combatpdw | WEAPON_COMBATPDW | 9mm | mag_combatpdw, _extended, _drum | 2000 |
| gunny_machinepistol | WEAPON_MACHINEPISTOL | 9mm | mag_machinepistol, _extended, _drum | 1600 |
| gunny_tecpistol ("Tactical SMG") | WEAPON_TECPISTOL | 9mm | mag_tecpistol, _extended | 1800 |
| gunny_rifle ("Assault Rifle") | WEAPON_WHIP_ASSAULTRIFLE | 5.56x45 | mag_rifle, _extended, _drum | 2300 |
| gunny_rifle_mk2 | WEAPON_ASSAULTRIFLE_MK2 | 5.56x45 | mag_rifle_mk2, _extended | 2300 |
| gunny_carbinerifle | WEAPON_CARBINERIFLE | 5.56x45 | mag_carbinerifle, _extended, _drum | 2200 |
| gunny_carbinerifle_mk2 | WEAPON_CARBINERIFLE_MK2 | 5.56x45 | mag_carbinerifle_mk2, _extended | 2200 |
| gunny_advancedrifle | WEAPON_ADVANCEDRIFLE | 5.56x45 | mag_advancedrifle, _extended | 2100 |
| gunny_specialcarbine | WEAPON_SPECIALCARBINE | 5.56x45 | mag_specialcarbine, _extended, _drum | 2200 |
| gunny_specialcarbine_mk2 | WEAPON_SPECIALCARBINE_MK2 | 5.56x45 | mag_specialcarbine_mk2, _extended | 2200 |
| gunny_bullpuprifle | WEAPON_BULLPUPRIFLE | 5.56x45 | mag_bullpuprifle, _extended | 2100 |
| gunny_bullpuprifle_mk2 | WEAPON_BULLPUPRIFLE_MK2 | 5.56x45 | mag_bullpuprifle_mk2, _extended | 2100 |
| gunny_compactrifle | WEAPON_COMPACTRIFLE | 7.62x39 | mag_compactrifle, _extended, _drum | 2000 |
| gunny_militaryrifle | WEAPON_MILITARYRIFLE | 5.56x45 | mag_militaryrifle, _extended | 2200 |
| gunny_heavyrifle | WEAPON_HEAVYRIFLE | 7.62x51 | mag_heavyrifle, _extended | 2400 |
| gunny_tacticalrifle ("Service Carbine") | WEAPON_TACTICALRIFLE | 5.56x45 | mag_tacticalrifle, _extended | 2200 |
| gunny_battlerifle | WEAPON_BATTLERIFLE | 7.62x51 | mag_battlerifle, _extended | 2400 |
| gunny_mg | WEAPON_MG | 7.62x51 | mag_mg, _extended | 3500 |
| gunny_combatmg | WEAPON_COMBATMG | 7.62x51 | mag_combatmg, _extended | 3800 |
| gunny_combatmg_mk2 | WEAPON_COMBATMG_MK2 | 7.62x51 | mag_combatmg_mk2, _extended | 3800 |
| gunny_gusenberg | WEAPON_GUSENBERG | .45 ACP | mag_gusenberg, _extended | 2500 |
| gunny_sniperrifle | WEAPON_WHIP_SNIPERRIFLE | .308 Win | mag_sniperrifle | 2500 |
| gunny_heavysniper | WEAPON_HEAVYSNIPER | .50 BMG | mag_heavysniper | 3000 |
| gunny_heavysniper_mk2 | WEAPON_HEAVYSNIPER_MK2 | .50 BMG | mag_heavysniper_mk2, _extended | 3000 |
| gunny_marksmanrifle | WEAPON_MARKSMANRIFLE | 7.62x51 | mag_marksmanrifle, _extended | 2300 |
| gunny_marksmanrifle_mk2 | WEAPON_MARKSMANRIFLE_MK2 | 7.62x51 | mag_marksmanrifle_mk2, _extended | 2300 |
| gunny_precisionrifle | WEAPON_PRECISIONRIFLE | .50 BMG | mag_precisionrifle | 2800 |
| gunny_assaultshotgun | WEAPON_ASSAULTSHOTGUN | 12 Gauge | mag_assaultshotgun, _extended | 2800 |
| gunny_heavyshotgun | WEAPON_HEAVYSHOTGUN | 12 Gauge | mag_heavyshotgun, _extended | 2400 |
| gunny_autoshotgun ("Sweeper Shotgun") | WEAPON_AUTOSHOTGUN | 12 Gauge | mag_autoshotgun, _extended | 2600 |

(In the mags column, `mag_x` stands for `gunny_mag_x`, and `_extended`/`_drum` for `gunny_mag_x_extended`/`gunny_mag_x_drum`.) `defaultClipComponent` is `COMPONENT_<GUN>_CLIP_01`, except `COMPONENT_WHIP_HEAVYPISTOL_CLIP_01` and `COMPONENT_WHIP_ASSAULTRIFLE_CLIP_01`. gunny_sniperrifle keeps `COMPONENT_SNIPERRIFLE_CLIP_01`.

**Guns with no magazine (25).** Columns: item, hash, caliber, internalCapacity, reload ms. **L** = loopedReload.
| item | hash | cal | cap | ms |
|---|---|---|---|---|
| gunny_revolver ("Heavy Revolver") | WEAPON_WHIP_REVOLVER | .44 Magnum | 6 | 2500 |
| gunny_revolver_mk2 | WEAPON_WHIP_REVOLVER_MK2 | .357 Magnum | 6 | 2500 |
| gunny_doubleaction | WEAPON_WHIP_DOUBLEACTION | .45 ACP | 6 | 2500 |
| gunny_navyrevolver | WEAPON_WHIP_NAVYREVOLVER | .36 Navy | 6 | 2600 |
| gunny_marksmanpistol | WEAPON_MARKSMANPISTOL | .22 LR | 1 | 1500 |
| gunny_pumpshotgun **L** | WEAPON_WHIP_PUMPSHOTGUN | 12 Gauge | 6 | 3000 |
| gunny_pumpshotgun_mk2 **L** | WEAPON_PUMPSHOTGUN_MK2 (patched) | 12 Gauge | 6 | 3000 |
| gunny_sawnoffshotgun **L** | WEAPON_WHIP_SAWNOFFSHOTGUN | 12 Gauge | 4 (meta holds 6) | 1800 |
| gunny_dbshotgun | WEAPON_DBSHOTGUN | 12 Gauge | 2 | 2000 |
| gunny_musket | WEAPON_MUSKET | Musket Ball | 1 | 4000 |
| gunny_flaregun | WEAPON_FLAREGUN | Flare | 1 | 1500 |
| gunny_stungun | WEAPON_STUNGUN | Taser Cartridge | 1 | 1200 |
| gunny_bullpupshotgun | WEAPON_BULLPUPSHOTGUN | 12 Gauge | 14 | 3500 |
| gunny_combatshotgun **L** | WEAPON_COMBATSHOTGUN (patched) | 12 Gauge | 6 | 3000 |
| gunny_raypistol ("Up-n-Atomizer") | WEAPON_RAYPISTOL | Energy Cell | 20 | 2000 |
| gunny_raycarbine ("Unholy Hellbringer") | WEAPON_RAYCARBINE | Energy Cell | 999 | 3000 |
| gunny_railgun | WEAPON_RAILGUN | Railgun Slug | 1 | 3000 |
| gunny_minigun | WEAPON_MINIGUN | Minigun Round | 9999 | 5000 |
| gunny_rpg | WEAPON_RPG | Rocket | 1 | 3500 |
| gunny_hominglauncher | WEAPON_HOMINGLAUNCHER | Homing Rocket | 1 | 4000 |
| gunny_grenadelauncher | WEAPON_GRENADELAUNCHER | 40mm Grenade | 10 | 3000 |
| gunny_compactlauncher | WEAPON_COMPACTLAUNCHER | 40mm Grenade | 1 | 2000 |
| gunny_firework | WEAPON_FIREWORK | Firework | 1 | 2500 |
| gunny_rayminigun ("Widowmaker") | WEAPON_RAYMINIGUN | Energy Cell | 9999 | 5000 |
| gunny_emplauncher | WEAPON_EMPLAUNCHER | EMP Round | 1 | 2000 |

A tube-fed shotgun's `internalCapacity` must be no more than the `ClipSize` in its weapon meta.

**Melee (19), `melee = true`.** Each entry is `item = hash`:
- `gunny_bat` = `WEAPON_WHIP_BAT`, `gunny_hatchet` = `WEAPON_WHIP_HATCHET`, `gunny_knife` = `WEAPON_WHIP_KNIFE`, `gunny_dagger` = `WEAPON_WHIP_DAGGER` ("Antique Cavalry Dagger"), `gunny_machete` = `WEAPON_WHIP_MACHETE`, `gunny_golfclub` = `WEAPON_WHIP_GOLFCLUB`.
- `gunny_torch` = `WEAPON_FLASHLIGHT` ("Handheld Flashlight"). The key is not `gunny_flashlight`, which is the gun-mounted attachment; item keys are server-wide.
- `gunny_switchblade`, `gunny_crowbar`, `gunny_hammer`, `gunny_wrench` ("Pipe Wrench"), `gunny_nightstick`, `gunny_knuckle` ("Brass Knuckles"), `gunny_poolcue`, `gunny_bottle` ("Broken Bottle"), `gunny_battleaxe`, `gunny_stone_hatchet`, `gunny_stunrod` ("The Shocker") and `gunny_candycane` use the matching `WEAPON_*`.

**Jerry can.** `jerry_can` uses `WEAPON_PETROLCAN`, with `fuelCan = true`, `fuelCapacity = 30` (how much of a car's 100 tank a full can holds), weight 3.0 and prop `prop_jerrycan_01a`. The key is `jerry_can` because cans already in the world have that name.

**Throwables (11)**, `throwable = true`, with `maxStack` = GTA's DefaultMaxAmmo:
- maxStack 25: `gunny_grenade`, `gunny_stickybomb`, `gunny_molotov`, `gunny_bzgas`, `gunny_smokegrenade` ("Tear Gas") and `gunny_flare` ("Hand Flare").
- maxStack 10: `gunny_pipebomb`, `gunny_snowball`, `gunny_acidpackage` and `gunny_newspaper`.
- maxStack 5: `gunny_proxmine`.
- `WEAPON_ACIDPACKAGE` and `WEAPON_NEWSPAPER` need a recent game build. On an older build, a draw says "This server's version of the game has no `<label>`".

### Magazines (`items/magazines.lua`, `Config.Magazines`): 95 items
Fields: `weight` (default 0.3), `label`, `prop`, `caliber`, `capacity` (**required**, ≥1) and `component` (the GTA clip it shows; when nil, the gun's `defaultClipComponent`). Which guns take a magazine is each gun's `compatibleMags`. The naming is `gunny_mag_<gun>` (standard, no component), `gunny_mag_<gun>_extended` (`..._CLIP_02`) and `gunny_mag_<gun>_drum` (`..._CLIP_03`).

| gun | std / extended / drum capacity |
|---|---|
| pistol, pistol_mk2, combatpistol | 12 / 16 |
| appistol | 18 / 36 |
| pistol50 | 9 / 12 |
| snspistol, snspistol_mk2 | 6 / 12 |
| heavypistol | 18 / 36 (`COMPONENT_WHIP_HEAVYPISTOL_CLIP_02`) |
| vintagepistol | 7 / 12 |
| ceramicpistol | 12 / 17 |
| gadgetpistol | 12 |
| smg | 30 / 60 / 100 |
| smg_mk2, assaultsmg | 30 / 60 |
| microsmg | 16 / 30 |
| minismg | 20 / 30 |
| combatpdw | 30 / 60 / 100 |
| machinepistol | 12 / 30 / 60 |
| tecpistol | 17 / 33 |
| rifle | 30 / 60 (`COMPONENT_WHIP_ASSAULTRIFLE_CLIP_02`) / 100 (`COMPONENT_ASSAULTRIFLE_CLIP_03`) |
| rifle_mk2, carbinerifle_mk2, advancedrifle, specialcarbine_mk2, bullpuprifle, bullpuprifle_mk2, tacticalrifle | 30 / 60 |
| carbinerifle, specialcarbine, compactrifle (7.62x39) | 30 / 60 / 100 |
| militaryrifle | 30 / 50 |
| heavyrifle | 30 / 60 |
| battlerifle | 20 / 30 |
| mg | 54 / 100 |
| combatmg, combatmg_mk2 | 100 / 200 |
| gusenberg | 30 / 50 |
| sniperrifle | 10 |
| heavysniper | 6 |
| heavysniper_mk2 | 6 / 8 |
| marksmanrifle, marksmanrifle_mk2 | 8 / 16 |
| precisionrifle | 6 |
| assaultshotgun | 8 / 32 |
| heavyshotgun | 6 / 12 |
| autoshotgun | 10 / 32 ("Drum") |

### Attachments (`items/attachments.lua`)
- `Config.AttachmentCategories` holds the slots: `scope`, `muzzle`, `barrel`, `grip` and `flashlight`, each `{ label, icon }`. Camo is not supported.
- `Config.Attachments` has one entry per item, `{ label, category, tier, prop, weight? (0.2), description? ("<label> weapon attachment") }`. There are 15 items:
  - Scopes: `gunny_scope_macro`/macro, `gunny_scope_small`/small, `gunny_scope_medium`/medium, `gunny_scope_large`/large, `gunny_scope_holographic`/holographic, `gunny_scope_thermal`/thermal, `gunny_scope_nightvision`/nightvision.
  - Muzzles: `gunny_suppressor`/suppressor, `gunny_muzzle_flat`/flat, `gunny_muzzle_heavy`/heavy, `gunny_muzzle_slanted`/slanted, `gunny_muzzle_tactical`/tactical, `gunny_muzzle_bell`/bell.
  - Barrel: `gunny_barrel_heavy`/heavy. Grip: `gunny_grip_vertical`/vertical. Flashlight: `gunny_flashlight`/standard.
- `Config.WeaponAttachments[weaponItem][category][tier] = componentHash`. A weapon that is not listed takes no attachments. The tier names the part: a Macro Scope fits only where that weapon has a `macro` entry. Two tiers may map to one component; `gunny_pistol_mk2` has macro and holographic both = `COMPONENT_AT_PI_RAIL`.
- Weapons that take attachments (slot:tiers):
  - **Mk II guns.** pistol_mk2 scope:macro/holographic, muzzle:suppressor/flat, flashlight. snspistol_mk2 scope:macro, muzzle:suppressor/flat, flashlight. revolver_mk2 scope:holographic, muzzle:flat, flashlight. smg_mk2 scope:macro/small/holographic, muzzle:all 6, barrel, flashlight. rifle_mk2, carbinerifle_mk2 and specialcarbine_mk2 scope:macro/medium/holographic, muzzle:all 6, barrel, grip, flashlight. bullpuprifle_mk2 is the same with scope small in place of medium. combatmg_mk2 scope:macro/medium/holographic, muzzle:flat/heavy/slanted/tactical/bell, barrel, grip. heavysniper_mk2 scope:large/thermal/nightvision, muzzle:suppressor/flat/heavy, barrel. marksmanrifle_mk2 scope:macro/medium/large/holographic, muzzle:all 6, barrel, grip, flashlight. pumpshotgun_mk2 scope:holographic, muzzle:suppressor/flat, flashlight.
  - **Others.** pistol, combatpistol, appistol and pistol50 suppressor+flashlight. snspistol, heavypistol, vintagepistol, ceramicpistol, machinepistol and tecpistol suppressor. smg, microsmg and assaultsmg scope:macro, suppressor, flashlight. combatpdw scope:small, grip, flashlight. rifle scope:macro, suppressor, grip, flashlight. carbinerifle and specialcarbine scope:macro/medium, suppressor, grip, flashlight. advancedrifle scope:small/medium, suppressor, flashlight. bullpuprifle scope:macro/small, suppressor, grip, flashlight. tacticalrifle suppressor, flashlight. militaryrifle scope:small, suppressor, flashlight. heavyrifle scope:macro/medium, suppressor, grip, flashlight. battlerifle scope:macro, flashlight. mg scope:small/medium. combatmg scope:macro/medium, grip. sniperrifle scope:large/macro, suppressor. heavysniper and precisionrifle scope:large. marksmanrifle scope:large, suppressor, grip, flashlight. assaultshotgun, heavyshotgun and bullpupshotgun suppressor, grip, flashlight. pumpshotgun and combatshotgun suppressor, flashlight. grenadelauncher scope:small, flashlight.

### Lookups (`shared/catalog.lua`, both sides)
- `Config.GetWeapon/GetMagazine/GetCaliber/GetAttachment` are table indexes.
- `Config.IsMagCompatible(weapon, mag)`.
- `Config.GetAllClipComponents(weapon)` returns the default clip plus each compatible magazine's component.
- `Config.GetMagComponent(mag)` and `Config.GetAmmoItemForWeapon(weapon)`.
- Kind tests: `Config.IsFuelCan/IsThrowable/IsMelee/IsFirearm(cfg)` and `Config.KindOf(cfg)`.
- Attachment lookups: `Config.GetWeaponAttachmentComponent(weapon, category, tier)`, `Config.GetWeaponAttachmentCategories(weapon)` and `Config.GetAllAttachmentComponents(weapon)`.
- `Config.GetAllWeaponNames/GetAllMagazineNames/GetAllAttachmentNames()` return sorted lists.
- Jerry can conversions: `Config.FUEL_CAN_AMMO = 4500`. `Config.FuelToAmmo(fuel0to100)` returns floor(fuel/100*4500+0.5). `Config.AmmoToFuel(ammo)` returns 0–100 to 2 decimals.
- Validation at start, on both sides: `Config.MagazineProblem(m)` (needs capacity ≥1 and a known caliber) and `Config.WeaponProblem(w)` (needs a numeric `hash`; a firearm also needs a known caliber, and either `magless` with `internalCapacity ≥1` or a non-empty `compatibleMags` that all exist). A broken entry is **removed** and reported through `Whip.startProblem`, which prints in red (`'weapon X left out: why'`).

## Adding weapons in gunny's files

1. Add one entry per item to the right file under `items/`. Each file's header lists every field and its default.
2. A gun needs `hash` (listed in whip_core `shared/gta_weapons.lua`, or an add-on), a `caliber` from `items/calibers.lua`, and either `compatibleMags` or `magless = true` + `internalCapacity`. Its `prop` model is listed in whip_core `shared/gta_weapon_models.lua`.
3. A melee weapon needs only `weight`, `description`, `hash`, `label`, `prop` and `melee = true`. In code, only `hash` is strictly checked.
4. Icons go in `html/img/items/<key>.webp` (or `.png`; WebP wins). whip_core looks up an item's icon in the resource that registered it.
5. Run `restart whip_gunny`. A broken entry is left out with a `[GUNNY] WARNING` / start-problem line.
6. To survive updates, use a weapon pack instead of editing gunny's files.

## Item settings (/whip → Economy → Items)

Declared per item in `server/items.lua` and followed on both sides by `Config.FollowItemSettings`, which uses `OnItemSettingChanged` and `GetItemSetting`. A value set on the page **wins over the file until Reset**, and gunny writes it **into** the config tables, so all code reads the admin value.

| Item | key | type | min | max | other |
|---|---|---|---|---|---|
| gun (has reloadTime) | `reloadTime` | int | 100 | 10000 | step 50, unit ms, label "Reload time" |
| magless gun | `internalCapacity` | int | 1 | max(250, file default) | "Rounds it holds" |
| magazine | `capacity` | int | 1 | max(250, file default) | "Rounds it holds" |

- Raising the limit to the file default when it is above 250 (the minigun's 9999) exists because whip refuses an item whose default is past its setting's limit.
- A magazine whose `capacity` changes is **re-registered** (`RegisterItem` again) so that Load Bullets stops at the new size. A magazine already holding more keeps its rounds until they are fired or unloaded.
- A lowered `internalCapacity` trims a gun **at its next draw**, and the extra rounds go to the pockets as ammo with reason "more than the gun holds now". It never trims below the item file's own size (`server/weapons.lua:154-185`). If the pockets have no room, the rounds are put back in the gun; if that fails, they are lost and logged with `[GUNNY] WARNING`.
- Defaults are captured as each item arrives (`Config.NoteItemDefaults`), so the default shown on the page is always the file's or pack's value.

## Server exports

### GiveWeapon(source, weaponName, overrides?, reason?) — SERVER, WAITS
Gives a weapon item with a new serial (`server/items.lua:287`). whip_core's plain `AddItem` gives the same weapon empty; this export exists for the options.

| Param | Type | Meaning |
|---|---|---|
| source | number | player server id |
| weaponName | string | a weapon item (`'gunny_pistol'`, `'jerry_can'`, `'gunny_grenade'`) |
| overrides | table? | see below |
| reason | string or table? | passed straight through as `AddItem`'s 5th arg: a log reason, or a `WhipAddItemOpts` table such as `{ reason, noDrop }` |

`overrides` keys:
- `serial` (non-empty string): your own serial; otherwise a new one is generated.
- `attachments`: `{ [category] = attachmentItem }`. Each must be an attachment whose `category` matches and which the gun takes in that slot (`Config.GetWeaponAttachmentComponent`), or the call fails with `'<weapon> does not take <att> in its <cat> slot'`. It is checked **before** the melee/jerry-can/gun branch, so passing attachments for melee or the jerry can also fails. A throwable returns before this check, so attachments passed for it are ignored.
- A gun with magazines takes `magazine` (an item it takes) + `ammo`. `loaded = true` fills it, using `compatibleMags[1]` when no magazine is named. `ammo` with no `magazine` and no `loaded` is ignored: the gun comes empty.
- A magless gun takes `ammo`, or `loaded = true` to fill it to `internalCapacity`.
- The jerry can takes `fuel` (0–100, clamped; default 0). Its metadata becomes just `{ serial, fuel }`.
- A throwable takes `amount` (stack size, ≥1, floored; default 1). It carries no metadata and no serial.
- Rounds are clamped to `[0, capacity]` and floored, so `ammo = 999` means full.

Returns:
- `true, where, serial`. `where` is `'inventory'`, or `'ground'` (dropped at the player's feet when it didn't fit).
- For a throwable, `true, where` (no serial).
- Failures return `false, reason`:
  - `'Unknown weapon: X'`
  - `'Unknown magazine: X'`
  - `'<weapon> does not take <mag>'`
  - the attachment message above
  - `AddItem`'s own refusal (a player not loaded, `noDrop` and full, ...)
```lua
exports.whip_gunny:GiveWeapon(source, 'gunny_pistol', { loaded = true })
exports.whip_gunny:GiveWeapon(source, 'gunny_pistol', { serial = 'LSPD00000042', magazine = 'gunny_mag_pistol_extended', ammo = 10 })
exports.whip_gunny:GiveWeapon(source, 'jerry_can', { fuel = 100 }, 'fuel job')
exports.whip_gunny:GiveWeapon(source, 'gunny_grenade', { amount = 3 })
```

### GiveMagazine(source, magName, ammo?, reason?) — SERVER, WAITS
A magazine with new metadata `{ serial, ammo }`. `ammo` is clamped to `[0, capacity]` and floored; nil means empty, and any number past the size fills it. The size can change on the Items page. `reason` is passed through to `AddItem`.
Returns `true, where, serial` (the magazine's own serial), or `false, reason`: `'Unknown magazine: X'` or `AddItem`'s refusal.
```lua
local _, _, magSerial = exports.whip_gunny:GiveMagazine(source, 'gunny_mag_pistol', 999)   -- full
```

There is **no server export for "what is drawn"**. Use whip_core `GetHeldItem(source)`: gunny calls `SetHeldItem` on every draw and clears it on holster. You can also listen to the events.

## Pack exports

### RegisterWeapon(item, def) / RegisterMagazine(item, def) — BOTH (SERVER and CLIENT)
Defined in `shared/packs.lua`, so both sides must call them, from a file both sides load, inside `Gunny.register`. Register magazines **first**.
- Caller check: `GetInvokingResource()` must be another resource. gunny itself gets `'<X> is for other resources: whip_gunny's own items are in items/'`.
- Name check (`claim`): letters, digits, `_` and `-`, at most **50** characters. It is refused if it belongs to another running pack (`'<item> belongs to <res>'`), is already another kind of item (a magazine name for a weapon, an attachment), is one of gunny's ammo items (`"is one of whip_gunny's rounds"`), or is one of gunny's own items (`"is one of whip_gunny's own"`).
- `def` is validated like gunny's own entries (`Config.WeaponProblem` / `MagazineProblem`). Errors look like `'weapon <item>: <why>'` / `'magazine <item>: <why>'`.
- A weapon may add `attachments = { [slot] = { [kind] = componentHash } }`. Each slot must be in `Config.AttachmentCategories`, and each component must be a number. A kind that no attachment item has (say `medium` with no "medium" scope item) still registers, but is reported as a start problem (`'... no attachment in items/attachments.lua is a <tier> <slot>, so that one never fits'`). `def.attachments` is **removed from your table** and stored in `Config.WeaponAttachments[item]`.
- Your `def` table is stored **by reference** and later mutated by item settings (`capacity`, `reloadTime`, `internalCapacity`).
- The same pack registering again replaces its own item.
- Returns `true`, or `false, reason`. On the server, when whip_core is up, `RegisterItem` runs immediately. If whip_core refuses the item (the name is another resource's item), it is removed from gunny's tables and the export returns `false, '<item>: whip_core refused it (<why>)'`. A refused magazine is also removed from the pack's guns, and a gun left with none is refused too.
- Pack items get gunny's menus, magazine slot, settings, bench, icons (`@<pack>/html/img/items/<item>.webp|png`) and default weights.
- When the pack stops (`onResourceStop`), its items leave gunny's tables. Players keep the items, and they work again when the pack is back.

### Gunny.register(fn) — from `@whip_gunny/lib/pack.lua` (BOTH)
`shared_script '@whip_gunny/lib/pack.lua'` defines `Gunny.register(fn)`.
- `fn` runs immediately if `GetResourceState('whip_gunny') == 'started'`.
- It runs again on every `whip_gunny:packs:ready`, which gunny fires in a thread once all its files have loaded, each time it starts.
- Errors are caught and printed as `[<res>] Gunny.register errored: ...`.

Pack manifest (models and textures in `stream/`):
```lua
shared_script '@whip_gunny/lib/pack.lua'
shared_script 'gunny.lua'
data_file 'WEAPONCOMPONENTSINFO_FILE' 'data/mypack_weaponcomponents.meta'   -- before the weapons
data_file 'WEAPON_METADATA_FILE' 'data/mypack_weaponarchetypes.meta'
data_file 'WEAPON_ANIMATIONS_FILE' 'data/mypack_weaponanimations.meta'
data_file 'WEAPONINFO_FILE' 'data/mypack_weapons.meta'
files { 'data/*.meta', 'html/img/items/*.webp' }
```
```lua
-- gunny.lua
Gunny.register(function()
  print(exports.whip_gunny:RegisterMagazine('mypack_mag_m4', { weight = 0.2, label = 'M4 Magazine',
    prop = 'w_ar_mypack_m4_mag', caliber = '5.56x45', capacity = 30 }))
  print(exports.whip_gunny:RegisterWeapon('mypack_m4', { weight = 3.2, label = 'M4', description = 'A carbine.',
    hash = `WEAPON_MYPACK_M4`, prop = 'w_ar_mypack_m4', caliber = '5.56x45',
    compatibleMags = { 'mypack_mag_m4' }, reloadTime = 2200,
    attachments = { scope = { medium = `COMPONENT_MYPACK_M4_SCOPE` } } }))
end)
```
To show pack guns in WHIP's weapon lists (Director, Object Viewer), the pack must **also** load `@whip_core/lib/satellite.lua` and call `Whip.weapons(list, opts)` (see the catalog section). gunny's own `fxmanifest.lua` streams its add-ons the same way and is a full example.

## Client exports

### IsWeaponDrawn() — CLIENT
Returns `boolean`: whether one of gunny's weapons is in hand (`CurrentWeapon ~= nil`). To follow it instead of polling, listen to `whip_gunny:weapon:drawn` / `:holstered`.

### GetDrawnWeapon() — CLIENT
Returns a **copy** `{ item, label, kind, serial, slot, pocket, ammo, capacity, magazine, attachments }`, or `nil`.

| Field | Type | Meaning |
|---|---|---|
| item | string | item key |
| label | string | config label |
| kind | string | `'gun'`, `'melee'`, `'throwable'` or `'fuelCan'` |
| serial | string or nil | nil for a throwable |
| slot, pocket | number, string | pocket is `'player'` or `'accessory'` |
| ammo | number | A gun's rounds (live), a throwable's stack, or the jerry can's petrol in GTA units (**0–4500**, not 0–100%). 0 for melee. |
| capacity | number or nil | A magazine gun: the inserted magazine's size (nil with none in). A magless gun: `internalCapacity`. nil for anything else. |
| magazine | string or nil | the inserted magazine's item name |
| attachments | table | `{ [slot] = attachmentItem }` (copy) |

### DrawWeapon(slot, pocket?) — CLIENT, WAITS
Draws the weapon in a pocket slot with its animation, holstering any other first. Call it from a thread. `pocket` is `'player'` (default) or `'accessory'`. To put a weapon away, call whip_core's `FreeHands()`; gunny answers the `freeHands` hook.
Returns `true` (drawn, or already drawn in that slot), or `false, reason`:
- `'Already drawing a weapon'`
- `'Finish reloading first'` (any reload asked for or playing)
- the block's label when the hands are blocked (`AreHandsBlocked('weapon')`)
- the server's refusal: `'Invalid weapon'`, the server-side block label, `'Could not get the can ready'`, whip's slot-param refusal, rate limit, ...
- `'Unknown weapon hash'`
- `'Dead'`
- `'The weapon left its slot'` (the server took it back during the draw)
- `"This server's version of the game has no <label>"`

Every refusal is also shown to the player as a notification.
```lua
CreateThread(function() local ok, why = exports.whip_gunny:DrawWeapon(3) end)
```
During a reload, from the press until the reload ends (not only while the animation plays), it returns false and the gun stays out. Death or `BlockHands` still put the gun away at once.

### LoadBullets(slot, pocket?) — CLIENT, WAITS
Fills the magazine in that slot from the rounds carried, behind the server's bar (**300 ms per round**). One load per player at a time. It tells the player how it went. Call it from a thread.
Returns `true, roundsLoaded` (a load stopped partway keeps what went in), or `false, reason`:
- `'whip_core is not running'`
- `'Busy'` (a bar is already up locally, or a load is running on the server, or another bar won)
- `'Magazine not found'`, `'That is not a magazine'`, `'Magazine is full'`, `'Invalid magazine'`
- `'No <caliber label> ammunition available'`
- `'Loading cancelled'`
- `'The magazine or the rounds are not where they were'`
- `'Failed to load bullets'`
- whip's refusal of the event (rate limit, slot param), relayed through `onReject`

### UnloadBullets(slot, pocket?, count?) — CLIENT, WAITS
Empties the magazine into the pockets as rounds, or only `count` of them (default all; the schema clamps `count` to 1–9999, default 9999). Notifies the player.
Returns `true, roundsUnloaded`, or `false, reason`:
- `'That magazine is empty'`
- `'No room in your pockets for the rounds'` (it uses `noDrop`; the rounds go back into the magazine)
- `'Magazine not found'`, `'That is not a magazine'`, `'This magazine has no ammunition set up'`
- `'Could not unload: the magazine was not changed'`
- `'Could not unload the magazine'` (generic)

### ApplyWeaponAttachments(ped, hash, item, attachments) — CLIENT
Fits attachments as metadata holds them (`{ [slot] = attachmentItem }`) onto **any ped holding** that weapon (an NPC, a display), turning each into the GTA component that `item` takes for that slot and tier. Unknown entries are skipped. The ped must already have the weapon. Returns nothing.
```lua
GiveWeaponToPed(npc, `WEAPON_PISTOL`, 12, false, true)
exports.whip_gunny:ApplyWeaponAttachments(npc, `WEAPON_PISTOL`, 'gunny_pistol', { muzzle = 'gunny_suppressor' })
```
There is **no export to open a gun's magazine slot**. It is a panel item opened by the gun's `whip_gunny:open_weapon` context action.

## Events (public)

Listen with `AddEventHandler`. These are local events, not net events.

| Event | Side | Payload |
|---|---|---|
| `whip_gunny:weapon:drawn` | Server | `{ source, item, kind, serial, slot, pocket }`. Fired when the server **accepts** the draw, before the client has the gun. `serial` is nil for throwables. |
| `whip_gunny:weapon:holstered` | Server | `{ source, item, serial, slot, pocket, reason }`, once per draw record. `reason`: `'holstered'` (put away), `'moved'` (left its slot, or a shot arrived for a gun no longer there), `'replaced'` (a new draw found a stale record), `'logout'` (`whip_core:player:logout`) or `'dropped'` (`playerDropped`). |
| `whip_gunny:weapon:fired` | Server | `{ source, item, serial, shots, ammo, coords }`. Fired each time the server takes rounds off a drawn gun: per shot report (automatic fire is batched per frame, so `shots` can be >1, at most 10 per report), and also when the 5 s client sync lowers the count. `ammo` is what is left. `coords` is the ped's position, or nil once the shooter has gone. Only rounds actually there count: a claim past an empty gun fires nothing. Never fired for the jerry can, throwables or melee. |
| `whip_gunny:weapon:drawn` | Client | the `GetDrawnWeapon()` table, after gunny's own after-draw steps |
| `whip_gunny:weapon:holstered` | Client | `{ item, slot, pocket }`, after gunny's own after-holster steps |
| `whip_gunny:packs:ready` | Both | `{}`. gunny has loaded; `lib/pack.lua` re-runs `Gunny.register` functions on it. |

- The client has **no per-shot event**. Poll `GetDrawnWeapon` between drawn and holstered.
- Shots arriving up to **2000 ms after a holster** (`LATE_COUNT_MS`, `server/main.lua:172`) are still charged to that gun if it is still in its slot, and they fire `weapon:fired` for it.

## Internal net events and callbacks

All are declared with `RegisterGunnyCallback` / `RegisterGunnyEvent`, which wrap `SecureCallback` / `SecureEvent` inside `Whip.register`. **Callbacks with no `rateLimit` get gunny's floor: `rateLimit = 150` (ms), `burst = 8`.** `'slot'` params name a pocket slot as `{ sub = pocket, slot = n }` (`GunnySlot`). whip_core checks that the slot is the player's own and holds one of the listed items, and hands the handler `{ addr, item, amount, metadata }`.

| Name | Kind | Schema | Answer |
|---|---|---|---|
| `whip_gunny:equipWeapon` | callback | `weapon` slot ∈ weapons | `true, { hash, ammo, magazine, attachments, serial, countVersion=1 }` |
| `whip_gunny:holsterWeapon` | callback | `whileDead`, rate 200 burst 3; `remainingAmmo` int 0–9999, `countVersion` int 0–2^31-1 default 0 | `true` / `false,'No weapon drawn'` |
| `whip_gunny:performReload` | callback | `weapon` slot | `true, { ammo, magazine, countVersion }` |
| `whip_gunny:performMaglessReload` | callback | `weapon` slot | `true, { ammo, loaded, countVersion }` |
| `whip_gunny:beginLoopedReload` | callback | `weapon` slot | `true, room` |
| `whip_gunny:server:loopedReloadEnded` | event | rate 200 burst 3; `loaded` int 0–250 | — |
| `whip_gunny:server:shotFired` | event | `whileDead`, `sheet='light'`, rate **15** burst **30** (~66/s); `shotsFired` int 1–10 default 1 | answers with client `syncAmmo` |
| `whip_gunny:server:syncAmmo` | event | `whileDead`, rate 1000 burst 3; `ammoCount` int 0–9999, `countVersion` | — |
| `whip_gunny:server:thrown` | event | `whileDead`, `sheet='light'`, rate 100 burst 5; `count` int 1–10 default 1 | — |
| `whip_gunny:server:loadMagazine` | event | rate 200 burst 5; `mag` slot ∈ magazines, `ask` id 1–2^31-1; `onReject` answers `loadDone(ask,false,why)` | client `loadDone` |
| `whip_gunny:unloadBulletsFromMag` | callback | `mag` slot, `count` int 1–9999 default 9999 | `true, { left, unloaded }` |
| `whip_gunny:getWorkbenchData` | callback | `weapon` slot | `true, benchData` |
| `whip_gunny:installAttachment` | callback | `near` bench 4.0 m; `weapon` slot, `attachment` slot ∈ attachments | `true, benchData` |
| `whip_gunny:removeAttachment` | callback | `near` bench; `weapon` slot, `category` key ≤64 | `true, benchData` |
| `whip_gunny:countInventoryMags` | callback | `ace='whip.devtools'`; `weaponName` key ≤64 | `true, { count, totalAmmo, magless }` |
| `whip_gunny:server:debug` | event | ace devtools, rate 500 burst 3; `on` bool | — |
| `whip_gunny:server:ammoLedger` | event | ace devtools, rate 1000 burst 2; `reset` bool | client `ammoLedger` |

Server→client net events: `whip_gunny:client:useWeapon(slot, pocket, quick)`, `:forceHolster`, `:syncAmmo(ammo)`, `:syncFuel(ammo, countVersion)`, `:syncThrown(count, taken)`, `:magazineInserted(slot, ammo, countVersion, magItem)`, `:magazineRemoved(slot, countVersion)`, `:maglessAmmoInserted(slot, ammo, countVersion)`, `:maglessAmmoRemoved(slot, ammo, countVersion)`, `:countRestored(slot, ammo, countVersion, magItem)`, `:reloadShort(slot, pocket, ammo)`, `:magLoading(bool)`, `:magLoadVisual(loaderId, on)` (to everyone within **120 m**), `:loadDone(ask, ok, result)`, `:attachmentInstalled(slot, category, item, componentHash)`, `:attachmentRemoved(slot, category, componentHash)` and `:ammoLedger(lines)`.

Context actions (`RegisterContextAction`): `whip_gunny:equip_weapon`, `whip_gunny:load_mag` and `whip_gunny:unload_mag`. `whip_gunny:open_weapon` is the panel's action.

## Behaviour

### Count versioning (the core anti-dupe idea)
- The server's draw record is `EquippedWeapons[source] = { slot, pocket, weapon, serial, countVersion, fuel?, count?, taken? }`.
- Each time the **server** changes a drawn gun's rounds (reload, magazine slot, jerry can filled), `countVersion` goes up (`GunnyCountChanged`) and the client is told.
- A count sent by the client with an older version is ignored, both for `syncAmmo` and for the holster's `remainingAmmo`.
- Client counts are accepted **only when lower** than the server's. Firing only lowers, so a higher claim would be a free reload.

### Draw
1. Client `DrawWeapon` checks, in order: already drawn → true; equip latch (10 s timeout); reload under way; `AreHandsBlocked('weapon')`. It sets the latch, holsters any other gun, plays `reaction@intimidation@cop@unarmed`/`intro` (unless quick), and asks `equipWeapon`.
2. The server checks `AreHandsBlocked(source,'weapon')`. It gives a jerry can without a serial one, trims an over-full magless gun, ends any stale record (`'replaced'`), stores the record, calls `SetHeldItem(source, addr)`, fires `whip_gunny:weapon:drawn`, and answers.
3. The client:
   - Rejects an unknown hash, death, a called-off draw or an invalid weapon for this build. In each case it tells the server `holsterWeapon`, so the server also fires `holstered`.
   - Calls `PermitNativeWeapon(hash, true)` **before** `GiveWeaponToPed`.
   - Fits the magazine component, then the attachments.
   - Sets `CurrentWeapon` and starts the per-frame tick.
   - Writes the ammo through `GunnyAmmo`, runs the after-draw steps, then fires the client `drawn` event.
4. Inventory Equip toggles: a second Equip on the drawn slot holsters. From a ground pile's prompt (`how.from == 'ground'`), Equip picks the item up and draws it with no animation.

### Holster
- `GunnyHolster(serverDropped?, now?)` runs one at a time; a second caller waits on a promise.
- A normal holster is refused mid-reload ("Finish reloading first").
- Otherwise it blocks fire controls (block `gunGoingAway`, groups `combat`, `vehicleCombat`), settles throws, reads the count, plays `outro`, tells the server `holsterWeapon(ammo, countVersion)` (a refusal still puts the gun away), waits about 300 ms, removes the weapon and `PermitNativeWeapon(hash,false)`.
- The server writes the count **only if lower** and if the versions match, ends the record (`'holstered'`) and clears `SetHeldItem`.
- Forced cases:
  - `whip_gunny:client:forceHolster` (the gun left its slot) and `whip_core:player:logout` remove the gun at once.
  - `whip_core:player:died` uses `now`: no animation, even mid-reload.
  - `whip_core:hands:blocked` holsters, at once if a reload is running.
  - The `beforeGiveMode` and `freeHands` client hooks holster.
- A once-a-second tick sees a gun the game took away (another script, or GTA after the last throwable) and tells the server.
- `onResourceStop` removes the GTA weapon.
- The server watches `whip_core:inventory:changed`. If the drawn item is no longer in its slot with the same serial, it force-holsters (`'moved'`). The same handler pushes the jerry can's new level (`syncFuel`) and a changed throwable stack (`syncThrown`).

### Shooting
- On the client tick, `IsPedShooting` with ammo > 0 spends `GunnyAmmo.roundsFired(ped)` (1–10, read from what the ped really lost) and sends `server:shotFired(n)`.
- The server takes the rounds from `meta.ammo` (magless) or `meta.magazine.ammo`, writes metadata with `{ quiet = true }` (no inventory push; the pockets are saved about once a second), answers `client:syncAmmo(newAmmo)` and fires `weapon:fired`.
- A magazine gun with no magazine in it answers 0.
- A periodic backup sync every **5000 ms** sends the count when it changed and no reload is playing.
- When a gun runs dry on foot, the stuck aim task is ended after 150 ms. In a vehicle, the empty gun reloads automatically.
- Client answers that are higher while shots are still in flight are treated as stale and ignored.
- The ped holds at most 250 rounds per gun at default skill. A minigun holding 3000 has 250 on the ped, topped up after each shot.
- `SetWeaponsNoAutoswap(true)` keeps an empty gun in hand.

### Reload (R / B, or automatic in a seat)
- **Fire is blocked from the press** (block `gunReloading`, controls 24, 257, 69, 70, 92) until the reload ends. Aiming stays allowed.
- **Magazine gun** (`performReload`): the server picks the **fullest** compatible magazine carried (`FindAllItems` over `compatibleMags`). It `StoreTake`s that magazine (take first), writes the gun's `meta.magazine`, bumps the version, and gives the old magazine back with `Whip.core:AddItem` (pockets, or the ground). If the old magazine has nowhere at all to go, the reload is **undone** (the new magazine goes back, `countRestored`).
  - Refusals: `'No magazines for this weapon on you'`, `'All your magazines for this weapon are empty'`, `'Could not take the magazine, try again'`, `'Could not reload, the magazine is back in your pockets'`, `'No room for the old magazine'`, `'That weapon is not reloaded'` and `'That weapon is loaded with rounds, not magazines'`.
- **Magless, all at once** (`performMaglessReload`): loads `min(room, carried)` rounds. It removes them from the pockets, then writes the gun; a failed write gives them back.
  - Refusals: `'Already fully loaded'`, `'No ammunition for this weapon on you'`, `'This weapon has no ammunition set up'`, `'Could not take the rounds, try again'`, `'You are carrying too much to load it. Put something down first'` (on `'Too heavy'`), `'Could not reload, the rounds are back in your pockets'` and `'That weapon takes magazines'`.
- **Shell at a time** (`loopedReload`, on foot only; in a seat it fills at once):
  - `beginLoopedReload` returns `room` and **takes nothing**.
  - Fire is unblocked as the animation starts; firing or running stops the reload.
  - At the end the client sends `loopedReloadEnded(loaded)`. The server takes `min(loaded, room, space, carried)` within **30000 ms** (`LOOPED_REPORT_MS`) and sends `reloadShort` if it took fewer.
  - A reload that never reports (death, holster) takes nothing.
  - While it is open, the gun's magazine-slot panel refuses changes with `'Finish reloading first'`.
  - Client time-outs: 1000 ms settle, 4000 ms stall, 15000 ms total.
- In a seat, R and B do nothing. The last round, or pulling the trigger on an empty gun, reloads automatically. A seated reload takes at least `reloadTime` (default 1500 ms if unset).
- The client reload animation is borrowed from GTA: a fake reserve of 100, `MakePedReload`, a 100 ms settle, then the reserve is removed.

### Loading magazines (Load Bullets)
- Started from the context action `whip_gunny:load_mag` (in its own thread) or the client `LoadBullets` (event + `ask` id).
- Plan: rounds to load = `min(capacity - ammo, carried)`.
- The bar is `Whip.core:Progress(source, { label = 'Loading N rounds into magazine', duration = N*300, canCancel = true, item = { item, metadata }, anim = { dict='whippy_mag_load', clip='load_x2', flag=49 } or seated clip 'load_x2_seated', disable = { move='walk', car=true }, notWhile = { 'swimming','falling' } })`.
- If the bar is stopped by `'cancelled'` or `'dead'`, the rounds loaded are floor(elapsed/300). Other failures (`'too fast'`, `'timeout'`, `'refused'`, `'player left'`, `'whip_core stopped'`, `'busy'`) load nothing.
- After the bar, the server **re-plans** and loads `min(count, now.toLoad)`. It `RemoveItem`s the rounds (reason "loaded into a magazine"), then `SetItemMetadata`; a failed write gives the rounds back.
- During the load, the client's weapon is switched to unarmed and restored afterwards. Everyone within 120 m draws the magazine and rounds in the loader's hands and hears the `mag_seat` sound from set `whippy_gunny_sounds` (heard within 25 m).

### Magazine slot (panel)
- `RegisterPanelItem(gunItem, { action='whip_gunny:open_weapon', slots=1, label='<label> Mag' | '<label> Chamber', read, onValidate, write, onChange })` is registered for every **firearm**, after the items, because a panel naming an unknown item is refused.
- `read`: a magless gun shows `{ item = ammoItem, amount = ammo }`; a magazine gun shows the magazine as `{ item, amount = 1, metadata }`.
- `onValidate(ctx)` (`ctx.host`, `ctx.direction`, `ctx.item`, `ctx.amount`, `ctx.swap`, `ctx.replacing`):
  - Refused during a looped reload.
  - Taking out is always allowed.
  - Into a magless gun, only its own ammo item fits: `'Only accepts <caliber> ammunition'`, `'Chamber full — it holds N rounds'`. During a swap, the current rounds don't count.
  - Into a magazine gun: `'Only magazines can be inserted'`, `'That magazine does not fit this weapon'`, `'Remove the current magazine first'`. A swap or replace is allowed.
- `write` folds the slot back into `meta.ammo` or `meta.magazine`.
- `onChange` runs after the commit. It bumps `countVersion` when this is the drawn gun and tells the client (`magazineInserted/Removed`, `maglessAmmoInserted/Removed`), which plays a reload gesture and swaps the clip component.

### Throwables
- The hand holds the whole stack. GTA throws them. The client watches GTA's count and sends `server:thrown(n)` (in chunks of up to 10).
- The server `StoreTake`s from the drawn slot (reason `'thrown'`), never gives, and caps at the stack.
- If the stack changes while drawn, the client gets `syncThrown(count, taken)`.
- G sets off every sticky bomb the player owns within **2000 m** (`ExplodeProjectiles`). It does this whether or not a throwable is drawn, and it replaces the ammo check while any bomb is out.

### Jerry can
- The ped's ammo for it is GTA petrol, 0–4500, equal to `fuel` × 45.
- Pouring on the ground is GTA's own. Every 500 ms the client reads the ped's petrol and sends `syncAmmo` (about once per second) when it is lower. The server writes `fuel` **down only** (`quiet`).
- Filling at a pump or pouring into a car is whip_fuel's job. It reads `GetHeldItem(source)` and the item def's `fuelCapacity`, then writes `fuel`. gunny sees that through `inventory:changed`, bumps the version and pushes `syncFuel` to the client.
- A new can is empty. GiveWeapon `{ fuel = n }` sets the level. See `autos-fuel-dealership.md` for the whip_fuel side.

### Vehicles
- GTA's drive-by does the shooting, and shots are counted as on foot. R does nothing in a seat; reloads are automatic.
- Controller in a seat: a double tap on RB (within `GAP_MS` 220) toggles aiming. While aiming, RB fires only after being held **100 ms** (`HOLD_MS`), so a tap fires nothing. LB never aims, because LB+A is talk.
- Not aiming, RB is the handbrake. The pad block id is `padDriveBy`.
- Controls: driver aim/fire 68/69, passenger 91/92, handbrake 76.

## The weapon bench

- `Config.WeaponBench = { enabled = true, coords = vector4(-1069.5194, -1666.3589, 3.3856, 302.7092), model = \`gr_prop_gr_bench_04b\`, label = 'Weapon Bench' }`. With `enabled = false` there is no bench, no prompt, and server installs are refused, because `near` has no position.
- On the client, inside `Whip.register`, gunny spawns the frozen bench prop and adds an `AddAction` prompt `{ id = 'weapon_bench', at = { coords }, label, onSelect }`. Pressing E there with a gun **drawn** opens the bench. Without a gun: `'You must have a weapon equipped'`. A gun that takes nothing: `'This weapon does not support attachments'`.
- The page is NUI (`html/`, styled with whip_core's `fonts.css`/`base.css` and `page-tools.js`). It uses whip_core `PlayCamera` (fov 50, 500 ms transitions, `exitKey=false`, async; framing derived from the reference bench and rotated with the heading) and `SetScreenOpen(true)`. A `Whip.padScreen` drives it from a controller: the right stick turns the gun at 600 px/s with a 0.12 dead zone.
- The display gun is `CreateWeaponObject`. It is **never deleted, only hidden** between uses, because deleting one crashes GTA V Enhanced after a few times (citizenfx/rfc #495).
- NUI callbacks: `close`, `selectWeapon`, `rotateWeapon`, `installAttachment` (`{ attachmentSlot, attachmentPocket }`) and `removeAttachment` (`{ category }`). The gun is always the one in hand, never one the page names.
- Install (`installAttachment`, within 4.0 m of the bench, `'Stand at the weapon bench'`):
  - Requires the component to exist for that weapon, slot and tier, and the slot to be free (`'That slot already has an attachment'`).
  - `StoreTake`s the attachment (take first), copies its metadata into `attachmentMeta[slot]`, and writes the gun. A failed write gives the attachment back.
- Remove (`removeAttachment`):
  - Clears the slot on the gun first, then `Whip.core:AddItem`s the attachment with its metadata.
  - If that fails, it re-fits the attachment, or logs it as LOST: `'No room for the attachment'`.
- Both answer the bench data afterwards: `{ weapon = { name, attachments, categories }, attachments = [{ slot, pocket, name, label, category, tier }] }`. The drawn gun updates at once (`attachmentInstalled/Removed`).
- The bench closes on death, logout or holster.

## Controls, commands, key mappings, pad actions, control blocks

| Input | Command / id | Does |
|---|---|---|
| R (rebindable) | `+gunny_reload` "Reload Weapon" | Reload. Guns only, on foot only, and only when `IsGameInputFree()`. |
| G (rebindable) | `+gunny_check_ammo` "Check Ammo / Detonate Sticky Bombs" | Detonate sticky bombs if any are out; otherwise check the ammo on a gun. The check gives a fuzzy text: Full / Almost full... / More than half... / Roughly half... / Less than half... / Looking low... / Basically empty... / Empty. / No magazine. |
| Pad B (on foot) | pad action `gunny_reload`, slot `foot_b`, where `foot` | Ready only while a gun is drawn |
| Pad LB+B | pad action `gunny_check_ammo`, slot `lb_b` | |
| E at the bench | AddAction `weapon_bench` | Bench |

- Commands:
  - `/gunnydebugreset` (client) zeroes the overlay counters; needs dev tools.
  - `/ammoledger [reset]` (client) prints the ammo ledger in F8 and the server console; needs dev tools.
  - `/gunnydebugserver` (server `Whip.command`, `dev = true`, `whileDead`): what is drawn. In the console it lists everyone; in game it lists your own.
- Debug tool: `RegisterDebugTool('gunny', { label='Gunny Debug', onToggle })` in /w → Debug.
- Client hooks: `beforeGiveMode` and `freeHands`.
- Control blocks (see `/whipcontrols`):
  - `gunInHand`: 45, 140–143, which stop GTA's reload and pistol-whip with a gun in hand. The weapon wheel (HUD 19) is hidden.
  - `gunReloading`
  - `gunGoingAway`
  - `padDriveBy`

## Recipes

Give a gun and take exactly that one back (armory):
```lua
local issued = {}
local function issue(source)
  local ok, where, gunSerial = exports.whip_gunny:GiveWeapon(source, 'gunny_carbinerifle', { loaded = true }, 'armory issue')
  if not ok then return false, where end
  local _, _, magSerial = exports.whip_gunny:GiveMagazine(source, 'gunny_mag_carbinerifle', 999, 'armory issue')
  issued[source] = { gunSerial, magSerial }
  return true
end
local function takeBack(source)
  for _, serial in ipairs(issued[source] or {}) do
    local at = exports.whip_core:FindItemByMetadata('serial', serial)
    if at and at.kind == 'player' and at.id == source then
      exports.whip_core:StoreTake(at, 1, { reason = 'returned to the armory' })   -- a drawn gun is holstered first
    end
  end
  issued[source] = nil
end
```
A spare magazine that has been put into a gun is inside it, so its serial finds nothing until it comes out.

Every shot fired (server): `AddEventHandler('whip_gunny:weapon:fired', function(e) ... e.coords may be nil ... end)`. It runs as often as anyone fires, so keep the handler short and rate-limit alerts per `e.source`.

HUD rounds (client): on `whip_gunny:weapon:drawn` with `w.kind == 'gun'`, start a loop that reads `GetDrawnWeapon()` about every 150 ms. On `:holstered`, end it by bumping a token counter.

No weapons here: call `exports.whip_core:BlockHands(source, 'myjail', { only = 'weapons', label = 'No weapons in here' })` (server; the client form is `BlockHands(id, opts)`). gunny refuses draws with the label and puts away a drawn gun until `UnblockHands`. A zone's own "Weapons away" rule acts on GTA's weapons, not gunny's.

## How gunny uses whip_core

| whip_core API | Where | Purpose |
|---|---|---|
| `Whip.register`, `Whip.isReady`, `Whip.startProblem`, `Whip.sayStarted`, `Whip.command`, `Whip.padScreen`, `Whip.weapons` (satellite) | everywhere | declarations, start report, commands, the pad on NUI, catalog |
| `RegisterItem`, `RegisterItemDefaultMetadata` | server/items.lua | items and new-item serials |
| `RegisterContextAction`, `RegisterPanelItem` | items, magpanel | right-click options and the magazine slot |
| `OnItemSettingChanged`, `GetItemSetting` | shared/catalog.lua | item settings |
| `SecureCallback`, `SecureEvent` | server/main.lua | every client→server message |
| `GetItemAt`, `SetItemMetadata` (opts `quiet`), `StoreTake`, `FindAllItems`, `GetItemCount`, `RemoveItem`, `AddItem` (opts `noDrop`) | server | inventory reads and writes |
| `Progress` | magazines | server-timed bar |
| `SetHeldItem` | weapons | the held item, read by whip_fuel through `GetHeldItem` |
| `AreHandsBlocked` (both sides) | draw | blocks |
| `NotifyPlayer` / `Notify` | both | messages |
| `GetGroundItem`, `GetGroundItemsNearby` | ledger | debug |
| `PermitNativeWeapon` | client/weapons.lua | weapon guard |
| `BlockControls`, `UnblockControls`, `IsGameInputFree` | client | controls |
| `RegisterPadAction`, `SetPadActionReady`, `IsControllerActive` | client | controller |
| `RegisterClientHook('beforeGiveMode'/'freeHands')` | client/main.lua | hand moments |
| `IsProgressActive`, `LoadAnimDict`, `LoadModel`, `IsPlayerDead`, `HasDevTools` | client | helpers |
| `PlayCamera`, `StopCamera`, `SetScreenOpen`, `AddAction`, `RegisterDebugTool` | client | bench and debug |
| events: `whip_core:inventory:changed`, `player:logout`, `player:died`, `hands:blocked`, `pad:deviceChanged`, `item:added`/`item:removed` | both | reactions |

## whip_core weapon catalog (Whip.weapons)

`whip_core/shared/weapon_catalog.lua` and `lib/satellite.lua:1726`.
- `Whip.weapons(list, opts)` (BOTH sides, one call in a shared file) adds a resource's add-on weapons to every WHIP weapon list: the Director's NPC weapons and its Hold a Weapon step, Fixed Weapons (firearms with a model), Dungeon Mode, and the Object Viewer's Give a weapon. Each is shown as "`Label (tag)`".
  - `list` entries are `{ name, label, group, model? }`.
  - `name` must match `^WEAPON_[A-Z0-9_]+$` (uppercased, ≤64) and must **not** be one of GTA's.
  - `label` is 1–40 characters.
  - `group` is one of `pistol`, `smg`, `rifle`, `machine gun`, `shotgun`, `sniper`, `heavy`, `thrown`, `stun gun` or `melee`.
  - `model` is a firearm's world model and is only allowed for the firearm groups (pistol, smg, rifle, machine gun, shotgun, sniper, heavy). It is lowercased, `^[%w_]+$`, and must not be a GTA weapon's model or another weapon's.
  - `opts.tag` is ≤16 characters and defaults to the resource name.
  - At most **200** per resource. Calling again **replaces** the whole list. Nothing is added if any entry is refused.
  - Returns false (and prints) if `list` is not a table. whip_core's refusal is printed as `[res] Whip.weapons refused: why`.
  - The weapons go when the resource stops. `Whip.removeWeapons()` removes them all.
  - An NPC given one carries the GTA gun, never your item, so none of your ammo or reload code applies to it.
- Exports behind it: `__AddWeapons(list, opts)` → `true | false, why` and `__RemoveWeapons()` → `true`.
- Internal API: `WeaponCatalog.get(name)`, `.modelOf(name)`, `.weaponOf(model)`, `.title(w)`, `.goneWith(name)`, `.list()` (sorted by group in GTA order, then by label, GTA's first) and `.onChange(fn)`.
- gunny's `shared/whip_weapons.lua` lists its 15 add-ons with `{ tag = 'gunny' }`. The firearms have models: `w_pi_whip_heavypistol`, `w_pi_whip_revolver`, `w_pi_whip_revolvermk2`, `w_pi_whip_wep1_gun` (Double-Action), `w_pi_whip_wep2_gun` (Navy), `w_ar_whip_assaultrifle`, `w_sg_whip_pumpshotgun`, `w_sg_whip_sawnoff` and `w_sr_whip_sniperrifle`. The six melee have none. Labels come from the matching item.
- `GtaWeapons` (`shared/gta_weapons.lua`) holds **108** GTA weapons from DurtyFree's dump: pistol 19, smg 8, rifle 15, machine gun 5, shotgun 9, sniper 7, heavy 12, thrown 12, stun gun 2, melee 19. Fields are `{ name, label, group }`, with `GtaWeapons.byName`. Editors offer only weapons this game has (checked with `IsWeaponValid`).
- `GtaWeaponModels` (`shared/gta_weapon_models.lua`): `groups` lists the Fixed-Weapon groups, `byName[WEAPON_X] = 'w_...'`, and there are `modelOf(name)` and `weaponOf(model)`. A model shared by two weapons belongs to `WEAPON_GRENADELAUNCHER`.

## whip_core weapon guard

`whip_core/client/weapon_guard.lua`; config `Config.WeaponGuard = { Enabled = true, Allow = { 'GADGET_PARACHUTE' }, SweepMs = 5000 }`. It is editable in /whip Settings as "Block GTA's own guns" (`WeaponGuard.Enabled`) and "GTA weapons players may keep" (`WeaponGuard.Allow`, up to 50 names).
- Purpose: no GTA gun that WHIP did not hand out (a dead NPC's gun, a police car's shotgun). It has three layers, none of them per frame:
  1. All weapon pickups are made uncollectable for the player at each spawn.
  2. Ped config flag 14 is set, so the ped doesn't drop its weapons when dead.
  3. A sweep removes every listed weapon that nothing permits. It runs on spawn, revive and model change; on vehicle entry (+1 s and +3 s); on a collected pickup (`gameEventTriggered`); on Settings changes; and every `max(1000, SweepMs)` ms. It prints `[whip_core:weapons] took X (why): not handed out by whip`.
- `PermitNativeWeapon(weapon, on)` — CLIENT. `weapon` is a hash or a name. Call it **before** `GiveWeaponToPed` and **after** `RemoveWeaponFromPed`. Permits use a shared registry: several resources may permit one weapon, and the permit lasts until the last one lets go or stops. Your permits go when your resource stops. Returns `false` for a weapon that is not a hash or name, otherwise `true`.
- The swept list is a fixed list of GTA base weapon names (`WEAPON_NAMES`), including the parachute, `WEAPON_PETROLCAN`, the hazard and fertilizer cans, briefcases, digiscanner, and so on. **Add-on weapons (`WEAPON_WHIP_*`, pack weapons) are not in the list and are never swept.** gunny calls `PermitNativeWeapon` for every weapon anyway.
- whip_core's own thrown ball (`WEAPON_BALL`) is permitted the same way (`client/inventory.lua`).

## Debugging and troubleshooting

- /w → Debug → **Gunny Debug** (developer mode) shows on screen the drawn weapon's rounds as the game, gunny and the server count them, shots sent against confirmed, stale answers, count jumps, and magazines carried (polled every 100 frames through `countInventoryMags`). It also turns on `[GUNNY]` debug prints here and on the server while anyone has it on.
- `[GUNNY] WARNING: ...` lines always print. They report a failed write or an undo that did not land ("... LOST ...").
- Ammo ledger (`server/ledger.lua`) applies to magless guns only. It tracks ground (piles within 60 m), pockets, gun and spent rounds; a sum that stays off for 1 s is printed as `LEAK`. Moving rounds elsewhere (a stash, a car, another player) reads as a leak.

A gun that won't reload:
| Player sees | Cause |
|---|---|
| No magazines for this weapon on you | none of its `compatibleMags` is carried |
| All your magazines for this weapon are empty | Load Bullets one, carrying its caliber's rounds |
| No ammunition for this weapon on you | a magless gun needs its caliber's loose rounds |
| No room for the old magazine | the old magazine had nowhere to go, not even the ground, so the reload was undone |
| Nothing at all | R does nothing in a vehicle, with a melee weapon or throwable, with a screen or bar up (`IsGameInputFree` false), or while the gun is being put away |

## Learning from gunny: WHIP patterns

1. **Declare every client message.** Use `SecureEvent`/`SecureCallback` inside `Whip.register`; whip_core rate-limits and type-checks the params before the handler runs.
   - `'int'` **clamps** into range (9999 counts as 10) and does not refuse, which suits shot counts.
   - Use `'amount'` for money and items (it refuses) and `'id'` for an exact id.
   - gunny's wrappers exist only to re-declare when packs change the item lists for the `'slot'` params. They refill the same list tables in place and re-run every declaration once per burst (`server/main.lua:147-162`).
2. **Declare inside `Whip.register`.** whip_core keeps items, callbacks, panels and hooks in memory. With `dependency 'whip_core'`, a whip_core restart restarts you, so there is nothing to clean up.
3. **Name the clicked item with a `'slot'` param** (`{ item = list }`). whip_core checks ownership and kind and hands over `{ addr, item, amount, metadata }`; an item moved meanwhile is refused with a readable reason. The client learns `addr.slot`/`addr.sub` from a `RegisterContextAction`. Prefix every action, event and callback with the resource name: names are server-wide, and an action name is at most **32 characters**.
4. **Declare a panel, don't handle one.** Use `read`/`write`/`onValidate`/`onChange`, or just `allowedItems`. The item must not stack and needs an action that opens it.
5. **Take before you give, and check every result.**
   - Reload takes the new magazine before giving back the old one; unload lowers the count before giving rounds.
   - A failure gives back what was taken (`GunnyGiveBack`, which logs "LOST" if even that fails).
   - `GunnyStillThere(addr, item, serial)` re-reads the slot after any wait, so an undo lands on the same item.
6. **A bar the server times.** Use server `Progress` through `Whip.core`, and load only when it returns `true`; a finish sooner than the bar could fill is refused with `'too fast'`. It waits, so run it from a SecureEvent or context action (in a thread), **never from a SecureCallback**, because the client gives up after 10 s. Read the item again afterwards. To use an item at the end of a bar, pass `RegisterUseHandler` a table.
7. **Go by the server's own record.** Shots, throws and holsters use `GunnyDrawnWeapon` (slot + serial), never a slot the client names. Give findable items a serial through `RegisterItemDefaultMetadata`; WHIP's `uid` only appears the first time an item is logged.
8. **Calling whip_core.** Call an export directly when it returns at once and you are inside a handler whip_core runs (`GetItemAt`, `SetItemMetadata`). Use `Whip.core:X(...)` for calls that can wait (`AddItem`, `Progress`), for everything after such a wait, and outside whip_core's handlers: it returns `false, why` (`'whip_core stopped'`) instead of throwing. Client side, `GunnyCallback` is `Whip.core:Callback(name, ...)`.
9. **Run per-frame work only while needed.** Use one tick thread (`GunnyStartTick`, `RegisterGunnyTick(name, fn(ped, now))`) that exists only while a weapon is drawn. Each job runs in its own `pcall`.
10. **Hold controls with named blocks** (`BlockControls(id, { controls | groups })`) and release them on every exit path.
11. **Let whip_core's moments drive cross-resource behaviour** (`RegisterClientHook('freeHands'|'beforeGiveMode')`, `whip_core:hands:blocked`), so whip_core never needs to know gunny exists.
12. Files to read: `server/main.lua`, `server/items.lua` (`registerWithWhip`), `server/weapons.lua` (`equipWeapon`, `GunnyDrawnWeapon`), `server/magpanel.lua`, `server/magazines.lua` (`runLoad`, `unloadBulletsFromMag`), `server/reload.lua` (`performReload`), `client/main.lua` (`GunnyCallback`, `GunnySlot`, the tick), `client/weapons.lua` (`DrawWeapon`) and `client/reload.lua` (`holdFire`).

## Gotchas

1. `whip_gunny:weapon:drawn` (server) fires when the **server** accepts the draw. The client can still abort (unknown hash, died mid-draw, game build lacks the weapon), and the server then fires `holstered` with reason `'holstered'`.
2. `GetDrawnWeapon().ammo` for the jerry can is GTA petrol **0–4500**, not the item's 0–100 `fuel`. Convert with ×45, or `Config.AmmoToFuel`.
3. `GiveWeapon` with `ammo` but neither `magazine` nor `loaded` gives an **empty** magazine gun: `ammo` applies only to a named magazine or a magless gun.
4. Passing `attachments` to `GiveWeapon` for a melee weapon, throwable or jerry can fails the whole call.
5. `GiveWeapon`'s `reason` is passed through as `AddItem`'s 5th arg, so a table such as `{ reason = 'x', noDrop = true }` works and makes a full inventory refuse instead of dropping.
6. Throwables carry no serial, so they can't be tracked with `FindItemByMetadata`. `GiveWeapon` returns no serial for them.
7. There is no server "drawn weapon" export. Use whip_core `GetHeldItem(source)` or the events.
8. A magazine inside a gun is not findable by its serial; it is nested in the gun's `meta.magazine`.
9. Loading magazines takes **300 ms per round** (a 100-round drum is 30 s). Never trigger it from a SecureCallback, which times out after 10 s; `LoadBullets` uses an event + ask id for this reason.
10. `DrawWeapon` and holsters are refused from the moment R is pressed until the reload ends, not only while the animation plays. Death and `BlockHands` still holster at once.
11. Client ammo claims are accepted only if **lower**, and only with the current `countVersion`.
12. Shots up to 2 s after a holster are still charged to the holstered gun and fire `weapon:fired`.
13. `weapon:fired` can arrive from the 5 s backup sync as well as from shot reports. `shots` is the number of rounds removed, up to 10 per report.
14. Weapon-pack items need both sides: register them in a **shared** file. Magazines must come first, or the weapon's `compatibleMags` check fails.
15. `RegisterWeapon` removes `def.attachments` from your table and keeps your table by reference.
16. A pack that wants its guns in WHIP's lists must load `@whip_core/lib/satellite.lua` and call `Whip.weapons`. The pack fxmanifest example in the docs doesn't show it.
17. The whip_core weapon guard never sweeps add-on weapons. Only GTA base weapons are policed.
18. Don't list `stream/` files in `files{}`: it breaks Enhanced start-up.
19. Lowering `internalCapacity` on the Items page trims a gun only **on its next draw**, and never below the file's default.
20. A magazine's capacity change re-registers the item; magazines already over the new size keep their rounds.
21. Item names are server-wide. `gunny_torch` is the handheld flashlight and `gunny_flashlight` is the attachment.
22. In vehicles, R and B do nothing; reloads are automatic and take at least `reloadTime`. Shell-at-a-time guns fill all at once in a seat.
23. G detonates all your sticky bombs within 2000 m even with no throwable drawn, and only does the ammo check when none are out.
24. The bench display gun is hidden, never deleted (Enhanced crash). The bench prompt exists whether or not a gun is drawn; the server checks 4.0 m only on install and remove.
25. A whip_core stop stops gunny first (dependency), and no `holstered` event fires for drawn guns then.

## Docs vs code

1. The documented `DrawWeapon` failures are "hands blocked, a reload, the server refused". The code also returns `'Already drawing a weapon'`, `'Unknown weapon hash'`, `'Dead'`, `'The weapon left its slot'` and a missing-game-build message (`client/weapons.lua:149,192,206,216,228`). The internal `DrawWeapon` has a 3rd `quick` param that the export does not pass (`client/weapons.lua:416`).
2. The documented `LoadBullets` reasons are a subset. The code also returns `'whip_core is not running'`, `'Magazine not found'`, `'That is not a magazine'`, `'Invalid magazine'`, `'The magazine or the rounds are not where they were'`, `'Failed to load bullets'` and whip's own refusal (`client/magazines.lua:18`, `server/magazines.lua:60-167,203-206`).
3. The docs say `GiveWeapon`'s `reason` is "as AddItem takes". The code passes it through untouched, so the options table form works as well (`server/items.lua:295,337`).
4. The docs say `ammo` is "with" `magazine`. In code, `ammo` alone on a magazine gun is silently ignored (`server/items.lua:322-332`).
5. The docs' weapon-pack manifest omits `@whip_core/lib/satellite.lua`, which the docs' own `Whip.weapons` advice needs (`whip_core/lib/satellite.lua:1749`).
6. The docs say "E at it with a gun in hand". The prompt (`AddAction 'weapon_bench'`) is always there; the gun check is client-side in `openBench`, and the distance check (4.0 m) is server-side only on install and remove (`client/attachments.lua:51-65,276-286`, `server/attachments.lua:51-59`).
7. The docs list the `holstered` reasons. The code also ends records silently, with no event, when gunny or whip_core stops (`server/main.lua:197-205`).
