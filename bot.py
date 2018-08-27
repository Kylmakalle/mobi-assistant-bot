import io
import logging
import re
import sys
from datetime import datetime, timedelta
from statistics import mean

import bs4
# Setup database connection
import django.conf
import flask
import requests
import telebot
from PIL import Image
from bs4 import BeautifulSoup
from clarifai.rest import ClarifaiApp
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import *
from util import fetch_user_type

django.conf.ENVIRONMENT_VARIABLE = SETTINGS_VAR
os.environ.setdefault(SETTINGS_VAR, "settings")
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
from data.models import *

# End setup

API_TOKEN = TOKEN
WEBHOOK_PORT = 443
WEBHOOK_URL_BASE = "https://%s.serveo.net" % (SERVEO_SUB_DOMAIN)
WEBHOOK_URL_PATH = "/%s/" % (API_TOKEN)

app = flask.Flask(__name__)
bot = telebot.AsyncTeleBot(API_TOKEN)

mobibot_logger = logging.getLogger()
mobibot_logger.setLevel(logging.INFO)

ASSISTANT = bot.get_me().wait()

legit_usernames = ['twochannel', 'dvachannel', 'ru2chhw', 'ru2chmobi', 'anime2ch', 'ru2chvg', 'politach', 'ru2chmu',
                   'ru2chme',
                   'ru2chmov',
                   'ru2chsex',
                   'ru2chfg', 'ru2chga', 'ru2chby', 'ru2chdiy', 'velach', 'stolovach', 'motokonfa', 'ru2chfiz',
                   'ru2chfa',
                   'ru2chkz', 'ru2chukr', 'ru2chmg', 'ru2chmobiwp', 'animach', 'random2ch', 'hw_global']
legit_links = [
    'shikimori.org', 'myanimelist.net'
]


# Empty webserver index, return nothing, just http 200
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return ''


# Process webhook calls
@app.route('/%s/' % (TOKEN), methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)


def dump_telegram_object(msg):
    ret = {}
    for key, val in msg.__dict__.items():
        if isinstance(val, (int, str, dict)):
            pass
        elif val is None:
            pass
        elif isinstance(val, (tuple, list)):
            val = [dump_telegram_object(x) for x in val]
        else:
            val = dump_telegram_object(val)
        if val is not None:
            ret[key] = val
    return ret


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


def create_join_action(user, chat, date):
    return JoinAction.objects.update_or_create(
        user=user,
        chat=chat,
        date=date if isinstance(date, int) else date.timestamp()
    )[0]


def get_join_action(user, chat, date):
    joined = JoinAction.objects.filter(user=user, chat=chat)
    if joined:
        return joined[0]
    else:
        return create_join_action(user, chat, date)


def get_chat(chat_obj):
    chat_db = Chat.objects.filter(id=chat_obj.id)
    if chat_db:
        return chat_db[0]
    else:
        return create_chat(chat_obj)


def is_user_in_db(uid):
    return User.objects.filter(id=uid).first()


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


def process_user_type(username):
    logging.debug('Querying %s type from db' % username)
    user = User.objects.filter(username=username).first()
    if user:
        # logging.debug('Record found, type is: %s' % user['type'])
        return 'user'
    else:
        logging.debug('Doing network request for type of %s' % username)
        user_type = fetch_user_type(username)
        # logging.debug('Result is: %s' % user_type)
        return user_type


def parse_entity(text, entity):
    if sys.maxunicode == 0xffff:
        return text[entity.offset:entity.offset + entity.length]
    else:
        entity_text = text.encode('utf-16-le')
        entity_text = entity_text[entity.offset * 2:(entity.offset + entity.length) * 2]

    return entity_text.decode('utf-16-le')


