# ollama-scripts

Small CLI tools for working with a local [Ollama](https://ollama.com) instance.
They are aimed at people who frequently evaluate models, accumulate tags, and
need to understand or prune what is on disk.

This is an unofficial project and is not affiliated with Ollama.

## Tools

- **`ollama-info`** — show the metadata that `ollama list` hides, filter by
  capability, compare models side by side, or emit JSON.
- **`ollama-rm`** — interactively prune models one at a time, with no deletion
  until a final confirmation.

## Requirements

- Python 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/)
- A reachable Ollama daemon (defaults to `localhost:11434`; respects
  `OLLAMA_HOST`)

## Install

From a clone:

```bash
git clone https://github.com/allhailthetail/ollama-scripts.git
cd ollama-scripts
uv tool install .
```

For development, install in editable mode so source edits take effect
immediately:

```bash
uv tool install --editable .
```

`uv tool` installs the `ollama-rm` and `ollama-info` commands into
`~/.local/bin`, which should be on your `PATH`. The tool gets its own isolated
environment, including the `ollama` Python client, so it does not modify system
Python.

## Usage

### `ollama-info`

```bash
ollama-info                          # table of all models
ollama-info qwen3.5:4b llama3.1:8b   # compare models side by side
ollama-info --json                   # machine-readable output
ollama-info --has vision             # filter by capability
ollama-info --has vision --has tools # repeatable, AND semantics
ollama-info --sort size --reverse    # sort by size, largest first
ollama-info --wide                   # family, embedding, license, digest
```

The table shows `NAME`, `PARAMS`, `QUANT`, `CTX`, `CAPABILITIES`, `SIZE`, and
`MODIFIED`. `CTX` is the model's native context length, not the runtime
`num_ctx` shown by `ollama ps`. `completion` is omitted from `CAPABILITIES`
because it is universal; compare mode expands capabilities into a yes/no
matrix.

### `ollama-rm`

```bash
ollama-rm
```

Models are shown largest first. Answer `y`/`yes` to select one, `n`/`no` to
keep it, and `q`/`quit` to abort without deleting. Nothing is deleted until a
second confirmation prompt, which requires an explicit `y`/`yes` or `n`/`no`;
a blank line does not count as "no" and asks again.

## Development

```bash
uv sync
uv run pytest
uv run ollama-info
uv run ollama-rm
uv build
```

Tests mock the Ollama client, so no daemon is required.

## Uninstall

```bash
uv tool uninstall ollama-scripts
```

## License

MIT. See [LICENSE](LICENSE).
