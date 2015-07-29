# -*- coding: utf-8 -*-
import websocket
import json
import sys
import threading
import datetime
import logging
import os
import requests

from slackclient import SlackClient
from tendo import singleton

### gloabl settings ###
API_TOKEN = 'xoxb-6950292614-IVcIom9YwCqoLdqlCks8LPU6'
MAX_CONCURRENT_THREADS = 50
LOGOUT_COMMAND = 'log off now!'
#LOGOUT_USER = 'U06T9VAMC'
LOGOUT_USER = None
logfile = 'tastemakerbotlog_' +  datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S') + '.log'
logfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), logfile)
REC_ENGINE_API = 'http://localhost:8000/recs/'
LOG_LEVEL = logging.DEBUG
### end global settings ###

### logging ###
logging.basicConfig(
    filename=logfile,
    format='%(asctime)s %(thread)d %(levelname)s: %(message)s',
    level=LOG_LEVEL
)
### end logging ###

### bot class ###
class TasteMakerBot:

    user_map = {}

    help_message = 'Hola! I am the Gracenote Tastemaker Bot. I understand 2 commands:\n\n' \
                    '\t*dime* to get a recommendation\n' \
                    '\t*ten* to add a recommendation\n'

    bad_language_message = 'Que patán! No need for profanity.'
    bad_language = ['fuck', 'shit', 'bitch', 'ass', 'slut', 'cunt', 'dick', 'whore']

    def __init__(self, slack_client):
        self.userid = ''
        self.user_convo_map = {}
        self.user_convo_locks = {}
        self.slack_client = slack_client
        self.logoff_flag = False
        self.new_convo_lock = threading.Lock()

    def sign_on(self):
        response = self.slack_client.api_call('rtm.start')
        response = json.loads(response)

        if self._api_response_success(response):
            self.userid = response['self']['id']
            url = response['url']
            logging.info('Bot signed on: user id = %s' % self.userid)
            logging.info('Connected to websocket %s' % url)

            ### connect web socket ###
            ws = websocket.WebSocketApp(
                    url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )

            logging.info('Successfully connected websocket')
            ws.run_forever()
        else:
            logging.info('Sign on failed: error returned from slack.rtm.start!')

    def _api_response_success(self, response):

        if 'ok' not in response:
            return False

        return response['ok']

    ### websocket event handlers ###

    ### just create new thread to handle event ###
    def _on_message(self, ws, message):

        try:

            ### have to exit from main thread ###
            if self.logoff_flag:
                sys.exit()

            if threading.active_count() >= MAX_CONCURRENT_THREADS:
                t = threading.Thread(target=self._send_busy_message, args=(ws, message))
                t.start()
                return

            t = threading.Thread(target=self._handle_message, args=(ws, message))
            t.start()

        except Exception as e:
            logging.info('Error in message handler: %s' % str(e))

    def _on_error(self, ws, error):
        logging.info('Error from websocket: %s', error)

    def _on_close(self, ws):
        logging.info('Websocket closed!')
    ### end websocket event handlers ###

    def _handle_message(self, ws, message):
        try:
            message_data = json.loads(message)

            if not self._is_direct_text_message(message_data):
                return

            ### make sure not a message to self ###
            userid = message_data['user']
            if userid == self.userid:
                return

            logging.debug('Received message from userid %s: %s', userid, message_data['text'])

            self._check_for_logoff(message_data, userid)
            if self.logoff_flag:
                return

            if 'text' not in message_data:
                return

            username = self._get_username(userid)
            if username is None:
                return

            ### acquire user convo lock ###
            acquired = self._acquire_user_convo_lock(userid)
            
            ### if not acquired, then we are currently processing another message form this user
            ### bot can only respond to one message at a time per user
            if not acquired:
                return

            ### here is where message handling happens ###
            response_messages = [TasteMakerBot.help_message]
            try:
                message = message_data['text']

                if message.lower().startswith('dime') or message.lower().startswith('ten'):
                    self._start_convo(userid, username, message)
                    response_messages = self.user_convo_map[userid].messages
                elif message.lower() in ['help', 'hi', 'hello', 'hey', 'hola']:
                    response_messages = [TasteMakerBot.help_message]
                elif userid in self.user_convo_map:
                    convo = self.user_convo_map[userid]

                    if convo.waiting:
                        convo.load_next_message(message)
                        response_messages = convo.messages
                    elif self._has_bad_language(message):
                        response_messages = [TasteMakerBot.bad_language_message]

                    ### convo is done ###
                    if not convo.waiting:
                        del self.user_convo_map[userid]
                elif self._has_bad_language(message):
                    response_messages = [TasteMakerBot.bad_language_message]

            finally:
                self._release_user_convo_lock(userid)

            for response_message in response_messages:
                self.slack_client.api_call('chat.postMessage', 
                        channel=message_data['channel'],
                        text=response_message,
                        unfurl_media=True,
                        unfurl_links=True,
                        as_user=True,
                        link_names=1
                    )

        except Exception as e:
            logging.info('Error in handle message: %s' % str(e))

    def _start_convo(self, userid, username, message):
        convo = BotConversation(username, message)
        self.user_convo_map[userid] = convo

    def _release_user_convo_lock(self, userid):
        if userid in self.user_convo_locks:
            self.user_convo_locks[userid].release()

    def _acquire_user_convo_lock(self, userid):
        acquired = False

        ### add lock for new user ###        
        if userid not in self.user_convo_locks:
            ### block waiting for lock
            self.new_convo_lock.acquire(True)
            try:
                ### have to check again now that we have lock ###
                if userid not in self.user_convo_locks:
                    self.user_convo_locks[userid] = threading.Lock()
            finally:
                self.new_convo_lock.release()

        ### don't block waiting for lock ###
        acquired = self.user_convo_locks[userid].acquire(False)
        
        return acquired

    def _send_busy_message(self, ws, message):
        try:
            message_data = json.loads(message)

            if not self._is_direct_text_message(message_data):
                return

            self._check_for_logoff(message_data)
            if self.logoff_flag:
                return

            userid = message_data['user']
            if userid == self.userid:
                return

            self.slack_client.api_call('chat.postMessage', 
                    channel=message_data['channel'],
                    text='Sorry, I am too busy at the moment. Try again later!',
                    as_user=True
                )

        except Exception as e:
            logging.info('Error in send busy message: %s' % str(e))


    def _is_direct_text_message(self, message_data):
        if (
                'type' in message_data and message_data['type'] == 'message' and
                'channel' in message_data and message_data['channel'].upper().startswith('D')
            ):
            return True
            
        return False

    def _check_for_logoff(self, message_data, userid):
        if LOGOUT_USER is not None:
            if message_data['text'] == LOGOUT_COMMAND and userid == LOGOUT_USER:
                self.logoff_flag = True
        else:
            if message_data['text'] == LOGOUT_COMMAND:
                self.logoff_flag = True

    def _get_username(self, userid):
        if userid in TasteMakerBot.user_map:
            return TasteMakerBot.user_map[userid]

        response = self.slack_client.api_call('users.info', user=userid)
        response = json.loads(response)
        if self._api_response_success(response):
            username = response['user']['name']
            TasteMakerBot.user_map[userid] = username
            return username

        return None

    def _has_bad_language(self, message):
        message_low = message.lower()
        for word in TasteMakerBot.bad_language:
            if word in message_low:
                return True
        return False

