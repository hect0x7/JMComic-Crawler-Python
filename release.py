import os
import sys
import re


def add_output(k, v):
    cmd = f'echo {k}="{v}" >> $GITHUB_OUTPUT'
    print(cmd, os.system(cmd))


msg = sys.argv[1]
print(f'msg: {msg}')
p = re.compile('(.*?): ?(.*)')
match = p.search(msg)
assert match is not None, f'commit message format is wrong: {msg}'

tag, body = match[1], match[2]

add_output('tag', tag)
add_output('body', body)