def check_spam(msg):
    if GUARD_MODE:
        to_hide = False
        chat = get_chat(msg.chat)
        user = get_user(msg.from_user)
        if user.status == User.NEW or user.status == User.BANNED:
            while not to_hide:
                now = datetime.utcnow()
                join_date = get_join_action(user, chat, now)
                if not join_date:
                    return
                if now - timedelta(hours=24) > datetime.fromtimestamp(join_date.date):
                    user.status = User.OLDFAG
                    user.save()
                    return

                for ent in (msg.entities or []):
                    if ent.type in ('url', 'text_link'):
                        if ent.type == 'url':
                            url = parse_entity(msg.text, ent)
                        elif ent.type == 'text_link':
                            url = ent.url
                        if not next((link for link in legit_links if link in url), None):
                            to_hide = True
                            reason = 'external link'
                            break
                        else:
                            user.status = user.OLDFAG
                            user.save()
                            return
                    if ent.type in ('email',):
                        to_hide = True
                        reason = 'email'
                        break
                    if ent.type == 'mention':
                        username = parse_entity(msg.text, ent).lstrip('@')
                        user_type = process_user_type(username)
                        if user_type in ('group', 'channel'):
                            if username not in legit_usernames:
                                to_hide = True
                                reason = '@-link to {}'.format(user_type)
                                break
                            else:
                                user.status = user.OLDFAG
                                user.save()
                                return

                for cap_ent in (msg.caption_entities or []):
                    if cap_ent.type in ('url', 'text_link'):
                        if cap_ent.type == 'url':
                            url = parse_entity(msg.caption, cap_ent)
                        elif cap_ent.type == 'text_link':
                            url = cap_ent.url
                        if not next((link for link in legit_links if link in url), None):
                            to_hide = True
                            reason = 'caption external link'
                            break
                        else:
                            user.status = user.OLDFAG
                            user.save()
                            return
                    if cap_ent.type in ('email',):
                        to_hide = True
                        reason = 'caption email'
                        break
                    if cap_ent.type == 'mention':
                        username = parse_entity(msg.caption, cap_ent).lstrip('@')
                        user_type = process_user_type(username)
                        if user_type in ('group', 'channel'):
                            if username not in legit_usernames:
                                to_hide = True
                                reason = 'caption @-link to {}'.format(user_type)
                                break
                            else:
                                user.status = user.OLDFAG
                                user.save()
                                return

                if msg.forward_from:
                    reason = 'forwarded'
                    to_hide = True
                if msg.forward_from_chat:
                    if getattr(msg.forward_from_chat, 'username', None) not in legit_usernames:
                        reason = 'forwarded'
                        to_hide = True
                    else:
                        user.status = user.OLDFAG
                        user.save()
                        return
                break
            if to_hide:
                delete_text = 'Removed message from <a href="tg://user?id={USER_ID}">{FIRST_NAME}</a>\nReason: {REASON}'.format(
                    USER_ID=msg.from_user.id, FIRST_NAME=msg.from_user.first_name, REASON=reason)
                fwd_in_pm = bot.forward_message(MAINTAINER, msg.chat.id, msg.message_id).wait()

                logged_msg = bot.send_message(MAINTAINER, delete_text, reply_to_message_id=fwd_in_pm.message_id,
                                              parse_mode='HTML').wait()
                bot.delete_message(msg.chat.id, msg.message_id).wait()
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton('Ban {}'.format(msg.from_user.first_name),
                                                callback_data='ban-{}'.format(msg.from_user.id)),
                           InlineKeyboardButton('Ignore {}'.format(msg.from_user.first_name),
                                                callback_data='unwatch-{}'.format(msg.from_user.id)))
                del_msg = bot.send_message(msg.chat.id, delete_text, parse_mode='HTML', reply_markup=markup).wait()
                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton(msg.chat.title,
                                         'https://t.me/{}/{}'.format(msg.chat.username, del_msg.message_id)))
                bot.edit_message_reply_markup(logged_msg.chat.id, logged_msg.message_id, reply_markup=markup).wait()
                return to_hide


def get_file(file_id):
    return File.objects.filter(file_id=file_id).first()