### end bot class ###

### recommendation engine class ###
class RecEngine:

    def get_rec(self, username, from_username=None):
        url = REC_ENGINE_API + 'dime/'

        data = {'username' : username}

        if from_username is not None:
            data['recommendation_from'] = from_username

        r = requests.post(url, data=json.dumps(data))
        print r.text
        result = json.loads(r.text)

        if result['status'] != 'ok':
            return False, result['error_id'], result['error_message']

        return (
                True,
                result['recommendation_id'],
                result['recommendation_link'],
                result['recommendation_desc'],
                result['recommendation_from'],
                result['likes'],
                result['dislikes']
            )

    def add_rec(self, username, link, description=''):
        url = REC_ENGINE_API + 'ten/'

        data = {
            'username' : username,
            'link' : link,
            'desc' : description
        }

        r  = requests.post(url, data=json.dumps(data))
        print r.text
        result = json.loads(r.text)
        if result['status'] != 'ok':
            return False, result['error_id'], result['error_message']

        return True, result['recommendation_id']

    def add_like_dislike(self, username, recommendation_id, like):
        url = REC_ENGINE_API + 'like/'

        data = {
            'username' : username,
            'recommendation_id' : recommendation_id,
            'like' : like
        }

        r = requests.post(url, data=json.dumps(data))
        print r.text
        result = json.loads(r.text)
        if result['status'] != 'ok':
            return False, result['error_id'], result['error_message']

        return True,

