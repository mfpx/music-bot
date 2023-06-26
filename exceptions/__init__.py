""""
Copyright © Krypton 2019-2023 - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized discord bot in Python programming language.

Version: 5.5.0
"""

from discord.ext import commands


class UserBlacklisted(commands.CheckFailure):
    """
    Thrown when a user is attempting something, but is blacklisted.
    """

    def __init__(self, message="User is blacklisted!"):
        self.message = message
        super().__init__(self.message)


class UserNotOwner(commands.CheckFailure):
    """
    Thrown when a user is attempting something, but is not an owner of the bot.
    """

    def __init__(self, message="User is not an owner of the bot!"):
        self.message = message
        super().__init__(self.message)

class BadQueueObjectType(Exception):
    """
    Thrown when attempting to add something other than QueueItem to the Queue.
    """

    def __init__(self, message="Attempting to add the wrong type of object to the Queue!"):
        self.message = message
        super().__init__(self.message)

class AppInProdMode(Exception):
    """
    Thrown when the bot is configured for production, but attempting to run a developer function.
    """

    def __init__(self, message="Attempting to run a development function in a production environment!"):
        self.message = message
        super().__init__(self.message)
