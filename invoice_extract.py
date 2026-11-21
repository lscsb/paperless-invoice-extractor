#!/usr/bin/env python3
"""CLI entry point for invoice data extraction from Paperless-ngx."""

import argparse
import os
import sys


def check_dependencies() -> None:
    missing = []
    for module in ('pypdfium2', 'pyzbar'):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        print(f'ERROR: fehlende Abhängigkeiten: {", ".join(missing)}', file=sys.stderr)
        print('Installieren mit: pip install -r requirements.txt', file=sys.stderr)
        sys.exit(1)


def get_client():
    from paperless_client import PaperlessClient

    url   = os.environ.get('PAPERLESS_URL',   '').strip()
    token = os.environ.get('PAPERLESS_TOKEN', '').strip()

    if not url:
        print('ERROR: PAPERLESS_URL nicht gesetzt', file=sys.stderr)
        sys.exit(1)
    if not token:
        print('ERROR: PAPERLESS_TOKEN nicht gesetzt', file=sys.stderr)
        sys.exit(1)

    return PaperlessClient(base_url=url, token=token)


def get_config(args):
    from extract_config import load_config
    config_path = getattr(args, 'config', None)
    return load_config(config_path)


def cmd_extract(args) -> int:
    from pipeline import run_extract
    return run_extract(
        client=get_client(),
        cfg=get_config(args),
        document_ids=args.document or [],
        dry_run=args.dry_run,
        force=args.force,
    )


def cmd_setup(args) -> int:
    from paperless_client import PaperlessError
    from setup_paperless import run_setup

    try:
        ok = run_setup(get_client(), cfg=get_config(args), dry_run=args.dry_run)
        return 0 if ok else 1
    except PaperlessError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1


def _add_config_arg(parser) -> None:
    parser.add_argument(
        '--config', metavar='FILE',
        help='Pfad zu einer YAML-Konfigurationsdatei (Standard: eingebaute Defaults)',
    )


def main() -> int:
    check_dependencies()

    parser = argparse.ArgumentParser(
        prog='invoice_extract',
        description='Rechnungsdaten aus Paperless-ngx extrahieren (E-Rechnung / GiroCode)',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    # extract
    p_extract = sub.add_parser('extract', help='Rechnungsdaten extrahieren')
    p_extract.add_argument('--dry-run', action='store_true', help='Keine Änderungen schreiben')
    p_extract.add_argument('--document', metavar='ID', type=int, nargs='+',
                           help='Bestimmte Dokument-IDs verarbeiten')
    p_extract.add_argument('--force', action='store_true',
                           help='Auch bereits verarbeitete Dokumente erneut verarbeiten')
    _add_config_arg(p_extract)

    # setup
    p_setup = sub.add_parser('setup', help='Felder und Tags in Paperless anlegen')
    p_setup.add_argument('--dry-run', action='store_true', help='Nur anzeigen, was angelegt würde')
    _add_config_arg(p_setup)

    args = parser.parse_args()

    if args.command == 'extract':
        return cmd_extract(args)
    elif args.command == 'setup':
        return cmd_setup(args)

    return 0


if __name__ == '__main__':
    sys.exit(main())
