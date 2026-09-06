#!/usr/bin/env python3
"""Portable browser observer for one PPT Pilot run (Python 3.9+)."""
import argparse
import json
import sys

sys.dont_write_bytecode = True

from _dashboard import lifecycle


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='PPT Pilot 本地实时任务与 SVG 面板')
    parser.add_argument('action', choices=('start', 'serve', 'status', 'stop'))
    parser.add_argument('--run-dir', required=True, help='明确的运行目录，可尚未生成 run.json')
    parser.add_argument('--port', type=int, default=0, help='回环端口，0 自动选择可用端口')
    parser.add_argument('--open', action='store_true', help='start 后打开默认浏览器')
    parser.add_argument('--instance-id', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('--port 必须在 0–65535 之间')
    try:
        if args.action == 'start':
            result = lifecycle.start(args.run_dir, args.port, args.open)
        elif args.action == 'serve':
            lifecycle.serve(args.run_dir, args.port, args.instance_id)
            return 0
        else:
            result = getattr(lifecycle, args.action)(args.run_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print('面板操作失败：' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
