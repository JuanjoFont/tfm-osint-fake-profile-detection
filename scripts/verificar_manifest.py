"""Genera o verifica el manifiesto SHA-256 del paquete público."""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'MANIFEST_SHA256.json'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def current():
    files = (
        path for path in ROOT.rglob('*')
        if path.is_file()
        and '.git' not in path.parts
        and path != MANIFEST
        and '__pycache__' not in path.parts
    )
    return {
        path.relative_to(ROOT).as_posix(): digest(path)
        for path in sorted(files)
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Actualiza MANIFEST_SHA256.json')
    args = parser.parse_args()
    values = current()
    if args.write:
        MANIFEST.write_text(json.dumps(values, indent=2, ensure_ascii=False) + '\n')
        print(f'Manifiesto actualizado: {len(values)} archivos')
        return
    expected = json.loads(MANIFEST.read_text())
    if values != expected:
        missing = sorted(set(expected) - set(values))
        added = sorted(set(values) - set(expected))
        changed = sorted(k for k in set(values) & set(expected) if values[k] != expected[k])
        raise SystemExit(f'Manifiesto incorrecto. Faltan={missing}; nuevos={added}; modificados={changed}')
    print(f'Manifiesto correcto: {len(values)} archivos')


if __name__ == '__main__':
    main()
