from __future__ import print_function

import app
import logging
import urllib
import numpy as np

from . import irsystem, request, render_template, session
from app.irsystem.models.search import do_jaccard, do_cosine_sim
from app.steam.models import Game

DEFAULT_KWARGS = {
    "name": "Steamy Reviews",
    "netid": "bg379, hju3, nsk43, pmc85",
}
MAX_RANK_RESULTS = 27

@irsystem.route("/", methods=["GET"])
def search():
    app_id = request.args.get("app_id", "").strip() or None
    query = request.args.get("search", "").strip() or None
    if app_id is not None and app_id.isdigit():
        game = Game.get(int(app_id))
        if game is not None:
            return render_ranking_page(game)
        else:
            return render_template("search.html", no_such_app_id=True, **DEFAULT_KWARGS)
    elif query is not None and len(query) > 0:
        game = Game.find_by_name(query)
        if game is not None:
            return render_ranking_page(game)
        else:
            logging.error("No result for " + query.encode("ascii", "ignore"))
            didyoumean1, didyoumean2 = Game.correct_game_name(query, max_results=2)
            return render_template("search.html",
                                   didyoumean1=didyoumean1,
                                   didyoumean2=didyoumean2,
                                   query=query,
                                   **DEFAULT_KWARGS)

    else:
        return render_template("search.html", **DEFAULT_KWARGS)

def render_ranking_page(game):
    bias_vector = None
    print(session)
    if ('bias_vector' in session):
        bias_vector = np.array(session['bias_vector'])
    print(bias_vector)
    ranking = do_cosine_sim(game, max_results=MAX_RANK_RESULTS, biasVector=bias_vector)
    logging.error("Results for " + game.normalized_name + ": " + str(ranking))
    return render_template("search.html", game=game, ranking=ranking, **DEFAULT_KWARGS)
