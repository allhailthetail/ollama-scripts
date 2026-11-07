"""Show and compare the metadata hidden by `ollama list`."""

import argparse
import json
import shutil
import sys

import ollama

from . import __version__
from .common import context_detail, format_context, format_size

CAPABILITY_ORDER = (
    'completion',
    'tools',
    'vision',
    'audio',
    'thinking',
    'embedding',
    'insert',
)

JSON_FIELDS = (
    'name',
    'size',
    'size_label',
    'modified_at',
    'digest',
    'format',
    'family',
    'families',
    'parameter_size',
    'parameter_count',
    'quantization',
    'context_length',
    'embedding_length',
    'capabilities',
    'license',
)


def parse_parameter_size(text):
    """Turn a label like '7.6B' into an approximate parameter count."""
    if not text:
        return None
    text = text.strip().upper()
    units = {'K': 1e3, 'M': 1e6, 'B': 1e9, 'T': 1e12}
    if text[-1] not in units:
        return None
    try:
        return int(float(text[:-1]) * units[text[-1]])
    except ValueError:
        return None


def describe(item, shown):
    """Normalize one list entry and its show response into a record."""
    details = getattr(item, 'details', None)
    model_info = {}
    if shown is not None:
        model_info = getattr(shown, 'modelinfo', None)
        if model_info is None:
            model_info = getattr(shown, 'model_info', None)
    if not isinstance(model_info, dict):
        model_info = {}

    family = getattr(details, 'family', None)
    families = list(getattr(details, 'families', None) or [])
    architecture = model_info.get('general.architecture') or family

    context_length = None
    if architecture:
        context_length = model_info.get(f'{architecture}.context_length')
    if context_length is None:
        for key, value in model_info.items():
            if key.endswith('.context_length'):
                context_length = value
                break
    if context_length is None:
        context_length = getattr(details, 'context_length', None)

    embedding_length = None
    if architecture:
        embedding_length = model_info.get(f'{architecture}.embedding_length')

    parameter_size = getattr(details, 'parameter_size', None)
    parameter_count = model_info.get('general.parameter_count')
    if parameter_count is None:
        parameter_count = parse_parameter_size(parameter_size)

    capabilities = []
    if shown is not None:
        for capability in getattr(shown, 'capabilities', None) or []:
            capabilities.append(capability)

    modified = getattr(item, 'modified_at', None)

    return {
        'name': getattr(item, 'model', None) or '',
        'size': int(getattr(item, 'size', 0) or 0),
        'size_label': format_size(getattr(item, 'size', 0)),
        'modified_at': modified.isoformat() if modified else None,
        'modified_date': modified.strftime('%Y-%m-%d') if modified else '-',
        'digest': getattr(item, 'digest', None) or '',
        'format': getattr(details, 'format', None),
        'family': family,
        'families': families,
        'parameter_size': parameter_size,
        'parameter_count': parameter_count,
        'quantization': getattr(details, 'quantization_level', None),
        'context_length': context_length,
        'embedding_length': embedding_length,
        'capabilities': capabilities,
        'license': model_info.get('general.license'),
    }


def gather(models, selection):
    """Collect records for the selected models, preserving the given order."""
    by_name = {}
    for model in models:
        by_name[model.model] = model

    names = []
    missing = []
    if selection:
        for name in selection:
            if name not in by_name:
                missing.append(name)
            elif name not in names:
                names.append(name)
    else:
        for model in models:
            names.append(model.model)

    records = []
    failures = []
    for name in names:
        shown = None
        try:
            shown = ollama.show(name)
        except Exception as error:
            failures.append((name, str(error)))
        records.append(describe(by_name[name], shown))
    return records, missing, failures


def sort_value(record, field):
    """Return the value used to sort a record by the given field."""
    if field == 'size':
        return record['size']
    if field == 'modified':
        return record['modified_at'] or ''
    if field == 'params':
        return record['parameter_count'] or 0
    if field == 'context':
        return record['context_length'] or 0
    return (record['name'] or '').lower()


