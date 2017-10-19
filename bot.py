import flask
import telebot
import logging
import re
import django
import os
import requests
import bs4
from bs4 import BeautifulSoup
from random import randint
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from credentials import host, token, testtoken, local_port, MAINTAINER

os.environ.setdefault("DJANGO_MOBIBOT_SETTINGS_MODULE", "mobi.settings")
django.setup()

from mobi.settings import DEBUG
from mobibotweb.models import User, Chat

API_TOKEN = testtoken

WEBHOOK_HOST = host
WEBHOOK_PORT = local_port
WEBHOOK_URL_BASE = "https://%s" % (WEBHOOK_HOST)
WEBHOOK_URL_PATH = "/%s/" % (API_TOKEN)

app = flask.Flask(__name__)
bot = telebot.AsyncTeleBot(API_TOKEN)

mobibot_logger = logging.getLogger()
mobibot_logger.setLevel(logging.INFO)
handler = logging.FileHandler('mobibot.log', 'a', 'utf-8')
handler.setFormatter(logging.Formatter('%(levelname)-8s [%(asctime)s] %(message)s'))
mobibot_logger.addHandler(handler)

ASSISTANT = bot.get_me().wait()


# Empty webserver index, return nothing, just http 200
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return ''


# Process webhook calls
@app.route('/', methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)


def random_equation():
    num_a = randint(-15, 15)
    num_b = randint(-10, 10)
    answer = num_a + num_b
    fake_answer = randint(-25, 25)
    while fake_answer == answer:
        fake_answer = randint(-25, 25)
    return {'a': num_a, 'b': num_b, 'answer': answer, 'fake_answer': fake_answer}


def get_welcome_message(chat, user, chat_db=None):
    if chat_db and chat_db.welcome_message:
        return {'message': chat_db.welcome_message.format(USER_ID=user.id, FIRST_NAME=user.first_name, TITLE=chat.title,
                                                          VAR_A=chat_db.welcome_var_a,
                                                          VAR_B=chat_db.welcome_var_b),
                'VAR_A': chat_db.welcome_var_a,
                'VAR_B': chat_db.welcome_var_b}
    else:
        equation = random_equation()
        sample_welcome_message = 'Привет, <a href="tg://user?id={}">{}</a>! Добро пожаловать в <b>{}</b>.\n' \
                                 'Сколько будет {} + {}\n' \
                                 '<b>{VAR_A}</b> или <b>{VAR_B}</b>?'.format(user.id, user.first_name, chat.title,
                                                                             equation['a'], equation['b'],
                                                                             VAR_A=equation['answer'],
                                                                             VAR_B=equation['fake_answer'])
        return {'message': sample_welcome_message, 'VAR_A': equation['answer'], 'VAR_B': equation['fake_answer']}


def create_user(usr):
    user, created = User.objects.update_or_create(
        id=usr.id,
        first_name=usr.first_name,
        status=User.NEW
    )
    if usr.last_name:
        user.last_name = usr.last_name
    if usr.username:
        user.username = usr.username
    user.save()
    return user


def create_chat(chat_obj):
    chat, created = Chat.objects.update_or_create(
        id=chat_obj.id,
        title=chat_obj.title,
    )
    if chat_obj.username:
        chat.username = chat_obj.username
    chat.save()
    return chat


def is_legit(chat_id):
    return Chat.objects.filter(id=chat_id).first()


def get_chat(chat_obj):
    chat_db = Chat.objects.filter(id=chat_obj.id)
    if chat_db:
        return chat_db[0]
    else:
        return create_chat(chat_obj)


def get_user(usr):
    user = User.objects.filter(id=usr.id)
    if user:
        return user[0]
    else:
        return create_user(usr)


def update_user_info(usr):
    user = get_user(usr)
    changed = False
    if user.first_name != usr.first_name:
        user.first_name = usr.first_name
        changed = True
    if user.last_name != usr.last_name:
        user.last_name = usr.last_name
        changed = True
    if user.username != usr.username:
        user.username = usr.username
        changed = True
    if changed:
        user.save()


def strike(text):
    result = ''
    for c in text:
        result = result + c + '\u0336'
    return result


