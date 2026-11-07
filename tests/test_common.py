from ollama_scripts.common import context_detail, format_context, format_size


def test_format_size():
    assert format_size(0) == '0 B'
    assert format_size(1024) == '1.0 KB'
    assert format_size(1536) == '1.5 KB'
    assert format_size(1024 ** 3) == '1.0 GB'
    assert format_size(4.7 * 1024 ** 3) == '4.7 GB'


def test_format_context():
    assert format_context(None) == '-'
    assert format_context(0) == '-'
    assert format_context(512) == '512'
    assert format_context(32768) == '32k'
    assert format_context(262144) == '256k'
    assert format_context(1572864) == '1.5m'


def test_context_detail():
    assert context_detail(None) == '-'
    assert context_detail(1000) == '1000'
    assert context_detail(262144) == '262144 (256k)'
