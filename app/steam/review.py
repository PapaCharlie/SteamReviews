from __future__ import print_function, division

import requests
import re

from bs4 import BeautifulSoup

people_re_part = "(?:person|people)"
helpful_re = re.compile("(-?[0-9,]+) of ([0-9,]+) " + people_re_part)
funny_re = re.compile("(-?[0-9,]+) " + people_re_part)
on_record_re = re.compile("(-?[0-9,]+\.?\d*) hrs? on record")
products_re = re.compile("(-?[0-9,]+) products? in account")
reviews_re = re.compile("(-?[0-9,]+) reviews?")

class Review(object):
    @classmethod
    def from_review_soup(cnstr, app_id, review_id, review_soup):
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
                msg = "Could not match \"%s\" with \"%s\""%(compiled_re.pattern,
                                                            text)
                raise Exception(msg)
            return map(lambda g: dtype(g.replace(",", "")), match.groups())

        body = find_div_text("content") or ""
        reviewer = find_div_text("persona_name") or ""
        date = find_div_text("postedDate") or ""

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
            num_owned_games, = get_numerical_groups(num_owned_games_div,
                                                    products_re,
                                                    int)
        else:
            num_owned_games = 0

        num_reviews_div = find_div_text("num_reviews")
        if num_reviews_div is not None:
            num_reviews, = get_numerical_groups(find_div_text("num_reviews"),
                                                reviews_re,
                                                int)
        else:
            num_reviews = 0

        avatar_url = review_soup.find("div", class_="avatar").find("a")["href"]
        reviewer_id = filter(lambda s: len(s) > 0, avatar_url.split("/"))[-1]

        return cnstr(review_id=review_id,
                     app_id=app_id,
                     reviewer_id=reviewer_id,
                     reviewer=reviewer,
                     body=body,
                     date=date,
                     helpful=helpful,
                     total=total,
                     funny=funny,
                     is_recommended=is_recommended,
                     on_record=on_record,
                     num_owned_games=num_owned_games,
                     num_reviews=num_reviews)

    def __init__(self, review_id, app_id, reviewer_id, reviewer, body, date,
                 helpful, total, funny, is_recommended, on_record,
                 num_owned_games, num_reviews):
        self.review_id = review_id
        self.app_id = app_id
        self.reviewer_id = reviewer_id
        self.reviewer = reviewer
        self.body = body
        self.date = date
        self.helpful = helpful
        self.total = total
        self.funny = funny
        self.is_recommended = is_recommended
        self.on_record = on_record
        self.num_owned_games = num_owned_games
        self.num_reviews = num_reviews

def get_app_reviews(app_id, max_reviews=1000, filter="all", language="english"):
    reviews = dict()
    params = {
        "day_range": "9223372036854776000",
        "filter": filter,
        "language": language
    }
    offset = 0
    while len(reviews) < max_reviews:
        params["start_offset"] = offset
        url = "http://store.steampowered.com/appreviews/%s"%app_id
        print("Getting %s with %s"%(url, params))
        r = requests.get(url, params=params)

        json = r.json()
        if json.get('success') != 1 or not 200 <= r.status_code < 300:
            break

        soup = BeautifulSoup(json['html'], "lxml")
        review_box = soup.find_all('div', class_="review_box")
        added = 0
        for review_id, review in zip(json['recommendationids'], review_box):
            if review_id not in reviews:
                reviews[review_id] = Review.from_review_soup(app_id,
                                                             review_id,
                                                             review)
                added += 1

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

if __name__ == '__main__':
    print(get_app_reviews("396750", 1000))
