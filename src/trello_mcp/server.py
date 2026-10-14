from __future__ import annotations

from functools import lru_cache

from fastmcp import FastMCP

from .client import TrelloApiError, TrelloClient, TrelloConfig


mcp = FastMCP(
    "Trello MCP",
    instructions=(
        "Use these tools to inspect Trello boards, lists, cards, and comments, "
        "to add comments and image attachments (from URL or local file) to cards, "
        "to create cards, to move cards between lists, to update card descriptions, "
        "to add members to cards, and to rename lists (columns) on behalf of the "
        "authenticated Trello user."
    ),
)


@lru_cache(maxsize=1)
def get_client() -> TrelloClient:
    config = TrelloConfig.from_env()
    return TrelloClient(config)

### RESOURCES ###

@mcp.resource(
    "trello://boards{?include_closed}",
    name="trello_boards",
    mime_type="application/json",
)
def list_boards(include_closed: bool = False) -> list[dict]:
    """Readable Trello boards accessible to the configured account."""

    return get_client().list_boards(include_closed=include_closed)


@mcp.resource(
    "trello://boards/{board_id}/lists{?include_closed}",
    name="trello_board_lists",
    mime_type="application/json",
)
def list_lists(board_id: str, include_closed: bool = False) -> list[dict]:
    """Readable Trello lists on a board."""

    return get_client().list_lists(board_id=board_id, include_closed=include_closed)


@mcp.resource(
    "trello://lists/{list_id}/cards{?include_closed}",
    name="trello_list_cards",
    mime_type="application/json",
)
def list_cards(list_id: str, include_closed: bool = False) -> list[dict]:
    """Readable Trello cards in a list."""

    return get_client().list_cards(list_id=list_id, include_closed=include_closed)


@mcp.resource(
    "trello://cards/{card}",
    name="trello_card",
    mime_type="application/json",
)
def get_card(card: str) -> dict:
    """Readable Trello card by card ID or shortlink."""

    return get_client().get_card(card=card)


@mcp.resource(
    "trello://cards/{card}/comments{?limit}",
    name="trello_card_comments",
    mime_type="application/json",
)
def get_card_comments(card: str, limit: int | None = None) -> list[dict]:
    """Readable comments from a Trello card by card ID or shortlink."""

    return get_client().get_card_comments(card=card, limit=limit)

### PROMPTS ### 

@mcp.prompt
def summarize_card(card: str) -> str:
    return f"""Given the Trello card reference `{card}`, read the resources `trello://cards/{card}` and `trello://cards/{card}/comments`.

Create a summary that helps a teammate quickly understand the card history and what still needs attention.

Include:
- Current status
- What has been addressed
- Decisions made
- Open issues

Use the comments to reconstruct the discussion over time. Treat newer comments as more relevant for the current state. Do not invent missing details, and explicitly mark uncertain or unresolved items."""

### TOOLS ###

@mcp.tool
def add_comment(card: str, text: str) -> dict:
    """Add a comment to a Trello card by card ID, shortlink, or full URL."""

    return get_client().add_comment(card=card, text=text)


@mcp.tool
def create_card(
    list_id: str,
    name: str,
    description: str | None = None,
    due: str | None = None,
) -> dict:
    """Create a Trello card in the given list."""

    return get_client().create_card(
        list_id=list_id,
        name=name,
        description=description,
        due=due,
    )


@mcp.tool
def add_member_to_card(card: str, member: str) -> dict:
    """Add a Trello member to a card by card reference and member ID/username/'me'."""

    return get_client().add_member_to_card(card=card, member=member)


@mcp.tool
def update_card_description(card: str, description: str) -> dict:
    """Update a Trello card description by card ID, shortlink, or full URL."""

    return get_client().update_card_description(card=card, description=description)


@mcp.tool
def move_card(card: str, list_id: str) -> dict:
    """Move a Trello card to another list by card reference and list ID."""

    return get_client().move_card(card=card, list_id=list_id)


@mcp.tool
def attach_image_to_card(card: str, image_url: str, name: str | None = None) -> dict:
    """Attach an image URL to a Trello card by card ID, shortlink, or full URL."""

    return get_client().attach_image_to_card(card=card, image_url=image_url, name=name)


@mcp.tool
def attach_local_image_to_card(
    card: str,
    file_path: str,
    name: str | None = None,
    mime_type: str | None = None,
) -> dict:
    """Attach a local image file to a Trello card by card ID, shortlink, or full URL."""

    return get_client().attach_local_image_to_card(
        card=card,
        file_path=file_path,
        name=name,
        mime_type=mime_type,
    )


@mcp.tool
def rename_list(list_id: str, new_name: str) -> dict:
    """Rename a Trello list (column) by list ID."""

    return get_client().rename_list(list_id=list_id, new_name=new_name)


def main() -> None:
    try:
        get_client()
    except TrelloApiError as exc:
        raise SystemExit(str(exc)) from exc

    mcp.run(transport="stdio")
