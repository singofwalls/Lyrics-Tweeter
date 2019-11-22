#!/usr/bin/env python3.7
import lyricsgenius
import spotipy
import spotipy.util
import twitter
import pylast
import requests

import json
import random
import urllib
import datetime
import traceback
import os
import re

from functools import reduce


CHANCE_TO_TWEET = 40
CHANCE_TO_ADD_LINE = 2
TWEET_LIMIT = 280

LOG_FILE = "log.txt"
LOG_SIZE = 10000
LOG_TIMESTAMP = "%b %d, %Y %I:%M:%S %p"

GITHUB_LINK = "https://github.com/singofwalls/Lyrics-Tweeter"


def get_lastfm_link(artist, track, l_creds):
    """Get a link to the song from last fm based on artist and name."""
    pass_hash = pylast.md5(l_creds["password"])
    network = pylast.LastFMNetwork(api_key=l_creds["api key"], 
                                   api_secret=l_creds["shared secret"], 
                                   username=l_creds["username"], 
                                   password_hash=pass_hash)

    song = network.get_track(artist, track)
    if isinstance(song, type(None)):
        log("Song not found on Lastfm trying remove parens")
        song_search = re.sub("\([\w\W]*\)", "", track)
        song = network.get_track(artist, track)
        if isinstance(song, type(None)):
            log(f"Song {song_search} by {artist} not found on Last.fm")
            return
    return song.get_url() + "/+lyrics"


def get_apple_link(query):
    """Get a link to the song from Apple based on artist, name, and album."""

    response = requests.get(f"https://itunes.apple.com/search?term={query}&limit=1")
    if not response.ok or not response.content:
        return ""

    content = json.loads(response.content)
    results = content["results"]
    if not results:
        return ""

    url = results[0]["trackViewUrl"]
    return url


def get_spotify(s_creds):
    """Get the spotify object from which to make requests."""
    # Authorize Spotify
    token = spotipy.util.prompt_for_user_token(
        s_creds["username"],
        s_creds["scopes"],
        s_creds["client_id"],
        s_creds["client_secret"],
        s_creds["redirect_uri"],
    )

    return spotipy.Spotify(auth=token)


def get_twitter(t_creds):
    """Get the twitter object from which to make requests."""
    # Authorize Twitter
    api = twitter.Api(
        t_creds["consumer key"],
        t_creds["consumer secret"],
        t_creds["access token"],
        t_creds["access token secret"],
    )

    return api


def main():

    with open("creds.json") as f:
        creds = json.load(f)

    spotify = get_spotify(creds["spotify"])
    current_song = spotify.current_user_playing_track()

    if isinstance(current_song, type(None)):
        log("Not playing a song currently")
        return

    song_name = current_song["item"]["name"]
    artist_name = current_song["item"]["artists"][0]["name"]
    album_name = current_song["item"]["album"]["name"]

    log(f"Playing {song_name} by {artist_name}")

    genius = lyricsgenius.Genius(creds["genius"]["client access token"])
    song = genius.search_song(song_name, artist_name)
    if isinstance(song, type(None)):
        log("Song not found on Genius trying remove parens")
        song_search = re.sub("\([\w\W]*\)", "", song_name)
        song = genius.search_song(song_search, artist_name)
        if isinstance(song, type(None)):
            log(f"Song {song_search} by {artist_name} not found on Genius")
            return

    paragraphs = song.lyrics.split("\n\n")

    if not paragraphs:
        log("No paragraphs")
        return

    if random.randrange(0, CHANCE_TO_TWEET):
        # One in ten chance to tweet lyrics
        log("Failed roll")
        return

    chosen_lines = [set()] * len(paragraphs)
    chosen_paragraphs = set()
    selected_lines = []
    while len(paragraphs) != len(chosen_paragraphs):
        paragraph_num = random.choice(
            list(set(range(0, len(paragraphs))) - chosen_paragraphs)
        )
        paragraph = paragraphs[paragraph_num]

        lines = [line for line in paragraph.split("\n") if line and line[0] != "["]
        start = random.choice(
            list(set(range(0, len(lines))) - chosen_lines[paragraph_num])
        )
        chosen_lines[paragraph_num].add(start)
        if len(lines) == len(chosen_lines[paragraph_num]):
            chosen_paragraphs.add(paragraph_num)

        selected = lines[start]
        long_sentence = False
        while len(selected) > TWEET_LIMIT:
            if "." in selected:
                selected = ".".join(selected.split(".")[:-1])
            else:
                long_sentence = True
                break

        if long_sentence:
            continue

        selected_lines = [selected]
        while random.randrange(0, CHANCE_TO_ADD_LINE):
            next_line_num = start + len(selected_lines)
            if next_line_num >= len(lines):
                break

            next_line = lines[next_line_num]
            current_len = len("\n".join(selected_lines))
            if current_len + len(next_line) > TWEET_LIMIT:
                break
            selected_lines.append(next_line)
        break

    status = "\n".join(selected_lines)
    log("Tweeting:\n" + status)

    twit = get_twitter(creds["twitter"])
    tweet = twit.PostUpdate(status)

    query = " ".join((artist_name, song_name, album_name))
    query = re.sub("\([\w\W]*\)", "", query)  # Remove stuff in parens
    query = urllib.parse.quote_plus(query)

    apple_link = get_apple_link(query)
    genius_link = song.url
    spotify_link = current_song["item"]["external_urls"]["spotify"]

    lastfm_link = get_lastfm_link(artist_name, song_name, creds["lastfm"])

    reply = f"\n\ngenius: {genius_link}"
    if lastfm_link:
        reply += f"\nlastfm: {lastfm_link}"
    if apple_link:
        reply += f"\napple: {apple_link}"
    reply += f"\nspotify: {spotify_link}"
    twit.PostUpdate(reply, in_reply_to_status_id=tweet.id)


def log(message):
    """Log to the log file."""
    # Halve log if greater than 1000 lines
    print(message)

    
    with open(LOG_FILE, "a") as log:
        log.write(datetime.datetime.now().strftime(
            LOG_TIMESTAMP) + " " + message + "\n")

    with open(LOG_FILE) as f:
        contents = f.read()
        lines_num = contents.count("\n")
        if lines_num > LOG_SIZE:
            lines = contents.split("\n")
            line_index = lines_num - LOG_SIZE
            lines = lines[line_index:]

            with open(LOG_FILE, "w") as f:
                f.write("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        tb = traceback.format_exception(etype=type(e), value=e,
                                        tb=e.__traceback__)
        log("ERROR\n" + "".join(tb))
        raise e
