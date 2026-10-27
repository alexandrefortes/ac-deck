#!/usr/bin/env python3
"""Prepara a prática local e adapta %command% da Steam. Ferramenta de teste.

Não instala runtime, inicia Steam, altera opções da conta ou fabrica AppID.
O comando steam recebe o contexto real da entrada Assetto Corsa na biblioteca.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.launcher import file_io as safe, package_setup, steam


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    build = sub.add_parser('preparar', help='Copia o recorte e gera configurações, sem execução')
    build.add_argument('--jogo', type=Path, required=True)
    build.add_argument('--lote', required=True)
    start = sub.add_parser('steam', help='Recebe -- %%command%% nas opções do jogo')
    start.add_argument('--pacote', type=Path, required=True)
    start.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.action == 'preparar':
            print(package_setup.prepare(args.jogo, args.lote, project_root=ROOT))
        else:
            command = args.command[1:] if args.command[:1] == ['--'] else args.command
            steam.run_from_steam(args.pacote, command)
    except (OSError, ValueError, safe.SafetyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0



if __name__ == '__main__':
    raise SystemExit(main())
