from discord.ext import commands

ROLES = {
    "\N{TRIANGULAR RULER}": 778892281675251712,
}
CHANNEL_ID = 779804644288757780


class Roles(commands.Cog):
    """For roles."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        if payload.channel_id != CHANNEL_ID:
            return

        emoji = (
            str(payload.emoji.id)
            if payload.emoji.is_custom_emoji()
            else payload.emoji.name
        )

        if emoji in ROLES:
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(ROLES[emoji])
            await guild.get_member(payload.user_id).add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        if payload.channel_id != CHANNEL_ID:
            return

        emoji = (
            str(payload.emoji.id)
            if payload.emoji.is_custom_emoji()
            else payload.emoji.name
        )

        if emoji in ROLES:
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(ROLES[emoji])
            await guild.get_member(payload.user_id).remove_roles(role)


def setup(bot):
    bot.add_cog(Roles(bot))
