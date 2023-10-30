import os
import sys
import re


def add_output(k, v):
    cmd = f'echo {k}="{v}" >> $GITHUB_OUTPUT'
    print(cmd, os.system(cmd))


def parse_body(body):
    if ';' not in body:
        return body

    parts = body.split(";")
    points = []
    for i, e in enumerate(parts):
        e: str = e.strip()
        points.append(f'{i}. {e}')

    print('\n'.join(points))


msg = sys.argv[1]
print(f'msg: {msg}')
p = re.compile('(.*?): ?(.*)')
match = p.search(msg)
assert match is not None, f'commit message format is wrong: {msg}'

tag, body = match[1], match[2]

add_output('tag', tag)
add_output('body', parse_body(body))
