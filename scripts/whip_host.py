#!/usr/bin/env python3
"""whip_host.py - step 1 of a WHIP server setup (scan), and a check of a finished install.

  scan  [folders...]       What this machine already has, so the questions you ask the user are the right ones:
                           OS, disk, FXServer artifacts (and the current recommended one), databases (binaries,
                           versions, listening ports), the ports WHIP needs and who holds them, existing WHIP
                           installs, and whether GitHub is reachable.
  check <server-data>      A finished install against WHIP's rules: resources present, server.cfg lines (licence
                           placeholder, OneSync, oxmysql before whip_core, the voice permission, game build or
                           platform, a second server's voice ports), and the database port answering.

Read-only: it opens no files for writing and changes nothing. Standard library only, Python 3.9+.

  python -I whip_host.py scan D:/servers C:/servers
  python -I whip_host.py check D:/servers/whip/server-data
"""
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import urllib.request

PORTS = {
    30120: 'FiveM game (default)', 40120: 'txAdmin web (default)', 3306: 'MySQL/MariaDB (default)',
    3307: 'MySQL/MariaDB (common alt)', 7880: 'whip_voice LiveKit HTTP/signal', 7881: 'whip_voice TCP',
    7882: 'whip_voice UDP (first of 7882-7893)', 7980: 'whip_voice API (second-server convention)',
}
DB_GUESSES_WIN = [r'C:\xampp\mysql\bin', r'C:\laragon\bin\mysql',
                  r'C:\Program Files\MariaDB 11.4\bin', r'C:\Program Files\MariaDB 10.11\bin',
                  r'C:\Program Files\MariaDB 10.6\bin', r'C:\Program Files\MySQL\MySQL Server 8.0\bin',
                  r'C:\Program Files\MySQL\MySQL Server 8.4\bin']
WHIP_RESOURCES = ['whip_core', 'whip_autos', 'whip_autos_shop', 'whip_chat', 'whip_dealership', 'whip_fuel',
                  'whip_gunny', 'whip_loadingscreen', 'whip_phone', 'whip_rope', 'whip_voice', 'oxmysql',
                  'whip_media_clothing_male', 'whip_media_clothing_female', 'whip_media_props',
                  'whip_media_previews', 'whip_media_map', 'whip_homes_mirrorpark', 'whip_graphics']


def listening(port, host='127.0.0.1'):
    s = socket.socket()
    s.settimeout(0.4)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (r.stdout or r.stderr).strip()
    except Exception as e:
        return f'({e})'


def find_files(roots, names, depth=4):
    hits = []
    for root in roots:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            continue
        base = root.rstrip(os.sep).count(os.sep)
        for d, dirs, files in os.walk(root):
            if d.count(os.sep) - base >= depth:
                dirs[:] = []
            dirs[:] = [x for x in dirs if x not in ('node_modules', '.git', 'cache', 'Windows', '$Recycle.Bin')]
            for n in names:
                if n in files or n in dirs:
                    hits.append(os.path.join(d, n))
    return hits


def scan(roots):
    out = {'os': f'{platform.system()} {platform.release()}', 'python': sys.version.split()[0]}
    print(f"OS: {out['os']}   Python {out['python']}")
    for r in roots or ['.']:
        if os.path.exists(r):
            du = shutil.disk_usage(r)
            print(f'Disk {r}: {du.free / 1e9:.0f} GB free (WHIP needs about 1 GB, plus the artifact)')

    print('\nPorts on this machine:')
    for p, what in PORTS.items():
        print(f"  {p:5}  {'IN USE' if listening(p) else 'free  '}  {what}")

    print('\nDatabases:')
    dirs = [os.path.dirname(p) for p in (shutil.which('mysqld'), shutil.which('mariadbd'), shutil.which('mysql')) if p]
    if os.name == 'nt':
        dirs += [d for d in DB_GUESSES_WIN if os.path.isdir(d)]
    seen = set()
    for d in dirs:
        for exe in ('mysqld.exe', 'mariadbd.exe', 'mysqld', 'mariadbd'):
            p = os.path.join(d, exe)
            if os.path.isfile(p) and p not in seen:
                seen.add(p)
                v = run([p, '--version'])
                ok = ''
                m = re.search(r'Ver (\d+)\.(\d+)\.(\d+)-MariaDB', v)
                m2 = re.search(r'Ver (\d+)\.(\d+)\.(\d+)', v)
                if m:
                    ok = 'OK for WHIP' if tuple(map(int, m.groups())) >= (10, 2, 3) else 'TOO OLD (needs 10.2.3+)'
                elif m2:
                    ok = 'OK for WHIP' if tuple(map(int, m2.groups())) >= (8, 0, 16) else 'TOO OLD (MySQL needs 8.0.16+)'
                print(f'  {p}\n      {v[:110]}  [{ok}]')
    if not seen:
        print('  none found: install MariaDB (10.2.3+) or MySQL (8.0.16+)')
    if os.name == 'nt':
        svc = run(['powershell', '-NoProfile', '-Command',
                   "Get-Service | Where-Object { $_.Name -match 'maria|mysql' } | ForEach-Object { $_.Name + ' ' + $_.Status }"])
        if svc and not svc.startswith('('):
            print('  services: ' + svc.replace('\n', '; '))

    print('\nFXServer artifacts and WHIP installs under:', ', '.join(roots) if roots else '(none given)')
    for p in find_files(roots, ['FXServer.exe', 'run.sh'], depth=4):
        print('  artifact:', p)
    for p in find_files(roots, ['whip_core'], depth=6):
        man = os.path.join(p, 'fxmanifest.lua')
        ver = ''
        if os.path.isfile(man):
            m = re.search(r"^version\s+'([^']+)'", open(man, encoding='utf-8', errors='ignore').read(), re.M)
            ver = m.group(1) if m else ''
        print(f'  WHIP install: {p}  (whip_core {ver})')
    for p in find_files(roots, ['txData'], depth=3):
        print('  txAdmin data:', p)

    print('\nRemote:')
    try:
        req = urllib.request.Request('https://changelogs-live.fivem.net/api/changelog/versions/win32/server',
                                     headers={'User-Agent': 'whip-skill'})
        info = json.loads(urllib.request.urlopen(req, timeout=10).read())
        print(f"  FXServer recommended {info.get('recommended')}, latest {info.get('latest')} "
              f"(WHIP Legacy needs 38435+): {info.get('recommended_download')}")
    except Exception as e:
        print(f'  could not read the FXServer versions: {e}')
    for host in ('github.com', 'codeload.github.com', 'raw.githubusercontent.com'):
        try:
            socket.create_connection((host, 443), timeout=5).close()
            print(f'  {host}: reachable')
        except Exception as e:
            print(f'  {host}: NOT reachable ({e})')
    print('\nNext: ask the user (route txAdmin/manual, Legacy/Enhanced, which database, folder, ports), then set up.')


