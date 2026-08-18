#!/usr/bin/env python3
import json, subprocess
cmds = json.load(open('/home/kharki/csgo-src/build/compile_commands.json'))
for x in cmds:
    if 'cdll_client_int' in x['file']:
        a = list(x['arguments'])
        oi = [i for i, v in enumerate(a) if v == '-o']
        if not oi:
            print('no -o arg; args sample:', a[:5], '...', a[-5:])
            break
        a[oi[0] + 1] = '/tmp/test_client.o'
        cmd = ' '.join(a)
        # insert -H after compiler invocation (first token)
        parts = cmd.split(' ', 1)
        hcmd = parts[0] + ' -H ' + parts[1]
        r = subprocess.run(hcmd, shell=True, capture_output=True, text=True)
        print('rc=', r.returncode)
        for line in r.stderr.splitlines():
            if 'utlvector' in line:
                print(line)
        break
