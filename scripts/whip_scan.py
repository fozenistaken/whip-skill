#!/usr/bin/env python3
"""whip_scan.py - static triage for FiveM resources moving to, or built on, the WHIP framework.

Two passes, run together by default:

  port    Finds QBCore, Qbox (qbx_core), ESX, ox_core/ox_lib/ox_inventory/ox_target and common
          standalone-script calls, and names the WHIP feature that replaces each one, with the
          reference file to read. Use it to plan a port: the output is a work list, not a patch.
  review  Checks a resource that already uses WHIP against "the WHIP way": declarations in
          Whip.register, SecureEvent instead of RegisterNetEvent, no client-sent prices, session
          checks after waits, one transaction per action, manifest lines, name prefixes, and more.

It reads files as text and never runs them. Findings are leads: open each one at its line and
confirm before changing code.

Usage:
  python whip_scan.py <resource-or-folder> [--mode port|review|all] [--json] [--min-severity LOW]
  python whip_scan.py <resource> --plan        a port plan (Markdown) grouped by WHIP surface
  python whip_scan.py --selfcheck <references/export-index.md>

Exit code 1 when any HIGH finding remains (usable as a CI gate).
Python 3.9+, standard library only.
"""
import argparse
import json
import os
import re
import sys

SEVERITIES = ['INFO', 'LOW', 'MEDIUM', 'HIGH']
SKIP_DIRS = {'node_modules', '.git', 'dist', 'build', 'stream', 'html', 'web', 'ui', '.vscode'}

