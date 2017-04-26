from __future__ import print_function

from app import app
import requests
import json

from . import accounts, request, render_template, session, redirect, make_response
from app.irsystem.models.search import do_jaccard, do_cosine_sim
from app.steam.models import Game

STEAM_API_KEY = app.config['STEAM_API_KEY']
SECRET_KEY = app.config['SECRET_KEY']
#app.secret_key = SECRET_KEY


@accounts.route("/login", methods=['GET', 'POST'])
def login():
    if (request.method == "GET"):
        return render_template("login.html")
    username = request.form['username']
    redirect_to_home = redirect("/")
    response = make_response(redirect_to_home)
    if (username != ""):
        params = {
            'key': STEAM_API_KEY,
            'vanityurl': username
        }
        r = requests.get("http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/", params)
        success = int(r.json()['response']['success'])
        if (success == 1):
            steamid = r.json()['response']['steamid']
            response.set_cookie("steam_ID", value=steamid)
            del params['vanityurl']
            params['steamids'] = steamid
            r3 = requests.get(
                "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/", params)
            print(r3.text)
            response.set_cookie(
                "username", value=r3.json()['response']['players'][0]['personaname'])
            r2 = requests.get("http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=" +
                              STEAM_API_KEY + "&steamid=" +
                              steamid + "&format=json&include_played_free_games=1")
            games = r2.json()['response']['games']
            games_list = []
            for game in games:
                appID = game['appid']
                games_list.append(int(appID))
            GameVector = Game.compute_bias_vector(games_list)
            response.set_cookie("bias_vector", value=json.dumps(GameVector.tolist()))
    else:
        if (request.cookies.get('username')):
            del session['steam_ID']
            del session['bias_vector']
            response.set_cookie("steam_id", "", max_age=0)
            response.set_cookie("bias_vector", "", max_age=0)
    return response
