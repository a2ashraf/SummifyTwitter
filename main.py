import os

import keys
import tweepy
import openai
import json

MOST_RECENT_ID_CHECKED = "most_recent_checked.txt"

SEARCH_QUERY = "@a2ashraf spring-nose"
ALREADY_REPLIED = "Already replied to this tweet"
IGNORE_RETWEETS = "IGNORE RETWEETS"
IGNORE_TOO_MANY_MENTIONS = "I only reply to the original author"


def auth():
    auth = tweepy.OAuthHandler(keys.api_key, keys.api_secret_key)
    auth.set_access_token(keys.access_token, keys.access_token_secret)
    return auth


def api(auth):
    api = tweepy.API(auth)
    return api


def client(api: tweepy.API):
    client = tweepy.Client(api)
    return client


# whatever the fk a mention is....
def get_mentions(api: tweepy.API):
    mentions = api.mentions_timeline(tweet_mode="extended", since_ids=None, max_id=None)
    mention_id = None
    reply_in_status_id = None

    for mention in mentions:
        if ("spring-nose" in mention.full_text):
            mention_id = mention.id_str
            reply_in_status_id = mention.in_reply_to_status_id_str
    return mention_id, reply_in_status_id


def post_tweet(api: tweepy.API, message: str, id: str = None):
    # api.update_status(message, auto_populate_reply_metadata=True)
    # api.update_status(message, in_reply_to_status_id=id, auto_populate_reply_metadata=True)
    pass


def get_tweets_text(api, tweet_id):
    if tweet_id is None:
        return None
    tweet = api.get_status(tweet_id, tweet_mode="extended")
    tweet_text = tweet.full_text
    num_mentions = tweet.full_text.count("@")

    if tweet.full_text.startswith("RT"):
        return IGNORE_RETWEETS
    elif num_mentions > 2:
        while tweet.in_reply_to_status_id_str is not None:
            tweet = api.get_status(tweet.in_reply_to_status_id_str, tweet_mode="extended")
            if ALREADY_REPLIED in tweet.full_text:
                return ALREADY_REPLIED

        return IGNORE_TOO_MANY_MENTIONS
    else:

        while tweet.in_reply_to_status_id_str is not None:
            tweet = api.get_status(tweet.in_reply_to_status_id_str, tweet_mode="extended")
            tweet_text = tweet.full_text + "\n\n" + tweet_text

    return tweet_text


# openai summarization
def summaryze(key, text):
    openai.api_key = key
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "You can summarize text shared with you without losing context or meaning including with an emphasis on numerical data "},
            {"role": "user", "content": text}
        ])
    return response.choices[0].message.content


def has_been_retweeted(api, parent_id):
    retweets = api.get_retweets(parent_id)
    for retweet in retweets:
        if retweet.user.screen_name == "a2ashraf":
            return True

def write_to_file(file_path, text):
    try:
        with open(file_path, "r+") as file:
            file_content = file.read()
            file.seek(0, 0)
            file.write(text.rstrip('\r\n') + '\n' + file_content)
        return True
    except:
        return False


def write_json_to_file(file_path, summary):
    try:
        with open(file_path, "w") as file:
            json.dump(summary, file, indent=4)
        return True
    except:
        return False


def read_first_line(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            file.write("")
            return ""

    with open(file_path, "r") as file:
        first_line = file.readline().strip()
    return first_line


def convert_to_json(summary, id):
    json = {
        "id": id,
        "summary": summary
    }
    return json


if __name__ == "__main__":
    auth = auth()
    api = api(auth)
    client = client(keys.bearer_token)

    most_recent_checked = read_first_line(MOST_RECENT_ID_CHECKED)
    if most_recent_checked == "":
        tweets = client.search_recent_tweets(query=SEARCH_QUERY)
    else:
        tweets = client.search_recent_tweets(query=SEARCH_QUERY, since_id=most_recent_checked)

    if tweets.data is None:
        print("No tweets found")
        exit(0)

    parent_id = tweets.data[0].id
    most_recent_checked = parent_id
    write_to_file(MOST_RECENT_ID_CHECKED, str(most_recent_checked))
    for tweet in tweets.data:
        a_tweet = api.get_status(tweet.id)
        a_tweet_client = client.get_tweet(id=tweet.id)
        thead_as_text = get_tweets_text(api, tweet.id)
        if thead_as_text == ALREADY_REPLIED:
            print(ALREADY_REPLIED)
            post_tweet(api, ALREADY_REPLIED, id=tweet.id)
        elif thead_as_text == IGNORE_RETWEETS:
            print(IGNORE_RETWEETS)
        elif thead_as_text == IGNORE_TOO_MANY_MENTIONS:
            print(IGNORE_TOO_MANY_MENTIONS)
            post_tweet(api, IGNORE_TOO_MANY_MENTIONS, id=tweet.id)
        else:
            summary = summaryze(keys.open_ai_key, thead_as_text)
            print(summary)
            get_json_from_summary = convert_to_json(summary, tweet.id)
            write_json_to_file(f'/Users/ahsana/Documents/development/summeryze/threads/{tweet.id}.json',
                               get_json_from_summary)
            # print(f'file:///Users/ahsana/Documents/development/summeryze/threads/{tweet.id}.json')
            print(f'http://localhost:3000/page/{tweet.id}')
            # post_tweet(api, "link here", id=tweet.id)
