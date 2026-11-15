#!/usr/bin/env python3
"""install_whip.py - install WHIP without txAdmin, by running WHIP's own txAdmin recipe by hand.

It reads the recipe (whip-legacy.yaml or whip-enhanced.yaml from WHIPFX/txAdmin-recipe, fetched live so the
tag list is always the current release) and performs its tasks the way txAdmin does:

  download_github  repo at a tag, from codeload.github.com (no GitHub API call, so no 60/hour limit); the
                   zip's top folder is stripped, as txAdmin does
  download_file    a release asset (whip_gunny, the media packs, mirrorpark and oxmysql ship as zips)
  unzip            extract into dest (release zips have no top folder)
  remove_path      delete the tmp folder
  connect_database not done here: create the database and login yourself (the script prints the SQL)
  write_file       server.cfg, with txAdmin's {{placeholders}} filled from the options below

Usage:
  python -I install_whip.py <server-data folder> [--game legacy|enhanced] [--recipe URL-or-file]
         [--port 30120] [--maxclients 48] [--db mysql://user:pass@127.0.0.1:3306/whip]
         [--license KEY] [--create-db] [--mysql-client PATH] [--dry-run] [--only-cfg]

Without --license, server.cfg gets sv_licenseKey "CHANGE_ME": paste your key from portal.cfx.re there yourself.
Without --db, the connection string is a template to edit. Existing resource folders are replaced. The FXServer
artifact itself is not downloaded: get it from https://runtime.fivem.net/artifacts/ (Legacy: 38435 or newer).

Standard library only. Python 3.9+.
"""
import argparse
import io
import os
import re
import shutil
import sys
import time
import urllib.request
import zipfile

RECIPES = {
    'legacy': 'https://raw.githubusercontent.com/WHIPFX/txAdmin-recipe/main/whip-legacy.yaml',
    'enhanced': 'https://raw.githubusercontent.com/WHIPFX/txAdmin-recipe/main/whip-enhanced.yaml',
}
UA = {'User-Agent': 'whip-skill-installer'}


def fetch(url, tries=4):
    """GET url into memory, with retries and a simple progress line."""
    last = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                total = int(r.headers.get('Content-Length') or 0)
                buf, got, t0 = io.BytesIO(), 0, time.time()
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    buf.write(chunk)
                    got += len(chunk)
                    if total:
                        sys.stdout.write(f'\r    {got / 1e6:7.1f} / {total / 1e6:.1f} MB')
                    else:
                        sys.stdout.write(f'\r    {got / 1e6:7.1f} MB')
                    sys.stdout.flush()
                sys.stdout.write(f'  ({time.time() - t0:.0f} s)\n')
                return buf.getvalue()
        except Exception as e:  # network hiccup: retry
            last = e
            print(f'    attempt {attempt} failed: {e}')
            if 'CERTIFICATE_VERIFY_FAILED' in str(e):
                # Python's OpenSSL does not fetch missing intermediate certificates the way Windows does
                # (seen with codeload.github.com). curl on Windows uses the system store: let it download.
                data = fetch_with_curl(url)
                if data is not None:
                    return data
            time.sleep(3 * attempt)
    raise RuntimeError(f'could not download {url}: {last}')


def fetch_with_curl(url):
    curl = shutil.which('curl')
    if not curl:
        print('    no curl on PATH to fall back to')
        return None
    import subprocess
    print('    retrying with curl (system certificate store)')
    r = subprocess.run([curl, '-fsSL', '--retry', '3', '-A', UA['User-Agent'], url], capture_output=True)
    if r.returncode != 0:
        print(f"    curl failed: {r.stderr.decode('utf-8', 'replace').strip()}")
        return None
    print(f'    {len(r.stdout) / 1e6:.1f} MB')
    return r.stdout


def parse_recipe(text):
    """The recipe's tasks as dicts. A small parser for txAdmin's recipe YAML: '- action:' items with flat
    'key: value' fields, and write_file's 'data: |' block."""
    tasks, cur, lines, i = [], None, text.split('\n'), 0
    in_tasks = False
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('tasks:'):
            in_tasks = True
        elif in_tasks:
            m = re.match(r'^  - (\w+):\s*(.*)$', ln)
            m2 = re.match(r'^    (\w+):\s*(.*)$', ln)
            if m:
                cur = {m.group(1): clean(m.group(2))}
                tasks.append(cur)
            elif m2 and cur is not None:
                key, val = m2.group(1), m2.group(2)
                if val.strip() == '|':
                    block, i = [], i + 1
                    while i < len(lines) and (lines[i].startswith('      ') or lines[i].strip() == ''):
                        block.append(lines[i][6:])
                        i += 1
                    cur[key] = '\n'.join(block).rstrip('\n') + '\n'
                    continue
                cur[key] = clean(val)
        i += 1
    return tasks