@bot.message_handler(commands=['nsfw', 'sfw'])
def nsfw_command(msg):
    if msg.chat.type == 'supergroup':
        if msg.reply_to_message:
            mime_type = None
            if msg.reply_to_message.photo:
                file_id = msg.reply_to_message.photo[-1].file_id
                file_type = 'photo'

            elif msg.reply_to_message.document:
                if msg.reply_to_message.document.thumb:
                    file_id = msg.reply_to_message.document.file_id
                    file_type = 'document'
                    mime_type = msg.reply_to_message.document.mime_type
                else:
                    bot.send_message(msg.chat.id, 'Данный тип файла не поддерживается',
                                     reply_to_message_id=msg.reply_to_message.message_id).wait()
                    return
            elif msg.reply_to_message.sticker:
                file_id = msg.reply_to_message.sticker.file_id
                file_type = 'sticker'
            elif msg.reply_to_message.video:
                bot.send_message(msg.chat.id, 'Данный тип файла не поддерживается',
                                 reply_to_message_id=msg.reply_to_message.message_id).wait()
                return
            else:
                bot.send_message(msg.chat.id, 'Данный тип файла не поддерживается',
                                 reply_to_message_id=msg.reply_to_message.message_id).wait()
                return
            bot.send_chat_action(msg.chat.id, 'typing').wait()
            file = get_file(file_id)
            if file:
                bot.send_message(msg.chat.id, 'Я на <code>{:.1%}</code> уверен, что это <b>{}</b>'.format(
                    getattr(file, file.status.lower()), file.status),
                                 reply_to_message_id=msg.reply_to_message.message_id,
                                 parse_mode='HTML').wait()
            else:
                file_info = bot.get_file(file_id).wait()
                if isinstance(file_info, telebot.types.File):
                    url = telebot.apihelper.FILE_URL.format(bot.token, file_info.file_path)
                    if file_type == 'sticker':
                        img = requests.get(url, stream=True).raw.read()
                        imgdata = Image.open(io.BytesIO(img))
                        png = io.BytesIO()
                        imgdata.save(png, format='PNG')
                        file_bytes = png.getvalue()
                    else:
                        file_bytes = requests.get(url).content
                    capp = ClarifaiApp(api_key=CLARIFAI_TOKEN)
                    model = capp.models.get('nsfw-v1.0')
                    is_video = True if ((mime_type and 'mp4' in mime_type) or file_type == 'video') else False
                    try:
                        prediction = model.predict_by_bytes(file_bytes, is_video=is_video)
                        if prediction['status']['code'] == 10000:
                            if prediction['outputs'][0]['data'].get('frames'):
                                sfw_list = []
                                nsfw_list = []
                                for frame in prediction['outputs'][0]['data']['frames']:
                                    for concept in frame['data']['concepts']:
                                        if concept['name'] == 'sfw':
                                            sfw_list.append(concept['value'])
                                        else:
                                            nsfw_list.append(concept['value'])
                                sfw = mean(sfw_list)
                                nsfw = mean(nsfw_list)
                            else:
                                for concept in prediction['outputs'][0]['data']['concepts']:
                                    if concept['name'] == 'sfw':
                                        sfw = concept['value']
                                    else:
                                        nsfw = concept['value']
                            status = 'NSFW' if nsfw >= sfw else 'SFW'
                            percentage = nsfw if nsfw >= sfw else sfw
                            bot.send_message(msg.chat.id,
                                             'Я на <code>{:.1%}</code> уверен, что это <b>{}</b>'.format(percentage,
                                                                                                         status),
                                             parse_mode='HTML', reply_to_message_id=msg.reply_to_message.message_id)
                            File.objects.create(
                                file_id=file_id,
                                type=file_type,
                                mime_type=mime_type,
                                nsfw=nsfw,
                                sfw=sfw,
                                status=status
                            )
                        else:
                            bot.send_message(MAINTAINER, 'Error!\n\n' + '<pre>' + prediction + '</pre>',
                                             parse_mode='HTML').wait()
                            bot.send_message(msg.chat.id, 'Неизвестная ошибка',
                                             reply_to_message_id=msg.message_id).wait()
                    except Exception as e:
                        print(e)
                        bot.send_message(MAINTAINER, 'Error!\n\n' + '<pre>' + str(e) + '</pre>',
                                         parse_mode='HTML').wait()
                        bot.send_message(msg.chat.id, 'Неизвестная ошибка',
                                         reply_to_message_id=msg.message_id).wait()
                else:
                    bot.send_message(msg.chat.id, 'Не могу получить файл, возможно он слишком большой',
                                     reply_to_message_id=msg.reply_to_message.message_id).wait()
        else:
            bot.send_message(msg.chat.id, 'Отправь команду в ответ на медиа', reply_to_message_id=msg.message_id).wait()
    else:
        bot.send_message(msg.chat.id, 'Команда работает только в группах', reply_to_message_id=msg.message_id).wait()


@bot.edited_message_handler(content_types=['photo', 'video', 'audio', 'sticker', 'document'])
@bot.message_handler(content_types=['photo', 'video', 'audio', 'sticker', 'document'])
def process_attachments(msg):
    update_user_info(msg.from_user)
    if msg.chat.type == 'private':
        pass
    elif msg.chat.type == 'supergroup':
        if check_spam(msg):
            return


@bot.edited_message_handler(content_types=['text'])
@bot.message_handler(content_types=['text'])
def message_handler(msg):
    update_user_info(msg.from_user)
    if msg.chat.type == 'private':
        bot.send_message(msg.chat.id, 'Предложка обоев временно недоступна, отпиши админам в @ru2chmobi').wait()
    elif msg.chat.type == 'supergroup':
        if check_spam(msg):
            return
        try:
            dvach_reveal(msg)
        except Exception as e:
            mobibot_logger.error('Error in 2ch reveal ' + str(e))
            # get_chat(msg.chat)


@bot.message_handler(content_types=['new_chat_members'])
def new_chat_members_handler(msg):
    if is_legit(msg.chat.id):
        chat = get_chat(msg.chat)
        for new_member in msg.new_chat_members:
            if new_member.id != ASSISTANT.id:  # and new_member.is_bot() is False:
                user = get_user(new_member)
                if user.status == User.NEW:
                    get_join_action(user, chat, msg.date)
    elif ASSISTANT.id in [member.id for member in msg.new_chat_members] and get_user(
            msg.from_user).status < User.ADMIN:
        mobibot_logger.info('Added to chat ' + str(msg.chat) + ' by ' + str(msg.from_user))
        bot.send_message(msg.chat.id, 'Contact @Kylmakalle first!').wait()
        bot.leave_chat(msg.chat.id).wait()


