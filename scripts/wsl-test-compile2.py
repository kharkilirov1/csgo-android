#!/usr/bin/env python3
import json, subprocess, sys, os
cmds = json.load(open('/home/kharki/csgo-src/build/compile_commands.json'))
for x in cmds:
    if 'cdll_client_int' in x['file']:
        a = list(x['arguments'])
        # find -o target
        try:
            oi = a.index('-o')
            a[oi+1] = '/tmp/test_client.o'
        except ValueError:
            for i, v in enumerate(a):
                if v.endswith('.o') and '-o' in v:
                    a[i] = '-o /tmp/test_client.o'
        cmd = ' '.join(a)
        r = subprocess.run(cmd, shell=True, cwd=x['directory'], capture_output=True, text=True)
        print('rc=', r.returncode)
        if r.returncode != 0:
            print(r.stderr[:2000])
        break
else:
    print('not found')
