import requests
import json
import urllib
import datetime
import time
import bot_framework
import unicodedata

import xml.etree.ElementTree as ET
from dateutil.relativedelta import relativedelta

bot = None
strike_search_url = "https://getstrike.net/api/v2/torrents/search/?phrase="
CONFIG_FILE = 'config.xml'
client_url = 'http://127.0.0.1'
client_port = '8080'
timeout_for_params = 5
client_user = 'admin'
client_pass = 'password'
telegram_token = None
num_of_torrents = 8
torrent_emoji = [bot_framework.Bot.Emoji.DIGIT_ONE_PLUS_COMBINING_ENCLOSING_KEYCAP,
                 bot_framework.Bot.Emoji.DIGIT_TWO_PLUS_COMBINING_ENCLOSING_KEYCAP,
                 bot_framework.Bot.Emoji.DIGIT_THREE_PLUS_COMBINING_ENCLOSING_KEYCAP,
                 bot_framework.Bot.Emoji.DIGIT_FOUR_PLUS_COMBINING_ENCLOSING_KEYCAP,
                 bot_framework.Bot.Emoji.DIGIT_FIVE_PLUS_COMBINING_ENCLOSING_KEYCAP,
                 bot_framework.Bot.Emoji.DIGIT_SIX_PLUS_COMBINING_ENCLOSING_KEYCAP,
                 bot_framework.Bot.Emoji.DIGIT_SEVEN_PLUS_COMBINING_ENCLOSING_KEYCAP,
                 bot_framework.Bot.Emoji.DIGIT_EIGHT_PLUS_COMBINING_ENCLOSING_KEYCAP]


auth_telegram_users = []



'''
#example usage
response = requests.get('http://127.0.0.1:8080/query/torrents')
if not response.ok:
    response.raise_for_status()

for torrent in json.loads(response.content):
    if torrent['progress'] >= 0:
        print torrent['name']
'''

def strip_accents(s):
   return ''.join(c for c in unicodedata.normalize('NFD', s)
                  if unicodedata.category(c) != 'Mn')


def eta_fmt(seconds):
    if seconds <= 0:
        return '0'
    if seconds >= 8640000:
        return 'inf' #return u'\u221e'.encode('utf-8')
    delta = relativedelta(seconds=seconds)
    attrs = ['years', 'months', 'days', 'hours', 'minutes', 'seconds']
    times = ['%d %s' % (getattr(delta, attr), getattr(delta, attr) > 1 and attr or attr[:-1])
        for attr in attrs if getattr(delta, attr)]
    return times[0] + (', ' + times[1] if len(times) > 1 else '')

def sizeof_fmt(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)


def get_days_ago(date_string):
    print date_string
    if " " in date_string:
        parsed = time.strptime(date_string, '%b %d, %Y')
    else:
        return None

    dt = datetime.datetime.fromtimestamp(time.mktime(parsed))
    return (datetime.datetime.now() - dt).days


def parse_config_file():
    global client_url, client_port, client_user, client_pass, telegram_token
    tree = ET.parse(CONFIG_FILE)

    #client data
    client_data = tree.find('client_data');
    client_url = client_data.find('url').text
    client_port = client_data.find('port').text
    client_user = client_data.find('user').text
    client_pass = client_data.find('pass').text

    #telegram data
    telegram_token = tree.find('telegram_token').text
    for user_id in tree.iter('telegram_user_id'):
        auth_telegram_users.append(user_id.text)



def search_torrent(search_term):
    print search_term
    term = urllib.quote(search_term)
    response = requests.get(strike_search_url + term)

    if 'torrents' not in json.loads(response.content):
        return None
    return json.loads(response.content)['torrents'][:num_of_torrents]

def download_torrent(torrent_for_dl):
    response = requests.post('http://127.0.0.1:8080/command/download', {'urls': torrent_for_dl['magnet_uri']})
    if not response.ok:
        return False
    return True



def authenticate_user(message):
    if str(message.chat.id) in auth_telegram_users:
        return True
    else:
        bot.send_message(message.chat_id, ("Unauthorized user %s %s, user id: %s. Please edit bot configuration file using an authenticated account to change this." % (message.chat.first_name,
                                          message.chat.last_name, message.chat.id)))
        return False

