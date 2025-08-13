import os
import sys
import argparse

CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from code_index_mcp.scip.proto import scip_pb2


def normalize(p: str) -> str:
    return p.replace('\\', '/')


def load_index(path: str) -> scip_pb2.Index:
    with open(path, 'rb') as f:
        data = f.read()
    idx = scip_pb2.Index()
    idx.ParseFromString(data)
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--path', required=True, help='Path to index.scip')
    ap.add_argument('--file', required=True, help='Relative path to match (forward slashes)')
    args = ap.parse_args()

    idx = load_index(args.path)
    target = normalize(args.file)

    print(f'Total docs: {len(idx.documents)}')

    doc = None
    for d in idx.documents:
        if normalize(d.relative_path) == target:
            doc = d
            break
    if doc is None:
        # try case-insensitive
        tl = target.lower()
        for d in idx.documents:
            if normalize(d.relative_path).lower() == tl:
                doc = d
                print('(case-insensitive hit)')
                break

    if doc is None:
        print('Document not found')
        sys.exit(2)

    print(f'Document: {doc.relative_path} language={doc.language}')
    print(f'Occurrences: {len(doc.occurrences)}')
    print(f'Symbols: {len(doc.symbols)}')

    for i, s in enumerate(doc.symbols[:200]):
        try:
            kind_name = scip_pb2.SymbolInformation.Kind.Name(s.kind)
        except Exception:
            kind_name = str(s.kind)
        dn = getattr(s, 'display_name', '')
        print(f'  [{i}] name={dn!r} kind={s.kind} ({kind_name})')


if __name__ == '__main__':
    main()
