# bot.py
import discord
from discord.ext import commands
from datetime import datetime
import os
import json
import logging
import re
import requests
import resources
from report import Report

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(
    filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter(
    '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'token.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    perspective_key = tokens['perspective']


class ModBot(discord.Client):

    def __init__(self, key):
        intents = discord.Intents.default()
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {}  # Map from guild to the mod channel id for that guild
        self.reports = {}  # Map from user IDs to the state of their report
        # Track the status of automatic flagging based on moderators' judgement
        self.automatic_flag_reports = {}
        self.mod_channel_messages = {}
        self.perspective_key = key
        self.tox_threshold = 0.5
        self.flirt_threshold = 0.7

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception(
                "Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from us
        if message.author.id == self.user.id:
            if message.guild and message.channel.name == f'group-{self.group_num}-mod':
                self.mod_channel_messages[message.id] = message
            return

        # Check if this message was sent in a server ("guild") or if it's a DM

        if message.guild:
            if message.channel.name == f'group-{self.group_num}':
                await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply = "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle this message; forward all the messages it returns to uss
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            self.reports.pop(author_id)

        # handel message submision from the dm channel
        if self.reports[author_id].report_submitted():
            CID = 802408308471496744
            channel = client.get_channel(CID)
            await channel.send(f'**Suspected message:**\n**Suspected abuser:** {Report.reported_message.author.name} \n**Message ID:**__`#{Report.reported_message.id}#`__ **Message Content:** `{Report.reported_message.content}`'+'\n' +
                               '**Message report type:**`{Report.type}`' + '\n'+'Please use one of the following reactions:' +
                               '\n\n'+resources.DEL_MSG_EMOJI+' `Delete` the reported message'
                               + '\n\n'+resources.BAN_USER_EMOJI+' `Ban` the reported user'
                               + '\n\n'+resources.REPORT_AND_BAN_EMOJI +
                               ' `Ban` the reported user and `Escalate` this incident to local authorities'
                               + '\n\n'+resources.RESOLVED_NO_ACTION +
                               ' Mark this report as `Resolved` with no further actions'
                               + '\n\n'+'Select any other reaction to mark the report as false alarm')

        # Forward and flag POTENTIAL_CHILD_SOLICITATION reports
        if self.reports[author_id].child_solicitation():
            CID = 802408308471496744
            channel = client.get_channel(CID)
            await channel.send(f'🚨🚨🚨🚨🚨🚨🚨🚨🚨\n'+'🚨🚨   **High Priority**   🚨🚨\n'+'🚨🚨🚨🚨🚨🚨🚨🚨🚨\n\n\n' + '**POTENTIAL_CHILD_SOLICITATION**\n\n'
                               '**Suspected message:**\n**Suspected abuser:** {Report.reported_message.author.name} \n**Message ID:**__`#{Report.reported_message.id}#`__ **Message Content:** `{Report.reported_message.content}`'+'\n' +
                               '**Message report type:**`{Report.type}`' + '\n'+'Please use one of the following reactions:' +
                               '\n\n'+resources.DEL_MSG_EMOJI+' `Delete` the reported message'
                               + '\n\n'+resources.BAN_USER_EMOJI+' `Ban` the reported user'
                               + '\n\n'+resources.REPORT_AND_BAN_EMOJI +
                               ' `Ban` the reported user and `Escalate` this incident to local authorities'
                               + '\n\n'+resources.RESOLVED_NO_ACTION +
                               ' Mark this report as `Resolved` with no further actions'
                               + '\n\n'+'Select any other reaction to mark the report as false alarm')

    async def handle_channel_message(self, message):
        # Forward the message to the mod channel
        mod_channel = self.mod_channels[message.guild.id]
        scores = self.eval_text(message)

        tmp = [scores[k] for k in scores if k != 'FLIRTATION']
        if max(tmp) > self.tox_threshold or scores['FLIRTATION'] > self.flirt_threshold:
            self.automatic_flag_reports[message.id] = message
            await mod_channel.send(f'**Suspected message:**\n**Suspected abuser:** {message.author.name} \n**Message ID:**__`#{message.id}#`__ **Message Content:** `{message.content}`'+'\n' +
                                   '**Message Suspicion Score:**\n'+self.code_format(json.dumps(
                                       scores, indent=2))+'\n'+'Please use one of the following reactions:'+'\n\n'+resources.DEL_MSG_EMOJI+' `Delete` the reported message'
                                   + '\n\n'+resources.BAN_USER_EMOJI+' `Ban` the reported user'
                                   + '\n\n'+resources.REPORT_AND_BAN_EMOJI +
                                   ' `Ban` the reported user and `Escalate` this incident to local authorities'
                                   + '\n\n'+resources.RESOLVED_NO_ACTION +
                                   ' Mark this report as `Resolved` with no further actions'
                                   + '\n\n'+'Select any other reaction to mark the report as false alarm')

    async def on_raw_reaction_add(self, payload):
        '''
        Handles the moderator's action to an automatically flagged message based on an emoji
        '''
        if payload.guild_id and payload.channel_id == self.mod_channels[payload.guild_id].id and payload.event_type == 'REACTION_ADD':
            message = self.mod_channel_messages.pop(payload.message_id)
            main_channel_message_id = message.content.split(':')[
                3].split('#')[1]
            try:
                main_channel_message = self.automatic_flag_reports.pop(
                    int(main_channel_message_id))
            except:
                print("This message has already been handled!")
                return
            if payload.emoji.name == resources.DEL_MSG_EMOJI:
                # Simulate delete
                await self.mod_channels[payload.guild_id].send(f'**Deleted** the following message:\n\n**From:** `{main_channel_message.author.name}`  **Message ID:**__`#{message.id}#`__   **Message Content:** : "`{main_channel_message.content}`" \n**At** `{datetime.now()}`')
            elif payload.emoji.name == resources.BAN_USER_EMOJI:
                # Simulate shadow ban
                await self.mod_channels[payload.guild_id].send(f'**Shadow Banning** the user:\n`{main_channel_message.author.name}` for sending **Message ID:**__`#{message.id}#`__   **Message Content:** : "`{main_channel_message.content}`" \n**At** `{datetime.now()}`')
            elif payload.emoji.name == resources.REPORT_AND_BAN_EMOJI:
                # Simulate baning a user and sending the report to authorities
                await self.mod_channels[payload.guild_id].send(f'`{main_channel_message.author.name}` is **Banded** for sending : **Message ID:**__`#{message.id}#`__   **Message Content:** : "`{main_channel_message.content}`" \n**At** `{datetime.now()}` this report has been shared with local authorities.')
            elif payload.emoji.name == resources.RESOLVED_NO_ACTION:
                # Simulate Resolved with no action.
                await self.mod_channels[payload.guild_id].send(f'\nThis report has been marked as **Resolved** with no further actions.')
            else:
                # False positive case
                await self.mod_channels[payload.guild_id].send(f'This was a false positive:\n`{main_channel_message.author.name}`  {payload.emoji.name}  Sent **Message ID:**__`#{message.id}#`__   **Message Content:** : "`{main_channel_message.content}`" \n**At** `{datetime.now()}`')

    async def on_raw_message_edit(self, payload):
        '''
        Handle edited messages in the main channel
        '''
        if 'guild_id' in payload.data and payload.data['channel_id'] != self.mod_channels[int(payload.data['guild_id'])].id:
            guild = self.get_guild(int(payload.data['guild_id']))
            channel = guild.get_channel(int(payload.channel_id))
            message = await channel.fetch_message(int(payload.message_id))
            await self.handle_channel_message(message)

    def eval_text(self, message):
        '''
        Given a message, forwards the message to Perspective and returns a dictionary of scores.
        '''
        PERSPECTIVE_URL = 'https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze'

        url = PERSPECTIVE_URL + '?key=' + self.perspective_key
        data_dict = {
            'comment': {'text': message.content},
            # 'languages': ['en'],
            'requestedAttributes': {
                'SEVERE_TOXICITY': {}, 'PROFANITY': {},
                'IDENTITY_ATTACK': {}, 'THREAT': {},
                'TOXICITY': {}, 'FLIRTATION': {}
            },
            'doNotStore': True
        }
        response = requests.post(url, data=json.dumps(data_dict))
        response_dict = response.json()

        scores = {}
        for attr in response_dict["attributeScores"]:
            scores[attr] = response_dict["attributeScores"][attr]["summaryScore"]["value"]

        return scores

    def code_format(self, text):
        return "```" + text + "```"


client = ModBot(perspective_key)
client.run(discord_token)