# ---------------------------------------------------------------------------------------------
# Port rules: (id, severity, side, regex, what it is, WHIP replacement, reference)
# side: 'any', 'server', 'client'. The replacement names WHIP exports exactly; --selfcheck
# verifies every `Name(` in backticks exists in references/export-index.md or the satellite.
# ---------------------------------------------------------------------------------------------
PORT_RULES = [
    # --- framework object / player ---
    ('P001', 'HIGH', 'any', r"exports\[['\"]qb-core['\"]\]:GetCoreObject|QBCore\s*=\s*exports|GetCoreObject\(\)",
     'QBCore core object', "Nothing to fetch. Manifest: `dependency 'whip_core'` + `@whip_core/lib/satellite.lua`; declare in `Whip.register` via `Whip.core:…`, call `exports.whip_core:…` in handlers", 'porting-to-whip.md'),
    ('P002', 'HIGH', 'any', r"getSharedObject|ESX\s*=\s*exports\[['\"]es_extended['\"]\]|esx:getSharedObject|@es_extended/imports\.lua",
     'ESX shared object', "Same as P001: satellite + `Whip.register`", 'porting-to-whip.md'),
    ('P003', 'HIGH', 'any', r"exports\.qbx_core|exports\[['\"]qbx_core['\"]\]|@qbx_core/modules/|QBX\.PlayerData|(?<![\w/])qbx\.[a-zA-Z]+\(",
     'Qbox (qbx_core) call or module', "Remove qbx_core; WHIP is the framework. Map each call with porting-to-whip.md (Qbox table)", 'porting-to-whip.md'),
    ('P004', 'HIGH', 'any', r"@ox_core/lib/init\.lua|exports\.ox_core|Ox\.GetPlayer|Ox\.GetPlayers",
     'ox_core framework call', "Remove ox_core. Player: `GetPlayer(source)` (plain table), `GetCharId(source)`", 'porting-to-whip.md'),
    ('P005', 'HIGH', 'server', r"QBCore\.Functions\.GetPlayer(?:ByCitizenId)?\(|ESX\.GetPlayerFromId\(|ESX\.GetPlayerFromIdentifier\(|:GetPlayerByCitizenId\(",
     'Player object lookup', "`GetPlayer(source)` or `GetPlayer({ charId = n })`: plain data, no methods; act through exports. Save `player.charId`, never source", 'players-stats-hud.md'),
    ('P006', 'MEDIUM', 'any', r"\.citizenid\b|xPlayer\.identifier|\.getIdentifier\(\)|PlayerData\.license",
     'Character identifier', "`player.charId` (a number, kept forever). Account: `player.userId`. Identifiers: `GetPlayerIdentifiers(source)`", 'players-stats-hud.md'),
    # --- money ---
    ('P010', 'HIGH', 'server', r"Functions\.AddMoney\(|xPlayer\.addMoney\(|xPlayer\.addAccountMoney\(|:AddMoney\(|Functions\.SetMoney\(|xPlayer\.setMoney\(",
     'Give money', "`PayPlayer(source, amount, { reason = '…' })` (cash; `method = 'bank'` for bank). Offline: `PayPlayer({ charId = n }, …)`", 'money-banks.md'),
    ('P011', 'HIGH', 'server', r"Functions\.RemoveMoney\(|xPlayer\.removeMoney\(|xPlayer\.removeAccountMoney\(|:RemoveMoney\(",
     'Take money', "`ChargePlayer(source, amount, opts)` returns a receipt; on any later failure `RefundPlayer(receipt)` (valid 30 min)", 'money-banks.md'),
    ('P012', 'MEDIUM', 'server', r"PlayerData\.money|xPlayer\.getMoney\(|xPlayer\.getAccount\(|Functions\.GetMoney\(",
     'Read balance', "Cash is banknote items: `GetPlayerCash(source)`; bank: the bank API. Usually you only need `ChargePlayer`, which picks cash then bank", 'money-banks.md'),
    ('P013', 'LOW', 'any', r"['\"]crypto['\"]|markedbills|black_money",
     'Extra money type', "No crypto/black money accounts. Make dirty money an item (`RegisterItem`) or a separate bank account", 'porting-to-whip.md'),
    # --- items / inventory ---
    ('P020', 'HIGH', 'server', r"Functions\.AddItem\(|xPlayer\.addInventoryItem\(|exports\.ox_inventory:AddItem\(|exports\[['\"](?:qb|ps|lj)-inventory['\"]\]:AddItem\(",
     'Give item', "`AddItem(source, item, amount, metadata, opts)` returns 'inventory'|'ground' or false, why", 'inventory-items.md'),
    ('P021', 'HIGH', 'server', r"Functions\.RemoveItem\(|xPlayer\.removeInventoryItem\(|exports\.ox_inventory:RemoveItem\(|exports\[['\"](?:qb|ps|lj)-inventory['\"]\]:RemoveItem\(",
     'Take item', "`RemoveItem(source, item, amount, metadata, opts)`; to move between places use one `StoreMove` call", 'inventory-items.md'),
    ('P022', 'MEDIUM', 'any', r"Functions\.GetItemByName\(|Functions\.HasItem\(|xPlayer\.getInventoryItem\(|xPlayer\.hasItem\(|exports\.ox_inventory:(?:Search|GetItemCount|GetItem)\(|-inventory['\"]\]:HasItem\(",
     'Item lookup', "`HasItem`, `GetItemCount` (server)", 'inventory-items.md'),
    ('P023', 'HIGH', 'server', r"CreateUseableItem\(|RegisterUsableItem\(|exports\.ox_inventory:registerHook|ox_inventory.*usable",
     'Usable item', "`RegisterUseHandler(item, fn | timedUseTable)` in `Whip.register`; a table gives a server-timed use with bar, anim and prop", 'inventory-items.md'),
    ('P024', 'HIGH', 'any', r"shared/items\.lua|ox_inventory/data/items\.lua|QBCore\.Shared\.Items|ESX\.Items",
     'Item definitions table', "`RegisterItem(key, def)` in your resource (prefix keys with your resource name), or /whip → Economy → Items", 'inventory-items.md'),
    ('P025', 'MEDIUM', 'any', r"RegisterStash\(|inventory:server:OpenInventory|OpenInventory\(['\"]stash|ox_inventory:openInventory",
     'Stash', "`EnsureContainer(…)`; every place items sit is a store `{ kind, id, sub, slot }`", 'stores-containers-panels.md'),
    ('P026', 'MEDIUM', 'any', r"SetItemMetadata|Functions\.SetInventory|\.info\s*=|setMetadata",
     'Item metadata', "`SetItemMetadata` (metadata is visible to the holder's game: never a secret)", 'inventory-items.md'),
    ('P027', 'LOW', 'any', r"inventory:client:ItemBox|ItemBox",
     'Item-box popup', "Not needed: WHIP's inventory shows gains itself", 'inventory-items.md'),
    # --- callbacks / events ---
    ('P030', 'HIGH', 'server', r"Functions\.CreateCallback\(|ESX\.RegisterServerCallback\(|lib\.callback\.register\(",
     'Server callback', "`SecureCallback(name, schema, fn)`: return the answer (no cb), checks run before your handler", 'security.md'),
    ('P031', 'MEDIUM', 'client', r"Functions\.TriggerCallback\(|ESX\.TriggerServerCallback\(|lib\.callback\.await\(|lib\.callback\(",
     'Client callback call', "`Callback(name, …)` on the client", 'security.md'),
    ('P032', 'HIGH', 'server', r"RegisterNetEvent\(|RegisterServerEvent\(",
     'Server net event', "`SecureEvent(name, schema, handler)`: declares rateLimit, near and value checks; handler gets (source, player, …); return false, 'why' to refuse", 'security.md'),
    ('P033', 'MEDIUM', 'any', r"QBCore:Server:OnPlayerLoaded|QBCore:Client:OnPlayerLoaded|esx:playerLoaded|qbx_core:client:playerLoaded|QBCore:Server:PlayerLoaded|ox:playerLoaded",
     'Player loaded event', "`whip_core:player:loaded` (see events-and-data.md for side and payload)", 'events-and-data.md'),
    ('P034', 'MEDIUM', 'any', r"QBCore:Client:OnPlayerUnload|QBCore:Server:OnPlayerUnload|esx:onPlayerLogout|esx:playerDropped|qbx_core:server:playerLoggedOut|ox:playerLogout",
     'Player unloaded event', "`whip_core:player:logout` (see events-and-data.md)", 'events-and-data.md'),
    ('P035', 'MEDIUM', 'any', r"QBCore:Client:OnJobUpdate|QBCore:Server:OnJobUpdate|esx:setJob|QBCore:Client:SetDuty|SetJobDuty|ToggleDuty",
     'Job / duty change', "Duty is clocking on: `ClockOn`/`ClockOff`, `IsPlayerClockedOn`; the client reads `LocalPlayer.state.whipJob`; job events in events-and-data.md", 'jobs-shops-properties-doors.md'),
    ('P036', 'LOW', 'any', r"QBCore:Client:UpdateObject|QBCore:Player:SetPlayerData|esx:setPlayerData",
     'Player data sync', "Not needed: read with `GetPlayer` / client player exports when you need it", 'players-stats-hud.md'),
    # --- jobs / gangs / metadata ---
    ('P040', 'MEDIUM', 'any', r"PlayerData\.job|xPlayer\.job|xPlayer\.getJob\(|\.job\.name|\.job\.onduty|\.job\.grade",
     'Job read', "On duty: `GetPlayerJob(source)` (nil off duty). Works there at all: `GetPlayerRole(source, job)`. Permission: `HasJobPermission`", 'jobs-shops-properties-doors.md'),
    ('P041', 'MEDIUM', 'any', r"PlayerData\.gang|\.gang\.name|SetGang\(",
     'Gang', "No gangs in WHIP: make the gang a job with `EnsureJob`", 'porting-to-whip.md'),
    ('P042', 'MEDIUM', 'any', r"shared/jobs\.lua|QBCore\.Shared\.Jobs|SetJob\(|xPlayer\.setJob\(",
     'Job definitions / set job', "`EnsureJob(key, def)` in `Whip.register`; hire with `HirePlayer`", 'jobs-shops-properties-doors.md'),
    ('P043', 'MEDIUM', 'any', r"SetMetaData\(|GetMetaData\(|PlayerData\.metadata|xPlayer\.(?:set|get)Meta\(",
     'Player metadata', "Facts: `SetPlayerFlag`/`GetPlayerFlag` (online) or `SetPlayerMetadata`. Hunger/thirst/stress: stats (`AddStat`, `RegisterStat`)", 'players-stats-hud.md'),
    ('P044', 'MEDIUM', 'any', r"['\"]hunger['\"]|['\"]thirst['\"]|['\"]stress['\"]|hud:server:|esx_status",
     'Status values', "Stats: built-in hunger/thirst (100 full → 0); your own with `RegisterStat`; listen with `OnStatChanged`", 'players-stats-hud.md'),
    # --- target / menus / UI ---
    ('P050', 'HIGH', 'client', r"exports\[['\"]qb-target['\"]\]|exports\.ox_target|exports\['ox_target'\]|exports\[['\"]qtarget['\"]\]",
     'Target system', "`AddAction({ at = { coords | entity | model | vehiclePart }, options, require = { job, onDuty, … }, reach })`; removed when your resource stops", 'interactions.md'),
    ('P051', 'MEDIUM', 'client', r"exports\[['\"]qb-menu['\"]\]|lib\.registerContext|lib\.showContext|ESX\.UI\.Menu|lib\.registerMenu|exports\[['\"]qb-radialmenu['\"]\]",
     'List / context menu', "No list menu: use `options` on an `AddAction` prompt (menus), or a select field in `Input`", 'interactions.md'),
    ('P052', 'MEDIUM', 'any', r"QBCore\.Functions\.Notify|QBCore:Notify|lib\.notify|ESX\.ShowNotification|esx:showNotification|xPlayer\.showNotification|okokNotify",
     'Notification', "`NotifyPlayer(source, text, kind)` (server), `Notify` (client), or `return false, 'why'` from a SecureEvent", 'ui-nui-camera.md'),
    ('P053', 'HIGH', 'client', r"Functions\.Progressbar|lib\.progressBar|lib\.progressCircle|exports\[['\"]progressbar['\"]\]|esx_progressbar",
     'Client progress bar', "If anything is given at the end: server `Progress(source, opts)` or a timed use. A client bar is the player's word", 'ui-nui-camera.md'),
    ('P054', 'MEDIUM', 'client', r"lib\.skillCheck|exports\[['\"]qb-skillbar['\"]\]|ps-ui|qb-minigames",
     'Skill check', "`SkillCheck(difficulty)`; server-side variant exists; custom games via `Whip.skillCheckGame`", 'ui-nui-camera.md'),
    ('P055', 'MEDIUM', 'client', r"lib\.inputDialog|exports\[['\"]qb-input['\"]\]|lib\.alertDialog|ESX\.UI\.Menu\.Open\(['\"]dialog",
     'Input / dialog', "`Input`, `Alert`, `Confirm`", 'ui-nui-camera.md'),
    ('P056', 'LOW', 'client', r"lib\.showTextUI|lib\.hideTextUI|DrawText3D|DrawText3Ds|exports\[['\"]qb-core['\"]\]:DrawText",
     '3D / text UI', "Usually a prompt says it already; else `ShowText` (client) / `ShowPlayerText` (server)", 'ui-nui-camera.md'),
    ('P057', 'MEDIUM', 'client', r"SetNuiFocus\(",
     'Own NUI focus', "Ask WHIP for the screen: `SetScreenOpen`; controls: `BlockControls`; hands: `FreeHands`", 'ui-nui-camera.md'),
    # --- zones / world ---
    ('P060', 'MEDIUM', 'any', r"PolyZone|BoxZone:Create|CircleZone:Create|ComboZone|lib\.zones\.",
     'Zones', "`EnsureZone` (server) / client zones API", 'world-zones-time-npcs.md'),
    ('P061', 'LOW', 'client', r"AddBlipForCoord\(|SetBlipRoute\(",
     'Blip / route', "Shows on WHIP's maps as is, but nameless; `ShowBlip(audience, id, { coords, label, route = true, … })` from the server keeps the name", 'porting-playbooks.md'),
    ('P066', 'MEDIUM', 'client', r"AddBlipForRadius\(|AddBlipForArea\(",
     'Radius / area blip', "WHIP's pause map and radar skip area circles: use a labelled point blip (`ShowBlip`) plus `EnsureZone` for the logic", 'porting-playbooks.md'),
    ('P062', 'MEDIUM', 'any', r"qb-doorlock|ox_doorlock|nui_doorlock",
     'Door lock resource', "`EnsureDoors` (Doors)", 'jobs-shops-properties-doors.md'),
    ('P063', 'LOW', 'any', r"qb-weathersync|vSync|cd_easytime|Renewed-Weathersync",
     'Time/weather sync', "Built in: Time & Weather API", 'world-zones-time-npcs.md'),
    ('P064', 'LOW', 'any', r"qb-houses|ps-housing|qs-housing|bcs_housing|loaf_housing",
     'Housing', "Properties & Homes: `GivePropertyKey`, `HasPropertyAccess`, …", 'jobs-shops-properties-doors.md'),
    ('P065', 'LOW', 'any', r"qb-shops|ox_inventory.*shops|esx_shops",
     'Shops', "`EnsureShop` (Shops)", 'jobs-shops-properties-doors.md'),
    # --- vehicles ---
    ('P070', 'HIGH', 'any', r"Functions\.SpawnVehicle|ESX\.Game\.SpawnVehicle|ESX\.OneSync\.SpawnVehicle|qbx\.spawnVehicle|lib\.callback.*spawnVehicle|CreateVehicleServerSetter\(",
     'Spawn vehicle', "Job/rental car: `SpawnTempVehicle(model, coords, { forSource, despawnAfter, tag })` (driver gets a key; gone on despawn or resource stop)", 'vehicles-garages.md'),
    ('P071', 'MEDIUM', 'any', r"vehiclekeys:client:SetOwner|qb-vehiclekeys|qbx_vehiclekeys|wasabi_carlock|MrNewbVehicleKeys",
     'Vehicle keys', "Keys are items: `GiveVehicleKey`", 'vehicles-garages.md'),
    ('P072', 'MEDIUM', 'any', r"exports\[['\"]LegacyFuel['\"]\]|exports\.ox_fuel|cdn-fuel|ps-fuel|SetFuel\(|GetFuel\(|Entity\(.*\)\.state\.fuel",
     'Fuel', "The 'fuel' vehicle stat (whip_fuel): vehicle stats API", 'vehicles-garages.md'),
    ('P073', 'MEDIUM', 'any', r"Functions\.SetVehicleProperties|Functions\.GetVehicleProperties|lib\.setVehicleProperties|lib\.getVehicleProperties|ESX\.Game\.SetVehicleProperties",
     'Vehicle properties', "Client: `SetVehicleProperties({ entity = veh }, props)` (a bare number is a vehicleId). Keep the look: `SetVehicleAppearance` (server)", 'vehicles-garages.md'),
    ('P074', 'LOW', 'any', r"qb-garages|jg-advancedgarages|esx_garage|qbx_garages|cd_garage",
     'Garages', "Built in: Garages", 'vehicles-garages.md'),
    ('P075', 'MEDIUM', 'any', r"player_vehicles|owned_vehicles",
     'Owned vehicle table', "WHIP owns vehicles: `CreateOwnedVehicle`, `GetVehicle({ plate = … })`, `SetVehicleData`", 'vehicles-garages.md'),
    # --- commands, db, misc ---
    ('P080', 'MEDIUM', 'server', r"QBCore\.Commands\.Add\(|lib\.addCommand\(|ESX\.RegisterCommand\(",
     'Framework command', "`Whip.command(name, opts, fn)`: rate limit, whileDead, ace, dev", 'core-concepts.md'),
    ('P081', 'LOW', 'any', r"Lang:t\(|locale\(|_U\(|TranslateCap\(",
     'Locale system', "No locale system: your resource's text is your own (keep a local table if you want one)", 'porting-to-whip.md'),
    ('P082', 'MEDIUM', 'any', r"exports\[['\"]pma-voice['\"]\]|exports\['mumble-voip'\]|exports\[['\"]saltychat['\"]\]",
     'Voice resource', "`Whip.voice(name, …)` calls whichever voice system runs (whip_voice)", 'voice.md'),
    ('P083', 'LOW', 'any', r"lib\.requestModel|lib\.requestAnimDict|lib\.waitFor|lib\.table|lib\.math",
     'ox_lib helpers', "ox_lib helpers are fine to keep; only its on-screen UI conflicts with WHIP's one-screen rule", 'porting-to-whip.md'),
    ('P084', 'INFO', 'any', r"exports\[['\"]qb-phone['\"]\]|lb-phone|npwd|gksphone|qs-smartphone",
     'Phone resource', "whip_phone: apps are modules any resource can add (see phone-chat-loadingscreen.md)", 'phone-chat-loadingscreen.md'),
    ('P085', 'MEDIUM', 'any', r"exports\[['\"]qb-management['\"]\]|qb-banking|okokBanking|Renewed-Banking|esx_society",
     'Banking / society', "Bank API: business accounts belong to jobs; `ChargePlayer`/`PayPlayer`", 'money-banks.md'),
    ('P086', 'LOW', 'any', r"qb-multicharacter|esx_multicharacter|qb-spawn|qb-apartments|qb-clothing|illenium-appearance|esx_skin|skinchanger",
     'Character / spawn / clothing', "Built into WHIP (characters, appearance editor, arrival choice): remove", 'porting-to-whip.md'),
    ('P087', 'MEDIUM', 'any', r"exports\[['\"]qb-policejob['\"]\]|qb-ambulancejob|esx_ambulancejob|hospital:server:SetDeathStatus|metadata\[['\"]isdead['\"]\]|esx:onPlayerDeath",
     'Death / EMS hooks', "Death & Revive API: `IsPlayerDead`, revive exports, death events", 'players-stats-hud.md'),
]

