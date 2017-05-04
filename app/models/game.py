from __future__ import print_function, division

import csv
import base64
import json
import logging
import numpy as np
import os
import requests
import re
import sys
import time

from . import Review
from app import app
from app.dynamodb import db, utils
from app.utils import data_file, mallet_file
from bs4 import BeautifulSoup
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from datetime import datetime
from functools import partial
from itertools import islice, imap
from Levenshtein import distance
from sklearn.preprocessing import normalize as normalize_matrix

reviews_re = re.compile(r"\(([0-9,]+) reviews?\)")
userscore_to_digit = {
    "Overwhelmingly Positive": 8,
    "Very Positive": 7,
    "Positive": 6,
    "Mostly Positive": 5,
    "Mixed": 4,
    "Mostly Negative": 3,
    "Negative": 2,
    "Very Negative": 1,
    "Overwhelmingly Negative": 0
}
digit_to_userscore = {score: r for r,score in userscore_to_digit.iteritems()}

MAX_SPIDER_FEATURES = app.config["MAX_SPIDER_FEATURES"]

class GameNotFoundException(Exception):
    def __init__(self, app_id):
        super(GameNotFoundException, self).__init__("Game %s does not exist!"%app_id)

class Game(object):
    table_name = "apps"
    table = db.Table(table_name)
    hash_key = ("app_id", utils.NUMBER)
    sorting_key = None

    __app_ids = None
    __app_id_to_index = None
    __compressed_matrix = None
    __ranking = None
    __game_cache = None
    __name_inverted_index = None
    __dimensions = None
    __dimensions_inverted_index = None

    @classmethod
    def _load_caches(cls):
        # cls.__app_ids, cls.__compressed_matrix = load_compressed_matrix()
        cls.__app_ids, cls.__compressed_matrix = load_mallet_matrix()

        # So we can pre-compute the ranking for every single game, since the compressed matrix is
        # static per instance. Saves us a couple cycles
        cls.__similarities = cls.__compressed_matrix.dot(cls.__compressed_matrix.T)
        cls.__ranking = np.array([np.argsort(row)[::-1] for row in cls.__similarities])

        cls.__app_id_to_index = {app_id: i for i, app_id in enumerate(cls.__app_ids)}

        cls.__game_cache = {game.app_id: game
                            for game in iter_all_games()
                            if game.app_id in cls.__app_id_to_index}

        cls.__name_inverted_index = {game.normalized_name: game.app_id
                                     for game in cls.__game_cache.itervalues()}
        cls.__dimensions = load_feature_names()
        cls.__dimensions_inverted_index = {dim: i for i, dim in enumerate(cls.__dimensions)}

    @classmethod
    def get_from_steamspy(cls, app_id):
        res = requests.get("http://steamspy.com/api.php?request=appdetails&appid=%s"%app_id)
        if not 200 <= res.status_code < 300:
            raise GameNotFoundException(app_id)
        else:
            return cls.from_steampspy_json(res.json())

    @classmethod
    def from_steampspy_json(cls, game):
        # We don"t use any of these guys so we have to delete them
        game.pop("owners_variance", None)
        game.pop("players_forever", None)
        game.pop("players_forever_variance", None)
        game.pop("players_2weeks", None)
        game.pop("players_2weeks_variance", None)
        game.pop("average_forever", None)
        game.pop("average_2weeks", None)
        game.pop("median_forever", None)
        game.pop("median_2weeks", None)
        game.pop("ccu", None)

        game["app_id"] = int(game.pop("appid"))
        game["price"] = float(game["price"] or 0) / 100 # price is in cents

        game["developer"] = game.get("developer", "") or ""
        game["publisher"] = game.get("publisher", "") or ""

        if len(game["tags"]) > 0 and isinstance(game["tags"], dict):
            tags = {k.lower().strip(): v for k, v in game["tags"].iteritems()}
        else:
            tags = dict()
        game["tags"] = tags

        # we have to set the actual userscore and num_reviews to None because this API doesn"t
        # return those values
        game["userscore"] = None
        game["num_reviews"] = None

        if game["score_rank"] == "":
            game["score_rank"] = None
        else:
            game["score_rank"] = game["score_rank"]

        game["last_updated"] = datetime.utcnow()
        return cls(**game)

    @classmethod
    def from_json(cls, game_json):
        game_json["last_updated"] = datetime.utcfromtimestamp(int(game_json["last_updated"]))
        return cls(**game_json)

    @classmethod
    def from_dynamo_json(cls, dynamo_json):
        dynamo_json["name"] = dynamo_json.get("name") or ""
        dynamo_json["normalized_name"] = dynamo_json.get("normalized_name") or ""
        dynamo_json["developer"] = dynamo_json.get("developer") or ""
        dynamo_json["publisher"] = dynamo_json.get("publisher") or ""
        dynamo_json["price"] = float(dynamo_json["price"])
        if dynamo_json["tags"] is not None and len(dynamo_json["tags"]) > 0:
            dynamo_json["tags"] = {k: int(v) for k, v in dynamo_json["tags"].iteritems()}
        else:
            dynamo_json["tags"] = dict()
        dynamo_json["last_updated"] = int(dynamo_json["last_updated"])
        return cls.from_json(dynamo_json)

    @classmethod
    def batch_save(cls, games):
        return utils.batch_save(cls, games)

    @classmethod
    def find_by_name(cls, name):
        game = cls.__name_inverted_index.get(normalize(name))
        if game is not None:
            return cls.get(game)

    @classmethod
    def correct_game_name(cls, game_name, max_results=2):
        game_name = normalize(game_name)
        matches = sorted(cls.__name_inverted_index.keys(), key=partial(distance, game_name))
        return [cls.get(cls.__name_inverted_index[match]) for match in matches[:max_results]]

    @classmethod
    def get(cls, to_get):
        if isinstance(to_get, int):
            return cls.__game_cache.get(to_get)
        if not (isinstance(to_get, set) and len(to_get) > 0):
            raise ValueError("`to_get` must be an int or a non-empty set! (got %s)"%type(to_get))
        results = dict()
        for app_id in to_get:
            # this is a little funky, but it just standardizes how we get a single game, since
            # we can"t really to actual multi-gets from Dynamo.
            results[app_id] = cls.get(app_id)
        return results

    @classmethod
    def get_all(cls):
        return cls.__game_cache.itervalues()

    @classmethod
    def get_from_dynamo(cls, to_get):
        multi = isinstance(to_get, set) and len(to_get) > 0
        if not (multi or isinstance(to_get, int)):
            raise ValueError("`to_get` must be an int or a non-empty set! (got %s)"%type(to_get))
        if multi:
            results = dict()
            for app_id in to_get:
                # this is a little funky, but it just standardizes how we get a single game, since
                # we can"t really to actual multi-gets from Dynamo
                results[app_id] = cls.get(app_id)
            return results
        else:
            return cls.table.query(KeyConditionExpression=Key(cls.hash_key[0]).eq(to_get))

    @classmethod
    def get_all_from_dynamo(cls):
        return imap(cls.from_dynamo_json, utils.table_scan(cls))

    @classmethod
    def get_unscored(cls):
        return (game for game in cls.__game_cache.itervalues() if game.userscore is not None)

    @classmethod
    def get_unscored_from_dynamo(cls, limit=1000):
        attr_cond = Attr("userscore").eq(None)
        return imap(cls.from_dynamo_json,
                    islice(utils.table_scan(cls, FilterExpression=attr_cond, Limit=limit), limit))

    @classmethod
    def get_feature_indices(cls, features):
        return np.array([cls.__dimensions_inverted_index[feature]
                         for feature in features
                         if feature in cls.__dimensions_inverted_index], dtype=np.int)

    @classmethod
    def compute_library_vector(cls, app_id_list, playtimes):
        library_vector = np.zeros(Game.__compressed_matrix.shape[1])
        for app_id, pt in zip(app_id_list, playtimes):
            if app_id in Game.__app_id_to_index:
                library_vector += cls.__game_cache[app_id].vector() * np.log(pt + 1)
        library_vector = normalize_matrix(library_vector)[0]
        return library_vector

    @classmethod
    def compute_ranking_for_vector(cls, query_vector, removed_features, app_id=None):
        new_vector = np.copy(query_vector)
        new_vector[removed_features] = 0
        new_vector = normalize_matrix(new_vector)[0]
        scores = cls.__compressed_matrix.dot(new_vector)
        return [(scores[index], cls.get(cls.__app_ids[index]))
                for index in np.argsort(scores)[::-1]
                if cls.__app_ids[index] != app_id]

    @classmethod
    def get_vector_best_features(cls, vector, json_format=False):
        best_features = np.argsort(vector)[::-1][:MAX_SPIDER_FEATURES]
        best_features.sort()
        if json_format:
            return (json.dumps(vector[best_features].tolist()),
                    json.dumps(cls.__dimensions[best_features].tolist()))
        else:
            return vector[best_features], cls.__dimensions[best_features]

    def __init__(self, app_id, name, developer, publisher, owners, userscore, num_reviews,
                 score_rank, price, tags, last_updated,  **kwargs):
        self.app_id = app_id
        self.name = name
        # this one is in the kwargs because it"s optional but depends on self.name
        self.normalized_name = kwargs.get("normalized_name") or normalize(self.name)
        self.normalized_name = self.normalized_name.encode("ascii")
        self.developer = developer
        self.publisher = publisher
        self.owners = owners
        self.userscore = userscore
        self.num_reviews = num_reviews
        self.score_rank = score_rank
        self.price = price
        self.tags = tags
        self.last_updated = last_updated
        if self.app_id not in Game.__app_id_to_index:
            return
        self.__app_index = Game.__app_id_to_index[self.app_id]
        self.__vector = Game.__compressed_matrix[self.__app_index]
        self.__best_feature_indices = np.argsort(self.vector())[::-1][:MAX_SPIDER_FEATURES]
        # This is just so that the spider chart doens't look so *regular*
        self.__best_feature_indices.sort()

    def __repr__(self):
        return "Game(app_id=%d,name=%s)"%(self.app_id, self.normalized_name)

    def __str__(self):
        return self.__repr__()

    def vector(self):
        if self.app_id not in Game.__app_id_to_index:
            raise GameNotFoundException(self.app_id)
        else:
            return self.__vector

    def vector_parsable(self):
        return ",".join(map(str, self.vector()))

    def steam_url(self):
        return "http://store.steampowered.com/app/%s"%self.app_id

    def steam_image_url(self):
        return "http://cdn.akamai.steamstatic.com/steam/apps/%s/header.jpg"%self.app_id

    def tags_json(self, just_keys=False, encoded=False):
        to_return = None
        if just_keys:
            to_return = json.dumps(sorted(self.tags.keys(), key=self.tags.get, reverse=True))
        else:
            to_return = json.dumps(self.tags)
        if encoded:
            return base64.b64encode(to_return)
        else:
            return to_return

    def offset_vector(self, library_vector, library_vector_weight=0.3, only_best_features=False):
        new_vector = self.vector().copy() + library_vector * library_vector_weight
        new_vector = normalize_matrix(new_vector)[0]
        if only_best_features:
            return new_vector[self.__best_feature_indices]
        else:
            return new_vector


    def get_ranking(self, library_vector, removed_features):
        if self.app_id not in Game.__app_id_to_index:
            raise GameNotFoundException(self.app_id)
        if library_vector is None and len(removed_features) == 0:
            ranking = Game.__ranking[self.__app_index]
            scores = Game.__similarities[self.__app_index, ranking]
            return [(score, Game.get(Game.__app_ids[app_index]))
                    for score, app_index in zip(scores, ranking)
                    if app_index != self.__app_index]
        else:
            query_vector = None
            if library_vector is None:
                query_vector = self.vector()
            else:
                query_vector =  self.offset_vector(library_vector)
            return Game.compute_ranking_for_vector(query_vector,
                                                   removed_features=removed_features,
                                                   app_id=self.app_id)

    def best_features(self, json_format=False):
        features = self.__vector[self.__best_feature_indices]
        if json_format:
            return json.dumps(features.tolist())
        else:
            return features

    def best_feature_names(self, json_format=False):
        dimensions = Game.__dimensions[self.__best_feature_indices]
        if json_format:
            return json.dumps(dimensions.tolist())
        else:
            return dimensions

    def intersect_features(self, other_game, json_format=False):
        features = self.__vector[other_game.__best_feature_indices]
        if json_format:
            return json.dumps(features.tolist())
        else:
            return features

    def compare_features(self, library_vector, json_format=False):
        features = self.__vector[np.argsort(library_vector)[::-1][:MAX_SPIDER_FEATURES]]
        if json_format:
            return json.dumps(features.tolist())
        else:
            return features

    def to_json(self):
        return {
            "app_id": self.app_id,
            "name": self.name,
            "normalized_name": self.normalized_name,
            "developer": self.developer,
            "publisher": self.publisher,
            "owners": self.owners,
            "userscore": self.userscore,
            "num_reviews": self.num_reviews,
            "score_rank": self.score_rank,
            "price": self.price,
            "tags": self.tags if len(self.tags) > 0 else None,
            "last_updated": int(time.mktime(self.last_updated.timetuple())),
        }

    def to_dynamo_json(self):
        dynamo_json = self.to_json()
        dynamo_json["price"] = Decimal(str(self.price))
        dynamo_json["name"] = self.name or None
        dynamo_json["normalized_name"] = self.normalized_name or None
        dynamo_json["developer"] = self.developer or None
        dynamo_json["publisher"] = self.publisher or None
        return dynamo_json

    def save(self):
        Game.table.put_item(Item=self.to_dynamo_json())

    def fetch_more_reviews(self, limit=1000, save=False):
        reviews = Review.get_reviews_from_steam(self.app_id, max_reviews=limit)
        if save:
            Review.batch_save(reviews)
        return reviews

    def get_saved_reviews(self, key_condition, filter_expression, max_items):
        primary_condition = Key(Review.hash_key[0]).eq(self.app_id)
        if key_condition is not None:
            primary_condition = primary_condition & key_condition
        return Review.get(primary_condition, filter_expression, max_items)

    def get_recent_reviews(self, max_reviews=100):
        return self.get_saved_reviews(None, None, max_reviews)

    def update_and_save(self):
        self.update_steamspy_attributes()
        self.update_userscore()
        self.last_updated = datetime.utcnow()
        self.save()

    def update_steamspy_attributes(self):
        new_game = Game.get_from_steamspy(self.app_id)
        self.name = new_game.name
        self.developer = new_game.developer
        self.publisher = new_game.publisher
        self.owners = new_game.owners
        self.userscore = new_game.userscore
        self.num_reviews = new_game.num_reviews
        self.score_rank = new_game.score_rank
        self.price = new_game.price
        self.tags = new_game.tags

    def update_userscore(self):
        page = requests.get("http://store.steampowered.com/app/%s"%self.app_id)
        soup = BeautifulSoup(page.text, "lxml")

        summary_section = soup.find_all("div", class_="summary_section")
        for sec in summary_section:
            title, score, num_reviews = sec.stripped_strings
            if "overall" in title.lower():
                matches = reviews_re.match(num_reviews)
                if score in userscore_to_digit and matches is not None:
                    self.userscore = userscore_to_digit[score]
                    num_reviews, = matches.groups()
                    self.num_reviews = int(num_reviews.replace(",", ""))
                    print("Succesfully updated userscore for", self.app_id)
                    return

        # This is just so that we don"t retry any games that can"t be scored (maybe because they
        # haven"t come out yet) automatically.
        print("Could not update userscore for", self.app_id)
        self.userscore = -2
        self.num_reviews = -2

