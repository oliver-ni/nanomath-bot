import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

POTD_ROLE_ID = 778892281675251712
POTD_CHANNEL_ID = 767164490587570187
CONGRATS_CHANNEL_ID = 779545713323147264


async def anext(iterator):
    async for item in iterator:
        return item
    else:
        return None


class POTD(commands.Cog):
    """For problem of the day."""

    def __init__(self, bot):
        self.bot = bot
        self.release_daily.start()

    @tasks.loop(hours=24)
    async def release_daily(self):
        await self.release_potd()

    @release_daily.before_loop
    async def _wait_release(self):
        now = datetime.utcnow()
        time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if time < now:
            time += timedelta(days=1)
        print(time)
        await discord.utils.sleep_until(time)

    async def ask_for(self, ctx, message):
        message = await ctx.send(message)
        response = await self.bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel == message.channel,
            timeout=60,
        )
        return response.content

    async def send_potd_end(self, potd):
        channel = self.bot.get_channel(POTD_CHANNEL_ID)
        lines = (
            f"**POTD #{potd['_id']}** is now over.",
            f"Answer: {potd['answer']}",
            f"Source: {potd['source']}",
        )
        await channel.send("\n".join(lines))

    async def send_potd(self, potd):
        channel = self.bot.get_channel(POTD_CHANNEL_ID)
        buffer = await self.bot.get_cog("Misc").tex_to_img(potd["problem"])
        await channel.send(
            f"<@&{POTD_ROLE_ID}> **{potd['release_date']:%B %-d, %Y}: POTD #{potd['_id']}**",
            file=discord.File(buffer, filename="potd.png"),
            allowed_mentions=discord.AllowedMentions.all(),
        )
        await channel.send(
            "Please DM answers to me. You can also type **$potd** to view the POTD."
        )

    async def solve_potd(self, potd, user):
        await self.bot.mongo.db.potd.update_one(
            {"_id": potd["_id"]}, {"$push": {"solved_users": user.id}}
        )
        channel = self.bot.get_channel(CONGRATS_CHANNEL_ID)
        await channel.send(
            f"Congratulations {user.mention} on solving POTD #{potd['_id']}!",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    def get_current_potd(self, users=False):
        args = [{"ongoing": True}]
        if not users:
            args.append({"solved_users": 0})
        return anext(self.bot.mongo.db.potd.find(*args))

    async def end_current_potd(self):
        potd = await self.get_current_potd()
        if potd is None:
            return

        await self.bot.mongo.db.potd.update_one(
            {"_id": potd["_id"]}, {"$set": {"ongoing": False}}
        )
        await self.send_potd_end(potd)

    async def release_potd(self, id=None):
        await self.end_current_potd()

        query = {"release_date": None, "ongoing": False}
        if id is not None:
            query["_id"] = id
        potd = await anext(self.bot.mongo.db.potd.find(query).sort("_id", 1))
        if potd is None:
            return None

        async with await self.bot.mongo.client.start_session() as session:
            async with session.start_transaction():
                release_date = datetime.utcnow()
                await self.bot.mongo.db.potd.update_many(
                    {"ongoing": True},
                    {"$set": {"ongoing": False}},
                    session=session,
                )
                await self.bot.mongo.db.potd.update_one(
                    {"_id": potd["_id"]},
                    {"$set": {"release_date": release_date, "ongoing": True}},
                    session=session,
                )
                await self.send_potd({**potd, "release_date": release_date})
        return potd

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or message.guild is not None:
            return

        try:
            answer = int(message.content)
        except ValueError:
            return await message.channel.send(
                "That's not a valid answer! All answers are integers, unless otherwise specified."
            )

        potd = await self.get_current_potd(users=True)
        if potd is None:
            return await message.channel.send("There is no POTD active!")
        if message.author.id in potd["solved_users"]:
            return await message.channel.send(
                f"You have already solved POTD #{potd['_id']}."
            )

        if answer == potd["answer"]:
            await message.channel.send("Congratulations! That is the correct answer.")
            return await self.solve_potd(potd, message.author)
        await message.channel.send("Unfortunately, that is not the correct answer.")

    @commands.group(invoke_without_command=True)
    async def potd(self, ctx, id: int = None):
        """View a current or past problem of the day."""

        query = {"release_date": {"$ne": None}}
        if id is not None:
            query["_id"] = id
        else:
            query["ongoing"] = True

        potd = await anext(self.bot.mongo.db.potd.find(query).sort("_id", -1))
        if potd is None:
            return await ctx.send("Could not find POTD.")

        lines = [f"**POTD #{potd['_id']}, released {potd['release_date']:%B %-d, %Y}**"]
        if not potd["ongoing"]:
            lines.append(f"Answer: {potd['answer']}")
            lines.append(f"Source: {potd['source']}")
        buffer = await self.bot.get_cog("Misc").tex_to_img(potd["problem"])
        await ctx.send(
            "\n".join(lines),
            file=discord.File(buffer, filename="potd.png"),
        )

    @commands.is_owner()
    @potd.command()
    async def release(self, ctx, *, id: int = None):
        """Release the next POTD in the queue."""

        potd = await self.release_potd(id)
        if potd is None:
            return await ctx.send("Could not find a POTD to release.")

        return await ctx.send(f"Released POTD #{potd['_id']}.")

    @commands.is_owner()
    @potd.command()
    async def add(self, ctx, *, problem):
        """Add a POTD problem to the queue."""

        try:
            buffer = await self.bot.get_cog("Misc").tex_to_img(problem)
            await ctx.send(
                "Adding the following problem to the POTD queue.",
                file=discord.File(buffer, filename="potd.png"),
            )

            answer = await self.ask_for(
                ctx,
                "Please enter the answer as an integer, `proof` if proof-based, or anything else to abort the process.",
            )
            try:
                answer = int(answer)
            except ValueError:
                if answer.lower() == "proof":
                    answer = None
                else:
                    return await ctx.send("Aborting the POTD creation process.")

            source = await self.ask_for(
                ctx, "Lastly, please enter the source to credit for this problem."
            )

            potd = {
                "_id": await self.bot.mongo.reserve_id("potd"),
                "problem": problem,
                "answer": answer,
                "source": source,
                "release_date": None,
                "ongoing": False,
                "solved_users": [],
            }
            await self.bot.mongo.db.potd.insert_one(potd)

            await ctx.send("Added problem to the queue!")

        except asyncio.TimeoutError:
            return await ctx.send("Looks like you're not quite ready yet. Aborted.")


def setup(bot):
    bot.add_cog(POTD(bot))
