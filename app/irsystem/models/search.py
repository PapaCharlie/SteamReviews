from __future__ import print_function, division

import logging

from app.steam.models import Game, Tag
from operator import itemgetter

MAX_GAMES = 27

def jaccard_sim(tag_set1, tag_set2):
    return len(tag_set1 & tag_set2) / len(tag_set1 | tag_set2)

def do_jaccard(query):
    tag_set = set(query.tags.keys())
    matching_app_ids = Tag.get_games_with_tags(tag_set)
    to_get = set()
    for games in matching_app_ids.values():
        to_get.update(games)
    to_get.remove(query.app_id)
    games = Game.get(to_get)
    scores = [(jaccard_sim(tag_set, set(g.tags.keys())), g.score_rank, g) for g in games.values()]
    # Magic trick: Python sorts tuples element-wise, so if the first value in a pair of tuples
    # is equal, it will sort by the next and so on. Since the score_rank is second element,
    # games with equal Jaccard will then be sorted by score_rank.
    scores.sort(reverse=True)
    return map(itemgetter(2), scores)[:MAX_GAMES]
