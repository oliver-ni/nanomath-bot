import io
import re

import discord
from discord.ext import commands
from jishaku.functools import executor_function
from latex import build_pdf
from pdf2image import convert_from_bytes

TEX_BASE = (
    r"\documentclass[border=4pt,crop,varwidth=256pt]{{standalone}}"
    r"\usepackage{{xcolor}}"
    r"\usepackage{{amsmath}}"
    r"\pagecolor[HTML]{{36393e}}"
    r"\color{{white}}"
    r"\begin{{document}}"
    "{}"
    r"\end{{document}}"
)
IMAGE_HEIGHT = 50
IMAGE_PADDING = 15


class Misc(commands.Cog):
    """For problem of the day."""

    def __init__(self, bot):
        self.bot = bot

    @executor_function
    def tex_to_img(self, latex):
        latex = re.sub(r"\s+", " ", latex.strip())
        pdf = build_pdf(TEX_BASE.format(latex))
        im = convert_from_bytes(bytes(pdf), dpi=800, single_file=True)[0]
        im = im.convert("RGBA")
        width, height = im.size
        im = im.crop((1, 1, width - 1, height - 1))

        buffer = io.BytesIO()
        im.save(buffer, "PNG")
        buffer.seek(0)
        return buffer

    @commands.command(aliases=("latex",))
    async def tex(self, ctx, *, latex):
        """Render LaTeX to an image."""

        buffer = await self.tex_to_img(latex)
        await ctx.send(file=discord.File(buffer, filename="latex.png"))


def setup(bot):
    bot.add_cog(Misc(bot))