def cell_value(record, key):
    """Return one table cell as a string."""
    if key == 'context':
        return format_context(record['context_length'])
    if key == 'capabilities_label':
        capabilities = []
        for capability in record['capabilities']:
            if capability != 'completion':
                capabilities.append(capability)
        if not capabilities:
            return '-'
        return ', '.join(capabilities)
    if key == 'embedding':
        value = record['embedding_length']
        return str(value) if value else '-'
    if key == 'digest':
        return (record['digest'] or '')[:12] or '-'
    value = record.get(key)
    return value if value not in (None, '') else '-'


def table_columns(wide):
    """Return (header, record key, alignment) tuples for the list view."""
    columns = [
        ('NAME', 'name', '<'),
        ('PARAMS', 'parameter_size', '>'),
        ('QUANT', 'quantization', '<'),
        ('CTX', 'context', '>'),
    ]
    if wide:
        columns.append(('FAMILY', 'family', '<'))
        columns.append(('EMBED', 'embedding', '>'))
    columns.append(('CAPABILITIES', 'capabilities_label', '<'))
    if wide:
        columns.append(('LICENSE', 'license', '<'))
    columns.append(('SIZE', 'size_label', '>'))
    columns.append(('MODIFIED', 'modified_date', '<'))
    if wide:
        columns.append(('DIGEST', 'digest', '<'))
    return columns


def pad(text, width, align):
    """Pad or truncate a cell to the given width."""
    if len(text) > width:
        if width > 3:
            text = text[:width - 3] + '...'
        else:
            text = text[:width]
    if align == '>':
        return text.rjust(width)
    return text.ljust(width)


def format_row(values, widths, aligns):
    """Format one row of cells with two spaces between columns."""
    cells = []
    for value, width, align in zip(values, widths, aligns):
        cells.append(pad(value, width, align))
    return '  '.join(cells)


def fit_widths(widths, headers):
    """Shrink the flexible columns so the table fits a typical terminal."""
    minimums = []
    for header in headers:
        if header == 'NAME':
            minimums.append(12)
        elif header == 'CAPABILITIES':
            minimums.append(10)
        else:
            minimums.append(len(header))

    terminal = shutil.get_terminal_size((120, 24)).columns
    excess = sum(widths) + 2 * (len(widths) - 1) - terminal
    if excess <= 0:
        return widths

    fitted = list(widths)
    for index, header in enumerate(headers):
        if header not in ('NAME', 'CAPABILITIES'):
            continue
        reducible = fitted[index] - minimums[index]
        if reducible > 0:
            cut = min(reducible, excess)
            fitted[index] -= cut
            excess -= cut
        if excess <= 0:
            break
    return fitted


def render_table(records, wide):
    """Print the all-models listing."""
    columns = table_columns(wide)
    headers = []
    keys = []
    aligns = []
    for header, key, align in columns:
        headers.append(header)
        keys.append(key)
        aligns.append(align)

    rows = []
    for record in records:
        row = []
        for key in keys:
            row.append(cell_value(record, key))
        rows.append(row)

    widths = []
    for index, header in enumerate(headers):
        width = len(header)
        for row in rows:
            width = max(width, len(row[index]))
        widths.append(width)
    widths = fit_widths(widths, headers)

    print(format_row(headers, widths, aligns).rstrip())
    for row in rows:
        print(format_row(row, widths, aligns).rstrip())


def capability_key(capability):
    """Sort known capabilities first, then any unknown ones by name."""
    if capability in CAPABILITY_ORDER:
        return (CAPABILITY_ORDER.index(capability), '')
    return (len(CAPABILITY_ORDER), capability)


def short_digest(record):
    """Return the first twelve characters of a digest."""
    return (record['digest'] or '')[:12] or '-'


