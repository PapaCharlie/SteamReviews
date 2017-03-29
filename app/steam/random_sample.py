from __future__ import print_function, division

import json
import os
import random
import review

from util import data_dir
from operator import itemgetter

if __name__ == '__main__':
    with open(os.path.join(data_dir, "app_ids.json")) as f:
        apps = json.load(f)
    apps_sample = random.sample(apps, 250)
    reviews = dict()
    for app in apps_sample:
        print("Getting reviews for %s"%app["name"].encode('ascii', 'ignore'))
        reviews[app["app_id"]] = review.get_app_reviews(app["app_id"],
                                                        max_reviews=100)
        # Just save every time so we don't lose our progress
        with open(os.path.join(data_dir, "reviews.json"), "w") as f:
            json.dump(reviews, f, default=lambda o: o.__dict__, indent=2)