def cmd_search_torrent(message, params_text):
    #authenticate user
    default_mu = bot_framework.Bot.create_markup()
    if not authenticate_user(message):
        return

    #check if params are legal
    if not params_text:
        bot.send_message(message.chat_id, "Please enter search term")
        param_msg, params = bot.wait_for_message(message.chat_id, timeout_for_params)
        if not params:
            bot.send_message(message.chat_id, "No search parameters received - aborting operation")
            return
    else:
        params = params_text



    #get best torrents
    best_torrents = search_torrent(params)
    if not best_torrents:
        bot.send_message(message.chat_id, "No torrents found for term - " + params, default_mu)
        return

    #print optionsX
    print_torrent_options(best_torrents, message.chat_id)
    #create markup and wait for answer
    keyboard = [[str((i + 1)) for i in range(len(best_torrents))] + [bot_framework.Bot.Emoji.CROSS_MARK]]
    print keyboard
    print len(best_torrents)
    markup = bot_framework.Bot.create_markup(keyboard)

    bot.send_message(message.chat_id, "Please choose torrent to download from list", markup)
    reply_msg, reply = bot.wait_for_message(message.chat_id, 20)

    markup = bot_framework.Bot.create_markup()

    #parse reply
    if not reply or int(reply) not in range(len(best_torrents)):
        bot.send_message(message.chat_id, "Operation aborted", markup)
        return

    chosen_torrent = best_torrents[int(reply) - 1]

    #download chosen torrent
    status = download_torrent(chosen_torrent)
    #post completion message
    if not status:
        bot.send_message(message.chat_id, "Download failed", markup)
    else:
        bot.send_message(message.chat_id, "Started torrent download - " + chosen_torrent['torrent_title'], markup)


def generate_torrent_message(torrent, index):
    days = get_days_ago(torrent['upload_date'])

    if 'torrent_title' not in torrent:
        return None
    else:
        title = strip_accents(torrent['torrent_title'])

    if not days:
       time_str = ""
    elif days < 1:
        time_str = "\nUpload time: Today"
    elif days == 1:
        time_str = "\nUpload time: Yesterday"
    else:
        time_str = "\nUpload time: " + str(days) + " days ago"

    if 'seeds' not in torrent:
        seeds_str = ""
    else:
        seeds_str = "\nSeeds: " + str(torrent['seeds'])

    if 'size' not in torrent:
        size_str = ""
    else:
        size_str = "\nSize: " + sizeof_fmt(int(torrent['size']))

    return torrent_emoji[index] + (": " + title + seeds_str + size_str + time_str).encode('UTF8')

def print_torrent_options(best_torrents, chat_id):
    for i in range(len(best_torrents)):
        message = generate_torrent_message(best_torrents[i], i)
        if message:
            bot.send_message(chat_id, message)

def cmd_torrent_status(message, param_text):
    if not authenticate_user(message):
        return

    include_complete = False
    list_entires = 50

    #handle secret params
    if param_text:
        # number - limit entry count
        try:
            list_entires = abs(int(param_text))
        except:
            pass

        # include complete torrents
        print param_text
        if param_text == 'complete':
            include_complete = True

    #get list
    response = requests.get(client_url + ':' + client_port + '/query/torrents')
    if not response.ok:
        response.raise_for_status()

    for torrent in json.loads(response.content):
        if torrent['progress'] < 1 or include_complete:
            torrent_list_entry = '%s - %s (%s) speed:%s eta:%s status:%s\n' % (torrent['name'], str(int(torrent['progress'] * 100)) + '%',
                                                                               (sizeof_fmt(torrent['size'] * torrent['progress']) + '/' + sizeof_fmt(torrent['size'])),
                                                                               sizeof_fmt(torrent['dlspeed'], 'B/s'), eta_fmt(int(torrent['eta'])), torrent['state'])
            #print list to user
            bot.send_message(message.chat_id, torrent_list_entry)





def cmd_pause_all_torrents(): #me
    pass

def cmd_resume_all_torrents(): #me
    pass


def main():
    global bot
    #parse config file
    parse_config_file()
    #setup bot commands
    bot = bot_framework.Bot(token = telegram_token)
    bot.add_command(cmd_name='/status', cmd_cb=cmd_torrent_status, cmd_description='Show a list of current torrents, use "/status <number>" to limit list size and "/status complete" to see finished torrents as well')
    bot.add_command(cmd_name='/search', cmd_cb=cmd_search_torrent, cmd_description='Search for specific torrent, use "/status <term>" to search immidiatly')
    #activate bot
    bot.activate()




'''
def callback(message, params):
    bot.send_message(chat_id=message.chat_id, message=bot.Emoji.DI)
    if not params:
        bot.send_message(chat_id=message.chat_id, message='wrong params %s, put in number - ' % message.chat.first_name)
        msg, params = bot.wait_for_message(chat_id=message.chat_id, timeout=10)

    if not params:
        params = 'none'
    print 'params - ', params
    bot.send_message(chat_id=message.chat_id, message='%s ? kthxbye' % params)
'''


if __name__ == "__main__":
    main()
