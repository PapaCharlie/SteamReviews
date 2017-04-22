from __future__ import print_function, division

import json
import os
import requests
import re
import sys

from app.steam.models import Review
from app.steam.models.game import iter_all_games
from argparse import ArgumentParser
from datetime import datetime
from random import sample

def get_missing_reviews_s3(games, instances, identifier):
    already_computed = set(int(obj.key) for obj in Review.bucket.objects.all())
    remaining = set(g.app_id
                    for g in games
                    if g.app_id % instances == identifier and g.app_id not in already_computed)
    while len(remaining) > 0:
        app_id, = sample(remaining, 1)
        if not Review.exists_in_s3(app_id):
            print(datetime.now().time(), "Getting reviews for", app_id)
            reviews = Review.get_reviews_from_steam(app_id, 1000)
            Review.upload_to_s3(app_id, reviews)
        else:
            print(datetime.now().time(), "Reviews for", app_id, "already exist!")
            remaining.remove(app_id)

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("instances", help="Number of instances doing work.", type=int)
    parser.add_argument("identifier", help="Instance number", type=int)
    args = parser.parse_args()
    get_missing_reviews_s3(list(iter_all_games()), args.instances, args.identifier)