# ---------------------------------------------------------------------------------------------
# Review rules (only for resources that use WHIP)
# ---------------------------------------------------------------------------------------------
DECLARE = r"(?:RegisterItem|RegisterUseHandler|SecureEvent|SecureCallback|AddAction|AddPoint|Ensure\w+|RegisterStat|RegisterVehicleStat|RegisterStoreKind|RegisterPanelItem|RegisterClientHook|OnStatChanged|OnVehicleStatChanged|WatchVehicleStat)"


FOREIGN = (r"qb-core|QBCore\.|es_extended|ESX\.|qbx_core|QBX\.|ox_core|Ox\.GetPlayer|ox_inventory|ox_target|"
           r"qb-target|qb-inventory|lib\.callback|lib\.notify|lib\.progressBar|lib\.registerContext")


_NAMES = None


def load_names():
    """references/whip-names.json, or {} when it is missing (the invented-name checks are then skipped)."""
    global _NAMES
    if _NAMES is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references', 'whip-names.json')
        try:
            _NAMES = json.load(open(p, encoding='utf-8'))
        except Exception:
            _NAMES = {}
    return _NAMES


def table_keys(text, start):
    """Top-level `key =` names of the Lua table whose `{` is at text[start]. Assignments inside function
    bodies (`onSelect = function() local ok = … end`) are not keys: a block counter skips them."""
    keys, depth, block, i, n = [], 0, 0, start, len(text)
    while i < n:
        c = text[i]
        if c in '"\'':
            q, i = c, i + 1
            while i < n and text[i] != q:
                i += 2 if text[i] == '\\' else 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return keys
        elif (c.isalpha() or c == '_') and not (text[i - 1].isalnum() or text[i - 1] in '_.:'):
            w = re.match(r'[A-Za-z_]\w*', text[i:i + 80]).group(0)
            if w == 'function' or (block and w in ('if', 'do', 'repeat')):
                block += 1
            elif block and w in ('end', 'until'):
                block -= 1
            elif depth == 1 and not block and re.match(r'\s*=(?!=)', text[i + len(w):i + len(w) + 4]):
                keys.append(w)
            i += len(w)
            continue
        i += 1
    return keys


