# Agents

## Project

This repository is a small Python package providing CLI tools for working with
a local Ollama instance. It is aimed at people who frequently evaluate new
models, accumulate many tags, and need to understand or prune what is on disk.

- `ollama-rm` — interactive pruning. It lists every model with its size and
  modification date, asks about each one, and deletes the selected models after
  a final confirmation.
- `ollama-info` — read-only metadata listing and side-by-side comparison, with
  JSON output for scripts.

## Layout

- `src/ollama_scripts/` — the package. `rm.py` and `info.py` hold the command
  implementations; `common.py` holds genuinely shared helpers.
- `tests/` — pytest suite. Tests mock `ollama.list`, `ollama.show`, and
  `ollama.delete`; they never need a daemon.
- `pyproject.toml` — project metadata, dependencies, and `[project.scripts]`
  entry points. The installed `ollama-rm` and `ollama-info` commands are
  generated from this file; there are no extensionless source scripts.
- `uv.lock` — locked environment for development and tests. Commit changes to
  it.
- `README.md` — user-facing install and usage documentation.
- `LICENSE` — MIT license text.

## Running

During development:

```bash
uv run ollama-rm
uv run ollama-info
```

To install the commands into `~/.local/bin` with live source edits:

```bash
uv tool install --editable .
```

Requirements:

- Python 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/)
- A reachable Ollama daemon (defaults to `localhost:11434`; respects
  `OLLAMA_HOST`)

## Behavior and safety

### ollama-rm

- Answers are `y`/`yes` (case-insensitive, whitespace-trimmed) and `q`/`quit` to
  abort without deleting.
- Models are sorted largest first; sizes are shown human-readable and the final
  prompt includes the total size to be freed.
- Nothing is deleted until the second confirmation. That final prompt requires
  an explicit `y`/`yes` or `n`/`no`; a blank line re-prompts rather than
  declining.
- `ollama.delete()` removes one tag, not every tag sharing a digest.
- A failed deletion does not stop the run; failures are reported and the script
  exits `1`. Interrupts exit `130`. Success and "nothing selected" exit `0`.
- Ctrl-C or Ctrl-D before confirming deletes nothing.

### ollama-info

- Read-only: it never deletes, copies, pulls, or modifies models, and makes no
  network calls beyond the Ollama daemon.
- `ollama.list()` supplies name, size, modification time, digest, family,
  parameter size, and quantization.
- One `ollama.show()` call per model supplies capabilities, native context
  length, embedding length, and license. Missing fields are shown as `-` and the
  run continues.
- `CTX` is the model's native context length, not the runtime `num_ctx` shown by
  `ollama ps`.
- `CAPABILITIES` omits `completion`; compare mode prints a yes/no matrix.
- `--has CAP` filters the list view by capability and is repeatable (AND).
- `--wide` adds family, embedding length, license, and digest columns.
- `--sort` supports `name`, `size`, `modified`, `params`, and `context`;
  `--reverse` flips the order.
- Unknown model names are reported and make the command exit `1`; the other
  requested models are still shown.
- A failed `ollama.show()` is reported on stderr but does not stop the listing.
- An unreachable daemon exits `1`; interrupts exit `130`.

## Conventions

- Keep it dependency-light: standard library plus `ollama`.
- Put command code in `src/ollama_scripts/`; declare installed commands in
  `[project.scripts]`, not as standalone executable files.
- Keep `main()` returning an integer and retain the
  `if __name__ == '__main__':` guard so modules can also run with
  `python -m ollama_scripts.<name>`.
- Do not use list comprehensions for side effects; use loops.
- Follow the existing style: single quotes, `snake_case`, short helpers, no
  unnecessary abstraction.
- Prefer read-only, reporting behavior. Destructive operations need an explicit
  confirmation and should be easy to test without touching real models.
- Preserve the interactive, one-model-at-a-time workflow unless asked to add
  non-interactive flags.

## Testing

There is no external test service. Before committing, run:

```bash
uv sync
uv run pytest
```

and exercise the safe smoke paths:

```bash
uv run ollama-info
uv run ollama-info --json | python3 -m json.tool
uv run ollama-info --has vision
uv run ollama-info MODEL_A MODEL_B

printf 'n\nn\nq\n' | uv run ollama-rm    # quit without deleting
uv run ollama-rm < /dev/null             # EOF, must exit 130
```

Avoid deletion tests against a real daemon; the pytest suite mocks
`ollama.delete`. For metadata edge cases, tests mock `ollama.list` and
`ollama.show` rather than relying on a particular local model set.
