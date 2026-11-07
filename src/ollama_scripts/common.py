"""Shared formatting helpers for the Ollama CLI tools."""


def format_size(size):
    """Return a byte count as a short human-readable string."""
    size = float(size or 0)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024 or unit == 'TB':
            return f'{size:.0f} {unit}' if unit == 'B' else f'{size:.1f} {unit}'
        size /= 1024


def format_context(length):
    """Return a context length as a short human-readable string."""
    if not length:
        return '-'
    if length >= 1024 * 1024:
        return f'{length / (1024 * 1024):g}m'
    if length >= 1024:
        return f'{length // 1024}k'
    return str(length)


def context_detail(length):
    """Return an exact context length with a short label in parentheses."""
    if not length:
        return '-'
    short = format_context(length)
    if short == str(length):
        return str(length)
    return f'{length} ({short})'
