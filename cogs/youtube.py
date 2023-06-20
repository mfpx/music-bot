import re
from typing import List
import youtube_dl
import discord
import asyncio
import glob
import os
import aiohttp
from exceptions import BadQueueObjectType
from os.path import exists
from discord.ext import commands
from discord.ext.commands import Context

from helpers import checks

"""
KNOWN ISSUES:
Sometimes the bot will fail with KeyError: 'QV' - youtube_dl bug (https://github.com/ytdl-org/youtube-dl/issues/32314)
"""

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn -v debug',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class QueueItem:
    def __init__(self, title: str, data_url: str, content_url: str = None) -> None:
        self.title = title
        self.data_url = data_url
        self.content_url = content_url

class Queue:
    def __init__(self) -> None:
        self.items = []

    def __check_object_instance(self, object, object_type):
        if not isinstance(object, object_type):
            raise BadQueueObjectType
        
    def __fix_queue_order(self) -> None:
        """
        Once a track is removed, the order will be messed up, so this fixes track_id ordering
        """
        for index, item in enumerate(self.items):
            item.track_id = index

    def add_to_queue(self, item: QueueItem) -> None:
        self.__check_object_instance(item, QueueItem)
        self.items.append(item)

    def remove_from_queue(self, index: int) -> None:
        del self.items[index]
        self.__fix_queue_order()

    def clear_queue(self) -> None:
        self.items.clear()

    def get_queue_item(self, index: int) -> QueueItem:
        return self.items[index]

    def get_queue(self) -> list:
        titles = []
        for index, item in enumerate(self.items):
            titles.append({'track_id': index, 'queueitem': item})

        return titles

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        ffmpeglog = open("ffmpeg.log", "w")
        if stream:
            before_opts = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        else:
            before_opts = ""
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options, stderr=ffmpeglog, before_options=before_opts), data=data)

