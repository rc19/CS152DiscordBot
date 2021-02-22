from enum import Enum, auto
from typing import Text
import discord
import re
import resources
from datetime import datetime


class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    REPORT_COMPLETE = auto()
    POTENTIAL_CHILD_SOLICITATION = auto()
    REPORT_SUBMITID = auto()


class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    reported_message = None
    reported_user = None
    type = None

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None

    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]

        if self.state == State.REPORT_START:
            reply = "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]

        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.MESSAGE_IDENTIFIED
            Report.reported_message = message
            Report.reported_user = message
            print(Report.reported_message)
            return ["I found this message: ", "```" + message.author.name + ": " + message.content + "```",
                    "If this is not the right message, type `cancel` and restart to reporting process.\n" +
                    "Otherwise, let me know which of the following abuse types this message is\n" +
                    '`' + resources.INTIMATE_KEYWORD + '`\n`' + resources.SELF_KEYWORD + '`\n`' +
                    resources.HATE_KEYWORD + '`\n`' + resources.VIOLENCE_KEYWORD + '`\n`' +
                    resources.SPAM_KEYWORD + '`\n`' + resources.OTHER_KEYWORD + '`']

        if self.state == State.MESSAGE_IDENTIFIED:
            if message.content == resources.INTIMATE_KEYWORD or message.content == resources.SELF_KEYWORD or message.content == resources.HATE_KEYWORD or message.content == resources.HATE_KEYWORD or message.content == resources.SELF_KEYWORD or message.content == resources.OTHER_KEYWORD:
                Report.type = message.content
                return [f"\nWe are sorry to hear that you received a concerning message. In order to properly prioritize your message, will you let us know if you are under the age of 18?\nPlease respond `{resources.UNDERAGE_KEYWORD}` or `{resources.OVERAGE_KEYWORD}` "]
            if message.content == resources.UNDERAGE_KEYWORD:
                self.state = State.POTENTIAL_CHILD_SOLICITATION
                return [f" Thanks so much for letting us know. **You are so brave!** For your safety, we've prevented this user from contacting you again.{self.send_solicitation_resources()}\n**Reported user:** `{message.author.name}` **Reported message:** `{message.content}` \n**At:**`{datetime.now()}` "]
            elif message.content == resources.OVERAGE_KEYWORD:
                return [f"Thanks for letting us know! We will contact you when we have reviewed your case. In the meantime, would you like to block the user from this conversation? Reply `{resources.BLOCK_KEYWORD}` or `{resources.DO_NOT_BLOCK_KEYWORD}`:"]
            elif message.content == resources.BLOCK_KEYWORD:
                self.state = State.REPORT_COMPLETE
                return [f"We have **Blocked** {message.author.name} and prevented the account from any future interactions.\nYour report is **Successfully submitted**\n**Reported user:** `{message.author.name}` **Reported message:** `{message.content}` \n**At:**`{datetime.now()}`"]
            elif message.content == resources.DO_NOT_BLOCK_KEYWORD:
                self.state = State.REPORT_SUBMITID
                return [f"Your report is **Successfully submitted**\n**Reported user:** `{message.author.name}` **Reported message:** `{message.content}` \n**At:**`{datetime.now()}`"]
            else:
                return [f"I'm sorry, I didn't get that. In order to properly prioritize your message, will you let us know if you are under 18? Please respond `{resources.UNDERAGE_KEYWORD}` or `{resources.OVERAGE_KEYWORD}`: "]

        if self.state == State.POTENTIAL_CHILD_SOLICITATION:
            return self.send_solicitation_resources()

        return []

    def send_solicitation_resources(self):
        text1 = """
    Hey, just so you know, it is NOT your fault if you experienced something uncomfortable or did something you think you maybe shouldn't have done.
    You're a kid and you're still learning. The fault is ALWAYS on the adults. 
    Here are some educational and emotional resources for you to look at in the meantime as we're reviewing your case. 
    https://www.missingkids.org/gethelpnow/csam-resources 
    https://www.pacer.org/cmh/
    https://childmind.org/
        """
        return text1

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE

    def report_submitted(self):
        return self.state == State.REPORT_SUBMITID

    def child_solicitation(self):
        return self.state == State.POTENTIAL_CHILD_SOLICITATION
