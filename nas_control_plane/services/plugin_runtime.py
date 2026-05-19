"""Plugin-script-facing inventory and reporting services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from nas_control_plane.models import (
    AccountInventoryRecord,
    AmmoTargetRecord,
    CreatorInboxRecord,
    DailyActionStatRecord,
    PluginAutoDispatchRecord,
    PluginCampaignRecord,
)
from nas_control_plane.services.repositories import (
    AccountInventoryRepository,
    AmmoTargetRepository,
    CreatorInboxRepository,
    DailyActionStatRepository,
    PluginAutoDispatchRepository,
    PluginCampaignRepository,
)


class PluginRuntimeService:
    """Stores plugin-facing targets, account inventory, creator inbox, and daily action stats."""

    def __init__(
        self,
        *,
        creator_repository: CreatorInboxRepository | None = None,
        ammo_repository: AmmoTargetRepository | None = None,
        account_repository: AccountInventoryRepository | None = None,
        stat_repository: DailyActionStatRepository | None = None,
        campaign_repository: PluginCampaignRepository | None = None,
        auto_dispatch_repository: PluginAutoDispatchRepository | None = None,
        now_fn: Callable[[], datetime] | None = None,
        retention_days: int = 15,
    ) -> None:
        self._creator_repository = creator_repository
        self._ammo_repository = ammo_repository
        self._account_repository = account_repository
        self._stat_repository = stat_repository
        self._campaign_repository = campaign_repository
        self._auto_dispatch_repository = auto_dispatch_repository
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._retention_days = max(1, retention_days)
        self._creator_items = self._creator_repository.load_items() if self._creator_repository is not None else {}
        self._ammo_targets = self._ammo_repository.load_targets() if self._ammo_repository is not None else {}
        self._accounts = self._account_repository.load_accounts() if self._account_repository is not None else {}
        self._stats = self._stat_repository.load_stats() if self._stat_repository is not None else {}
        self._campaigns = self._campaign_repository.load_campaigns() if self._campaign_repository is not None else {}
        self._auto_dispatch_rules = (
            self._auto_dispatch_repository.load_rules() if self._auto_dispatch_repository is not None else {}
        )
        self.cleanup_expired_stats()

    def report_creator(
        self,
        *,
        creator_id: str,
        handle: str | None,
        source: str,
        terminal_id: str | None,
        profile_id: str | None,
        plugin_name: str | None,
        dedupe_key: str | None,
        raw_payload: dict[str, object],
    ) -> CreatorInboxRecord:
        """Receive one creator/blogger identifier from a plugin-facing interface."""

        for record in self._creator_items.values():
            if dedupe_key and record.dedupe_key == dedupe_key:
                return record

        now = self._now_fn()
        inbox_id = f"creator-{len(self._creator_items) + 1}"
        record = CreatorInboxRecord(
            inbox_id=inbox_id,
            creator_id=creator_id,
            handle=handle,
            source=source,
            terminal_id=terminal_id,
            profile_id=profile_id,
            plugin_name=plugin_name,
            dedupe_key=dedupe_key,
            raw_payload=dict(raw_payload),
            received_at=now,
        )
        self._creator_items[inbox_id] = record
        self._save_creators()
        return record

    def add_ammo_target(
        self,
        *,
        target_value: str,
        target_type: str,
        source: str,
        creator_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AmmoTargetRecord:
        """Store one distributable target for plugin work."""

        now = self._now_fn()
        target_id = f"ammo-{len(self._ammo_targets) + 1}"
        record = AmmoTargetRecord(
            target_id=target_id,
            target_value=target_value,
            target_type=target_type,
            source=source,
            creator_id=creator_id,
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        self._ammo_targets[target_id] = record
        self._save_ammo()
        return record

    def list_ammo_targets(self, *, status: str | None = None) -> list[AmmoTargetRecord]:
        """List ammo targets, optionally filtered by status."""

        items = list(self._ammo_targets.values())
        if status is None:
            return items
        return [item for item in items if item.status == status]

    def list_creator_items(self) -> list[CreatorInboxRecord]:
        """List creator inbox items in receive order."""

        return sorted(self._creator_items.values(), key=lambda item: (item.received_at, item.inbox_id))

    def register_account(
        self,
        *,
        account_id: str,
        profile_id: str,
        handle: str | None,
        terminal_id: str | None,
        plugin_name: str | None,
        capability_tags: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AccountInventoryRecord:
        """Register or update one account available for plugin dispatch."""

        now = self._now_fn()
        existing = self._accounts.get(account_id)
        if existing is None:
            record = AccountInventoryRecord(
                account_id=account_id,
                profile_id=profile_id,
                handle=handle,
                terminal_id=terminal_id,
                plugin_name=plugin_name,
                capability_tags=list(capability_tags or []),
                metadata=dict(metadata or {}),
                created_at=now,
                updated_at=now,
            )
        else:
            record = replace(
                existing,
                profile_id=profile_id,
                handle=handle,
                terminal_id=terminal_id,
                plugin_name=plugin_name,
                capability_tags=list(capability_tags or existing.capability_tags),
                metadata=dict(metadata or existing.metadata),
                updated_at=now,
            )
        self._accounts[account_id] = record
        self._save_accounts()
        return record

    def set_account_status(
        self,
        *,
        account_id: str,
        status: str,
        metadata: dict[str, object] | None = None,
    ) -> AccountInventoryRecord:
        """Update one account runtime availability state."""

        existing = self._accounts[account_id]
        now = self._now_fn()
        updated = replace(
            existing,
            status=status,
            metadata={
                **existing.metadata,
                **dict(metadata or {}),
            },
            updated_at=now,
        )
        self._accounts[account_id] = updated
        self._save_accounts()
        return updated

    def list_accounts(self, *, status: str | None = None) -> list[AccountInventoryRecord]:
        """List registered plugin-facing accounts."""

        items = list(self._accounts.values())
        if status is None:
            return items
        return [item for item in items if item.status == status]

    def get_account(self, account_id: str) -> AccountInventoryRecord:
        """Return one account by identifier."""

        return self._accounts[account_id]

    def claim_ammo_target(
        self,
        *,
        account_id: str,
        plugin_name: str | None,
        target_type: str | None = None,
        action_type: str | None = None,
        stat_date: str | None = None,
    ) -> AmmoTargetRecord | None:
        """Assign the next available ammo target to one account."""

        now = self._now_fn()
        account = self._accounts.get(account_id)
        if account is None:
            return None
        eligibility = self.evaluate_account_eligibility(
            account_id=account_id,
            plugin_name=plugin_name,
            action_type=action_type,
            stat_date=stat_date,
        )
        if not eligibility["eligible"]:
            return None
        for target in sorted(self._ammo_targets.values(), key=lambda item: (item.created_at, item.target_id)):
            if target.status != "available":
                continue
            if target_type is not None and target.target_type != target_type:
                continue
            campaign_id = str(target.metadata.get("campaign_id")) if target.metadata.get("campaign_id") is not None else None
            campaign = self._campaigns.get(campaign_id) if campaign_id is not None else None
            selected_copy = self._select_campaign_copy(campaign)
            updated = replace(
                target,
                status="assigned",
                assigned_account_id=account_id,
                assigned_terminal_id=account.terminal_id,
                assigned_at=now,
                updated_at=now,
                metadata={
                    **target.metadata,
                    "plugin_name": plugin_name,
                    "action_type": action_type,
                    "selected_copy": selected_copy,
                },
            )
            self._ammo_targets[target.target_id] = updated
            self._accounts[account_id] = replace(
                account,
                last_used_at=now,
                updated_at=now,
            )
            self._save_accounts()
            self._save_ammo()
            return updated
        return None

    def mark_ammo_consumed(self, *, target_id: str, task_id: str | None = None) -> AmmoTargetRecord:
        """Finalize one assigned ammo target after plugin action execution."""

        record = self._ammo_targets[target_id]
        now = self._now_fn()
        updated = replace(
            record,
            status="consumed",
            consumed_at=now,
            assigned_task_id=task_id or record.assigned_task_id,
            updated_at=now,
        )
        self._ammo_targets[target_id] = updated
        self._save_ammo()
        return updated

    def bind_ammo_target_to_task(self, *, target_id: str, task_id: str) -> AmmoTargetRecord:
        """Attach one assigned ammo target to the created NAS task."""

        record = self._ammo_targets[target_id]
        now = self._now_fn()
        updated = replace(
            record,
            assigned_task_id=task_id,
            updated_at=now,
        )
        self._ammo_targets[target_id] = updated
        self._save_ammo()
        return updated

    def get_ammo_target(self, target_id: str) -> AmmoTargetRecord:
        """Return one ammo target by identifier."""

        return self._ammo_targets[target_id]

    def release_ammo_target(
        self,
        *,
        target_id: str,
        reason: str | None = None,
    ) -> AmmoTargetRecord:
        """Return one previously assigned ammo target back to the available pool."""

        record = self._ammo_targets[target_id]
        now = self._now_fn()
        metadata = dict(record.metadata)
        if reason is not None:
            metadata["last_release_reason"] = reason
        updated = replace(
            record,
            status="available",
            assigned_account_id=None,
            assigned_terminal_id=None,
            assigned_task_id=None,
            assigned_at=None,
            updated_at=now,
            metadata=metadata,
        )
        self._ammo_targets[target_id] = updated
        self._save_ammo()
        return updated

    def sync_task_result_for_ammo(
        self,
        *,
        target_id: str,
        task_id: str,
        task_status: str,
        retryable: bool,
        final: bool,
        error_code: str | None = None,
    ) -> AmmoTargetRecord:
        """Project one NAS task outcome back into the ammo lifecycle."""

        record = self._ammo_targets[target_id]
        if record.assigned_task_id is not None and record.assigned_task_id != task_id:
            raise ValueError(f"ammo target bound to different task: {target_id}")

        if task_status == "completed":
            return self.mark_ammo_consumed(target_id=target_id, task_id=task_id)
        if final and not retryable:
            return self.release_ammo_target(
                target_id=target_id,
                reason=error_code or task_status,
            )

        now = self._now_fn()
        metadata = {
            **record.metadata,
            "last_task_status": task_status,
            "last_task_retryable": retryable,
            "last_task_final": final,
        }
        if error_code is not None:
            metadata["last_task_error_code"] = error_code
        updated = replace(
            record,
            assigned_task_id=task_id,
            updated_at=now,
            metadata=metadata,
        )
        self._ammo_targets[target_id] = updated
        self._save_ammo()
        return updated

    def record_daily_action(
        self,
        *,
        account_id: str | None,
        terminal_id: str | None,
        plugin_name: str | None,
        script_name: str,
        action_type: str,
        success: bool,
        metadata: dict[str, object] | None = None,
        stat_date: str | None = None,
    ) -> DailyActionStatRecord:
        """Aggregate one plugin-facing action event into the daily stat table."""

        now = self._now_fn()
        day = stat_date or now.astimezone(UTC).date().isoformat()
        stat_id = "|".join([day, account_id or "-", terminal_id or "-", plugin_name or "-", script_name, action_type])
        existing = self._stats.get(stat_id)
        if existing is None:
            existing = DailyActionStatRecord(
                stat_id=stat_id,
                stat_date=day,
                account_id=account_id,
                terminal_id=terminal_id,
                plugin_name=plugin_name,
                script_name=script_name,
                action_type=action_type,
            )
        updated = replace(
            existing,
            success_count=existing.success_count + (1 if success else 0),
            failure_count=existing.failure_count + (0 if success else 1),
            total_count=existing.total_count + 1,
            metadata={
                **existing.metadata,
                **dict(metadata or {}),
            },
            updated_at=now,
        )
        self._stats[stat_id] = updated
        self.cleanup_expired_stats()
        self._save_stats()
        return updated

    def upsert_campaign(
        self,
        *,
        campaign_id: str,
        plugin_name: str,
        script_name: str,
        action_type: str,
        copy_items: list[dict[str, object]] | None = None,
        status: str = "active",
        metadata: dict[str, object] | None = None,
    ) -> PluginCampaignRecord:
        """Create or update one plugin campaign/copy bundle."""

        now = self._now_fn()
        existing = self._campaigns.get(campaign_id)
        if existing is None:
            record = PluginCampaignRecord(
                campaign_id=campaign_id,
                plugin_name=plugin_name,
                script_name=script_name,
                action_type=action_type,
                status=status,
                copy_items=list(copy_items or []),
                metadata=dict(metadata or {}),
                created_at=now,
                updated_at=now,
            )
        else:
            record = replace(
                existing,
                plugin_name=plugin_name,
                script_name=script_name,
                action_type=action_type,
                status=status,
                copy_items=list(copy_items if copy_items is not None else existing.copy_items),
                metadata={
                    **existing.metadata,
                    **dict(metadata or {}),
                },
                updated_at=now,
            )
        self._campaigns[campaign_id] = record
        self._save_campaigns()
        return record

    def list_campaigns(
        self,
        *,
        plugin_name: str | None = None,
        status: str | None = None,
    ) -> list[PluginCampaignRecord]:
        """List plugin campaign bundles."""

        items = list(self._campaigns.values())
        if plugin_name is not None:
            items = [item for item in items if item.plugin_name == plugin_name]
        if status is not None:
            items = [item for item in items if item.status == status]
        return items

    def upsert_auto_dispatch_rule(
        self,
        *,
        rule_id: str,
        account_id: str,
        plugin_name: str,
        script_name: str,
        action_plan: list[dict[str, object]] | None = None,
        campaign_id: str | None = None,
        terminal_id: str | None = None,
        instance_id: str | None = None,
        target_type: str = "handle",
        status: str = "active",
        metadata: dict[str, object] | None = None,
    ) -> PluginAutoDispatchRecord:
        """Create or update one plugin auto-dispatch rule used by task pull."""

        now = self._now_fn()
        existing = self._auto_dispatch_rules.get(rule_id)
        if existing is None:
            record = PluginAutoDispatchRecord(
                rule_id=rule_id,
                account_id=account_id,
                plugin_name=plugin_name,
                script_name=script_name,
                action_plan=list(action_plan or []),
                campaign_id=campaign_id,
                terminal_id=terminal_id,
                instance_id=instance_id,
                target_type=target_type,
                status=status,
                metadata=dict(metadata or {}),
                created_at=now,
                updated_at=now,
            )
        else:
            record = replace(
                existing,
                account_id=account_id,
                plugin_name=plugin_name,
                script_name=script_name,
                action_plan=list(action_plan if action_plan is not None else existing.action_plan),
                campaign_id=campaign_id,
                terminal_id=terminal_id,
                instance_id=instance_id,
                target_type=target_type,
                status=status,
                metadata={
                    **existing.metadata,
                    **dict(metadata or {}),
                },
                updated_at=now,
            )
        self._auto_dispatch_rules[rule_id] = record
        self._save_auto_dispatch_rules()
        return record

    def list_auto_dispatch_rules(
        self,
        *,
        account_id: str | None = None,
        plugin_name: str | None = None,
        status: str | None = None,
    ) -> list[PluginAutoDispatchRecord]:
        """List plugin auto-dispatch rules for runtime pull."""

        items = list(self._auto_dispatch_rules.values())
        if account_id is not None:
            items = [item for item in items if item.account_id == account_id]
        if plugin_name is not None:
            items = [item for item in items if item.plugin_name == plugin_name]
        if status is not None:
            items = [item for item in items if item.status == status]
        return items

    def select_auto_dispatch_rule(
        self,
        *,
        account_id: str,
        plugin_name: str | None,
        script_name: str | None,
        terminal_id: str | None,
        instance_id: str | None,
    ) -> PluginAutoDispatchRecord | None:
        """Select one active auto-dispatch rule matching the current runtime."""

        rules = self.list_auto_dispatch_rules(account_id=account_id, plugin_name=plugin_name, status="active")
        for item in sorted(rules, key=lambda record: (record.updated_at, record.rule_id), reverse=True):
            if script_name is not None and item.script_name != script_name:
                continue
            if item.terminal_id is not None and terminal_id is not None and item.terminal_id != terminal_id:
                continue
            if item.instance_id is not None and instance_id is not None and item.instance_id != instance_id:
                continue
            return item
        return None

    def evaluate_account_eligibility(
        self,
        *,
        account_id: str,
        plugin_name: str | None,
        action_type: str | None,
        stat_date: str | None = None,
    ) -> dict[str, object]:
        """Evaluate whether one account may receive another plugin dispatch now."""

        account = self._accounts[account_id]
        now = self._now_fn()
        metadata = dict(account.metadata)
        if account.status != "available":
            return {"eligible": False, "reason": "account_unavailable"}

        if action_type is not None:
            blocked_actions = {str(item) for item in metadata.get("blocked_action_types", [])}
            if action_type in blocked_actions:
                return {"eligible": False, "reason": "action_blocked"}

        cooldown_until_raw = metadata.get("cooldown_until")
        if cooldown_until_raw:
            cooldown_until = _parse_runtime_datetime(cooldown_until_raw)
            if cooldown_until is not None and cooldown_until > now:
                return {
                    "eligible": False,
                    "reason": "account_cooldown",
                    "cooldown_until": cooldown_until.isoformat(),
                }

        action_cooldowns = metadata.get("action_cooldowns", {})
        if action_type is not None and isinstance(action_cooldowns, dict):
            cooldown_raw = action_cooldowns.get(action_type)
            if cooldown_raw:
                cooldown_until = _parse_runtime_datetime(cooldown_raw)
                if cooldown_until is not None and cooldown_until > now:
                    return {
                        "eligible": False,
                        "reason": "action_cooldown",
                        "cooldown_until": cooldown_until.isoformat(),
                    }

        if action_type is not None:
            day = stat_date or now.astimezone(UTC).date().isoformat()
            daily_limit = _coerce_int(metadata.get("daily_action_limits", {}).get(action_type) if isinstance(metadata.get("daily_action_limits"), dict) else None)
            if daily_limit is not None:
                total = self.daily_action_total_for_account(
                    account_id=account_id,
                    action_type=action_type,
                    plugin_name=plugin_name,
                    stat_date=day,
                )
                if total >= daily_limit:
                    return {
                        "eligible": False,
                        "reason": "daily_limit_reached",
                        "daily_limit": daily_limit,
                        "daily_total": total,
                    }

        return {"eligible": True, "reason": "ok"}

    def daily_action_total_for_account(
        self,
        *,
        account_id: str,
        action_type: str,
        plugin_name: str | None,
        stat_date: str,
    ) -> int:
        """Return the aggregated count for one account/action/day."""

        return sum(
            item.total_count
            for item in self._stats.values()
            if item.account_id == account_id
            and item.action_type == action_type
            and item.stat_date == stat_date
            and (plugin_name is None or item.plugin_name == plugin_name)
        )

    def list_daily_stats(self, *, stat_date: str | None = None) -> list[DailyActionStatRecord]:
        """List daily aggregated action rows."""

        items = list(self._stats.values())
        if stat_date is None:
            return items
        return [item for item in items if item.stat_date == stat_date]

    def cleanup_expired_stats(self) -> int:
        """Delete daily aggregated rows older than the retention window."""

        cutoff = self._cutoff_date()
        before = len(self._stats)
        self._stats = {
            stat_id: item
            for stat_id, item in self._stats.items()
            if _parse_iso_date(item.stat_date) >= cutoff
        }
        removed = before - len(self._stats)
        if removed:
            self._save_stats()
        return removed

    def ammo_summary(self) -> dict[str, int]:
        """Return a compact ammo library summary."""

        total = len(self._ammo_targets)
        available = sum(1 for item in self._ammo_targets.values() if item.status == "available")
        assigned = sum(1 for item in self._ammo_targets.values() if item.status == "assigned")
        consumed = sum(1 for item in self._ammo_targets.values() if item.status == "consumed")
        return {
            "total": total,
            "available": available,
            "assigned": assigned,
            "consumed": consumed,
        }

    def _cutoff_date(self) -> date:
        return self._now_fn().astimezone(UTC).date() - timedelta(days=self._retention_days - 1)

    def _save_creators(self) -> None:
        if self._creator_repository is not None:
            self._creator_repository.save_items(self._creator_items)

    def _save_ammo(self) -> None:
        if self._ammo_repository is not None:
            self._ammo_repository.save_targets(self._ammo_targets)

    def _save_accounts(self) -> None:
        if self._account_repository is not None:
            self._account_repository.save_accounts(self._accounts)

    def _save_stats(self) -> None:
        if self._stat_repository is not None:
            self._stat_repository.save_stats(self._stats)

    def _save_campaigns(self) -> None:
        if self._campaign_repository is not None:
            self._campaign_repository.save_campaigns(self._campaigns)

    def _save_auto_dispatch_rules(self) -> None:
        if self._auto_dispatch_repository is not None:
            self._auto_dispatch_repository.save_rules(self._auto_dispatch_rules)

    def _select_campaign_copy(self, campaign: PluginCampaignRecord | None) -> dict[str, object] | None:
        if campaign is None or campaign.status != "active" or not campaign.copy_items:
            return None
        return dict(campaign.copy_items[0])


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def _coerce_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_runtime_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