def match_close(text, i):
    """Index of the bracket closing the one at text[i] ( ( [ or { ), or -1."""
    pairs = {'(': ')', '{': '}', '[': ']'}
    stack, n = [], len(text)
    while i < n:
        c = text[i]
        if c in '"\'':
            q, i = c, i + 1
            while i < n and text[i] != q:
                i += 2 if text[i] == '\\' else 1
        elif c in pairs:
            stack.append(pairs[c])
        elif stack and c == stack[-1]:
            stack.pop()
            if not stack:
                return i
        i += 1
    return -1


def nth_arg(text, paren, n):
    """Start index (first non-space) of the n-th argument (1-based) of the call whose `(` is at paren."""
    end = match_close(text, paren)
    if end < 0:
        return None
    i, k, start = paren + 1, 1, paren + 1
    while i < end:
        c = text[i]
        if c in '({[' or c in '"\'':
            j = match_close(text, i) if c in '({[' else text.find(c, i + 1)
            i = (j if j > 0 else end) + 1
            continue
        if c == ',':
            if k == n:
                break
            k, start = k + 1, i + 1
        i += 1
    if k != n:
        return None
    while start < end and text[start] in ' \t\r\n':
        start += 1
    return start


def sub_tables(text, pos, sub):
    """Positions of the nested tables `sub` ('at', or 'options[]' = each table in the options list)."""
    name, each = (sub[:-2], True) if sub.endswith('[]') else (sub, False)
    end = match_close(text, pos)
    out, depth, i = [], 0, pos
    while i < end:
        c = text[i]
        if c in '"\'':
            j = text.find(c, i + 1)
            i = (j if j > 0 else end) + 1
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif depth == 1:
            m = re.match(name + r'\s*=\s*\{', text[i:i + 40])
            if m and not (text[i - 1].isalnum() or text[i - 1] == '_'):
                t = i + m.end() - 1
                if not each:
                    out.append(t)
                else:
                    close, j = match_close(text, t), t + 1
                    while 0 < j < close:
                        if text[j] == '{':
                            out.append(j)
                            j = match_close(text, j)
                        j += 1
                i = t
                continue
        i += 1
    return out


def side_of(rel):
    r = rel.replace('\\', '/').lower()
    name = r.rsplit('/', 1)[-1]
    if '/server/' in '/' + r or name.startswith(('sv_', 'server')) or name.endswith(('_sv.lua', '_server.lua')):
        return 'server'
    if '/client/' in '/' + r or name.startswith(('cl_', 'client')) or name.endswith(('_cl.lua', '_client.lua')):
        return 'client'
    return 'shared'


def strip_comments(text):
    """Blank out Lua comments, keeping line numbers. Strings are left alone (good enough for triage)."""
    text = re.sub(r'--\[(=*)\[.*?\]\1\]', lambda m: '\n' * m.group(0).count('\n'), text, flags=re.S)
    return re.sub(r'--[^\n]*', '', text)


def line_of(text, pos):
    return text.count('\n', 0, pos) + 1


_BLOCK_TOK = re.compile(r'--\[(=*)\[.*?\]\1\]|--[^\n]*|\[(=*)\[.*?\]\2\]|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\''
                        r'|\b(function|if|do|repeat|end|until)\b', re.S)


