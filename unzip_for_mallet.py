import json
import re

from nltk.tokenize import word_tokenize

token_re = re.compile(r"([a-z0-9]+((-|/)[a-z0-9]+)?)")

def num_tokens(body):
    review_str = body.encode('ascii', 'ignore')
    tokens = word_tokenize(review_str)
    token_count = 0
    for token in tokens:
        lower_token = token.lower()
        match = token_re.match(lower_token)

        # verify that the regex matches the whole token
        if match != None and match.group(0) == lower_token:
            if '/' in lower_token:
                token_count += len(lower_token.split('/'))
            else:
                token_count += 1

    return token_count

def main():
    with open("data/uncompressed_reviews.json", "r") as f:
        reviews = json.load(f)
    app_ids = reviews.keys()
    for app_id in app_ids:
        with open("data/cut_reviews/%s"%app_id, "w") as f:
            toks = 0
            if len(reviews[app_id]) >= 100:
                for r in reviews[app_id]:
                    if toks > 5000:
                        break
                    else:
                        toks += num_tokens(r["body"])
                        f.write(r["body"].encode("ascii", "ignore"))
                    f.write("\n")
        del reviews[app_id]

if __name__ == '__main__':
    main()