def clean(v):
    v = re.sub(r'\s+#.*$', '', v).strip()
    return v.strip('"').strip("'")


def safe_join(root, rel):
    p = os.path.normpath(os.path.join(root, rel))
    if not p.startswith(os.path.normpath(root)):
        raise ValueError(f'path escapes the install folder: {rel}')
    return p


def extract(data, dest, strip_top):
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    top = ''
    if strip_top:
        first = names[0].split('/')[0] + '/'
        if all(n.startswith(first) for n in names):
            top = first
    for n in names:
        rel = n[len(top):]
        if not rel or rel.endswith('/'):
            continue
        out = safe_join(dest, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with z.open(n) as src, open(out, 'wb') as dst:
            shutil.copyfileobj(src, dst)
    return len(names)


def fill_cfg(text, a):
    endpoints = (f'endpoint_add_tcp "0.0.0.0:{a.port}"\nendpoint_add_udp "0.0.0.0:{a.port}"')
    if a.for_txadmin:
        endpoints += ('\n# OneSync: set in txAdmin (Settings > FXServer > OneSync: On), not here: txAdmin starts'
                      '\n# FXServer with it. The recipe asks for $onesync: on.')
    elif a.onesync:
        # txAdmin applies the recipe's `$onesync: on` itself, outside server.cfg; without txAdmin it must be here
        endpoints += f'\n# OneSync: the recipe\'s $onesync: {a.onesync}, which txAdmin would set for you\nset onesync {a.onesync}'
    principals = ('# First admin: join, type /w, and the server console prints the add_ace line for you.\n'
                  '# Or add your identifier here: add_principal identifier.fivem:1234567 group.admin')
    values = {
        'svLicense': a.license or 'CHANGE_ME',
        'maxClients': str(a.maxclients),
        'serverEndpoints': endpoints,
        'dbConnectionString': a.db or 'mysql://whip:CHANGE_ME@127.0.0.1:3306/whip',
        'addPrincipalsMaster': principals,
    }
    return re.sub(r'\{\{(\w+)\}\}', lambda m: values.get(m.group(1), m.group(0)), text)


def create_database(conn, client=None):
    """CREATE DATABASE IF NOT EXISTS from an oxmysql connection string, through the mysql/mariadb command-line
    client (the standard library cannot speak MySQL). The password goes in MYSQL_PWD, never on the command line."""
    import subprocess
    m = re.match(r'^mysql://([^:@/]+)(?::([^@]*))?@([^:/]+)(?::(\d+))?/([A-Za-z0-9_]+)', conn or '')
    if not m:
        print('  --create-db needs --db mysql://user:password@host:port/database (letters, digits and _ in the name)')
        return False
    user, pw, host, port, db = m.group(1), m.group(2) or '', m.group(3), m.group(4) or '3306', m.group(5)
    exe = client or shutil.which('mariadb') or shutil.which('mysql')
    if not exe:
        import glob
        guesses = (glob.glob(r'C:\Program Files\MariaDB*\bin\mysql.exe')
                   + glob.glob(r'C:\Program Files\MySQL\MySQL Server*\bin\mysql.exe')
                   + [r'C:\xampp\mysql\bin\mysql.exe'])
        for guess in guesses:
            if os.path.isfile(guess):
                exe = guess
                break
    if not exe:
        print('  no mysql/mariadb client found: pass --mysql-client <path to mysql.exe>, or run the SQL below yourself')
        return False
    sql = f'CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'
    env = dict(os.environ, MYSQL_PWD=pw)
    r = subprocess.run([exe, '-u', user, '-h', host, '-P', port, '-e', sql], env=env, capture_output=True, text=True)
    err = '\n'.join(l for l in (r.stderr or '').splitlines() if 'insecure passwordless' not in l).strip()
    if r.returncode != 0:
        print(f'  could not create `{db}`: {err}')
        if 'Access denied' in err:
            print('  the login in the connection string is wrong, or it may not create databases: use an admin login')
        return False
    print(f'  database `{db}` is ready on {host}:{port} (utf8mb4_unicode_ci); whip_core makes its tables on first start')
    return True


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target', help='the server-data folder (resources/ and server.cfg go in it)')
    ap.add_argument('--game', choices=['legacy', 'enhanced'], default='legacy')
    ap.add_argument('--recipe', help='recipe URL or local file (default: the live one for --game)')
    ap.add_argument('--port', type=int, default=30120)
    ap.add_argument('--maxclients', type=int, default=48)
    ap.add_argument('--db', help='oxmysql connection string')
    ap.add_argument('--license', help='server licence key (better: paste it into server.cfg yourself)')
    ap.add_argument('--for-txadmin', action='store_true',
                    help="files for txAdmin's 'Existing Server Data' setup: OneSync left to txAdmin's settings")
    ap.add_argument('--create-db', action='store_true',
                    help="create the --db database with the mysql/mariadb client (the recipe's connect_database)")
    ap.add_argument('--mysql-client', help='path to mysql.exe / mariadb.exe when it is not on PATH')
    ap.add_argument('--dry-run', action='store_true', help='list the tasks, change nothing')
    ap.add_argument('--only-cfg', action='store_true', help='only write server.cfg')
    a = ap.parse_args()

    src = a.recipe or RECIPES[a.game]
    text = open(src, encoding='utf-8').read() if os.path.isfile(src) else fetch(src).decode('utf-8')
    tasks = parse_recipe(text)
    m = re.search(r'^\$onesync:\s*(\w+)', text, re.M)
    a.onesync = m.group(1) if m else None
    root = os.path.abspath(a.target)
    print(f'Recipe: {src}\n{len(tasks)} tasks into {root}\n')
    if a.only_cfg and a.create_db:
        create_database(a.db, a.mysql_client)
    if a.dry_run:
        for t in tasks:
            print(' ', t.get('action'), t.get('src') or t.get('url') or t.get('path') or t.get('file') or '',
                  t.get('ref') or '', '->', t.get('dest') or t.get('path') or '')
        return
    os.makedirs(root, exist_ok=True)
    done_dest = set()
    for n, t in enumerate(tasks, 1):
        act = t.get('action')
        if a.only_cfg and act != 'write_file':
            continue
        if act == 'download_github':
            dest = safe_join(root, t['dest'])
            ref = t.get('ref') or 'main'
            kind = 'tags' if re.match(r'^v?\d', ref) else 'heads'
            url = f"https://codeload.github.com/{t['src']}/zip/refs/{kind}/{ref}"
            print(f"[{n}/{len(tasks)}] {t['src']}@{ref} -> {t['dest']}")
            data = fetch(url)
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            extract(data, dest, strip_top=True)
        elif act == 'download_file':
            path = safe_join(root, t['path'])
            print(f"[{n}/{len(tasks)}] {t['url'].rsplit('/', 1)[-1]}")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(fetch(t['url']))
        elif act == 'unzip':
            zpath, dest = safe_join(root, t['src']), safe_join(root, t['dest'])
            if dest not in done_dest and os.path.isdir(dest) and not dest.endswith(']'):
                shutil.rmtree(dest)  # first part of a split release: start clean
            done_dest.add(dest)
            with open(zpath, 'rb') as f:
                count = extract(f.read(), dest, strip_top=False)
            print(f"    unzipped {count} entries -> {t['dest']}")
        elif act == 'remove_path':
            p = safe_join(root, t['path'])
            if os.path.exists(p):
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        elif act == 'connect_database':
            if a.create_db:
                print(f'[{n}/{len(tasks)}] connect_database')
                create_database(a.db, a.mysql_client)
            else:
                print(f'[{n}/{len(tasks)}] connect_database: skipped (pass --create-db, or make it yourself: below)')
        elif act == 'write_file':
            path = safe_join(root, t['file'])
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(fill_cfg(t['data'], a))
            print(f"[{n}/{len(tasks)}] wrote {t['file']}")
        else:
            print(f'[{n}/{len(tasks)}] unknown action {act!r}: skipped')

    if a.for_txadmin:
        print('\nDone. In txAdmin: setup page > "Existing Server Data" > this folder > server.cfg.')
        print('  Settings > FXServer: OneSync On. Paste your key into sv_licenseKey (txAdmin\'s CFG Editor works too).')
        return
    print('\nDone. Before the first start:')
    print('  1. server.cfg: paste your key into sv_licenseKey (portal.cfx.re), check mysql_connection_string.')
    print('  2. Make the database and a login oxmysql can use (MariaDB 10.2.3+ / MySQL 8.0.16+), e.g.:')
    print("       CREATE DATABASE whip CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    print("       CREATE USER 'whip'@'localhost' IDENTIFIED BY 'your-password';")
    print("       GRANT ALL PRIVILEGES ON whip.* TO 'whip'@'localhost';")
    print('  3. Open the voice ports (UDP 7882-7893, TCP 7881) and start FXServer with: +exec server.cfg')
    print('  4. Read the WHIP setup report in the console; `whipsetup` prints it again.')


if __name__ == '__main__':
    main()
