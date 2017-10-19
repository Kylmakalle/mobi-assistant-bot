from django.contrib import admin

# Register your models here.


from .models import User, Chat

admin.site.register(User)
admin.site.register(Chat)