def under_line(text):
    result = ''
    for c in text:
        result = result + c + '\u0332'
    return result


def convert_markdown(text):
    text = text.replace(r'\r\n', '')
    soup = BeautifulSoup(text, "html.parser")
    max_length = 500
    links_length = 0
    for br in soup.find_all("br"):
        br.replace_with("\n")
    if soup.big:
        soup.big.string = soup.big.string.upper()
        soup.big.replace_with(soup.big.string)
    if soup.p:
        soup.p.replace_with('')
    if soup.a:
        replies = soup.find_all('a', {'class': 'post-reply-link'})
        links = [len(str(i)) for i in replies]
        for x in links:
            links_length = links_length + x
        for reply in replies:
            reply['href'] = 'https://2ch.hk' + reply['href']
    if soup.span:
        spoilers = soup.find_all('span', {'class': 'spoiler'})
        for spoiler in spoilers:
            try:
                max_length = max_length + len(spoiler.string)
            except:
                max_length = max_length + len(spoiler.text)
            spoiler.string = strike(spoiler.text)
            spoiler.replace_with(spoiler.string)
        greentexts = soup.find_all('span', {'class': 'unkfunc'})
        for greentext in greentexts:
            new_tag = soup.new_tag('i')
            new_tag.string = greentext.string
            greentext.replace_with(new_tag)
        underlines = soup.find_all('span', {'class': 'u'})
        for underline in underlines:
            try:
                max_length = max_length + len(underline.string)
            except:
                max_length = max_length + len(underline.text)
            underline.string = under_line(underline.text)
            underline.replace_with(underline.string)
        unsupported = soup.find_all('span')  # TODO: Support for <pan> names
        unsupported.extend(soup.find_all('em'))
        for tag in unsupported:
            tag.unwrap()
    if len(str(soup)) - links_length > max_length:
        while len(str(soup)) - links_length > max_length:
            if isinstance(soup.contents[-1], bs4.element.Tag):
                if len(str(soup)) - links_length - len(soup.contents[-1].text) > max_length:
                    soup.contents.pop()
                elif soup.contents[-1].name != 'a':
                    soup.contents[-1].string = (soup.contents[-1].text[
                                                :(max_length - (
                                                    len(str(soup)) - links_length - len(soup.contents[-1].text)))])
                else:
                    break
            else:
                if len(str(soup)) - links_length - len(soup.contents[-1].string) > max_length:
                    soup.contents.pop()
                else:
                    new_string = (soup.contents[-1].string[
                                  :(max_length - (len(str(soup)) - links_length - len(soup.contents[-1].string)))])
                    soup.contents[-1] = soup.new_string(new_string)
        return str(soup) + '<b> ...</b>'
    else:
        return str(soup)


