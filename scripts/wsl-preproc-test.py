#!/usr/bin/env python3
import json, subprocess
cmds = json.load(open('/home/kharki/csgo-src/build/compile_commands.json'))
for x in cmds:
    if 'dmxelement' in x['file']:
        a = list(x['arguments'])
        for i, v in enumerate(a):
            if '$(IntDir)' in v:
                a[i] = a[i].replace('$(IntDir)', '')
            if v.startswith('-o/'):
                a[i] = '-o/tmp/dmx_test.o'
        # add -E to preprocess
        cmd = ' '.join(a)
        parts = cmd.split(' ', 1)
        pcmd = parts[0] + ' -E ' + parts[1]
        r = subprocess.run(pcmd, shell=True, capture_output=True, text=True, cwd='/home/kharki/csgo-src/build')
        print('rc=', r.returncode)
        out = r.stdout
        print('VecGuard in preprocessed:', out.count('VecGuard'))
        print('ANDROID defined check (sample):', 'ifdef ANDROID' in out)
        # find the actual include path of utlvector.h
        import re
        for m in re.finditer(r'utlvector\.h', out):
            pass
        # print first occurrence context
        idx = out.find('VecGuard')
        if idx >= 0:
            print(out[idx-200:idx+100])
        break
