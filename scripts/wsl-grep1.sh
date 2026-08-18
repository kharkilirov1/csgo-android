#!/bin/bash
cd ~/csgo-src
found=0
for f in build/*/lib*.so; do
  c=$(strings "$f" 2>/dev/null | grep -c 'DBG: ShowPixels')
  if [ "$c" != "0" ]; then
    echo "FOUND $f: $c"
    found=1
  fi
done
if [ "$found" = "0" ]; then echo "NOT FOUND anywhere"; fi
ls build/appframework/ 2>/dev/null | head -3