def block_problem(text):
    """W005: do Lua's blocks balance? Openers (function, if, do, repeat) against closers (end, until), outside strings
    and comments. Returns None, or (line, what is wrong). Not a parser: a stray or missing `end` is what it catches."""
    stack = []
    for m in _BLOCK_TOK.finditer(text):
        w = m.group(3)
        if not w:
            continue
        line = line_of(text, m.start())
        if w in ('function', 'if', 'do', 'repeat'):
            stack.append((w, line))
        elif not stack:
            return line, f'`{w}` closes a block that was never opened'
        else:
            opener, _ = stack.pop()
            if (w == 'until') != (opener == 'repeat'):
                return line, f'`{w}` closes a `{opener}` block'
    if stack:
        w, line = stack[-1]
        return line, f'this `{w}` is never closed'
    return None


class Scan:
    def __init__(self, root, mode, min_sev):
        self.root, self.mode, self.min = root, mode, SEVERITIES.index(min_sev)
        self.findings = []

    def add(self, rid, sev, path, line, msg, fix, ref):
        if SEVERITIES.index(sev) >= self.min:
            self.findings.append(dict(rule=rid, severity=sev, file=path, line=line, issue=msg, fix=fix, ref=ref))

    # -- resources ------------------------------------------------------------------------------
    def resources(self):
        if os.path.isfile(os.path.join(self.root, 'fxmanifest.lua')):
            return [self.root]
        out = []
        for d, dirs, files in os.walk(self.root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith('.')]
            if 'fxmanifest.lua' in files or '__resource.lua' in files:
                out.append(d)
                dirs[:] = []
        return out

    def lua_files(self, res):
        for d, dirs, files in os.walk(res):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith('.')]
            for f in files:
                if f.endswith('.lua') or f.endswith('.sql'):
                    p = os.path.join(d, f)
                    if os.path.getsize(p) <= 2_000_000:
                        yield p

    # -- passes ---------------------------------------------------------------------------------
    def run(self):
        for res in self.resources():
            name = os.path.basename(os.path.abspath(res))
            manifest_path = os.path.join(res, 'fxmanifest.lua')
            manifest = open(manifest_path, encoding='utf-8', errors='ignore').read() if os.path.isfile(manifest_path) else ''
            files = list(self.lua_files(res))
            texts = {}
            for p in files:
                if p.endswith('.lua'):
                    texts[p] = open(p, encoding='utf-8', errors='ignore').read()
            for p, raw in texts.items():   # W005 first: a file that does not load makes every other finding moot
                bad = block_problem(raw)
                if bad:
                    self.add('W005', 'HIGH', os.path.relpath(p, self.root), bad[0],
                             f'Lua blocks do not balance: {bad[1]}. The file will not load',
                             'Find the stray or missing `end`/`until` near that line (removing a function often leaves its `end`)',
                             'core-concepts.md')
            uses_whip = ('whip_core' in manifest) or any('exports.whip_core' in t or 'Whip.' in t for t in texts.values())
            if name.startswith('whip_') and name in ('whip_core',):
                continue  # the framework itself
            foreign = re.search(FOREIGN, strip_comments(manifest) + '\n'.join(strip_comments(t) for t in texts.values()))
            # A resource already on WHIP gets the port pass only when it still carries another framework
            # (a half-done port); asked for explicitly with --mode port, it always runs.
            if self.mode == 'port' or (self.mode == 'all' and (foreign or not uses_whip)):
                self.port_pass(res, texts)
            if self.mode in ('review', 'all') and uses_whip:
                self.review_pass(res, name, manifest, files, texts)

    def port_pass(self, res, texts):
        for p, raw in texts.items():
            rel = os.path.relpath(p, self.root)
            side = side_of(rel)
            text = strip_comments(raw)
            for rid, sev, rside, rx, what, fix, ref in PORT_RULES:
                if rside != 'any' and side not in (rside, 'shared'):
                    continue
                for m in re.finditer(rx, text):
                    if re.search(r'(?:whip_core|Whip\.core)\s*:\s*$', text[max(0, m.start() - 24):m.start()]):
                        continue  # already a WHIP call
                    self.add(rid, sev, rel, line_of(text, m.start()), f'{what}: `{m.group(0)[:60]}`', fix, ref)
                    break  # first hit per file per rule; the port touches the whole file anyway

    def invented(self, rel, side, raw):
        """W070-W073: names WHIP does not have. Uses references/whip-names.json (scripts/whip_names.py)."""
        names = load_names()
        if not names:
            return
        text = strip_comments(raw)
        exports, helpers = names['exports'], set(names['helpers'])
        for m in re.finditer(r"(?:exports\.whip_core|exports\[['\"]whip_core['\"]\]|Whip\.core)\s*:\s*([A-Za-z_]\w*)\s*\(", text):
            n = m.group(1)
            if n not in exports:
                self.add('W070', 'HIGH', rel, line_of(text, m.start()), f'`{n}` is not a whip_core export',
                         'Find the real call in references/export-index.md (or the topic reference); never guess a WHIP name', 'export-index.md')
            elif side in ('server', 'client') and side not in exports[n]:
                self.add('W070', 'MEDIUM', rel, line_of(text, m.start()),
                         f"`{n}` is a {'/'.join(exports[n])} export, called from a {side} file",
                         'Call it on its own side (export-index.md lists both sides separately)', 'export-index.md')
        for m in re.finditer(r'\bWhip\.([A-Za-z_]\w*)\b', text):
            if m.group(1) not in helpers:
                self.add('W070', 'HIGH', rel, line_of(text, m.start()), f'`Whip.{m.group(1)}` is not a satellite helper',
                         'The Whip.* helpers are listed in core-concepts.md (satellite helper)', 'core-concepts.md')
        evs, prefixes = set(names['events']), tuple(names['event_prefixes'])
        for m in re.finditer(r"(AddEventHandler|RegisterNetEvent|TriggerEvent|TriggerServerEvent|TriggerClientEvent)\(\s*['\"](whip_core:[^'\"]+)['\"]", text):
            ev = m.group(2)
            if ev.endswith(':'):
                continue  # a prefix the code completes ('whip_core:job:' .. kind): checked where it is fired
            if ':client:' in ev or ':server:' in ev:
                self.add('W071', 'MEDIUM', rel, line_of(text, m.start()), f'`{ev}` is one of WHIP\'s own network messages',
                         'Not an API: it may change or be refused. Use the documented whip_core:<domain>:<pastTense> events or an export', 'events-and-data.md')
            elif ev not in evs and not ev.startswith(prefixes):
                self.add('W071', 'HIGH', rel, line_of(text, m.start()), f'`{ev}` is not an event WHIP fires',
                         'Pick a real event from events-and-data.md; never guess an event name', 'events-and-data.md')
        for call, spec in names['fields'].items():
            for m in re.finditer(r"(?:exports\.whip_core|Whip\.core)\s*:\s*" + call + r"\s*\(", text):
                arg = nth_arg(text, m.end() - 1, spec['arg'])
                if arg is None or text[arg] != '{':
                    continue
                self.check_keys(rel, text, arg, call, '', spec['keys'], spec)
                for sub, allowed in (spec.get('nested') or {}).items():
                    for pos in sub_tables(text, arg, sub):
                        self.check_keys(rel, text, pos, call, sub, allowed, spec)

    def check_keys(self, rel, text, pos, call, where, allowed, spec):
        allowed = set(allowed)
        for k in table_keys(text, pos):
            if k not in allowed:
                sev = 'MEDIUM' if 'InteractSpec' in spec['source'] or 'FIELDS' in spec['source'] or 'SCHEMA' in spec['source'] else 'LOW'
                near = [a for a in sorted(allowed) if a.lower().startswith(k.lower()[:3])][:3]
                self.add('W072', sev, rel, line_of(text, pos), f"`{call}`{(' ' + where) if where else ''}: `{k}` is not a key it reads",
                         f"Allowed: see the reference ({spec['source']})" + (f"; did you mean {', '.join(near)}?" if near else ''),
                         'export-index.md')

    def review_pass(self, res, name, manifest, files, texts):
        mrel = os.path.relpath(os.path.join(res, 'fxmanifest.lua'), self.root)
        if manifest:
            if not re.search(r"dependenc(?:y|ies)[^\n]*whip_core|['\"]whip_core['\"]", manifest):
                self.add('W001', 'HIGH', mrel, 1, "No `dependency 'whip_core'`",
                         "Add `dependency 'whip_core'`: starts whip_core first and restarts you with it", 'core-concepts.md')
            if '@whip_core/lib/satellite.lua' not in manifest:
                self.add('W002', 'MEDIUM', mrel, 1, 'Satellite helper not loaded',
                         "Add `'@whip_core/lib/satellite.lua'` first in shared_scripts for `Whip.register`/`Whip.core`", 'core-concepts.md')
            if 'whip_requires' not in manifest:
                self.add('W003', 'LOW', mrel, 1, 'No `whip_requires`',
                         "Add `whip_requires '1.0'` so the setup report flags an older whip_core", 'core-concepts.md')
            if re.search(r"lua54\s+['\"]yes['\"]", manifest) is None:
                self.add('W004', 'LOW', mrel, 1, "No `lua54 'yes'`", "Add `lua54 'yes'` (WHIP's examples use it)", 'core-concepts.md')
        for p in files:
            if p.endswith('.sql'):
                self.add('W033', 'MEDIUM', os.path.relpath(p, self.root), 1, 'Resource ships a .sql file',
                         'Create tables with `EnsureTable(name, createSql, migrations)` in `Whip.register`: nobody imports SQL', 'core-concepts.md')
        for p, raw in texts.items():
            rel = os.path.relpath(p, self.root)
            side = side_of(rel)
            text = strip_comments(raw)
            lines = text.split('\n')
            has_register = 'Whip.register' in text
            # W010: declarations at file scope through exports
            for m in re.finditer(r'(?m)^exports\.whip_core:' + DECLARE + r'\(', text):
                self.add('W010', 'HIGH', rel, line_of(text, m.start()), 'Declaration at file scope through exports',
                         'Move into `Whip.register(function() Whip.core:… end)`: whip_core forgets declarations when it restarts', 'core-concepts.md')
            if not has_register:
                for m in re.finditer(r'exports\.whip_core:' + DECLARE + r'\(', text):
                    self.add('W011', 'INFO', rel, line_of(text, m.start()), 'Declaration in a file with no `Whip.register`',
                             'Fine if this function is only called from a `Whip.register` body; otherwise move it there (the one rule)', 'core-concepts.md')
                    break
            for m in re.finditer(r"AddEventHandler\(\s*['\"]onResourceStart['\"]", text):
                first = line_of(text, m.start()) - 1
                body = '\n'.join(lines[first:first + 12])
                if re.search(r"['\"]whip_core['\"]|whip_core:" + DECLARE, body):
                    self.add('W012', 'MEDIUM', rel, line_of(text, m.start()), 'Registering on onResourceStart',
                             'Use `Whip.register`: onResourceStart misses the first start and needs your own guards', 'core-concepts.md')
            for m in re.finditer(r'CreateThread\(\s*function\s*\(\s*\)\s*\n?\s*(?:Citizen\.)?Wait\(\s*\d+\s*\)[^\n]*\n(?:[^\n]*\n){0,4}?[^\n]*(?:exports\.whip_core|Whip\.core):' + DECLARE, text):
                self.add('W013', 'HIGH', rel, line_of(text, m.start()), 'Wait-then-register thread',
                         'Registers once; a whip_core restart strips it. Use `Whip.register`', 'core-concepts.md')
            if side in ('server', 'shared'):
                for m in re.finditer(r'\bRegisterNetEvent\(|\bRegisterServerEvent\(', text):
                    if side == 'server':
                        self.add('W020', 'HIGH', rel, line_of(text, m.start()), 'Plain net event in a WHIP resource',
                                 '`SecureEvent(name, { rateLimit, near, … }, fn)`: checks run before your code; return false, why', 'security.md')
                for m in re.finditer(r'(?m)^\s*RegisterCommand\(', text):
                    if side == 'server':
                        self.add('W021', 'MEDIUM', rel, line_of(text, m.start()), 'RegisterCommand on the server',
                                 '`Whip.command(name, { ace, rateLimit, whileDead, dev }, fn)`', 'core-concepts.md')
            if side in ('client', 'shared'):
                for m in re.finditer(r"TriggerServerEvent\(\s*['\"][^'\"]+['\"]\s*,([^\n)]*)", text):
                    args = m.group(1)
                    if re.search(r'\b(price|cost|amount|money|cash|pay|reward|count|qty|quantity|item|itemName)\b', args, re.I):
                        self.add('W022', 'HIGH', rel, line_of(text, m.start()), f'Client sends a value the server should decide: `{args.strip()[:50]}`',
                                 'Send nothing (or an id the server checks against its own table); price, item and amount come from server config', 'security.md')
                for m in re.finditer(r'\bSetNuiFocus\(', text):
                    if 'SetScreenOpen' in text:
                        break  # focus beside WHIP's screen claim is the documented pattern
                    self.add('W050', 'MEDIUM', rel, line_of(text, m.start()), 'Own NUI focus',
                             'Ask WHIP for the screen with `SetScreenOpen` (one owner, released on stop)', 'ui-nui-camera.md')
                    break
                for m in re.finditer(r'\bDisableControlAction\(', text):
                    self.add('W051', 'LOW', rel, line_of(text, m.start()), 'Disabling controls by hand',
                             '`BlockControls` (one owner, released on stop)', 'ui-nui-camera.md')
                    break
                for m in re.finditer(r'while\s+true\s+do\s*\n(?:[^\n]*\n){0,25}?[^\n]*\bWait\(\s*0\s*\)', text):
                    self.add('W052', 'MEDIUM', rel, line_of(text, m.start()), 'Per-frame loop',
                             'React to events/listeners instead; if it must run per frame, measure with WhipCost and call only quick exports behind `Whip.isReady()`', 'server-ops-devtools.md')
            # SecureEvent without near
            for m in re.finditer(r'SecureEvent\(\s*([\'"][^\'"]+[\'"])\s*,\s*\{(.*?)\}\s*,\s*function', text, re.S):
                if 'near' not in m.group(2):
                    self.add('W023', 'INFO', rel, line_of(text, m.start()), f'SecureEvent {m.group(1)} has no `near`',
                             'Add `near = { at, range, message }` when the action belongs to a place', 'security.md')
            # waits before giving without a session check
            if re.search(r'\b(?:Wait\(|Progress\(|SkillCheck\(|Callback\()', text) and \
               re.search(r':(?:AddItem|PayPlayer|StoreGive|GiveVehicleKey|GiveOnLogin)\(', text) and \
               'IsSessionCurrent' not in text and side != 'client':
                m = re.search(r':(?:AddItem|PayPlayer|StoreGive)\(', text)
                self.add('W030', 'MEDIUM', rel, line_of(text, m.start()), 'Gives after a wait with no session check',
                         'After any wait (Progress, Wait, DB), check `IsSessionCurrent(source, player.session)` before giving', 'core-concepts.md')
            # RemoveItem then AddItem close together -> StoreMove
            for i, ln in enumerate(lines):
                if re.search(r':RemoveItem\(', ln):
                    window = '\n'.join(lines[i:i + 12])
                    if re.search(r':(?:AddItem|StoreGive)\(', window):
                        self.add('W031', 'LOW', rel, i + 1, 'Remove then add as two calls',
                                 'One `StoreMove` call moves items between any two stores in one action/transaction', 'stores-containers-panels.md')
                        break
            # own SQL within a few lines after a money/item change, in the same handler
            for m in re.finditer(r':(?:RemoveItem|AddItem|ChargePlayer|PayPlayer|StoreMove|StoreGive)\(', text):
                after = text[m.end():m.end() + 1500]
                stop = re.search(r'\n(?:end\)|function\b|local function\b)', after)
                after = after[:stop.start()] if stop else after
                q = re.search(r'MySQL\.(?:insert|update|query|prepare|rawExecute|transaction)', after)
                if q:
                    self.add('W032', 'MEDIUM', rel, line_of(text, m.end() + q.start()), 'Own SQL right after an inventory/money change',
                             '`CommitWithAction(queries)` writes your rows in the same transaction as the action', 'core-concepts.md')
                    break
            for m in re.finditer(r'(?m)^\s*(?:exports\.whip_core|Whip\.core):ChargePlayer\(', text):
                self.add('W034', 'HIGH', rel, line_of(text, m.start()), 'ChargePlayer result ignored',
                         '`local receipt, why = …ChargePlayer(…)`; refuse when false; `RefundPlayer(receipt)` if what they paid for fails', 'money-banks.md')
            if re.search(r'(?m)^\s*exports\(', text) and '__cfx_functionReference' not in text:
                for m in re.finditer(r"type\(\s*\w+\s*\)\s*==\s*['\"]function['\"]", text):
                    self.add('W040', 'MEDIUM', rel, line_of(text, m.start()), "`type(fn) == 'function'` in a file with exports",
                             'A function passed through an export is a callable reference, not a function: test `fn ~= nil`, call with pcall', 'core-concepts.md')
                for m in re.finditer(r'(?m)return\s+nil\s*,', text):
                    self.add('W042', 'INFO', rel, line_of(text, m.start()), '`return nil, why` from code that exports',
                             'Return `false, why`: an export cuts its returns at the first nil', 'core-concepts.md')
            for m in re.finditer(r'\b(?:type|tostring|tonumber|json\.encode)\(\s*exports\.whip_core:', text):
                self.add('W041', 'LOW', rel, line_of(text, m.start()), 'Export result passed straight into another call',
                         'A nil return arrives as no value: assign to a local first', 'core-concepts.md')
            self.invented(rel, side, raw)
            # name prefixes
            for m in re.finditer(r":(RegisterItem|RegisterStat|RegisterVehicleStat)\(\s*['\"]([\w-]+)['\"]", text):
                if not m.group(2).startswith(name.split('_example')[0].replace('whip_', '') + '_') and not m.group(2).startswith(name + '_'):
                    self.add('W053', 'LOW', rel, line_of(text, m.start()), f"Name `{m.group(2)}` not prefixed with the resource name",
                             f"Prefix: `{name}_…` (names are server-wide, first come first served)", 'core-concepts.md')
            for m in re.finditer(r":(SecureEvent|SecureCallback)\(\s*['\"]([^'\"]+)['\"]", text):
                ev = m.group(2)
                if ':' not in ev:
                    self.add('W054', 'LOW', rel, line_of(text, m.start()), f'Event `{ev}` has no `resource:` prefix',
                             f'Name it `{name}:…`', 'core-concepts.md')
            if re.search(r'MySQL\.[\w.]+\([^\n]*\bsource\b', text):
                m = re.search(r'MySQL\.[\w.]+\([^\n]*\bsource\b', text)
                self.add('W060', 'MEDIUM', rel, line_of(text, m.start()), 'A server id may be saved to the database',
                         'Save `player.charId`; server ids are reused by the next player', 'core-concepts.md')

    # -- output ---------------------------------------------------------------------------------
    def report(self, as_json):
        self.findings.sort(key=lambda f: (-SEVERITIES.index(f['severity']), f['file'], f['line']))
        if as_json:
            print(json.dumps(self.findings, indent=2))
            return
        if not self.findings:
            print('No findings. A clean scan is not proof: walk the checklists in the references.')
            return
        cur = None
        for f in self.findings:
            if f['severity'] != cur:
                cur = f['severity']
                print(f'\n== {cur} ==')
            print(f"[{f['rule']}] {f['file']}:{f['line']}  {f['issue']}\n        fix: {f['fix']}  (read references/{f['ref']})")
        counts = {s: sum(1 for f in self.findings if f['severity'] == s) for s in SEVERITIES}
        print('\n' + '  '.join(f'{s}={counts[s]}' for s in reversed(SEVERITIES)))


    def plan(self):
        """A port plan: findings grouped by the WHIP surface they move to, plus what the scan saw."""
        by_area = {}
        for f in self.findings:
            if not f['rule'].startswith('P'):
                continue
            area = area_of(f['rule'])
            by_area.setdefault(area, []).append(f)
        root = os.path.abspath(self.root)
        inv = {'files': 0, 'lua_lines': 0, 'sql': [], 'nui': False, 'locales': False}
        for res in self.resources():
            for d, dirs, files in os.walk(res):
                dirs[:] = [x for x in dirs if x not in ('node_modules', '.git')]
                for fn in files:
                    p = os.path.join(d, fn)
                    inv['files'] += 1
                    if fn.endswith('.lua'):
                        with open(p, encoding='utf-8', errors='ignore') as fh:
                            inv['lua_lines'] += sum(1 for _ in fh)
                    elif fn.endswith('.sql'):
                        inv['sql'].append(os.path.relpath(p, root))
                    elif fn.endswith('.html'):
                        inv['nui'] = True
                if os.path.basename(d) in ('locales', 'locale', 'lang'):
                    inv['locales'] = True
        print(f'# WHIP port plan: {os.path.basename(root)}\n')
        print(f"{inv['files']} files, {inv['lua_lines']} Lua lines, {sum(len(v) for v in by_area.values())} port points."
              + (f" Ships SQL ({', '.join(inv['sql'])}): becomes EnsureTable." if inv['sql'] else '')
              + (' Has its own NUI: keep it, but take the screen with SetScreenOpen and use WHIP tokens.' if inv['nui'] else '')
              + (' Has locales: WHIP has no locale system, keep them.' if inv['locales'] else ''))
        print('\nWork through the areas in this order. For each, read the reference, apply the WHIP surface, '
              'then tick the matching section of references/integration.md.\n')
        for area in AREA_ORDER:
            items = by_area.get(area)
            if not items:
                continue
            title, surface = AREAS[area]
            print(f'## {title}\n\nWHIP surface: {surface}\n')
            seen = set()
            for f in sorted(items, key=lambda x: (x['rule'], x['file'], x['line'])):
                key = (f['rule'], f['file'])
                if key in seen:
                    continue
                seen.add(key)
                print(f"- [ ] {f['file']}:{f['line']}  {f['issue']}\n      → {f['fix']}  ({f['ref']})")
            print()
        print('## Always, even when the scan found nothing for it\n')
        for line in ALWAYS:
            print(f'- [ ] {line}')
        print('\nThen run `whip_scan.py <resource>` (review mode) until nothing above LOW remains.')