### convo class ###
class BotConversation:
    DIME = 0
    TEN = 1

    convo_map = {
        DIME : [
                    'Tell me what you think. Do you like that recommendation? (y/n)',
                    'Got it. Thanks!',
                    'Chutas! I was unable to get a recommendation for you :(',
                    'Hey! You cannot like or dislike your own recommendation.',
                    'Chutas! That didn\'t work :('
                ],
        TEN : [
                    'Alright! Send me a link to your recommendation.',
                    'Are you sure that link is correct? (y/n)',
                    'Do you want to add a description? (y/n)',
                    'Cool, send me your description. It cannot have more than 512 characters.',
                    'That was too many characters. Try limiting to 512 characters.',
                    'Ijoles, that is a popular one. I already have that recommendation.',
                    'Your recommendation has been added.\n' \
                        'Want to make this project even cooler? Tell us if your pick is in the Rhythm catalog here: ',
                    'Chutas! I was unable to add that recommendation :(',
                    'That link is too long. Try something less than 256 characters.'
                ]
    }

    def __init__(self, username, message):
        
        self.username = username
        self.waiting = False
        self.timestamp = datetime.datetime.utcnow()
        self.convo_index = 0
        self.messages = []
        self.rec_engine = RecEngine()
        self.rec_id = -1
        self.rec_link = ''
        self.rec_desc = ''

        message_low = message.lower()
        if message_low.startswith('ten'):
            self.convo_key = BotConversation.TEN
        else:
            self.convo_key = BotConversation.DIME

        self.load_next_message(message)

    ### need to refactor this part ###
    def load_next_message(self, response):

        response_low = response.lower()

        if self.convo_key == BotConversation.DIME:

            ### get recommendation ###
            if self.convo_index == 0:

                rec_username = None
                message_data = response.split(' ')
                if len(message_data) > 1:
                    rec_username = message_data[1]

                result = self.rec_engine.get_rec(self.username, rec_username)

                ### success ###
                if result[0]:
                    self.rec_id = result[1]
                    self.messages = ['Check out this recommendation from @%s:' % result[4]]

                    ### add description ###
                    if len(result[3]) > 0:
                        self.messages[0] += '\n\n"%s"' % result[3]

                    self.messages[0] += '\n%s' % result[2]
                    self.messages.append(BotConversation.convo_map[self.convo_key][0])
                    self.convo_index += 1
                    self.waiting = True
                ### failed getting rec ###
                else:
                    self.messages = [BotConversation.convo_map[self.convo_key][2]]
                    self.waiting = False

            ### like/dislike recommendation####
            elif self.convo_index == 1:
                like = None
                if response_low.startswith('y'):
                    like = True
                elif response_low.startswith('n'):
                    like = False
                
                if like is not None:
                    result = self.rec_engine.add_like_dislike(self.username, self.rec_id, like)
                    if result[0]:
                        self.messages = [BotConversation.convo_map[self.convo_key][1]]
                    elif result[1] == 409:
                        self.messages = [BotConversation.convo_map[self.convo_key][3]]
                    else:
                        self.messages = [BotConversation.convo_map[self.convo_key][4]]
                    
                    self.waiting = False
                else:
                    self.messages = [BotConversation.convo_map[self.convo_key][0]]
                    self.waiting = True

        elif self.convo_key == BotConversation.TEN:
            ### ask for link ###
            if self.convo_index == 0:
                self.messages = [BotConversation.convo_map[self.convo_key][0]]
                self.convo_index = 1
                self.waiting = True

            ### ask if want to add description ###
            elif self.convo_index == 1:
                if len(response) > 255:
                    self.waiting = False
                    self.messages = [BotConversation.convo_map[8]]
                    self.convo_index = 0
                elif self._is_message_link(response):
                    self.rec_link = self._clean_link(response)
                    self.messages = [BotConversation.convo_map[self.convo_key][2]]
                    self.convo_index = 2
                    self.waiting = True
                else:
                    self.rec_link = self._clean_link(response)
                    self.messages = [BotConversation.convo_map[self.convo_key][1]]
                    self.convo_index = 3
                    self.waiting = True

            ### process y/n for description ###
            elif self.convo_index == 2:
                if response_low.startswith('y'):
                    self.messages = [BotConversation.convo_map[self.convo_key][3]]
                    self.convo_index = 4
                    self.waiting = True
                elif response_low.startswith('n'):
                    self.rec_desc = ''
                    self._add_rec()

            ### are you sure that's a link ###
            elif self.convo_index == 3:
                if response_low.startswith('y'):
                    self.messages = [BotConversation.convo_map[self.convo_key][2]]
                    self.convo_index = 2
                    self.waiting = True
                elif response_low.startswith('n'):
                    self.messages = [BotConversation.convo_map[self.convo_key][0]]
                    self.convo_index = 1
                    self.waiting = True

            ### process description ###
            elif self.convo_index == 4:
                if len(response) <= 512:
                    self.rec_desc = response
                    self._add_rec()
                else:
                    self.messages = [BotConversation.convo_map[self.convo_key][4]]
                    self.convo_index = 4
                    self.waiting = True

    def _clean_link(self, link):
        if link[0] == '<' and link[-1] == '>':
            return link[1:-1]
        return link

    def _add_rec(self):
        result = self.rec_engine.add_rec(self.username, self.rec_link, self.rec_desc)
        if result[0]:
            search_link = REC_ENGINE_API + 'tracksearch/' + str(result[1])
            self.messages = [BotConversation.convo_map[self.convo_key][6] + search_link]
            self.waiting = False
        elif result[1] == 409:  ### rec already exists ###
            self.messages = [BotConversation.convo_map[self.convo_key][5]]
            self.waiting = False
        else:
            self.messages = [BotConversation.convo_map[self.convo_key][7]]
            self.waiting = False

    def _is_message_link(self, message):
        ###slack does link detection, surrounds with <> ###
        return message[0] == '<' and message[-1] == '>'

### end convo class ###

if __name__ == '__main__':
    me = singleton.SingleInstance()     # will sys.exit(-1) if other instance is running
    slack_client = SlackClient(API_TOKEN)
    bot = TasteMakerBot(slack_client)

    bot.sign_on()