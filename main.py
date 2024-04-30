import asyncio
import discord
from discord.ext import commands
from GeoBot import Geo
import logging


logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='-', intents=intents)
TOKEN = "MTIxNjAxNjk3MTQ3MzA5MjYyOA.GfLrTG.S2QrYJiKDqkdDrbe79-DuLsNxYJgs_1_Iq6oRg"


async def main():
    await bot.add_cog(Geo(bot, logger))
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
