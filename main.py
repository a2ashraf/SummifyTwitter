import time

import requests
import keys
import tweepy
import openai
import json
import schedule
import socket
import os

MOST_RECENT_ID_CHECKED = "most_recent_checked.txt"

SEARCH_QUERY = "@a2ashraf spring-nose"
ALREADY_REPLIED = "Already replied to this tweet"
IGNORE_RETWEETS = "IGNORE RETWEETS"
IGNORE_TOO_MANY_MENTIONS = "I only reply to the original author"

root_tweet = None


def auth():
    print("Authenticating...")
    auth = tweepy.OAuthHandler(keys.api_key, keys.api_secret_key)
    auth.set_access_token(keys.access_token, keys.access_token_secret)
    return auth


def api(auth):
    print("Creating Tweepy API object...")
    api = tweepy.API(auth)
    return api


def client(api: tweepy.API):
    print("Creating Tweepy client object...")
    client = tweepy.Client(api)
    return client


def get_mentions(api: tweepy.API):
    print("Retrieving mentions...")
    mentions = api.mentions_timeline(tweet_mode="extended", since_ids=None, max_id=None)
    mention_id = None
    reply_in_status_id = None

    for mention in mentions:
        if "spring-nose" in mention.full_text:
            mention_id = mention.id_str
            reply_in_status_id = mention.in_reply_to_status_id_str
    return mention_id, reply_in_status_id


def create_tinyurl(api_token, url, domain=None, alias=None, tags=None, expires_at=None):
    print("Creating TinyURL...")
    # set up the API endpoint URL
    endpoint_url = "https://api.tinyurl.com/create"

    # set up the headers and data for the request
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    data = {"url": url}

    # add optional parameters to the data if provided
    if domain is not None:
        data["domain"] = domain
    if alias is not None:
        data["alias"] = alias
    if tags is not None:
        data["tags"] = tags
    if expires_at is not None:
        data["expires_at"] = expires_at

    # make the API call
    response = requests.post(endpoint_url, headers=headers, data=json.dumps(data), params={"api_token": api_token})

    # check the response status code
    if response.status_code != 200:
        raise Exception("Failed to create TinyURL. Status code: {}".format(response.status_code))

    # return the JSON response
    return response.json()['data']['tiny_url']


def post_tweet(api: tweepy.API, message: str, id: str = None):
    try:
        # api.update_status(message, in_reply_to_status_id=id, auto_populate_reply_metadata=True)
        api.update_status(message, auto_populate_reply_metadata=True)
        print("Tweet posted:", message)
    except tweepy.TweepyException as e:
        print("Failed to post tweet:", e)


def get_tweets_text(api, tweet_id):
    print("Getting text for tweet with ID:", tweet_id)
    if tweet_id is None:
        return None
    tweet = api.get_status(tweet_id, tweet_mode="extended")
    tweet_text = tweet.full_text
    num_mentions = tweet.full_text.count("@")

    if tweet.full_text.startswith("RT"):
        print("Ignoring retweet")
        return IGNORE_RETWEETS
    elif num_mentions > 2:
        print("Ignoring tweet with too many mentions")
        while tweet.in_reply_to_status_id_str is not None:
            tweet = api.get_status(tweet.in_reply_to_status_id_str, tweet_mode="extended")
            if ALREADY_REPLIED in tweet.full_text:
                return ALREADY_REPLIED

        return IGNORE_TOO_MANY_MENTIONS
    else:
        print("Found tweet to summarize")
        while tweet.in_reply_to_status_id_str is not None:
            tweet = api.get_status(tweet.in_reply_to_status_id_str, tweet_mode="extended")
            tweet_text = tweet.full_text + "\n\n" + tweet_text
            if tweet.in_reply_to_status_id_str is None:
                global root_tweet
                root_tweet = tweet
        return tweet_text


def summaryze(key, text):
    print("Summarizing text")
    openai.api_key = key
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "You can summarize text shared with you without losing context or meaning including with an emphasis on numerical data "},
            {"role": "user", "content": text}
        ])
    return response.choices[0].message.content


def write_to_file(file_path, text):
    print("Writing to file:", file_path)
    try:
        with open(file_path, "r+") as file:
            file_content = file.read()
            file.seek(0, 0)
            file.write(text.rstrip('\r\n') + '\n' + file_content)
        return True
    except Exception as e:
        print("Error writing to file:", e)
        return False


def write_json_to_file(file_path, summary):
    print("Writing JSON to file:", file_path)
    try:
        with open(file_path, "w") as file:
            json.dump(summary, file, indent=4)
        return True
    except Exception as e:
        print("Error writing JSON to file:", e)
        return False


def read_first_line(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            file.write("")
            print(f"{file_path} created.")
            return ""

    with open(file_path, "r") as file:
        first_line = file.readline().strip()
        print(f"Read first line from {file_path}: {first_line}")
    return first_line


def convert_to_json(summary, id, root_tweet):
    json_string = {
        "id": id,
        "summary": summary,
        "root_tweet_image": root_tweet.user.profile_image_url,
        "root_tweet_name": root_tweet.user.name,
        "root_tweet_text": root_tweet.full_text,
        "root_tweet_screen_name": root_tweet.user.screen_name,
        "root_tweet_url": f"https://twitter.com/{root_tweet.user.screen_name}/status/{root_tweet.id}"
    }

    return json_string


def summaryze_where_needed(api, client):
    most_recent_checked = read_first_line(MOST_RECENT_ID_CHECKED)
    if most_recent_checked == "":
        tweets = client.search_recent_tweets(query=SEARCH_QUERY)
    else:
        tweets = client.search_recent_tweets(query=SEARCH_QUERY, since_id=most_recent_checked)

    if tweets.data is None:
        print("No tweets found")
        return

    parent_id = tweets.data[0].id
    most_recent_checked = parent_id
    write_to_file(MOST_RECENT_ID_CHECKED, str(most_recent_checked))
    for tweet in tweets.data:

        print("       _")
        print("    __(.)<")
        print("    \\___)")
        print("      / \\")
        print("\n\nChecking tweet:", tweet.text)
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
            print("Summarizing tweet:", tweet.text)
            summary = summaryze(keys.open_ai_key, thead_as_text)
            print("Summary:", summary)
            get_json_from_summary = convert_to_json(summary, tweet.id, root_tweet)
            write_json_to_file(f'/Users/ahsana/Documents/development/summeryze/threads/{tweet.id}.json',
                               get_json_from_summary)
            tiny_url = get_tiny_url(tweet)
            print("TinyURL:", tiny_url)
            post_tweet(api, f"Here is the summary:\n {tiny_url}", id=tweet.id)


def get_tiny_url(tweet):
    print("Getting tiny url")

    is_local = is_local_execution()
    if (is_local):
        print(f"Summary page URL: http://localhost:3000/page/{tweet.id}")
        tiny_url = create_tinyurl(api_token=keys.tinyurl_key, url=f'http://localhost:3000/page/{tweet.id}')
    else:
        print(f"Summary page URL: https://summeryze.com/page/{tweet.id}")
        tiny_url = create_tinyurl(api_token=keys.tinyurl_key, url=f'http://summeryze.com/page/{tweet.id}')

    return tiny_url


def is_local_execution():
    hostname = socket.gethostname()
    print("Your Computer Name is:" + hostname)
    if hostname == "Ahsans-MacBook-Pro.local":
        return True


auth = auth()
api = api(auth)
client = client(keys.bearer_token)
print("starting")
schedule.every(4).seconds.do(summaryze_where_needed, api, client)

while True:
    schedule.run_pending()
    print("sleeping")
    time.sleep(5)
