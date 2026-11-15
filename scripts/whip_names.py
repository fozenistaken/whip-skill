#!/usr/bin/env python3
"""whip_names.py - build references/whip-names.json: every name WHIP really has, for whip_scan.py's
"is this invented?" checks.

  python -I whip_names.py <path-to-whip_core> <out.json>

What it collects (all from whip_core itself, nothing typed by hand):
  exports   every `function whip_core:Name(...)` stub in types/server.lua and types/client.lua, with its side
  helpers   every `Whip.*` helper in types/satellite.lua
  events    every `whip_core:...` name in types/events.lua and every 'whip_core:...' string literal in the
            source (so events the stubs miss are still known)
  fields    the keys a definition table may have, per call. Taken from the tables whip_core uses to warn
            about unknown keys itself (InteractSpec.*, CONTAINER_FIELDS, DOOR_FIELDS, SCHEMA_KEYS), and from
            the type stubs' ---@class fields where the code has no such table.

Read-only on whip_core. Standard library only.
"""
import glob
import json
import os
import re
import sys


def table_keys(text, start):
    """Top-level `key =` names of the Lua table whose `{` is at text[start]."""
    keys, depth, i, n = [], 0, start, len(text)
    while i < n:
        c = text[i]
        if c in '"\'':
            q, i = c, i + 1
            while i < n and text[i] != q:
                i += 2 if text[i] == '\\' else 1
        elif text.startswith('--', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return keys
        elif depth == 1:
            m = re.match(r'([A-Za-z_]\w*)\s*=(?!=)', text[i:i + 80])
            if m and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] in '_.')):
                keys.append(m.group(1))
                i += len(m.group(1))
                continue
        i += 1
    return keys


def lua_table(path, name):
    text = open(path, encoding='utf-8', errors='ignore').read()
    m = re.search(r'(?m)^(?:local\s+)?' + re.escape(name) + r'\s*=\s*\{', text)
    return sorted(set(table_keys(text, m.end() - 1))) if m else []


def stub_classes(paths):
    classes, cur = {}, None
    for p in paths:
        for ln in open(p, encoding='utf-8').read().split('\n'):
            m = re.match(r'^---@class\s+(\w+)(?:\s*:\s*(\w+))?', ln)
            if m:
                cur = m.group(1)
                classes[cur] = {'parent': m.group(2), 'fields': []}
                continue
            m = re.match(r'^---@field\s+([A-Za-z_]\w*)\??\s', ln)
            if m and cur:
                classes[cur]['fields'].append(m.group(1))
            elif not ln.startswith('---'):
                cur = None
    return classes


def class_fields(classes, name):
    out, seen = [], set()
    while name and name in classes and name not in seen:
        seen.add(name)
        out += classes[name]['fields']
        name = classes[name]['parent']
    return sorted(set(out))


def param_keys(stub_path, fname, param):
    """Keys of an inline table type in a stub's ---@param line: `---@param data { name: string?, roles: … }`
    or `---@param data table { name, mode, x, … }`."""
    lines = open(stub_path, encoding='utf-8').read().split('\n')
    for i, ln in enumerate(lines):
        if re.match(r'^function whip_core:' + fname + r'\(', ln):
            for back in range(i - 1, max(0, i - 40), -1):
                m = re.match(r'^---@param\s+' + param + r'\??\s+(?:table\s*)?(\{.*\})', lines[back])
                if m:
                    body = m.group(1)[1:]
                    keys, depth, tok = [], 0, ''
                    for ch in body:
                        if ch in '{(<[':
                            depth += 1
                        elif ch in '})>]':
                            if depth == 0:
                                break
                            depth -= 1
                        if depth == 0 and ch == ',':
                            tok = ''
                            continue
                        tok += ch
                        if depth == 0:
                            mm = re.match(r'^\s*([A-Za-z_]\w*)\??\s*(?::|$|\()', tok)
                            if mm and ch in ':(':
                                keys.append(mm.group(1))
                    if not keys:  # `{ name, mode, x, … }`: bare names
                        keys = re.findall(r'(?:^|,)\s*([A-Za-z_]\w*)\??', body.split('}')[0])
                    return keys
            break
    return []


