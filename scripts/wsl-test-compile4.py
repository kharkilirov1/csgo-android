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
        parts = cmd.split(' ', 1)
        hcmd = parts[0] + ' -H ' + parts[1]
        r = subprocess.run(hcmd, shell=True, capture_output=True, text=True)
        print('rc=', r.returncode)
        for line in r.stderr.splitlines():
            if 'utlvector' in line:
                print(line)
        break
