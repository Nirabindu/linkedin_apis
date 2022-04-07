from django.shortcuts import render
from decouple import config
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
import requests
import webbrowser
import json
import random
import string
from urllib.parse import urlparse, parse_qs
from .models import OauthUser

# from django.shortcuts import redirect


# creating csrf accesstoken
def create_CSRF_token():
    """
    this function is use for creating csrf token/ random string to
    protect CSRF token.
    """
    random_str = string.ascii_lowercase
    token = "".join(random.choice(random_str) for i in range(20))
    return token


# get env config data
response_type = config("response_type")
client_id = config("client_id")
client_Secret = config("client_Secret")
redirect_uri = config("redirect_uri")
scope = config("scope")
state = create_CSRF_token()


# oauth2 with linkedin
@api_view(["GET"])
def oauth(request):
    # linkedin oauth url
    api_url = "https://www.linkedin.com/oauth/v2"
    params = {
        "response_type": response_type,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    response = requests.get(f"{api_url}/authorization", params=params)

    url = response.url
    res = webbrowser.open(url)
    if res == True:
        return Response(status=status.HTTP_200_OK)
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST)


# linkedin access token get
@api_view(["POST"])
def access_token(request):
    access_token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    redirect_url = request.data["redirect_url"]
    url = urlparse(redirect_url)
    url = parse_qs(url.query)
    code = url["code"][0]
    # get access token
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_Secret,
        "redirect_uri": redirect_uri,
    }
    response = requests.post(access_token_url, data=data)
    return Response(response.json())


# should be  a  function and every time we have to get the user id by passing token
def getProfile(token):
    headers = {
        "Authorization": token,
        "Content-type": "application/json",
    }
    response = requests.get(
        "https://api.linkedin.com/v2/me",
        headers=headers,
    )
    # extracting data that we getting from response
    response = response.json()
    social_id = response["id"]
    first_name = response["localizedFirstName"]
    last_name = response["localizedLastName"]
    # check id is already in database or not
    check_user = OauthUser.objects.filter(socialId=social_id).first()
    if not check_user:
        # save data into database
        database = OauthUser(
            socialId=social_id, firstName=first_name, lastName=last_name
        )
        database.save()
        return social_id
    else:
        return social_id


# register for linkedin image
def reg_image(token, author):
    api_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    post_data = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": author,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }
    response = requests.post(api_url, headers={"Authorization": token}, json=post_data)
    return response



# image upload
def upload_image(token, uploadUrl, image, assets):
    api_url = f"{uploadUrl}"
    headers = {
        "Authorization": token,
        "Content-Type": "image/jpeg,image/png,image/gif",
    }
    requests.post(api_url, headers=headers, data=image.read())

    # image upload status
    header = {
        "Authorization": token,
        "Content-Type": "multipart/form-data",
    }

    status_url = "https://api.linkedin.com/v2/assets/"
    return_response = requests.get(status_url + str(assets), headers=header)
    data = return_response.json()
    url_id = data["id"]
    return url_id


@api_view(["POST"])
def linkedin_post(request):
    header = request.headers
    description = request.data["description"]

    token = header["Authorization"]
    # get user id
    get_user = getProfile(token)
    author = f"urn:li:person:{get_user}"
    # call function for register image
    response = reg_image(token, author)
    data = response.json()
    uploadUrl = data["value"]["uploadMechanism"][
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ]
    uploadUrl = uploadUrl["uploadUrl"]
    assest = data["value"]["asset"]
    assest = assest.split(":")
    assest = assest[-1]
    image = request.FILES["media"]
    image_update_url = upload_image(token, uploadUrl, image, assest)
    if not image_update_url:
        return Response(
            {"msg": "something went wrong"}, status=status.HTTP_400_BAD_REQUEST
        )

    header = {
        "Authorization": token,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    # getting
    media = f"urn:li:digitalmediaAsset:{image_update_url}"
    payload = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": description},
                "shareMediaCategory": "IMAGE",
                "media": [
                    {
                        "status": "READY",
                        "description": {"text": description},
                        "media": media,
                        "title": {"text": "image"},
                    }
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    post_url = "https://api.linkedin.com/v2/ugcPosts"

    response = requests.post(post_url, headers=header, json=payload)
    return Response({'data':response.json(),'msg':'successfully post'},status=status.HTTP_201_CREATED)
