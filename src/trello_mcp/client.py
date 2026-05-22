from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
import mimetypes
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


class TrelloApiError(RuntimeError):
    """Raised when the Trello API returns an error."""


CARD_URL_RE = re.compile(r"trello\.com/c/([A-Za-z0-9]+)", re.IGNORECASE)
CARD_FIELDS = "name,desc,url,closed,due,dueComplete,idBoard,idList,shortLink"
CARD_COMMON_PARAMS = {
    "fields": CARD_FIELDS,
    "badges": "true",
    "labels": "true",
}
MAX_ACTIONS_LIMIT = 1000


@dataclass(frozen=True)
class TrelloConfig:
    api_key: str
    api_token: str
    base_url: str = "https://api.trello.com/1"
    timeout_seconds: float = 20.0
    upload_roots: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "TrelloConfig":
        load_dotenv()

        api_key = os.getenv("TRELLO_API_KEY", "").strip()
        api_token = os.getenv("TRELLO_API_TOKEN", "").strip()
        upload_roots = tuple(
            os.path.abspath(os.path.expanduser(root.strip()))
            for root in os.getenv("TRELLO_UPLOAD_ROOTS", "").split(",")
            if root.strip()
        )

        missing = [
            name
            for name, value in (
                ("TRELLO_API_KEY", api_key),
                ("TRELLO_API_TOKEN", api_token),
            )
            if not value
        ]
        if missing:
            missing_names = ", ".join(missing)
            raise TrelloApiError(
                f"Missing required environment variables: {missing_names}."
            )

        return cls(
            api_key=api_key,
            api_token=api_token,
            upload_roots=upload_roots,
        )


def normalize_card_reference(card: str) -> str:
    candidate = card.strip()
    if not candidate:
        raise TrelloApiError("Card reference cannot be empty.")

    match = CARD_URL_RE.search(candidate)
    if match:
        return match.group(1)

    return candidate