@bot.callback_query_handler(func=lambda call: True)
def callback_buttons(call):
    if call.message and call.data:
        if 'unwatch-' in call.data:
            if call.from_user.id in [admin.user.id for admin in
                                     bot.get_chat_administrators(
                                         call.message.chat.id).wait()] or call.from_user.id == MAINTAINER:
                call.data = call.data.split('unwatch-')[1]
                user = is_user_in_db(int(call.data))
                if user:
                    if user.status == User.BANNED or user.status == User.NEW:
                        user.status = User.OLDFAG
                        user.save()
                        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id).wait()
                        bot.send_message(MAINTAINER,
                                         '<a href="tg://user?id={ADMIN_ID}">{ADMIN_FIRST_NAME}</a> activated ignore for <a href="tg://user?id={USER_ID}">{FIRST_NAME}</a>'.format(
                                             ADMIN_ID=call.from_user.id,
                                             ADMIN_FIRST_NAME=call.from_user.first_name,
                                             USER_ID=user.id,
                                             FIRST_NAME=user.first_name
                                         ), parse_mode='HTML')
                        bot.answer_callback_query(call.id, 'Done!').wait()
                else:
                    bot.answer_callback_query(call.id, 'Something went wrong').wait()
            else:
                bot.answer_callback_query(call.id, 'Молодой человек, это не для Вас написано.', show_alert=True).wait()
        elif 'ban-' in call.data and not 'unban-' in call.data:
            if call.from_user.id in [admin.user.id for admin in
                                     bot.get_chat_administrators(
                                         call.message.chat.id).wait()] or call.from_user.id == MAINTAINER:
                call.data = call.data.split('ban-')[1]
                user = is_user_in_db(int(call.data))
                if user:
                    if user.status == User.NEW or user.status == User.OLDFAG:
                        user.status = User.BANNED
                        user.save()
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton('Unban {}'.format(user.first_name),
                                                    callback_data='unban-{}'.format(call.data)))
                    bot.kick_chat_member(call.message.chat.id, call.data).wait()
                    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                  reply_markup=markup).wait()
                    bot.send_message(MAINTAINER,
                                     '<a href="tg://user?id={ADMIN_ID}">{ADMIN_FIRST_NAME}</a> banned <a href="tg://user?id={USER_ID}">{FIRST_NAME}</a>'.format(
                                         ADMIN_ID=call.from_user.id,
                                         ADMIN_FIRST_NAME=call.from_user.first_name,
                                         USER_ID=user.id,
                                         FIRST_NAME=user.first_name
                                     ), parse_mode='HTML')
                    bot.answer_callback_query(call.id, 'Done!').wait()
                else:
                    bot.answer_callback_query(call.id, 'Something went wrong').wait()
            else:
                bot.answer_callback_query(call.id, 'Молодой человек, это не для Вас написано.', show_alert=True).wait()
        elif 'unban-' in call.data:
            if call.from_user.id in [admin.user.id for admin in
                                     bot.get_chat_administrators(
                                         call.message.chat.id).wait()] or call.from_user.id == MAINTAINER:
                call.data = call.data.split('unban-')[1]
                user = is_user_in_db(int(call.data))
                if user:
                    if user.status == User.BANNED:
                        user.status = User.OLDFAG
                        user.save()
                        bot.unban_chat_member(call.message.chat.id, call.data).wait()
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton('Ban {}'.format(user.first_name),
                                                        callback_data='ban-{}'.format(call.data)))
                        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                                      reply_markup=markup).wait()
                        bot.send_message(MAINTAINER,
                                         '<a href="tg://user?id={ADMIN_ID}">{ADMIN_FIRST_NAME}</a> unbanned <a href="tg://user?id={USER_ID}">{FIRST_NAME}</a>'.format(
                                             ADMIN_ID=call.from_user.id,
                                             ADMIN_FIRST_NAME=call.from_user.first_name,
                                             USER_ID=user.id,
                                             FIRST_NAME=user.first_name
                                         ), parse_mode='HTML')
                        bot.answer_callback_query(call.id, 'Done!').wait()
                else:
                    bot.answer_callback_query(call.id, 'Something went wrong').wait()
            else:
                bot.answer_callback_query(call.id, 'Молодой человек, это не для Вас написано.', show_alert=True).wait()


if __name__ == "__main__":
    bot.skip_pending = True
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
    app.run(host='0.0.0.0', port=8888)