STEAMSPY_GAMES_JSON = data_file("steamspy_games.json")
def iter_all_games():
    if os.path.exists(STEAMSPY_GAMES_JSON):
        with open(STEAMSPY_GAMES_JSON) as f:
            games_json = json.load(f)
    else:
        games_json = requests.get("http://steamspy.com/api.php?request=all").json()
        with open(STEAMSPY_GAMES_JSON, "w") as f:
            json.dump(games_json, f, default=lambda o: o.__dict__, indent=2)
    for app_id, game in games_json.iteritems():
        if app_id == "999999":
            continue
        yield Game.from_steampspy_json(game)

def normalize(game_name):
    return game_name.lower().encode("ascii", "ignore").strip()

def save_compressed_matrix(app_ids,
                           compressed_matrix,
                           filename=data_file("compressed_matrix.npy")):
    with open(filename, "wb") as f:
        np.save(f, np.column_stack((app_ids, compressed_matrix)))

def load_compressed_matrix(filename=data_file("compressed_matrix.npy")):
    with open(filename, "rb") as f:
        arr = np.load(f)
    return arr[:, 0].astype(np.int), arr[:, 1:]

def load_mallet_matrix(filename=mallet_file("40_features", "doc_matrix.tsv")):
    with open(filename, "r") as f:
        reader = csv.reader(f, delimiter="\t")
        app_ids = list()
        vectors = list()
        for line in reader:
            app_ids.append(np.int(line[1].split("/")[-1]))
            vector = np.array(map(np.float, line[2:]))
            vectors.append(vector)
    return np.array(app_ids), normalize_matrix(np.array(vectors))

def load_feature_names(filename=mallet_file("40_features", "feature_names.csv")):
    with open(filename, "rb") as f:
        return np.array([line.strip() for line in f if len(line) > 0])