def dvach_reveal(message):
    if message.entities is not None:
        for entity in message.entities:
            if entity.type == 'url':
                m = re.search('https://2ch\.(?:hk|pm)/([a-z]*)/res/([0-9]*)\.html#*($|[0-9]*)',
                              message.text[entity.offset:entity.offset + entity.length])
                if m:
                    output = ''
                    session = requests.session()
                    link = m.group(0)
                    board = m.group(1)
                    thread = m.group(2)
                    post = m.group(3)
                    if post and post != thread:
                        dvach_post = session.get('https://2ch.hk/makaba/mobile.fcgi',
                                                 data={'task': 'get_thread', 'board': board, 'thread': thread,
                                                       'num': post}).json()
                        if 'Error' in dvach_post:
                            output = '<b>Ошибка!</b> <i>{}</i>'.format(dvach_post['Error'])
                            bot.send_message(message.chat.id, output, parse_mode='HTML',
                                             reply_to_message_id=message.message_id).wait()
                            return
                        dvach_post = dvach_post[0]
                        disable_preview = True
                        if dvach_post['subject']:
                            output = output + '<b>{}</b>\n'.format(dvach_post['subject'], link)
                        if dvach_post['email']:
                            output = output + '<a href="{}">{}</a>'.format(dvach_post['email'], dvach_post['name'])
                        else:
                            output = output + dvach_post['name']
                        if dvach_post['op']:
                            output = output + ' <i># OP</i> '
                        output = output + ' {} <a href="{}">№{}</a><br><br>'.format(dvach_post['date'], link, post)

                        if 'files' in dvach_post and dvach_post['files']:
                            disable_preview = False
                            filelink = 'https://2ch.hk' + dvach_post['files'][0]['path']
                            filetype = session.get(filelink).headers[
                                'content-type']
                            if 'image' in filetype or 'mp4' in filetype:
                                output = '<a href="{}">&#8203;</a>'.format(filelink) + output
                            else:
                                filelink = 'https://2ch.hk' + dvach_post['files'][0]['thumbnail']
                                output = '<a href="{}">&#8203;</a>'.format(filelink) + output

                        output = output + dvach_post['comment']
                        # print(output)
                        bot.send_message(message.chat.id, convert_markdown(output),
                                         parse_mode='HTML',
                                         reply_to_message_id=message.message_id,
                                         disable_web_page_preview=disable_preview).wait()
                    else:
                        dvach_thread = session.get(
                            'https://2ch.hk/makaba/mobile.fcgi?task=get_post&board={}&post={}'.format(board,
                                                                                                      thread)).json()
                        if 'Error' in dvach_thread:
                            output = '<b>Ошибка!</b> <i>{}</i>'.format(dvach_thread['Error'])
                            bot.send_message(message.chat.id, output, parse_mode='HTML',
                                             reply_to_message_id=message.message_id).wait()
                            return
                        dvach_thread = dvach_thread[0]
                        dvach_stats = session.get('https://2ch.hk/{}/threads.json'.format(board)).json()
                        stats = False
                        disable_preview = True
                        for thd in dvach_stats['threads']:
                            if thd['num'] == thread:
                                views = thd['views']
                                posts_count = thd['posts_count']
                                score = thd['score']
                                stats = True
                                break
                        if dvach_thread['subject']:
                            output = output + '<b>{}</b> '.format(dvach_thread['subject'])
                        if dvach_thread['tags']:
                            output = output + '<b>/{}/</b>\n'.format(dvach_thread['tags'])
                        else:
                            output = output + '\n'
                        if dvach_thread['email']:
                            output = output + '<a href="{}">{}</a>'.format(dvach_thread['email'], dvach_thread['name'])
                        else:
                            output = output + dvach_thread['name']
                        if dvach_thread['op']:
                            output = output + ' <i># OP</i> '
                        output = output + ' {} <a href="{}">№{}</a><br><br>'.format(dvach_thread['date'], link, thread)

                        if 'files' in dvach_thread:
                            disable_preview = False
                            filelink = 'https://2ch.hk' + dvach_thread['files'][0]['path']
                            filetype = session.get(filelink).headers[
                                'content-type']
                            if 'image' in filetype or 'mp4' in filetype:
                                output = '<a href="{}">&#8203;</a>'.format(filelink) + output
                            else:
                                filelink = 'https://2ch.hk' + dvach_thread['files'][0]['thumbnail']
                                output = '<a href="{}">&#8203;</a>'.format(filelink) + output

                        output = output + dvach_thread['comment']
                        if stats:
                            stats = '\n\n<code>👁‍{} 💬{} 📊{}</code>'.format(views, posts_count,
                                                                              int(round(score)))
                        else:
                            stats = ''
                        # print(output)
                        bot.send_message(message.chat.id, convert_markdown(output) + stats, parse_mode='HTML',
                                         reply_to_message_id=message.message_id,
                                         disable_web_page_preview=disable_preview).wait()


@bot.message_handler(content_types=['text'])
def message_handler(msg):
    update_user_info(msg.from_user)
    if msg.chat.type == 'private':
        bot.send_message(msg.chat.id, 'Предложка обоев временно недоступна, отпиши админам в @ru2chmobi').wait()
    elif msg.chat.type == 'supergroup':
        try:
            dvach_reveal(msg)
        except Exception as e:
            mobibot_logger.error('Error in 2ch reveal ' + str(e))
            # get_chat(msg.chat)


