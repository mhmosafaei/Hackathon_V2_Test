"""Offline normalization only. Never imports or invokes an API transport."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.intelligence.deterministic import persist_projection


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_folder', type=Path)
    parser.add_argument('--filename', required=True)
    args = parser.parse_args()
    folder = args.run_folder.resolve()
    digest = sha256((folder / 'source.pdf').read_bytes()).hexdigest()
    output = persist_projection(folder, filename=args.filename, document_sha256=digest)
    print(output)
