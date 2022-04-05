from django.urls import path
from .views import oauth,access_token,linkedin_post




urlpatterns = [
    path('login/',oauth),
    path('token/',access_token),
    # path('user_data/',getProfile)
    path('post/',linkedin_post)
]

