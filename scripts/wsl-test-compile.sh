#!/bin/bash
cd ~/csgo-src/build
python3 -c "
import json
cmds=json.load(open('compile_commands.json'))
for x in cmds:
    if 'cdll_client_int' in x['file']:
        print(' '.join(x['arguments']).replace(' -o ' + x['arguments'][x['arguments'].index('-o')+1], ' -o /tmp/test_client.o -c ' + x['file']))
        break
" > /tmp/compile_cmd.sh
bash /tmp/compile_cmd.sh 2>&1 | head -5
echo "=== compile rc=$? ==="
strings /tmp/test_client.o | grep -c VecGuard