AREAS = {
    'boot': ('1. Manifest, framework object, identity', "satellite + Whip.register; charId; EnsureTable (core-concepts.md)"),
    'security': ('2. Events and callbacks', 'SecureEvent / SecureCallback with params, rateLimit, near; the Monitor (security.md)'),
    'money': ('3. Money', 'ChargePlayer receipts, PayPlayer, business accounts, bank statements (money-banks.md)'),
    'items': ('4. Items and storage', 'RegisterItem + pictures, timed use, containers, StoreMove (inventory-items.md, stores-containers-panels.md)'),
    'jobs': ('5. Jobs, status, metadata', 'EnsureJob roles/permissions, duty, stats, player flags (jobs-shops-properties-doors.md, players-stats-hud.md)'),
    'world': ('6. World: prompts, zones, doors, blips', 'AddAction, EnsureZone, EnsureDoors, ShowBlip (interactions.md, world-zones-time-npcs.md)'),
    'ui': ('7. Screens and UI', 'Notify, server Progress, SkillCheck, Input/Confirm, SetScreenOpen (ui-nui-camera.md)'),
    'vehicles': ('8. Vehicles', 'SpawnTempVehicle, keys, vehicle stats, garages (vehicles-garages.md)'),
    'admin': ('9. Commands, admin, misc', 'Whip.command, dev pages, permissions, configPage, voice, phone (server-ops-devtools.md, integration.md)'),
}
AREA_ORDER = ['boot', 'security', 'money', 'items', 'jobs', 'world', 'ui', 'vehicles', 'admin']
ALWAYS = [
    "Manifest: dependency 'whip_core', whip_requires '1.0', '@whip_core/lib/satellite.lua' first, lua54 'yes'",
    'Every declaration inside Whip.register; Whip.sayStarted() once on the server',
    'Admin-editable values on a Whip.configPage; admin tools on a RegisterDevPage or behind RegisterPermission',
    'LogActivity for every meaningful action; business money into the job business account',
    'A whip_phone module for anything players check from afar',
    'Logout mid-action, whip_core restart and resource stop all clean up (IsSessionCurrent, tags)',
]


