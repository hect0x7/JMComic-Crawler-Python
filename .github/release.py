import os
import sys
import re


def add_output(k, v):
    cmd = f'echo "{k}={v}" >> $GITHUB_OUTPUT'
    print(cmd, os.system(cmd))


def parse_body(body):
    if ';' not in body:
        return body

    parts = body.split(";")
    points = []
    for i, e in enumerate(parts):
        e: str = e.strip()
        if e == '':
            continue
        points.append(f'{i + 1}. {e}')

    return '\n'.join(points)


def get_tag_and_body():
    msg = sys.argv[1]
    print(f'msg: {msg}')
    p = re.compile('(.*?): ?(.*)')
    match = p.search(msg)
    assert match is not None, f'commit message format is wrong: {msg}'
    tag, body = match[1], match[2]
    return body, tag


def main():
    body, tag = get_tag_and_body()

    add_output('tag', tag)

    with open('release_body.txt', 'w', encoding='utf-8') as f:
        f.write(parse_body(body))


main()
