from django.shortcuts import render
from .config import LinkedinConfig
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
import requests
from .config import LinkedinConfig
import webbrowser
from urllib.parse import urlparse, parse_qs
from .models import OauthUser
import json

# creating objects
config = LinkedinConfig()


# oauth2 with linkedin
@api_view(["GET"])
def oauth(request):
    # linkedin oauth url
    api_url = "https://www.linkedin.com/oauth/v2"
    params = {
        "response_type": config.response_type,
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": config.scope,
        "state": config.state,
    }
    response = requests.get(f"{api_url}/authorization", params=params)
    url = response.url
    webbrowser.open(url)


# linkedin access token
@api_view(["POST"])
def access_token(request):
    access_token_url = "https://www.linkedin.com/oauth/v2/accessToken"

    url = urlparse(
        "http://127.0.0.1:8000/?code=AQRaPLYyqbxTeYpXs7BYWOMb-mWV-AnRnm5MgCBDnYiu5PBkEUvSnL9OctZn-aYLgAzLsWUZP48Eb0A_aDwn13MA35ppRKZRpx09rWmK2f-eJePdHKJLjzd5THfQFneP3NnUY2tL9s7iWX0C9RLnTQGh3ivIDkmYVw0xFoDDdH6ghzFpF1h0o2f_gYYJyVHZwfr27xabqo5cit19EWU&state=DCEeFWf45A53sdfKef428"
    )
    url = parse_qs(url.query)
    code = url["code"][0]

    # get access token
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": config.client_id,
        "client_secret": config.client_Secret,
        "redirect_uri": config.redirect_uri,
    }
    response = requests.post(access_token_url, data=data)
    return Response(response.json())


# should be  a  function and every time we have to get the user id by passing token
def getProfile(token):
    response = requests.get(
        "https://api.linkedin.com/v2/me",
        headers={"Authorization": token, "Content-type": "application/json"},
    )

    # Extract Data from response
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


# register for image
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
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "image/jpeg,image/png,image/gif",
    }
    requests.post(api_url, headers=headers, data=image.read())

    # image upload status
    header = {
        "Authorization": token,
        "X-Restli-Protocol-Version": "2.0.0",
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
    description = request.data['description']

    token = header["Authorization"]
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
    media = f"urn:li:digitalmediaAsset:{image_update_url}"
    payload = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": description
                },
                "shareMediaCategory": "IMAGE",
                "media": [
                    {
                        "status": "READY",
                        "description": {"text" : description},
                        "media": media,
                        "title": {"text" :"image" },
                    }
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    post_url = "https://api.linkedin.com/v2/ugcPosts"

    response = requests.post(post_url,headers= header,json = payload)
    return Response(response.json())
