# Trello MCP

A local `stdio` MCP server for Trello built with FastMCP and Python.

This package is for local agent clients (Claude Code, Codex, and other MCP-compatible tools) that need simple Trello read/write operations.

## 5-minute setup

1. Install dependencies:

```bash
uv sync
```

2. Create credentials file:

```bash
cp .env.example .env
```

Fill `.env`:

```env
TRELLO_API_KEY=your_trello_api_key
TRELLO_API_TOKEN=your_trello_api_token
```

3. Run the server:

```bash
uv run trello-mcp
```

That is enough for local usage.

## Optional hardening for local file uploads

The tool `attach_local_image_to_card` can read local files from your machine and upload them to Trello.

To restrict where files can be read from, set `TRELLO_UPLOAD_ROOTS` (comma-separated absolute paths):

```env
TRELLO_UPLOAD_ROOTS=/Users/you/Pictures,/Users/you/Desktop/safe-uploads
```

If `TRELLO_UPLOAD_ROOTS` is set, files outside those directories are rejected.

## Tools

- `list_boards(include_closed: bool = False)`
- `list_lists(board_id: str, include_closed: bool = False)`
- `list_cards(list_id: str, include_closed: bool = False)`
- `get_card(card: str)`
- `get_card_comments(card: str, limit: int | None = None)`
- `add_comment(card: str, text: str)`
- `create_card(list_id: str, name: str, description: str | None = None, due: str | None = None)`
- `add_member_to_card(card: str, member: str)`
- `move_card(card: str, list_id: str)`
- `update_card_description(card: str, description: str)`
- `attach_image_to_card(card: str, image_url: str, name: str | None = None)`
- `attach_local_image_to_card(card: str, file_path: str, name: str | None = None, mime_type: str | None = None)`
- `rename_list(list_id: str, new_name: str)`

Notes:
- Card arguments accept Trello card ID, shortlink, or full card URL.
- `get_card_comments(limit=...)` accepts values from `1` to `1000`.
- `create_card(due=...)` expects a valid ISO-8601 date/time string.
- `attach_local_image_to_card` only accepts image files.

## Claude Code setup

```bash
claude mcp add --transport stdio trello \
  --env TRELLO_API_KEY=your_trello_api_key \
  --env TRELLO_API_TOKEN=your_trello_api_token \
  -- uv run --directory /absolute/path/to/trello-mcp trello-mcp
```

Project-scoped `.mcp.json` example:

```json
{
  "mcpServers": {
    "trello": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/trello-mcp",
        "trello-mcp"
      ],
      "env": {
        "TRELLO_API_KEY": "${TRELLO_API_KEY}",
        "TRELLO_API_TOKEN": "${TRELLO_API_TOKEN}"
      }
    }
  }
}
```

## Codex setup

Use a local `stdio` server command with the same shape:

```bash
uv run --directory /absolute/path/to/trello-mcp trello-mcp
```

Configure `command`, `args`, and `env` in your Codex MCP config exactly like the Claude example.

## Validation checks (documented)

Run these before every release:

```bash
uv sync
uv run python -m compileall -q src
uv build
```

Expected result:
- `compileall` exits with no errors
- `uv build` creates both `.tar.gz` and `.whl` in `dist/`

## Publish checklist

Before pushing to GitHub:

1. Confirm `.env` is not committed.
2. Run the validation checks above.
3. Verify `README.md` setup steps from a clean shell.
4. Verify package metadata (`pyproject.toml`) version is correct.
5. (Recommended) add a license file (`LICENSE`) before public release.
6. Verify CI passes (`.github/workflows/ci.yml`).

## GitHub push steps

Replace `<your-user>` and `<repo>`:

```bash
git init
git add .
git commit -m "Initial release: Trello MCP server"
git branch -M main
git remote add origin git@github.com:<your-user>/<repo>.git
git push -u origin main
```

If the repository already exists locally with `.git`, skip `git init` and just run add/commit/push.
