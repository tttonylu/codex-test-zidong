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

    def resolve_browser_id(self, identifier: str | None, *, allow_single_running_fallback: bool = False) -> str:
        """Resolve a BitBrowser browser identifier from true id or visible sequence number."""

        normalized = str(identifier or "").strip()
        if normalized:
            browser = self.find_browser(normalized)
            if browser is not None:
                return str(browser["id"])
            return normalized

        if allow_single_running_fallback:
            running = self.list_running_browsers()
            if len(running) == 1:
                return str(running[0]["id"])
        raise RuntimeError("BitBrowser browser id is missing")

    def find_browser(self, identifier: str) -> dict[str, Any] | None:
        """Find one browser by true id or sequence number."""

        target = str(identifier).strip()
        if not target:
            return None
        for item in self._iter_browser_items():
            if str(item.get("id")) == target:
                return item
            if str(item.get("seq")) == target:
                return item
        return None

    def list_running_browsers(self) -> list[dict[str, Any]]:
        """Return currently running BitBrowser records."""

        return [item for item in self._iter_browser_items() if item.get("status") == 1]

    def get_browser_pids(self, browser_ids: list[str]) -> dict[str, int]:
        """Batch query OS process IDs for browser instance ids."""
        if not browser_ids:
            return {}

        response = self._post_json("/browser/pids", {"ids": browser_ids})
        if not isinstance(response, dict):
            return {}

        data = response.get("data")
        if not isinstance(data, dict):
            return {}

        result: dict[str, int] = {}
        for browser_id, raw_pid in data.items():
            try:
                pid = int(raw_pid)
                if pid > 0:
                    result[str(browser_id)] = pid
            except (ValueError, TypeError):
                pass
        return result

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

    def update_window_name(self, browser_id: str, name: str) -> dict[str, Any]:
        """Update one BitBrowser visible window name."""

        payload = {"id": browser_id, "name": name}
        payload.update(self._browser_update_context(browser_id))
        response = self._post_json("/browser/update", payload)
        if not response.get("success", False):
            raise RuntimeError(f"BitBrowser name update failed: {response.get('msg', 'unknown error')}")
        return response

    def browser_detail(self, browser_id: str) -> dict[str, Any]:
        """Fetch one BitBrowser window detail payload."""

        response = self._post_json("/browser/detail", {"id": browser_id})
        if not response.get("success", False):
            raise RuntimeError(f"BitBrowser detail failed: {response.get('msg', 'unknown error')}")
        data = response.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("BitBrowser detail did not return an object")
        return data

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

    def _iter_browser_items(self, page_size: int = 100, max_pages: int = 10):
        for page in range(max_pages):
            items = self.list_browsers(page=page, page_size=page_size)
            if not items:
                break
            for item in items:
                yield item
            if len(items) < page_size:
                break

    def _browser_update_context(self, browser_id: str) -> dict[str, Any]:
        """Build the extra fields some BitBrowser versions require for /browser/update."""

        try:
            detail = self.browser_detail(browser_id)
        except RuntimeError:
            return {}
        context: dict[str, Any] = {}

        fingerprint = detail.get("browserFingerPrint")
        if not fingerprint:
            for key, value in detail.items():
                if "finger" in str(key).lower():
                    fingerprint = value
                    break
        if fingerprint:
            context["browserFingerPrint"] = fingerprint

        proxy_method = detail.get("proxyMethod")
        if proxy_method is not None:
            context["proxyMethod"] = proxy_method

        proxy_type = detail.get("proxyType")
        if proxy_type is not None:
            context["proxyType"] = proxy_type

        return context

    def _browser_to_instance_state(self, item: dict[str, Any]) -> InstanceState:
        browser_id = str(item["id"])
        handle = _normalize_handle(item.get("remark"))
        profile_id = f"@{handle}#bitbrowser" if handle else browser_id

        return InstanceState(
            instance_id=browser_id,
            profile_id=profile_id,
            runtime_status=_map_browser_status(item.get("status")),
            health_status="unknown",
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
