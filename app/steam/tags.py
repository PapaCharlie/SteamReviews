from __future__ import print_function, division

import json
import os
import requests
import re

from bs4 import BeautifulSoup
from util import data_dir

products_re = re.compile("([0-9,]+) products?")
tag_id_re = re.compile("/tags/\?tagid=(\w+)")

class Tag(object):
    @classmethod
    def from_tag_soup(cnstr, tag_soup):
        products, title = tag_soup.get_text("\n", strip=True).split("\n")
        match = products_re.match(products)
        if match:
            count, = map(int, match.groups())

        match = tag_id_re.match(tag_soup.find("a", class_="label")["href"])
        if match:
            tag_id, = match.groups()

        return cnstr(tag_id = tag_id,
                     title = title,
                     count = count)

    def __init__(self, tag_id, title, count):
        self.tag_id = tag_id
        self.title = title
        self.count = count

def get_tags():
    url = "https://steamdb.info/tags/"
    res = requests.get(url)
    if not 200 <= res.status_code < 300:
        msg = "Invalid status code (%d)"%res.status_code
        raise Exception(msg)
    soup = BeautifulSoup(res.text, "lxml")
    tag_soups = soup.find_all("div", class_="span4")
    return map(Tag.from_tag_soup, tag_soups)

if __name__ == '__main__':
    tags = get_tags()
    with open(os.path.join(data_dir, "tags.json"), "w") as f:
        json.dump(tags, f, default=lambda o: o.__dict__, indent=2)

