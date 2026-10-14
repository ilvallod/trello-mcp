# Trello MCP

A local `stdio` MCP server for Trello built with FastMCP and Python. 

![Python](https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue)

## Setup

```bashß
uv sync
cp .env.example .env
```

 Fill `.env` with your Trello credentials.

```bash
uv run trello-mcp
```

## MCP Inspector

Start it from this project with:

```bash
npx @modelcontextprotocol/inspector uv --directory /absolute/path/to/trello-mcp run trello-mcp
```

The Inspector starts a local browser UI and prints a session token in the terminal, along with a URL that already includes the token. The easiest option is to copy and open the full URL printed by the Inspector. Or you can add the token manually if the Inspector UI is already open in **Configuration** > **Proxy Session Token**

## Resources

Read-only Trello data is exposed as MCP resources. Resources are addressed by URI and can be read by MCP clients without treating the operation as a mutating action. Like a GET

- `trello://boards{?include_closed}`
- `trello://boards/{board_id}/lists{?include_closed}`
- `trello://lists/{list_id}/cards{?include_closed}`
- `trello://cards/{card}`
- `trello://cards/{card}/comments{?limit}`

## Tools

Mutating Trello operations are exposed as MCP tools. Like a POST

- `add_comment(card: str, text: str)`
- `create_card(list_id: str, name: str, description: str | None = None, due: str | None = None)`
- `add_member_to_card(card: str, member: str)`
- `move_card(card: str, list_id: str)`
- `update_card_description(card: str, description: str)`
- `attach_image_to_card(card: str, image_url: str, name: str | None = None)`
- `attach_local_image_to_card(card: str, file_path: str, name: str | None = None, mime_type: str | None = None)`
- `rename_list(list_id: str, new_name: str)`

## Coding agent setup

Add this server definition to `.codex/config.toml` or or `~/.claude.json`:

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

```bash
uv run --directory /absolute/path/to/trello-mcp trello-mcp
```

## Optional hardening for local file uploads

The tool `attach_local_image_to_card` can read local files from your machine and upload them to Trello.

To restrict where files can be read from, set `TRELLO_UPLOAD_ROOTS`:

```env
TRELLO_UPLOAD_ROOTS=/Users/you/Pictures,/Users/you/Desktop/safe-uploads
```

## OAuth 2.0 note

The current implementation uses Trello's existing API key token model. Waiting for Trello to ship the OAuth 2.0 support. See Atlassian's RFC-89: [Introducing OAuth2 to Trello](https://community.developer.atlassian.com/t/rfc-89-introducing-oauth2-to-trello/90359).