def area_of(rule_id):
    n = int(rule_id[1:])
    if n < 10:
        return 'boot'
    if n < 20:
        return 'money'
    if n < 30:
        return 'items'
    if n < 40:
        return 'security'
    if n < 50:
        return 'jobs'
    if n < 60:
        return 'ui' if n >= 51 else 'world'
    if n < 70:
        return 'world'
    if n < 80:
        return 'vehicles'
    return 'admin'


def selfcheck(index_path):
    """Every `Name(` in a fix text must be a real whip_core export or a Whip.* satellite call."""
    idx = open(index_path, encoding='utf-8').read()
    exports = set(re.findall(r'^\| `(\w+)\(', idx, re.M))
    satellite = {'register', 'core', 'command', 'skillCheckGame', 'voice', 'isReady', 'configPage', 'playerSetting'}
    bad = []
    for rule in PORT_RULES:
        for n in re.findall(r'`(?:Whip\.)?(\w+)\(', rule[5]):
            if n not in exports and n not in satellite:
                bad.append((rule[0], n))
    src = open(__file__, encoding='utf-8').read()
    for n in set(re.findall(r"fix[^\n]*?`(?:Whip\.)?(\w+)\(", src)):
        if n not in exports and n not in satellite and n not in ('fn', 'name'):
            bad.append(('review', n))
    for rule in PORT_RULES:
        ref = os.path.join(os.path.dirname(index_path), rule[6])
        if not os.path.isfile(ref):
            bad.append((rule[0], 'missing reference ' + rule[6]))
    if bad:
        print('Unknown names in rule texts:', sorted(set(bad)))
        return 1
    print(f'selfcheck ok: {len(PORT_RULES)} port rules, every named export exists ({len(exports)} in index)')
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path', nargs='?')
    ap.add_argument('--mode', choices=['port', 'review', 'all'], default='all')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--min-severity', choices=SEVERITIES, default='INFO')
    ap.add_argument('--selfcheck', metavar='EXPORT_INDEX')
    ap.add_argument('--plan', action='store_true', help='port plan grouped by WHIP surface (implies --mode port)')
    a = ap.parse_args()
    if a.selfcheck:
        sys.exit(selfcheck(a.selfcheck))
    if not a.path or not os.path.isdir(a.path):
        ap.error('give a resource folder or a folder of resources')
    s = Scan(a.path, 'port' if a.plan else a.mode, 'INFO' if a.plan else a.min_severity)
    s.run()
    if a.plan:
        s.plan()
        sys.exit(0)
    s.report(a.json)
    sys.exit(1 if any(f['severity'] == 'HIGH' for f in s.findings) else 0)


if __name__ == '__main__':
    main()