def check(data):
    data = os.path.abspath(data)
    cfg_path = os.path.join(data, 'server.cfg')
    problems, notes = [], []
    found = {os.path.basename(p) for p in find_files([os.path.join(data, 'resources')], WHIP_RESOURCES, depth=4)}
    for r in WHIP_RESOURCES:
        if r not in found:
            problems.append(f'resource {r} not found under resources/')
    if not os.path.isfile(cfg_path):
        print(f'no server.cfg in {data}')
        return 1
    cfg = open(cfg_path, encoding='utf-8', errors='ignore').read()
    lines = [l.split('#', 1)[0].strip() for l in cfg.splitlines()]
    ens = [l.split(None, 1)[1] for l in lines if l.startswith('ensure ')]

    def has(rx):
        return any(re.match(rx, l) for l in lines)
    if re.search(r'sv_licenseKey\s+"?(CHANGE_ME|\{\{svLicense\}\})', cfg):
        problems.append('sv_licenseKey is still a placeholder: FXServer stops with "Invalid key format specified"')
    under_txadmin = 'txData' in data or 'OneSync: set in txAdmin' in cfg
    if under_txadmin:
        notes.append('run by txAdmin: OneSync comes from txAdmin > Settings > FXServer (check it is On)')
    if not has(r'set\s+onesync\s+(on|legacy)') and not under_txadmin:
        problems.append('no `set onesync on`: without txAdmin, OneSync must be in server.cfg (WHIP requires it)')
    if 'CHANGE_ME' in (re.search(r'mysql_connection_string\s+"([^"]*)"', cfg) or [None, ''])[1]:
        problems.append('mysql_connection_string still has CHANGE_ME')
    if 'oxmysql' in ens and 'whip_core' in ens and ens.index('oxmysql') > ens.index('whip_core'):
        problems.append('ensure oxmysql must come before ensure whip_core')
    if 'whip_voice' in ens:
        perm = [i for i, l in enumerate(lines) if l.startswith('add_unsafe_child_process_permission whip_voice')]
        ens_i = [i for i, l in enumerate(lines) if l == 'ensure whip_voice']
        if not perm or (ens_i and perm[0] > ens_i[0]):
            problems.append('add_unsafe_child_process_permission whip_voice must come before ensure whip_voice')
    enh = has(r'setr\s+whip_platform\s+enhanced')
    if has(r'set\s+whip_platform\s+enhanced'):
        problems.append('whip_platform must be setr (clients need it), not set')
    if not enh and not has(r'sv_enforceGameBuild\s+\d+'):
        problems.append('Legacy without sv_enforceGameBuild (WHIP wants 3407+, suggests 3889)')
    for bad in ('chat', 'spawnmanager', 'basic-gamemode', 'qb-core', 'es_extended', 'qbx_core', 'ox_core',
                'ox_inventory', 'ox_target', 'qb-target', 'pma-voice'):
        if bad in ens:
            problems.append(f'`ensure {bad}`: conflicts with WHIP')
    m = re.search(r'mysql://[^:@/]+(?::[^@]*)?@([^:/]+)(?::(\d+))?/', cfg)
    if m:
        host, port = m.group(1), int(m.group(2) or 3306)
        if host in ('127.0.0.1', 'localhost') and not listening(port):
            problems.append(f'the database port {port} is not answering: start MariaDB/MySQL')
    gp = re.search(r'endpoint_add_tcp\s+"[^:]+:(\d+)"', cfg)
    notes.append(f"game port {gp.group(1) if gp else '30120 (txAdmin default)'}")
    if has(r'set\s+whip_voice_udp'):
        notes.append('voice ports moved (second server on this machine)')
    elif listening(7880):
        notes.append('something already answers on 7880: if another WHIP server runs here, move this one\'s voice '
                     'ports (whip_voice_udp/tcp/api, whip_voicebot_url)')
    print(f'WHIP install check: {data}')
    for p in problems:
        print('  FIX  ', p)
    for n in notes:
        print('  note ', n)
    print('  ' + ('nothing to fix' if not problems else f'{len(problems)} to fix'))
    return 1 if problems else 0


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if len(sys.argv) < 2 or sys.argv[1] not in ('scan', 'check'):
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == 'scan':
        scan(sys.argv[2:])
    else:
        if len(sys.argv) < 3:
            print('check needs the server-data folder')
            sys.exit(2)
        sys.exit(check(sys.argv[2]))


if __name__ == '__main__':
    main()