class TrelloClient:
    def __init__(self, config: TrelloConfig) -> None:
        self._config = config
        self._upload_roots = tuple(Path(root).resolve() for root in config.upload_roots)
        self._http = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={"Accept": "application/json"},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        merged_params = {"key": self._config.api_key, "token": self._config.api_token}
        if params:
            merged_params.update(params)

        response = self._http.request(
            method,
            path,
            params=merged_params,
            data=data,
            files=files,
        )
        return self._handle_response(response, method=method, path=path)

    @staticmethod
    def _handle_response(response: httpx.Response, *, method: str, path: str) -> Any:
        if response.is_success:
            return response.json()

        message = response.text
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = payload.get("message") or payload.get("error") or message
        except ValueError:
            pass

        raise TrelloApiError(
            f"Trello API error {response.status_code} for {method} {path}: {message}"
        )

    def list_boards(self, include_closed: bool = False) -> list[dict[str, Any]]:
        boards = self._request(
            "GET",
            "/members/me/boards",
            params={
                "fields": "name,url,closed,desc,idOrganization,shortLink",
            },
        )
        return [
            {
                "id": board["id"],
                "short_link": board.get("shortLink"),
                "name": board["name"],
                "description": board.get("desc", ""),
                "url": board.get("url"),
                "closed": board.get("closed", False),
                "organization_id": board.get("idOrganization"),
            }
            for board in boards
            if include_closed or not board.get("closed", False)
        ]

    def list_lists(
        self, board_id: str, include_closed: bool = False
    ) -> list[dict[str, Any]]:
        lists = self._request(
            "GET",
            f"/boards/{board_id}/lists",
            params={"fields": "name,closed,pos"},
        )
        return [
            {
                "id": trello_list["id"],
                "name": trello_list["name"],
                "closed": trello_list.get("closed", False),
                "position": trello_list.get("pos"),
            }
            for trello_list in lists
            if include_closed or not trello_list.get("closed", False)
        ]

    def list_cards(
        self, list_id: str, include_closed: bool = False
    ) -> list[dict[str, Any]]:
        cards = self._request(
            "GET",
            f"/lists/{list_id}/cards",
            params=CARD_COMMON_PARAMS,
        )
        return [
            self._card_summary(card)
            for card in cards
            if include_closed or not card.get("closed", False)
        ]

    def get_card(self, card: str) -> dict[str, Any]:
        ref = normalize_card_reference(card)
        card_data = self._request(
            "GET",
            f"/cards/{ref}",
            params={
                **CARD_COMMON_PARAMS,
                "members": "true",
                "member_fields": "fullName,username",
            },
        )
        board = self._request(
            "GET",
            f"/boards/{card_data['idBoard']}",
            params={"fields": "name,url"},
        )
        trello_list = self._request(
            "GET",
            f"/lists/{card_data['idList']}",
            params={"fields": "name,closed"},
        )

        return {
            **self._card_summary(card_data),
            "description": card_data.get("desc", ""),
            "board": {
                "id": board["id"],
                "name": board["name"],
                "url": board.get("url"),
            },
            "list": {
                "id": trello_list["id"],
                "name": trello_list["name"],
                "closed": trello_list.get("closed", False),
            },
            "members": [
                {
                    "id": member["id"],
                    "full_name": member.get("fullName"),
                    "username": member.get("username"),
                }
                for member in card_data.get("members", [])
            ],
            "labels": [
                {
                    "id": label["id"],
                    "name": label.get("name"),
                    "color": label.get("color"),
                }
                for label in card_data.get("labels", [])
            ],
        }

    def get_card_comments(
        self, card: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        ref = normalize_card_reference(card)
        params: dict[str, Any] = {
            "filter": "commentCard",
        }
        if limit is not None:
            if not 1 <= limit <= MAX_ACTIONS_LIMIT:
                raise TrelloApiError(
                    f"Comment limit must be between 1 and {MAX_ACTIONS_LIMIT}."
                )
            params["limit"] = limit

        actions = self._request("GET", f"/cards/{ref}/actions", params=params)
        return [
            {
                "id": action["id"],
                "date": action.get("date"),
                "text": action.get("data", {}).get("text", ""),
                "member_creator": {
                    "id": action.get("memberCreator", {}).get("id"),
                    "full_name": action.get("memberCreator", {}).get("fullName"),
                    "username": action.get("memberCreator", {}).get("username"),
                },
            }
            for action in actions
        ]

    def add_comment(self, card: str, text: str) -> dict[str, Any]:
        ref = normalize_card_reference(card)
        comment_text = text.strip()
        if not comment_text:
            raise TrelloApiError("Comment text cannot be empty.")

        action = self._request(
            "POST",
            f"/cards/{ref}/actions/comments",
            params={"text": comment_text},
        )
        return {
            "id": action["id"],
            "date": action.get("date"),
            "text": action.get("data", {}).get("text", comment_text),
            "card": {
                "id": action.get("data", {}).get("card", {}).get("id"),
                "name": action.get("data", {}).get("card", {}).get("name"),
            },
            "member_creator": {
                "id": action.get("memberCreator", {}).get("id"),
                "full_name": action.get("memberCreator", {}).get("fullName"),
                "username": action.get("memberCreator", {}).get("username"),
            },
        }

    def create_card(
        self,
        list_id: str,
        name: str,
        description: str | None = None,
        due: str | None = None,
    ) -> dict[str, Any]:
        target_list_id = list_id.strip()
        if not target_list_id:
            raise TrelloApiError("List ID cannot be empty.")

        card_name = name.strip()
        if not card_name:
            raise TrelloApiError("Card name cannot be empty.")

        params: dict[str, Any] = {
            "idList": target_list_id,
            "name": card_name,
            **CARD_COMMON_PARAMS,
        }
        if description is not None:
            params["desc"] = description.strip()
        if due is not None and due.strip():
            params["due"] = self._normalize_due_datetime(due.strip())

        card = self._request("POST", "/cards", params=params)
        return self._card_summary(card)

    def add_member_to_card(self, card: str, member: str) -> dict[str, Any]:
        ref = normalize_card_reference(card)
        member_id = self._resolve_member_reference(member)

        self._request(
            "POST",
            f"/cards/{ref}/idMembers",
            params={"value": member_id},
        )
        card_data = self._request(
            "GET",
            f"/cards/{ref}",
            params={
                "fields": "name,shortLink",
                "members": "true",
                "member_fields": "fullName,username",
            },
        )
        return {
            "card": {
                "id": card_data["id"],
                "short_link": card_data.get("shortLink"),
                "name": card_data["name"],
            },
            "members": [
                {
                    "id": member_info["id"],
                    "full_name": member_info.get("fullName"),
                    "username": member_info.get("username"),
                }
                for member_info in card_data.get("members", [])
            ],
        }

    def update_card_description(self, card: str, description: str) -> dict[str, Any]:
        ref = normalize_card_reference(card)
        next_description = description.strip()

        card_data = self._request(
            "PUT",
            f"/cards/{ref}",
            params={
                "desc": next_description,
                **CARD_COMMON_PARAMS,
            },
        )
        return self._card_summary(card_data)

    def move_card(self, card: str, list_id: str) -> dict[str, Any]:
        ref = normalize_card_reference(card)
        target_list_id = list_id.strip()
        if not target_list_id:
            raise TrelloApiError("List ID cannot be empty.")

        try:
            card_data = self._request(
                "GET",
                f"/cards/{ref}",
                params={"fields": "name,idList,shortLink"},
            )
        except TrelloApiError as exc:
            raise TrelloApiError(
                f"Invalid card reference '{card}': card not found or inaccessible."
            ) from exc

        try:
            target_list = self._request(
                "GET",
                f"/lists/{target_list_id}",
                params={"fields": "name,closed"},
            )
        except TrelloApiError as exc:
            raise TrelloApiError(
                f"Invalid list ID '{target_list_id}': list not found or inaccessible."
            ) from exc

        if target_list.get("closed", False):
            raise TrelloApiError(
                f"Invalid list ID '{target_list_id}': target list is closed."
            )

        moved_card = self._request(
            "PUT",
            f"/cards/{card_data['id']}",
            params={
                "idList": target_list_id,
                **CARD_COMMON_PARAMS,
            },
        )
        return {
            **self._card_summary(moved_card),
            "previous_list_id": card_data.get("idList"),
            "target_list": {
                "id": target_list["id"],
                "name": target_list["name"],
                "closed": target_list.get("closed", False),
            },
        }

    def attach_image_to_card(
        self, card: str, image_url: str, name: str | None = None
    ) -> dict[str, Any]:
        ref = normalize_card_reference(card)
        candidate_url = image_url.strip()
        if not candidate_url:
            raise TrelloApiError("Image URL cannot be empty.")

        parsed_url = urlparse(candidate_url)
        if parsed_url.scheme.lower() not in {"http", "https"}:
            raise TrelloApiError("Image URL must start with http:// or https://.")

        params: dict[str, Any] = {"url": candidate_url}
        if name is not None and name.strip():
            params["name"] = name.strip()

        attachment = self._request(
            "POST",
            f"/cards/{ref}/attachments",
            params=params,
        )
        return self._attachment_summary(attachment)

    def attach_local_image_to_card(
        self,
        card: str,
        file_path: str,
        name: str | None = None,
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        ref = normalize_card_reference(card)
        candidate_path = file_path.strip()
        if not candidate_path:
            raise TrelloApiError("File path cannot be empty.")

        resolved_path = os.path.abspath(os.path.expanduser(candidate_path))
        if not os.path.isfile(resolved_path):
            raise TrelloApiError(f"File not found: {resolved_path}")
        self._validate_upload_path(Path(resolved_path))

        attachment_name = os.path.basename(resolved_path)
        if name is not None and name.strip():
            attachment_name = name.strip()

        content_type = None
        if mime_type is not None and mime_type.strip():
            content_type = mime_type.strip()
            if not content_type.lower().startswith("image/"):
                raise TrelloApiError("mime_type must be an image MIME type.")
        else:
            guessed_mime_type, _ = mimetypes.guess_type(resolved_path)
            if not guessed_mime_type or not guessed_mime_type.lower().startswith(
                "image/"
            ):
                raise TrelloApiError(
                    "File does not look like an image. Provide an image file or set mime_type."
                )
            content_type = guessed_mime_type

        with open(resolved_path, "rb") as image_file:
            files = {"file": (attachment_name, image_file, content_type)}

            attachment = self._request(
                "POST",
                f"/cards/{ref}/attachments",
                data={"name": attachment_name},
                files=files,
            )

        return self._attachment_summary(attachment)

    def rename_list(self, list_id: str, new_name: str) -> dict[str, Any]:
        target_list_id = list_id.strip()
        if not target_list_id:
            raise TrelloApiError("List ID cannot be empty.")

        next_name = new_name.strip()
        if not next_name:
            raise TrelloApiError("New list name cannot be empty.")

        trello_list = self._request(
            "PUT",
            f"/lists/{target_list_id}",
            params={"name": next_name, "fields": "name,closed,pos"},
        )
        return {
            "id": trello_list["id"],
            "name": trello_list["name"],
            "closed": trello_list.get("closed", False),
            "position": trello_list.get("pos"),
        }

    def _resolve_member_reference(self, member: str) -> str:
        candidate = member.strip()
        if not candidate:
            raise TrelloApiError("Member reference cannot be empty.")

        if candidate.lower() == "me":
            me = self._request("GET", "/members/me", params={"fields": "id"})
            return me["id"]

        member_data = self._request(
            "GET",
            f"/members/{candidate}",
            params={"fields": "id"},
        )
        return member_data["id"]

    def _validate_upload_path(self, candidate: Path) -> None:
        if not self._upload_roots:
            return

        resolved = candidate.resolve()
        if any(resolved.is_relative_to(root) for root in self._upload_roots):
            return

        allowed = ", ".join(str(root) for root in self._upload_roots)
        raise TrelloApiError(
            "File path is outside allowed upload roots configured in "
            f"TRELLO_UPLOAD_ROOTS: {allowed}"
        )

    @staticmethod
    def _normalize_due_datetime(candidate: str) -> str:
        normalized = candidate
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise TrelloApiError(
                "Invalid due date. Expected ISO-8601 date/time string."
            ) from exc
        return candidate

    @staticmethod
    def _attachment_summary(attachment: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": attachment["id"],
            "name": attachment.get("name"),
            "url": attachment.get("url"),
            "bytes": attachment.get("bytes"),
            "mime_type": attachment.get("mimeType"),
            "is_upload": attachment.get("isUpload", False),
            "date": attachment.get("date"),
            "edge_color": attachment.get("edgeColor"),
            "previews": attachment.get("previews", []),
        }

    @staticmethod
    def _card_summary(card: dict[str, Any]) -> dict[str, Any]:
        badges = card.get("badges", {})
        return {
            "id": card["id"],
            "short_link": card.get("shortLink"),
            "name": card["name"],
            "url": card.get("url"),
            "closed": card.get("closed", False),
            "description": card.get("desc", ""),
            "board_id": card.get("idBoard"),
            "list_id": card.get("idList"),
            "due": card.get("due"),
            "due_complete": card.get("dueComplete", False),
            "comments_count": badges.get("comments", 0),
            "labels": [
                {
                    "id": label["id"],
                    "name": label.get("name"),
                    "color": label.get("color"),
                }
                for label in card.get("labels", [])
            ],
        }
