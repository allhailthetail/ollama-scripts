import json
from datetime import datetime
from types import SimpleNamespace

from ollama_scripts import info


def make_details(**overrides):
    values = {
        'family': 'demo',
        'families': ['demo'],
        'parameter_size': '7.6B',
        'quantization_level': 'Q4_K_M',
        'format': 'gguf',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_model(name='demo:7b', size=4_000_000_000, digest='abcdef0123456789',
               modified=None, details=None):
    return SimpleNamespace(
        model=name,
        size=size,
        digest=digest,
        modified_at=modified or datetime(2026, 1, 2, 3, 4, 5),
        details=details or make_details(),
    )


def make_show(capabilities=None, modelinfo=None):
    return SimpleNamespace(
        capabilities=capabilities or [],
        modelinfo=modelinfo or {},
    )


def test_describe_full():
    model = make_model()
    show = make_show(
        capabilities=['completion', 'tools', 'vision'],
        modelinfo={
            'general.architecture': 'demo',
            'general.parameter_count': 7_600_000_000,
            'general.license': 'apache-2.0',
            'demo.context_length': 32768,
            'demo.embedding_length': 3584,
        },
    )

    record = info.describe(model, show)

    assert record['name'] == 'demo:7b'
    assert record['size'] == 4_000_000_000
    assert record['context_length'] == 32768
    assert record['embedding_length'] == 3584
    assert record['license'] == 'apache-2.0'
    assert record['capabilities'] == ['completion', 'tools', 'vision']
    assert record['parameter_count'] == 7_600_000_000
    assert record['modified_at'] == '2026-01-02T03:04:05'
    assert record['modified_date'] == '2026-01-02'


def test_describe_minimal():
    record = info.describe(make_model(), None)

    assert record['context_length'] is None
    assert record['embedding_length'] is None
    assert record['capabilities'] == []
    assert record['license'] is None
    assert record['parameter_count'] == 7_600_000_000


def test_describe_context_fallback():
    show = make_show(
        modelinfo={
            'general.architecture': 'demo',
            'other.context_length': 4096,
        },
    )

    record = info.describe(make_model(), show)

    assert record['context_length'] == 4096


def test_parse_parameter_size():
    assert info.parse_parameter_size('7.6B') == 7_600_000_000
    assert info.parse_parameter_size('512M') == 512_000_000
    assert info.parse_parameter_size('1T') == 1_000_000_000_000
    assert info.parse_parameter_size('unknown') is None
    assert info.parse_parameter_size(None) is None


def test_sort_value():
    record = {
        'name': 'Demo:7B',
        'size': 123,
        'modified_at': '2026-01-02T03:04:05',
        'parameter_count': 7_600_000_000,
        'context_length': 32768,
    }

    assert info.sort_value(record, 'name') == 'demo:7b'
    assert info.sort_value(record, 'size') == 123
    assert info.sort_value(record, 'modified') == '2026-01-02T03:04:05'
    assert info.sort_value(record, 'params') == 7_600_000_000
    assert info.sort_value(record, 'context') == 32768


def test_gather_preserves_order_and_reports_missing(monkeypatch):
    models = [make_model('a'), make_model('b')]
    monkeypatch.setattr(
        info.ollama,
        'show',
        lambda name: make_show(capabilities=['completion']),
    )

    records, missing, failures = info.gather(models, ['b', 'a', 'b', 'nope'])

    assert [record['name'] for record in records] == ['b', 'a']
    assert missing == ['nope']
    assert failures == []


def test_gather_tolerates_show_failure(monkeypatch):
    models = [make_model('a')]

    def fail_show(name):
        raise RuntimeError('bad manifest')

    monkeypatch.setattr(info.ollama, 'show', fail_show)

    records, missing, failures = info.gather(models, None)

    assert len(records) == 1
    assert records[0]['name'] == 'a'
    assert records[0]['capabilities'] == []
    assert missing == []
    assert failures == [('a', 'bad manifest')]


def test_cli_json(monkeypatch, capsys):
    models = [make_model('a'), make_model('b')]
    monkeypatch.setattr(
        info.ollama,
        'list',
        lambda: SimpleNamespace(models=models),
    )
    monkeypatch.setattr(
        info.ollama,
        'show',
        lambda name: make_show(capabilities=['completion']),
    )

    exit_code = info.main(['--json'])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert [record['name'] for record in output] == ['a', 'b']
    assert set(output[0]) == set(info.JSON_FIELDS)


def test_cli_compare_preserves_requested_order(monkeypatch, capsys):
    models = [make_model('a'), make_model('b')]
    monkeypatch.setattr(
        info.ollama,
        'list',
        lambda: SimpleNamespace(models=models),
    )
    monkeypatch.setattr(info.ollama, 'show', lambda name: make_show())

    exit_code = info.main(['--json', 'b', 'a'])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert [record['name'] for record in output] == ['b', 'a']


def test_cli_capability_filter(monkeypatch, capsys):
    models = [make_model('vision-model'), make_model('text-model')]

    def fake_show(name):
        if name == 'vision-model':
            return make_show(capabilities=['completion', 'vision'])
        return make_show(capabilities=['completion'])

    monkeypatch.setattr(
        info.ollama,
        'list',
        lambda: SimpleNamespace(models=models),
    )
    monkeypatch.setattr(info.ollama, 'show', fake_show)

    exit_code = info.main(['--has', 'vision'])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert 'vision-model' in output
    assert 'text-model' not in output


def test_cli_empty_filter_with_json(monkeypatch, capsys):
    monkeypatch.setattr(
        info.ollama,
        'list',
        lambda: SimpleNamespace(models=[make_model('a')]),
    )
    monkeypatch.setattr(info.ollama, 'show', lambda name: make_show())

    exit_code = info.main(['--json', '--has', 'nosuch'])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output == '[]\n'


def test_cli_missing_model(monkeypatch, capsys):
    monkeypatch.setattr(
        info.ollama,
        'list',
        lambda: SimpleNamespace(models=[make_model('a')]),
    )
    monkeypatch.setattr(info.ollama, 'show', lambda name: make_show())

    exit_code = info.main(['nope:1b'])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'No such model: nope:1b' in captured.err


def test_cli_unreachable_daemon(monkeypatch, capsys):
    def fail_list():
        raise RuntimeError('down')

    monkeypatch.setattr(info.ollama, 'list', fail_list)

    exit_code = info.main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'Could not list models: down' in captured.err


def test_cli_interrupt_returns_130(monkeypatch, capsys):
    def interrupt_list():
        raise KeyboardInterrupt

    monkeypatch.setattr(info.ollama, 'list', interrupt_list)

    exit_code = info.main([])
    captured = capsys.readouterr()

    assert exit_code == 130
    assert 'Interrupted.' in captured.err