@bot.message_handler(content_types=['new_chat_members'])
def new_chat_members_handler(msg):
    # update_user_info(msg.from_user)
    print('New member')
    if is_legit(msg.chat.id):
        for new_member in msg.new_chat_members:
            if new_member.id != ASSISTANT.id:  # and new_member.is_bot() is False:
                user = get_user(new_member)
                if user.status == user.NEW:# or user.status == user.OLDFAG:
                    markup = InlineKeyboardMarkup(row_width=2)
                    chat = get_chat(msg.chat)
                    welcome = get_welcome_message(msg.chat, new_member, chat)
                    markup.row(InlineKeyboardButton(str(welcome['VAR_A']),
                                                    callback_data='id={}VAR_A'.format(new_member.id)),
                               InlineKeyboardButton(str(welcome['VAR_B']),
                                                    callback_data='id={}VAR_B'.format(new_member.id)))

                    markup.add(InlineKeyboardButton('Проблемы с ответом 😕', url='https://t.me/Kylmakalle'))
                    sended_welcome = bot.send_message(msg.chat.id, welcome['message'], parse_mode='HTML',
                                                      reply_markup=markup).wait()
                    if isinstance(sended_welcome, tuple):
                        mobibot_logger.error(
                            'Incorrect welcome message markup! ' + str(sended_welcome) + ' ' + str(msg.chat))
                    else:
                        RSTRICT = bot.restrict_chat_member(msg.chat.id, new_member.id, can_send_messages=False,
                                                 can_send_media_messages=False, can_send_other_messages=False,
                                                 can_add_web_page_previews=False).wait()
                        print('RESTRICTED', RSTRICT)
    elif ASSISTANT in msg.new_chat_members:
        mobibot_logger.info('Added to chat ' + str(msg.chat) + ' by ' + str(msg.from_user))
        # bot.send_message(msg.chat.id, 'Contact @Kylmakalle first!').wait()
        # bot.leave_chat(msg.chat.id).wait()


@bot.callback_query_handler(func=lambda call: True)
def callback_buttons(call):
    if call.message and call.data:
        join_answer = re.search('id=([0-9]*)(VAR_A|VAR_B|OK)', call.data)
        if join_answer:
            if join_answer.group(1) == str(call.from_user.id):
                unrestrict = bot.restrict_chat_member(call.message.chat.id, call.from_user.id, can_send_messages=True,
                                                      can_send_media_messages=True, can_send_other_messages=True,
                                                      can_add_web_page_previews=True).wait()
                print('UNRESTRICTED', unrestrict)
                if isinstance(unrestrict, tuple):
                    mobibot_logger.error('Can\'t unrestrict user! ' + str(unrestrict) + ' ' + str(call))
                    # errorprocess
                    bot.send_message(MAINTAINER, 'Can\'t unrestrict user! ' + str(unrestrict) + ' ' + str(call)).wait()
                else:
                    user = get_user(call.from_user)
                    user.status = user.OLDFAG
                    user.save()
                    # chat = get_chat(call.message.chat)
                    ## add user to chat
                    if join_answer.group(2) == 'OK':
                        bot.edit_message_text(
                            'Привет, <a href="tg://user?id={}">{}</a>! Добро пожаловать в <b>{}</b>'.format(
                                call.from_user.id,
                                call.from_user.first_name,
                                call.chat.title),
                            call.message.chat.id, call.message.message_id, parse_mode='HTML').wait()
                    else:
                        welcome_var = \
                            get_welcome_message(call.message.chat, call.message.from_user, get_chat(call.message.chat))[
                                join_answer.group(2)]

                        bot.edit_message_text(
                            '<a href="tg://user?id={}">{}</a> выбирает <b>{}</b>. Поприветствуем!'.format(
                                call.from_user.id,
                                call.from_user.first_name,
                                welcome_var),
                            call.message.chat.id, call.message.message_id, parse_mode='HTML').wait()

                    bot.answer_callback_query(call.id).wait()
            else:
                bot.answer_callback_query(call.id, 'Молодой человек, это не для Вас написано.', show_alert=True).wait()


bot.remove_webhook()
if DEBUG:
    print('DEV STARTED')
    bot.polling()
else:
    bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
    print('PROD STARTED!')
    # Start flask server
    app.run(host='127.0.0.1', port=WEBHOOK_PORT)
