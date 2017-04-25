from __future__ import print_function

import app
import os
import requests

from . import accounts, request, render_template, session, redirect
from app.irsystem.models.search import do_jaccard, do_cosine_sim
from app.steam.models import Game

STEAM_API_KEY = os.environ['STEAM_API_KEY']
SECRET_KEY = os.environ['SECRET_KEY']
#app.secret_key = SECRET_KEY


@accounts.route("/login", methods=['GET', 'POST'])
def login():
    if (request.method == "GET"):
        return render_template("login.html")
    username = request.form['username']
    params = {
        'key': STEAM_API_KEY,
        'vanityurl': username
    }
    r = requests.get("http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/", params)
    success = int(r.json()['response']['success'])
    if (success == 1):
        steamid = r.json()['response']['steamid']
        session['steam_ID'] = int(steamid)
        r2 = requests.get("http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=" +
                          STEAM_API_KEY + "&steamid=" +
                          steamid + "&format=json&include_played_free_games=1")
        games = r2.json()['response']['games']
        games_list = []
        for game in games:
            appID = game['appid']
            games_list.append(int(appID))
        GameVector = Game.compute_bias_vector(games_list)
        session['bias_vector'] = GameVector.tolist()
    return redirect("/")