class Music(commands.Cog, name="music"):
    def __init__(self, bot):
        self.bot = bot
        self.queue = Queue()

    # TODO: This is a very dangerous command for production use! Disable before pushing to prod
    @commands.hybrid_command(
            name="repl",
            description="Python REPL"
    )
    @checks.is_owner()
    @checks.not_blacklisted()
    async def repl(self, ctx: Context, command: str):
        try:
            await ctx.send(eval(command))
        except Exception as ex:
            await ctx.send(ex)

    @commands.hybrid_command(
            name="join",
            description="Joins a voice channel"
    )
    @checks.not_blacklisted()
    async def join(self, ctx: Context, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.hybrid_command(
            name="dl_play",
            description="Plays from a url (almost anything youtube_dl supports)"
    )
    @checks.not_blacklisted()
    async def dl_play(self, ctx: Context, *, url):
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

        await ctx.send(f'Now playing: {player.title}')

    @commands.hybrid_command(
            name="add",
            description="Add song to queue"
    )
    @checks.not_blacklisted()
    async def add(self, ctx: Context, term: str):
        if not 'youtube.com' and not 'youtu.be' in term:
            if not 'https://' in term:
                term = await self.search(term)

        track_info = ytdl.extract_info(term, download = False)
        queue_item = QueueItem(track_info['title'], track_info['url'], track_info['webpage_url'])
        self.queue.add_to_queue(queue_item)

        await ctx.send(f'Added **{track_info["title"]}** to queue!\nThere are **{len(self.queue.get_queue())}** tracks in the queue.')

    @commands.hybrid_command(
            name="clearqueue",
            description="Clears all tracks from the queue"
    )
    @checks.not_blacklisted()
    async def clearqueue(self, ctx: Context):
         self.queue.clear_queue()

         await ctx.send("Cleared the queue.")

    @commands.hybrid_command(
            name="q",
            description="Shows the queue"
    )
    @checks.not_blacklisted()
    async def q(self, ctx: Context):
        string = f"There are **{len(self.queue.get_queue())}** tracks in queue.\n"
        for item in self.queue.get_queue():
            string += f"{item['track_id']}. {item['queueitem'].title}\n"

        await ctx.send(string)

    @commands.hybrid_command(
            name="rmtrack",
            description="Removes a song from queue using its queue number"
    )
    @checks.not_blacklisted()
    async def rmtrack(self, ctx: Context, id: int):
        """
        Using index -1 will remove from end of list\n
        So we use this to set `id` to 1
        """
        if id - 1 == -1:
            id = 1

        try:    
            await ctx.send(f"Removed **{self.queue.get_queue_item(id-1).title}** from queue.")
            self.queue.remove_from_queue(id-1)
        except IndexError:
            await ctx.send(f"ID **{id}** doesn't exist in queue!")

    @commands.hybrid_command(
            name="playqueue",
            description="Plays songs from the queue"
    )
    @checks.not_blacklisted()
    async def playqueue(self, ctx: Context, responded = False):
        if len(self.queue.get_queue()) > 0:
            song = self.queue.get_queue()[0]
            player = await YTDLSource.from_url(song['queueitem'].content_url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

            if not responded:
                await ctx.send("Playing songs from the queue")

            # remove item from queue - pop() is misbehaving
            self.queue.remove_from_queue(0)

            while ctx.voice_client.is_playing():
                await asyncio.sleep(1)

            await self.playqueue(ctx, True)
        else:
            if not responded:
                await ctx.send("No songs in queue.")

    @commands.hybrid_command(
            name="skip",
            description="Skips the currently playing song"
    )
    @checks.not_blacklisted()
    async def skip(self, ctx: Context):
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await self.playqueue(ctx, True)
        else:
            await ctx.send("Nothing is playing")

    @commands.hybrid_command(
            name="play",
            description="Streams from a url (same as dl_play, but doesn't predownload)"
    )
    @checks.not_blacklisted()
    async def play(self, ctx: Context, *, term: str):
        if not 'youtube.com' and not 'youtu.be' in term:
            if not 'https://' in term:
                term = await self.search(term)

        async with ctx.typing():
            try:
                player = await YTDLSource.from_url(term, loop=self.bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

                await ctx.send(f'**Warning**: This can randomly lag, might or might not fix sometime\nNow playing: {player.title}')
            except Exception as ex:
                await ctx.send("Something went wrong!\nIf the issue persists, inform the developer")


    async def search(self, search: str):
        params = {"search_query": search}
        headers = {"User-Agent": "Mozilla/5.0"}

        async with aiohttp.ClientSession() as client:
            async with client.get(
                    "https://www.youtube.com/results",
                    params = params, # GET params
                    headers = headers # Requested headers, UA in this case
                ) as response:
                
                dom = await response.text()
        found = re.findall(r'\/watch\?v=([a-zA-Z0-9_-]{11})', dom)
        return f"https://youtu.be/{found[0]}"

    @commands.hybrid_command(
            name="ffmpeglog",
            description="Retrieves the ffmpeg log."
    )
    @checks.is_owner()
    @checks.not_blacklisted()
    async def ffmpeglog(self, ctx: Context):
        try:
            logfile = discord.File("ffmpeg.log")
            await ctx.send(file=logfile)
        except FileNotFoundError:
            await ctx.send("No log file exists")

    @commands.hybrid_command(
            name="volume",
            description="Changes the player's volume"
    )
    @checks.not_blacklisted()
    async def volume(self, ctx: Context, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.hybrid_command(
            name="stop",
            description="Stops and disconnects the bot from voice"
    )
    @checks.not_blacklisted()
    async def stop(self, ctx: Context):
        """Stops and disconnects the bot from voice"""

        await ctx.voice_client.disconnect()

    @commands.hybrid_command(
            name="purgecache",
            description="Removes the cached downloads from the local filesystem"
    )
    @checks.not_blacklisted()
    @checks.is_owner()
    async def purgecache(self, ctx: Context):
        file_present = False
        filelist = glob.glob("youtube-*")
        if not filelist:
            await ctx.send("Cache is empty, nothing to purge")
        else:
            for x in filelist:
                os.remove(x)
                if exists(x):
                    file_present = True
            
            if file_present == False:
                await ctx.send("Purged the cache successfully")
            else:
                await ctx.send("Failed to purge the cache")

    @dl_play.before_invoke
    @play.before_invoke
    @playqueue.before_invoke
    async def ensure_voice(self, ctx: Context):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()

async def setup(bot):
    await bot.add_cog(Music(bot))