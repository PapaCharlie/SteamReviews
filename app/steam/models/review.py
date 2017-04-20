from __future__ import print_function, division, unicode_literals

import decimal
import requests
import re

from app.dynamodb import dynamodb, utils
from app.steam.util import data_file
from bs4 import BeautifulSoup
from datetime import datetime
from nltk.tokenize import word_tokenize
from progressbar import ProgressBar, UnknownLength

people_re_part = "(?:person|people)"
helpful_re = re.compile("(-?[0-9,]+) of ([0-9,]+) " + people_re_part)
funny_re = re.compile("(-?[0-9,]+) " + people_re_part)
on_record_re = re.compile("(-?[0-9,]+\.?\d*) hrs? on record")
products_re = re.compile("(-?[0-9,]+) products? in account")
reviews_re = re.compile("(-?[0-9,]+) reviews?")


class Review(object):
    table_name = "reviews"
    table = dynamodb.Table(table_name)
    hash_key = ("app_id", utils.NUMBER)
    sorting_key = ("review_date_review_id", utils.STRING)

    @classmethod
    def create_table(cls):
        utils.create_dynamo_table(cls)

    @classmethod
    def from_review_soup(cls, app_id, review_id, review_soup):
        def find_div_text(div_class, sep="\n", strip=True):
            div = review_soup.find('div', class_=div_class)
            if div is not None:
                return div.get_text(sep, strip=strip)

        def get_numerical_groups(text, compiled_re, dtype):
            """
            Find the first div with the class attribute, extract groups using
            the re and apply float to all
            """
            match = compiled_re.match(text)
            if match is None:
                msg = "Could not match \"%s\" with \"%s\""%(compiled_re.pattern, text)
                raise Exception(msg)
            return map(lambda g: dtype(g.replace(",", "")), match.groups())

        body = find_div_text("content") or ""
        reviewer = find_div_text("persona_name") or ""

        date_text = find_div_text("postedDate") or "Posted: July 20, 1969"
        try:
            review_date = datetime.strptime(date_text, "Posted: %B %d, %Y").date()
        except ValueError:
            # Reviews left in this year don't have a date, so we just default to this year's date
            review_date = datetime.strptime(date_text, "Posted: %B %d").date()
            review_date.replace(year=datetime.now().year)

        helpful, total, funny = 0, 0, 0
        header = find_div_text("header")
        if header:
            for line in header.split("\n"):
                line = line.lower()
                if "helpful" in line:
                    helpful, total = get_numerical_groups(line, helpful_re, int)
                if "funny" in line:
                    funny, = get_numerical_groups(line, funny_re, int)

        thumb = review_soup.find("div", class_="thumb")
        is_recommended = "thumbsup" in thumb.find("img")["src"].lower()

        hours_div = find_div_text("hours")
        if hours_div is not None:
            on_record, = get_numerical_groups(hours_div, on_record_re, float)
        else:
            on_record = 0

        num_owned_games_div = find_div_text("num_owned_games")
        if num_owned_games_div is not None:
            num_owned_games, = get_numerical_groups(num_owned_games_div, products_re, int)
        else:
            num_owned_games = 0

        num_reviews_div = find_div_text("num_reviews")
        if num_reviews_div is not None:
            num_reviews, = get_numerical_groups(find_div_text("num_reviews"), reviews_re, int)
        else:
            num_reviews = 0

        avatar_url = review_soup.find("div", class_="avatar").find("a")["href"]
        reviewer_id = filter(lambda s: len(s) > 0, avatar_url.split("/"))[-1]

        return cls(app_id=app_id,
                   review_id=review_id,
                   review_date=review_date,
                   reviewer_id=reviewer_id,
                   reviewer=reviewer,
                   body=body,
                   helpful=helpful,
                   total=total,
                   funny=funny,
                   is_recommended=is_recommended,
                   on_record=on_record,
                   num_owned_games=num_owned_games,
                   num_reviews=num_reviews)

    @classmethod
    def fetch_new_reviews(cls,
                          app_id,
                          stop_id=None,
                          limit=1000,
                          review_filter="all",
                          language="english"):
        reviews = dict()
        params = {
            "day_range": "9223372036854776000",
            "filter": review_filter,
            "language": language
        }
        offset = 0
        while len(reviews) < limit:
            params["start_offset"] = offset
            url = "http://store.steampowered.com/appreviews/%s"%app_id
            res = requests.get(url, params=params)

            json = res.json()
            if json.get('success') != 1 or not 200 <= res.status_code < 300:
                break

            soup = BeautifulSoup(json['html'], "lxml")
            review_box = soup.find_all('div', class_="review_box")
            added = 0
            with ProgressBar(max_value=UnknownLength) as progress:
                for review_id, review in zip(json['recommendationids'], review_box):
                    if stop_id is not None and review_id == stop_id:
                        return reviews.values()
                    if review_id not in reviews:
                        reviews[review_id] = cls.from_review_soup(app_id, review_id, review)
                        added += 1
                        progress.update(added)

            if added == 0:
                break

            # The way offset increases needs to be verified
            if offset == 0:
                offset = 5
            elif offset == 5:
                offset = 25
            else:
                offset += 25
        return reviews.values()

    @classmethod
    def fetch_top_rate(cls, app_id, positive=True, limit=500):
        if positive:
            url = "http://steamcommunity.com/app/%d/positivereviews/?browsefilter=toprated"%app_id
        else:
            url = "http://steamcommunity.com/app/%d/negativereviews/?browsefilter=toprated"%app_id


    @classmethod
    def from_json(cls, json):
        json["review_date"] = datetime.strptime(json["review_date"], "%Y-%m-%d").date()
        return cls(**json)

    @classmethod
    def from_dynamo_json(cls, dynamo_json):
        dynamo_json["on_record"] = float(dynamo_json["on_record"])
        return cls.from_json(dynamo_json)

    @classmethod
    def batch_save(cls, reviews):
        return utils.batch_save(cls, reviews)

    @classmethod
    def get(cls, key_condition, filter_expression, max_items, ascending=False):
        kwargs = {
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": ascending # get reviews in descending chronological order
        }
        if filter_expression is not None:
            kwargs["FilterExpression"] = filter_expression
        if max_items is not None:
            kwargs["Limit"] = max_items

        return map(cls.from_dynamo_json, utils.query(cls, **kwargs))

    def __init__(self, app_id, review_id, review_date, reviewer_id, reviewer, body, helpful, total,
                 funny, is_recommended, on_record, num_owned_games, num_reviews, **kwargs):
        self.app_id = app_id
        self.review_id = review_id
        self.review_date = review_date
        self.review_date_review_id = self.review_date.isoformat() + ":" + str(self.review_id)
        self.reviewer_id = reviewer_id
        self.reviewer = reviewer
        self.body = body
        self.helpful = helpful
        self.total = total
        self.funny = funny
        self.is_recommended = is_recommended
        self.on_record = on_record
        self.num_owned_games = num_owned_games
        self.num_reviews = num_reviews

    def to_json(self):
        return {
            "app_id": self.app_id,
            "review_id": self.review_id,
            "review_date": self.review_date.isoformat(),
            "review_date_review_id": self.review_date_review_id,
            "reviewer_id": self.reviewer_id,
            "reviewer": self.reviewer,
            "body": self.body,
            "helpful": self.helpful,
            "total": self.total,
            "funny": self.funny,
            "is_recommended": self.is_recommended,
            "on_record": self.on_record,
            "num_owned_games": self.num_owned_games,
            "num_reviews": self.num_reviews,
        }

    def to_dynamo_json(self):
        dynamo_json = self.to_json()
        # str here is ghetto af but it's the only way not to get rounding errors
        dynamo_json["on_record"] = decimal.Decimal(str(self.on_record))
        for k in dynamo_json:
            if dynamo_json[k] == "":
                dynamo_json[k] = None
        return dynamo_json

    def save(self):
        Review.table.put_item(Item=self.to_dynamo_json())

    def get_tokens(self):
        punc_regex = r'[!\"#\$%&\'\(\)\*\+,-\./:;<=>\?@\[\\\]\^_`{\|}~]+'
        # excludes situations such as boy-friend/girl-friend - but inconsequential
        token_re = r'([a-z0-9]+((-|/)[a-z0-9]+)?)'

        review_str = self.body.encode('ascii', 'ignore')
        tokens = word_tokenize(review_str)
        filtered_tokens = []
        for token in tokens:
            lower_token = str.lower(token)
            match = re.match(token_re, lower_token)

            # verify that the regex matches the whole token
            if match != None and match.group(0) == lower_token:
                if '/' in lower_token:
                    for elem in lower_token.split('/'):
                        filtered_tokens.append(elem)
                else:
                    filtered_tokens.append(lower_token)

        return filtered_tokens

def saved_review_generator():
    import json
    reviews_file = data_file("reviews.json")
    with open(reviews_file) as f:
        reviews = json.load(f)
    for app_id in reviews:
        for i in xrange(len(reviews[app_id])):
            yield Review.from_json(reviews[app_id][i])
