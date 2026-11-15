"""Selftest for whip_scan.py: each fixture must raise the rules listed, and WHIP's MIT examples must stay clean of
MEDIUM/HIGH findings. Run: python -I scripts/selftest/run.py"""
import json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
scan = os.path.join(here, '..', 'whip_scan.py')
examples = os.path.join(here, '..', '..', 'assets', 'examples')
def rules(path, mode='all'):
    out = subprocess.run([sys.executable, '-I', scan, path, '--mode', mode, '--json'], capture_output=True, text=True, encoding='utf-8')
    return json.loads(out.stdout)
expect = {
    'qb_shop': {'P001', 'P003', 'P005', 'P011', 'P020', 'P023', 'P024', 'P030', 'P032', 'P050', 'P052', 'P053', 'P055', 'P010'},
    'whip_bad': {'W001', 'W002', 'W010', 'W020', 'W021', 'W022', 'W030', 'W032', 'W034', 'W050', 'W051', 'W052', 'W053', 'W060', 'W070', 'W071', 'W072'},
}
fail = 0
for fx, want in expect.items():
    got = {f['rule'] for f in rules(os.path.join(here, fx))}
    missing = want - got
    print(f'{fx}: {len(got)} rules hit' + (f'; MISSING {sorted(missing)}' if missing else ''))
    fail |= bool(missing)
for ex in ('whip_cafe_example', 'whip_delivery_example'):
    bad = [f for f in rules(os.path.join(examples, ex)) if f['severity'] in ('HIGH', 'MEDIUM')]
    print(f'{ex}: {len(bad)} MEDIUM/HIGH' + (''.join(f"\n  {b['rule']} {b['file']}:{b['line']}" for b in bad)))
    fail |= bool(bad)
print('FAIL' if fail else 'PASS'); sys.exit(1 if fail else 0)
