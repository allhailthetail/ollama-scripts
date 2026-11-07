"""Interactive pruning of local Ollama models."""

import argparse
import sys

import ollama

from . import __version__
from .common import format_size


def describe(model, width):
    """Format one model as a name, size, and modification date row."""
    stamp = (
        model.modified_at.strftime('%Y-%m-%d')
        if model.modified_at else '----------'
    )
    return f'{model.model:<{width}}  {format_size(model.size):>9}  {stamp}'


def parse_args(argv=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='ollama-rm',
        description='Interactively remove local Ollama models.',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Run the interactive deletion flow and return an exit code."""
    parse_args(argv)

    try:
        response = ollama.list()
    except Exception as error:
        print(f'Could not list models: {error}', file=sys.stderr)
        return 1

    models = sorted(
        response.models,
        key=lambda model: model.size or 0,
        reverse=True,
    )
    if not models:
        print('No models found.')
        return 0

    width = max(len(model.model) for model in models)

    # Ask about every model, largest first.
    to_delete = []
    try:
        for item in models:
            print(describe(item, width))
            choice = input('Delete? (y/N/q) ').strip().lower()
            if choice in ('y', 'yes'):
                to_delete.append(item)
            elif choice in ('q', 'quit'):
                print('\nQuitting, nothing deleted.')
                return 0
    except (EOFError, KeyboardInterrupt):
        print('\nInterrupted, nothing deleted.')
        return 130

    if not to_delete:
        print('\nNo models selected, exiting.')
        return 0

    total_size = sum(model.size or 0 for model in to_delete)
    print('\nModels slated to be deleted:\n')
    for item in to_delete:
        print(describe(item, width))
    print(f'\n{len(to_delete)} model(s), {format_size(total_size)} total.')

    try:
        choice = input('Proceed with deletion? (y/N) ').strip().lower()
    except (EOFError, KeyboardInterrupt):
        print('\nInterrupted, nothing deleted.')
        return 130

    if choice not in ('y', 'yes'):
        print('No models were deleted, exiting.')
        return 0

    deleted = []
    failed = []
    try:
        for item in to_delete:
            try:
                ollama.delete(item.model)
            except Exception as error:
                failed.append(item.model)
                print(f'  FAILED {item.model}: {error}', file=sys.stderr)
            else:
                deleted.append(item)
                print(f'Deleted {item.model}')
    except KeyboardInterrupt:
        print('\nDeletion interrupted.')

    freed = sum(item.size or 0 for item in deleted)
    print(
        f'\nDeleted {len(deleted)} of {len(to_delete)} model(s), '
        f'freed ~{format_size(freed)}.'
    )
    if failed:
        print(f'Could not delete: {", ".join(failed)}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
