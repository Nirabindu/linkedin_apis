from django.db import models


class OauthUser(models.Model):
    socialId = models.CharField(max_length=200,unique=True)
    firstName = models.CharField(max_length=200)
    lastName  = models.CharField(max_length=200)




