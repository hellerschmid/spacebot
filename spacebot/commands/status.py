from __future__ import annotations

import time

from spacebot.commands import CommandContext, register


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {mins}m"
    days, hrs = divmod(hours, 24)
    return f"{days}d {hrs}h {mins}m"


@register("status", "Show bot status and statistics", "!!status", public=True)
async def cmd_status(ctx: CommandContext) -> str:
    uptime = _format_duration(time.time() - ctx.bot_state.startup_time)
    stats = await ctx.db.get_invite_stats()
    queue_size = ctx.bot_state.invite_queue.qsize()
    processing = len(ctx.bot_state.processing_users)
    sync_count = ctx.bot_state.sync_count

    lines = [
        "Spacebot Status",
        "",
        f"  Uptime: {uptime}",
        f"  Sync cycles: {sync_count}",
        f"  Queue: {queue_size} pending, {processing} processing",
        f"  Connected rooms: {len(ctx.client.rooms)}",
        "",
        "Invite Statistics",
        f"  Total: {stats.total}",
        f"  Invited: {stats.invited}",
        f"  Already joined: {stats.already_joined}",
        f"  Failed: {stats.failed}",
    ]
    return "\n".join(lines)
