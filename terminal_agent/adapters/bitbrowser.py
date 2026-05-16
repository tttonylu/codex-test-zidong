"""Minimal BitBrowser adapter for scanning local browser instances."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from terminal_agent.models import InstanceState


class BitBrowserClient:
    """Reads browser instance state from the local BitBrowser API."""

    def __init__(self, base_url: str = "http://127.0.0.1:54345") -> None:
        self._base_url = base_url.rstrip("/")

    def healthcheck(self) -> dict[str, Any]:
        """Check whether the BitBrowser local API is available."""

        return self._post_json("/health", {})

    def list_browsers(self, page: int = 0, page_size: int = 100) -> list[dict[str, Any]]:
        """Fetch one page of browser records from BitBrowser."""

        response = self._post_json("/browser/list", {"page": page, "pageSize": page_size})
        if not response.get("success", False):
            raise RuntimeError(f"BitBrowser request failed: {response.get('msg', 'unknown error')}")

        data = response.get("data", {})
        items = data.get("list", [])
        if not isinstance(items, list):
            raise RuntimeError("BitBrowser response did not contain a browser list")
        return items

    def scan_instances(self, page_size: int = 100, max_pages: int = 10) -> list[InstanceState]:
        """Scan browser pages and normalize them into terminal instance states."""

        states: list[InstanceState] = []
        for page in range(max_pages):
            items = self.list_browsers(page=page, page_size=page_size)
            if not items:
                break

            states.extend(self._browser_to_instance_state(item) for item in items)
            if len(items) < page_size:
                break

        return states

    def open_browser(self, browser_id: str, args: list[str] | None = None, queue: bool = True) -> dict[str, Any]:
        """Open one BitBrowser window."""

        response = self._post_json(
            "/browser/open",
            {
                "id": browser_id,
                "args": list(args or []),
                "queue": queue,
            },
        )
        if not response.get("success", False):
            raise RuntimeError(f"BitBrowser open failed: {response.get('msg', 'unknown error')}")
        return response

    def open_browser_for_url(self, browser_id: str, target_url: str, queue: bool = True) -> dict[str, Any]:
        """Open one browser directly against a target URL."""

        return self.open_browser(browser_id=browser_id, args=[target_url], queue=queue)

    def navigate(self, browser_id: str, target_url: str, queue: bool = True) -> dict[str, Any]:
        """Navigate a browser by opening it against the target URL."""

        return self.open_browser_for_url(browser_id=browser_id, target_url=target_url, queue=queue)

    def close_browser(self, browser_id: str) -> dict[str, Any]:
        """Close one BitBrowser window."""

        response = self._post_json("/browser/close", {"id": browser_id})
        if not response.get("success", False):
            raise RuntimeError(f"BitBrowser close failed: {response.get('msg', 'unknown error')}")
        return response

    def update_remark(self, browser_id: str, remark: str) -> dict[str, Any]:
        """Update one BitBrowser browser remark."""

        response = self._post_json("/browser/remark/update", {"remark": remark, "browserIds": [browser_id]})
        if not response.get("success", False):
            raise RuntimeError(f"BitBrowser remark update failed: {response.get('msg', 'unknown error')}")
        return response

    def annotate(self, browser_id: str, remark: str) -> dict[str, Any]:
        """Annotate a browser instance via its remark field."""

        return self.update_remark(browser_id=browser_id, remark=remark)

    def execute_action(self, browser_id: str, action: str, **params: Any) -> dict[str, Any]:
        """Execute one normalized high-level browser action."""

        if action == "navigate":
            return self.navigate(
                browser_id=browser_id,
                target_url=str(params["target_url"]),
                queue=bool(params.get("queue", True)),
            )
        if action == "annotate":
            return self.annotate(
                browser_id=browser_id,
                remark=str(params["remark"]),
            )
        if action == "close":
            return self.close_browser(browser_id=browser_id)
        raise ValueError(f"unsupported browser action: {action}")

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self._base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=5) as response:
                raw = response.read()
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"BitBrowser request failed: {exc.code} {raw}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"BitBrowser request failed: {exc.reason}") from exc

        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _browser_to_instance_state(self, item: dict[str, Any]) -> InstanceState:
        browser_id = str(item["id"])
        handle = _normalize_handle(item.get("remark"))
        profile_id = f"@{handle}#bitbrowser" if handle else browser_id

        return InstanceState(
            instance_id=browser_id,
            profile_id=profile_id,
            runtime_status=_map_browser_status(item.get("status")),
            handle=handle,
            window_id=browser_id,
            remark=item.get("remark"),
            metadata={
                "name": item.get("name"),
                "seq": item.get("seq"),
                "group_id": item.get("groupId"),
                "raw_status": item.get("status"),
            },
        )


def _map_browser_status(status: Any) -> str:
    if status == 1:
        return "running"
    if status == 0:
        return "idle"
    return "unknown"


def _normalize_handle(remark: Any) -> str | None:
    if remark is None:
        return None
    text = str(remark).strip()
    if not text:
        return None
    return text.lower().lstrip("@")