def main():
    core, out = sys.argv[1], sys.argv[2]
    t = os.path.join(core, 'types')
    exports = {}
    for side, f in (('server', 'server.lua'), ('client', 'client.lua')):
        for n in re.findall(r'(?m)^function whip_core:(\w+)\(', open(os.path.join(t, f), encoding='utf-8').read()):
            exports.setdefault(n, []).append(side)
    helpers = sorted(set(re.findall(r'(?m)^function WhipSatellite\.(\w+)\(',
                                    open(os.path.join(t, 'satellite.lua'), encoding='utf-8').read())))
    helpers += ['core']
    events = set(re.findall(r'whip_core:[a-zA-Z]+:[a-zA-Z:]+', open(os.path.join(t, 'events.lua'), encoding='utf-8').read()))
    for p in glob.glob(os.path.join(core, '**', '*.lua'), recursive=True):
        if os.sep + 'types' + os.sep in p:
            continue
        events.update(re.findall(r"['\"](whip_core:[a-zA-Z]+(?::[a-zA-Z0-9_]+)+)['\"]",
                                 open(p, encoding='utf-8', errors='ignore').read()))
    # Event names built from a prefix in code (WhipEmit('whip_core:door:' .. kind)): keep the prefixes too
    prefixes = set()
    for p in glob.glob(os.path.join(core, '**', '*.lua'), recursive=True):
        prefixes.update(re.findall(r"['\"](whip_core:[a-zA-Z]+:)['\"]\s*\.\.", open(p, encoding='utf-8', errors='ignore').read()))

    classes = stub_classes([os.path.join(t, f) for f in ('classes.lua', 'server.lua', 'client.lua')])
    spec = os.path.join(core, 'shared', 'interact_spec.lua')
    fields = {
        'AddAction': {'arg': 1, 'keys': lua_table(spec, 'InteractSpec.ACTION'), 'source': 'shared/interact_spec.lua InteractSpec.ACTION',
                      'nested': {'options[]': lua_table(spec, 'InteractSpec.ACTION_OPTION'),
                                 'at': lua_table(spec, 'InteractSpec.ACTION_AT'),
                                 'require': lua_table(spec, 'InteractSpec.REQUIRE')}},
        'AddPoint': {'arg': 1, 'keys': lua_table(spec, 'InteractSpec.POINT'), 'source': 'shared/interact_spec.lua InteractSpec.POINT',
                     'nested': {'options[]': lua_table(spec, 'InteractSpec.POINT_OPTION'),
                                'at': lua_table(spec, 'InteractSpec.POINT_AT')}},
        'SecureEvent': {'arg': 2, 'keys': lua_table(os.path.join(core, 'server', 'secure.lua'), 'SCHEMA_KEYS'),
                        'source': 'server/secure.lua SCHEMA_KEYS',
                        'nested': {'near': class_fields(classes, 'WhipSecureNear')}},
        'EnsureContainer': {'arg': 2, 'keys': lua_table(os.path.join(core, 'server', 'containers.lua'), 'CONTAINER_FIELDS') + ['require'],
                            'source': 'server/containers.lua CONTAINER_FIELDS (+ require)'},
        'RegisterItem': {'arg': 2, 'keys': class_fields(classes, 'WhipItemDef'), 'source': 'types/classes.lua WhipItemDef'},
        'RegisterUseHandler': {'arg': 2, 'keys': class_fields(classes, 'WhipTimedUse'), 'source': 'types/classes.lua WhipTimedUse'},
        'EnsureJob': {'arg': 2, 'keys': sorted(set(param_keys(os.path.join(t, 'server.lua'), 'EnsureJob', 'data'))),
                      'source': 'types/server.lua EnsureJob @param data'},
        'EnsureShop': {'arg': 2, 'keys': sorted(set(param_keys(os.path.join(t, 'server.lua'), 'EnsureShop', 'data')
                                                    + class_fields(classes, 'WhipShopDef'))),
                       'source': 'types/server.lua EnsureShop @param data + WhipShopDef'},
    }
    fields['SecureCallback'] = dict(fields['SecureEvent'])
    door = lua_table(os.path.join(core, 'server', 'doors.lua'), 'DOOR_FIELDS')
    if door:
        fields['EnsureDoor'] = {'arg': 2, 'keys': door + ['require'], 'source': 'server/doors.lua DOOR_FIELDS (+ require)'}
    for k, v in list(fields.items()):
        if not v['keys']:
            print(f'warning: no fields found for {k}; it is left out')
            del fields[k]
    data = {
        'about': 'Generated by scripts/whip_names.py from whip_core. Used by whip_scan.py to flag invented names.',
        'exports': {k: sorted(set(v)) for k, v in sorted(exports.items())},
        'helpers': sorted(set(helpers)),
        'events': sorted(events),
        'event_prefixes': sorted(prefixes),
        'fields': fields,
    }
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=1, sort_keys=False)
    print(f"{len(data['exports'])} exports, {len(data['helpers'])} helpers, {len(data['events'])} events "
          f"({len(prefixes)} prefixes), field lists for {', '.join(f'{k}({len(v['keys'])})' for k, v in fields.items())}")


if __name__ == '__main__':
    main()
