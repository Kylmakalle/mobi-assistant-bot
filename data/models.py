from django.db import models


# Create your models here.


class User(models.Model):
    class Meta:
        verbose_name_plural = 'Пользователи'
        verbose_name = 'Пользователь'

    # id пользователя на сервере Telegram
    id = models.IntegerField(primary_key=True, unique=True)

    # имя
    first_name = models.CharField(max_length=256, verbose_name='Имя')

    # фамилия
    last_name = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        default=None,
        verbose_name='Фамилия'
    )

    # username
    username = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        default=None,
        verbose_name='Юзернейм'
    )

    BANNED = -1
    NEW = 0
    OLDFAG = 1
    TRUSTED = 2
    ADMIN = 3
    SUPERUSER = 228

    STATUSES = (
        (BANNED, 'Banned'),
        (NEW, 'Unknown'),
        (OLDFAG, 'Known'),
        (TRUSTED, 'Trusted'),
        (ADMIN, 'Admin'),
        (SUPERUSER, 'Superuser'),
    )

    status = models.IntegerField(
        choices=STATUSES,
        default=NEW, verbose_name='Статус'
    )

    # временные метки
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.username is not None:
            return '@' + str(self.username)
        if self.last_name is not None:
            return self.first_name + ' ' + self.last_name
        return self.first_name

    def return_screen_name(self):
        if self.last_name:
            return self.first_name + ' ' + self.last_name
        else:
            return self.first_name

    return_screen_name.short_description = 'Имя'

    def return_first_name(self):
        return self.first_name

    return_first_name.short_description = 'Имя'

    def return_last_name(self):
        if self.last_name:
            return self.last_name
        else:
            return ''

    return_last_name.short_description = 'Фамилия'

    def return_username(self):
        if self.username:
            return '<a target="_blank" href="http://t.me/{0}">@{0}</a>'.format(str(self.username))
        else:
            return ''

    return_username.short_description = 'Юзернейм'
    return_username.allow_tags = True

    def return_id(self):
        return str(self.id)

    return_id.short_description = 'ID'

    def return_status(self):
        return self.status

    return_status.short_description = 'Статус'


class Chat(models.Model):
    class Meta:
        verbose_name_plural = 'Чаты'
        verbose_name = 'Чат'

    id = models.BigIntegerField(primary_key=True, unique=True)

    title = models.CharField(max_length=256, verbose_name='Название')

    username = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        default=None,
        verbose_name='Юзернейм'
    )

    welcome_message = models.TextField(max_length=3000, verbose_name='Приветствие', blank=True, null=True, default=None)

    welcome_var_a = models.CharField(max_length=32, blank=True, null=True, default=None)

    welcome_var_b = models.CharField(max_length=32, blank=True, null=True, default=None)

    users = models.ManyToManyField(User, blank=True, default=None)

    def __str__(self):
        return self.title

    def return_username(self):
        if self.username:
            return '<a target="_blank" href="http://t.me/{0}">@{0}</a>'.format(str(self.username))
        else:
            return ''

    return_username.short_description = 'Юзернейм'
    return_username.allow_tags = True

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)


class JoinAction(models.Model):
    user = models.ForeignKey(User)
    chat = models.ForeignKey(Chat)
    date = models.IntegerField()

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.user) + ' ' + str(self.chat)


class File(models.Model):
    file_id = models.CharField(max_length=128)
    type = models.CharField(max_length=128)
    nsfw = models.FloatField(max_length=128)
    sfw = models.FloatField(max_length=128)
    status = models.CharField(max_length=256)
    mime_type = models.CharField(max_length=128, null=True, blank=True, default=None)
