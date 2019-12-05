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
import string

from functools import reduce


CHANCE_TO_TWEET = 150
CHANCE_TO_ADD_LINE = 3
TWEET_LIMIT = 280

LOG_FILE = "log.txt"
LOG_SIZE = 10000
LOG_TIMESTAMP = "%b %d, %Y %I:%M:%S %p"

GITHUB_LINK = "https://github.com/singofwalls/Lyrics-Tweeter"

CREDS_FILE = "creds.json"
PREV_SONGS = "previous_songs.json"
MAX_PREV_SONGS = 100
REPLAY_REDUCE_FACTOR = (
    3  # Divide CHANCE_TO_TWEET by this if song previously played in last MAX_PREV_SONGS
)


def get_lastfm_link(artist, track, l_creds):
    """Get a link to the song from last fm based on artist and name."""
    pass_hash = pylast.md5(l_creds["password"])
    network = pylast.LastFMNetwork(
        api_key=l_creds["api key"],
        api_secret=l_creds["shared secret"],
        username=l_creds["username"],
        password_hash=pass_hash,
    )

    song = network.get_track(artist, track)
    if isinstance(song, type(None)):
        log("Song not found on Lastfm trying remove parens")
        song_search = remove_parens(track)
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


def get_spotify(s_creds, usernum):
    """Get the spotify object from which to make requests."""
    # Authorize Spotify
    cache_path = f"cache/{usernum}/"
    try:
        os.mkdir(cache_path)
    except FileExistsError:
        pass
    except FileNotFoundError:
        os.mkdir("cache")
        os.mkdir(cache_path)

    token = spotipy.util.prompt_for_user_token(
        s_creds["usernames"][usernum],
        s_creds["scopes"],
        s_creds["client_id"],
        s_creds["client_secret"],
        s_creds["redirect_uri"],
        cache_path + ".cache",
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


def remove_parens(name):
    """Remove the parentheses from a song name."""
    return re.sub("\([\w\W]*\)", "", name)


def clean(name):
    """Remove potential discrepencies from the string."""
    return "".join(list(filter(lambda c: c in (string.ascii_letters + string.digits + " "), remove_parens(name)))).lower().strip()


def match(song, other):
    """Determine whether a song matches the result"""
    artist_name = clean(song[1]) 
    other_artist = clean(other[1])
    if artist_name != other_artist:
        log(f"{artist_name} != {other_artist}")
        return False

    song_name = clean(song[0])
    other_name = clean(other[0])
    if song_name in other_name or other_name in song_name:
        return True

    log(f"{song_name} does not match {other_name}")
    return False


def run(usernum, creds):

    spotify = get_spotify(creds["spotify"], usernum)
    current_song = spotify.current_user_playing_track()
    current_user = creds["spotify"]["usernames"][usernum]

    if isinstance(current_song, type(None)) or not current_song["is_playing"]:
        log(f"{current_user} not playing a song currently")
        return

    song_name = current_song["item"]["name"]
    artist_name = current_song["item"]["artists"][0]["name"]
    album_name = current_song["item"]["album"]["name"]
    progress = current_song["progress_ms"]
    song_label = (song_name, artist_name, progress)

    log(f"{current_user} playing {song_name} by {artist_name}")

    # Track previously played songs
    try:
        with open(PREV_SONGS) as f:
            prev_songs_all = json.load(f)
    except FileNotFoundError:
        prev_songs_all = {current_user: []}

    if current_user not in prev_songs_all:
        prev_songs_all[current_user] = []

    # Add current song
    prev_songs = list(map(tuple, prev_songs_all[current_user]))

    replayed = bool(
        prev_songs
        and prev_songs[-1][:-1] == song_label[:-1]
        and prev_songs[-1][-1] >= song_label[-1]
    )
    continued = bool(prev_songs) and prev_songs[-1][:-1] == song_label[:-1]
    same_play = continued and not replayed
    if same_play:
        prev_songs = prev_songs[:-1]
    with open(PREV_SONGS, "w") as f:
        current_songs = prev_songs + [song_label]
        if len(current_songs) > MAX_PREV_SONGS:
            current_songs = current_songs[-MAX_PREV_SONGS:]
        prev_songs_all[current_user] = current_songs
        json.dump(prev_songs_all, f)
    if same_play:
        log("Already tried roll")
        # Only try once for each song
        return

    genius = lyricsgenius.Genius(creds["genius"]["client access token"])
    song_search = song_name
    for i in range(0, 2):
        song = genius.search_song(song_search, artist_name)
        if isinstance(song, type(None)) or not match((song_search, artist_name), (song.title, song.artist)):
            if i:
                log(f"Song {song_search} by {artist_name} not found on Genius")
                return
            else:
                log("Song not found on Genius trying remove parens")
                song_search = remove_parens(song_search)
        else:
            break


    paragraphs = song.lyrics.split("\n\n")

    if not paragraphs:
        log("No paragraphs")
        return

    replays = list(map(lambda l: l[:-1], prev_songs)).count(song_label[:-1])
    reduce_factor = max(replays * REPLAY_REDUCE_FACTOR, 1)
    odds = max(CHANCE_TO_TWEET // reduce_factor, 1)
    if replays:
        log(
            f"Song played {replays} times in last {MAX_PREV_SONGS} songs. "
            f"Dividing {CHANCE_TO_TWEET} by {reduce_factor} to {odds}."
        )
    if random.randrange(0, odds):
        # One in CHANCE_TO_TWEET chance to tweet lyrics
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

    if not selected_lines:
        log("No lines fit within tweet.")
        return

    status = "\n".join(selected_lines)
    log("****TWEETING****:\n" + status)

    twit = get_twitter(creds["twitter"][usernum])
    tweet = twit.PostUpdate(status)

    query = " ".join((artist_name, song_name, album_name))
    query = remove_parens(query)
    query = urllib.parse.quote_plus(query)

    apple_link = get_apple_link(query)
    genius_link = song.url
    spotify_link = current_song["item"]["external_urls"].get("spotify", "")

    lastfm_link = get_lastfm_link(artist_name, song_name, creds["lastfm"])

    reply = f"\n\ngenius: {genius_link}"
    if lastfm_link:
        reply += f"\nlastfm: {lastfm_link}"
    if apple_link:
        reply += f"\napple: {apple_link}"
    if spotify_link:
        reply += f"\nspotify: {spotify_link}"
    twit.PostUpdate(reply, in_reply_to_status_id=tweet.id)

    # Remove past replays of this song to reset odds in future
    with open(PREV_SONGS, "w") as f:
        current_songs = list(filter(lambda l: l[:-1] != song_label[:-1], current_songs))
        prev_songs_all[current_user] = current_songs + [song_label]
        json.dump(prev_songs_all, f)


def main():

    with open(CREDS_FILE) as f:
        creds = json.load(f)

    users = len(creds["spotify"]["usernames"])
    for usernum in range(0, users):
        run(usernum, creds)


def log(message):
    """Log to the log file."""
    # Halve log if greater than 1000 lines
    print(message)

    with open(LOG_FILE, "a") as log:
        log.write(
            datetime.datetime.now().strftime(LOG_TIMESTAMP) + " " + message + "\n"
        )

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
        tb = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
        log("ERROR\n" + "".join(tb))
        raise e
