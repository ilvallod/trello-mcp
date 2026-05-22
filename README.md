# Trello MCP

A local `stdio` MCP server for Trello built with FastMCP and Python. 

![Python](https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue)

## Setup

```bash
uv sync
cp .env.example .env
```

 Fill `.env` with your Trello credentials.

```bash
uv run trello-mcp
```

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

## Codex setup

```bash
uv run --directory /absolute/path/to/trello-mcp trello-mcp
```

Example config:

```toml
[mcp_servers.trello]
transport = "stdio"
command = "uv"
args = ["run", "--directory", "/absolute/path/to/trello-mcp", "trello-mcp"]

[mcp_servers.trello.env]
TRELLO_API_KEY = "${TRELLO_API_KEY}"
TRELLO_API_TOKEN = "${TRELLO_API_TOKEN}"
TRELLO_UPLOAD_ROOTS = "${TRELLO_UPLOAD_ROOTS}"
```

## Optional hardening for local file uploads

The tool `attach_local_image_to_card` can read local files from your machine and upload them to Trello.

To restrict where files can be read from, set `TRELLO_UPLOAD_ROOTS`:

```env
TRELLO_UPLOAD_ROOTS=/Users/you/Pictures,/Users/you/Desktop/safe-uploads
```
