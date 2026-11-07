from datetime import datetime
from types import SimpleNamespace

from ollama_scripts import rm


def make_model(name, size):
    return SimpleNamespace(
        model=name,
        size=size,
        modified_at=datetime(2026, 1, 1),
    )


def patch_list(monkeypatch, models):
    monkeypatch.setattr(
        rm.ollama,
        'list',
        lambda: SimpleNamespace(models=models),
    )


def patch_input(monkeypatch, answers):
    remaining = iter(answers)

    def fake_input(prompt=''):
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr('builtins.input', fake_input)


def test_quit_deletes_nothing(monkeypatch, capsys):
    patch_list(
        monkeypatch,
        [make_model('a', 2_000_000_000), make_model('b', 1_000_000_000)],
    )
    patch_input(monkeypatch, ['n', 'q'])
    deleted = []
    monkeypatch.setattr(rm.ollama, 'delete', deleted.append)

    exit_code = rm.main([])

    assert exit_code == 0
    assert deleted == []
    assert 'nothing deleted' in capsys.readouterr().out


def test_eof_returns_130(monkeypatch, capsys):
    patch_list(monkeypatch, [make_model('a', 1_000_000_000)])
    patch_input(monkeypatch, [])
    deleted = []
    monkeypatch.setattr(rm.ollama, 'delete', deleted.append)

    exit_code = rm.main([])

    assert exit_code == 130
    assert deleted == []
    assert 'nothing deleted' in capsys.readouterr().out


def test_no_selection_exits_zero(monkeypatch):
    patch_list(
        monkeypatch,
        [make_model('a', 2_000_000_000), make_model('b', 1_000_000_000)],
    )
    patch_input(monkeypatch, ['n', 'n'])
    deleted = []
    monkeypatch.setattr(rm.ollama, 'delete', deleted.append)

    exit_code = rm.main([])

    assert exit_code == 0
    assert deleted == []


def test_confirmed_selection_deletes_only_selected(monkeypatch, capsys):
    patch_list(
        monkeypatch,
        [make_model('large', 2_000_000_000), make_model('small', 1_000_000_000)],
    )
    patch_input(monkeypatch, ['y', 'n', 'y'])
    deleted = []
    monkeypatch.setattr(rm.ollama, 'delete', deleted.append)

    exit_code = rm.main([])

    assert exit_code == 0
    assert deleted == ['large']
    assert 'Deleted 1 of 1' in capsys.readouterr().out


def test_final_confirmation_declined_deletes_nothing(monkeypatch):
    patch_list(monkeypatch, [make_model('a', 1_000_000_000)])
    patch_input(monkeypatch, ['y', 'n'])
    deleted = []
    monkeypatch.setattr(rm.ollama, 'delete', deleted.append)

    exit_code = rm.main([])

    assert exit_code == 0
    assert deleted == []


def test_delete_failure_exits_one(monkeypatch, capsys):
    patch_list(monkeypatch, [make_model('a', 1_000_000_000)])
    patch_input(monkeypatch, ['y', 'y'])

    def fail_delete(name):
        raise RuntimeError('permission denied')

    monkeypatch.setattr(rm.ollama, 'delete', fail_delete)

    exit_code = rm.main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'FAILED a' in captured.err
    assert 'Could not delete: a' in captured.err


def test_list_failure_exits_one(monkeypatch, capsys):
    def fail_list():
        raise RuntimeError('down')

    monkeypatch.setattr(rm.ollama, 'list', fail_list)

    exit_code = rm.main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'Could not list models: down' in captured.err
