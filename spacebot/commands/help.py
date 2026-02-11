from __future__ import annotations

from spacebot.commands import CommandContext, get_all_commands, register


@register("help", "List available commands", "!!help", public=True)
async def cmd_help(ctx: CommandContext) -> str:
    prefix = ctx.config.command_prefix
    lines = ["Spacebot Commands:", ""]
    for name, cmd in sorted(get_all_commands().items()):
        usage = cmd.usage.replace("!!", prefix)
        lines.append(f"  {usage} -- {cmd.description}")
    return "\n".join(lines)
