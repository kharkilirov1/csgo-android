#!/usr/bin/env python3
import json, subprocess
cmds = json.load(open('/home/kharki/csgo-src/build/compile_commands.json'))
for x in cmds:
    if 'cdll_client_int' in x['file']:
        a = list(x['arguments'])
        for i, v in enumerate(a):
            if v.startswith('-o/'):
                a[i] = '-o/tmp/test_client.o'
        cmd = ' '.join(a)
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print('rc=', r.returncode)
        if r.returncode != 0:
            print('STDERR:', r.stderr[-1500:])
        break
