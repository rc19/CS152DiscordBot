from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    REPORT_COMPLETE = auto()
    POTENTIAL_CHILD_SOLICITATION = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    UNDERAGE_KEYWORD = "under"
    OVERAGE_KEYWORD = "over"
    BLOCK_KEYWORD = "block"
    DO_NOT_BLOCK_KEYWORD = "no block"

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
            reply =  "Thank you for starting the reporting process. "
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
            return ["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                    f"We are sorry to hear that you received a concerning message. In order to properly prioritize your message, will you \
                    let us know if you are under 18? Please respond \"{UNDERAGE_KEYWORD}\" or \"{OVERAGE_KEYWORD}\": "]
        
        if self.state == State.MESSAGE_IDENTIFIED:
            if message.content == UNDERAGE_KEYWORD:
                self.state = State.POTENTIAL_CHILD_SOLICITATION
                return [f"Thanks so much for letting us know. You are so brave! For your safety, we've prevented this user from contacting \
                        you again. {send_solicitation_resources()} "]
            else if message.content == OVERAGE_KEYWORD:
                self.state = State.REPORT_COMPLETE
                return [f"Thanks for letting us know! We will contact you when we have reviewed your case. In the meantime, would you like \
                to block the user from this conversation? Reply \"{BLOCK_KEYWORD}\" or \"{DO_NOT_BLOCK_KEYWORD}\":"]
            else:
                return [f"I'm sorry, I didn't get that. In order to properly prioritize your message, will you \
                        let us know if you are under 18? Please respond \"{UNDERAGE_KEYWORD}\" or \"{OVERAGE_KEYWORD}\": "]
        
        if self.state == State.POTENTIAL_CHILD_SOLICITATION:
            self.state = State.REPORT_COMPLETE
            return [f"Hey there! We detected some potentially dangerous content in your conversation. For your safety, we've prevented this \
                    user from contacting you again. {send_solicitation_resources()}"]          

        return []

    def send_solicitation_resources():
        return """
        Hey, just so you know, it is NOT your fault if you experienced something  
        uncomfortable or did something you think you maybe shouldn't have done. You're a kid and you're still learning. The fault is 
        ALWAYS on the adults. Here are some educational and emotional resources for you to look at in the meantime as we're reviewing your case. 
            https://www.missingkids.org/gethelpnow/csam-resources 
            https://www.pacer.org/cmh/
            https://childmind.org/
        """
        
    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    


    