def render_compare(records):
    """Print the selected models as an attribute-by-model table."""
    labels = [
        'Family',
        'Parameters',
        'Quantization',
        'Native context',
        'Embedding length',
        'License',
        'Size',
        'Modified',
        'Digest',
    ]

    values = []
    values.append([record['family'] or '-' for record in records])
    values.append([record['parameter_size'] or '-' for record in records])
    values.append([record['quantization'] or '-' for record in records])
    values.append(
        [context_detail(record['context_length']) for record in records]
    )
    embedding = []
    for record in records:
        value = record['embedding_length']
        embedding.append(str(value) if value else '-')
    values.append(embedding)
    values.append([record['license'] or '-' for record in records])
    values.append([record['size_label'] for record in records])
    values.append([record['modified_date'] for record in records])
    values.append([short_digest(record) for record in records])

    all_capabilities = []
    for record in records:
        for capability in record['capabilities']:
            if capability not in all_capabilities:
                all_capabilities.append(capability)
    all_capabilities.sort(key=capability_key)

    rows = []
    for label, row_values in zip(labels, values):
        rows.append((label, row_values))
    if all_capabilities:
        rows.append(('Capabilities', [''] * len(records)))
        for capability in all_capabilities:
            row_values = []
            for record in records:
                if capability in record['capabilities']:
                    row_values.append('yes')
                else:
                    row_values.append('no')
            rows.append(('  ' + capability, row_values))

    label_width = len('ATTRIBUTE')
    for label, _ in rows:
        label_width = max(label_width, len(label))

    model_widths = []
    for index, record in enumerate(records):
        width = len(record['name'])
        for _, row_values in rows:
            width = max(width, len(row_values[index]))
        model_widths.append(width)

    headers = ['ATTRIBUTE']
    for record in records:
        headers.append(record['name'])
    header_widths = [label_width] + model_widths
    header_aligns = ['<'] + ['<'] * len(records)
    print(format_row(headers, header_widths, header_aligns).rstrip())

    for label, row_values in rows:
        cells = [label] + row_values
        print(format_row(cells, header_widths, header_aligns).rstrip())


def render_json(records):
    """Print records as a JSON array with a stable set of fields."""
    payload = []
    for record in records:
        item = {}
        for field in JSON_FIELDS:
            item[field] = record[field]
        payload.append(item)
    print(json.dumps(payload, indent=2))


def parse_args(argv):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='ollama-info',
        description='Show and compare the model metadata ollama list hides.',
        epilog=(
            "CTX is the model's native context length, not the runtime "
            "num_ctx shown by 'ollama ps'."
        ),
    )
    parser.add_argument(
        'models',
        nargs='*',
        metavar='MODEL',
        help='models to compare side by side (default: list all models)',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='print JSON instead of a table',
    )
    parser.add_argument(
        '--sort',
        choices=('name', 'size', 'modified', 'params', 'context'),
        default='name',
        help=(
            'sort the list view by this field '
            '(default: name; list view only)'
        ),
    )
    parser.add_argument(
        '--reverse',
        action='store_true',
        help='reverse the sort order',
    )
    parser.add_argument(
        '--has',
        action='append',
        default=[],
        metavar='CAP',
        help=(
            'only list models with this capability '
            '(repeatable; list view only)'
        ),
    )
    parser.add_argument(
        '--wide',
        action='store_true',
        help='add family, embedding, license, and digest columns',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    )
    return parser.parse_args(argv)


def run(argv=None):
    """List or compare models and return an exit code."""
    args = parse_args(argv)

    try:
        response = ollama.list()
    except Exception as error:
        print(f'Could not list models: {error}', file=sys.stderr)
        return 1

    records, missing, failures = gather(response.models, args.models)

    for name, error in failures:
        print(f'Could not inspect {name}: {error}', file=sys.stderr)
    for name in missing:
        print(f'No such model: {name}', file=sys.stderr)

    if args.models:
        if not records:
            if args.json:
                print('[]')
            return 1
    else:
        if args.has:
            filtered = []
            for record in records:
                capabilities = set(record['capabilities'])
                matched = all(
                    capability.lower() in capabilities
                    for capability in args.has
                )
                if matched:
                    filtered.append(record)
            records = filtered
        if not records:
            if args.json:
                print('[]')
            elif args.has:
                print('No models matched the filters.')
            else:
                print('No models found.')
            return 0
        records.sort(
            key=lambda record: sort_value(record, args.sort),
            reverse=args.reverse,
        )

    if args.json:
        render_json(records)
    elif args.models:
        render_compare(records)
    else:
        render_table(records, args.wide)

    return 1 if missing else 0


def main(argv=None):
    """Run the tool, mapping interrupts to exit code 130."""
    try:
        return run(argv)
    except (EOFError, KeyboardInterrupt):
        print('\nInterrupted.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
