#!/usr/bin/env python3.7
import lyricsgenius
import spotipy
import spotipy.util
import twitter
import pylast
import requests
import unidecode
from textdistance import levenshtein
from better_profanity import profanity

import json
import random
import urllib
import datetime
import traceback
import re
import string
import sys


DONT_CONFIRM = True  # Do not ask user before sending tweet if True
CHANCE_TO_TWEET = 120
CHANCE_TO_ADD_LINE = 3
TWEET_LIMIT = 280
NO_RETRY = True  # Do not retry a roll if on the same play
FORCE = False  # Force a tweet regardless of odds or retries
FILTER_SLURS = True  # Do not tweet lyrics which contain blacklisted words
BLACKLIST_PATH = "./words_blacklist.txt"

LOG_FILE = "log.txt"
LOG_SIZE = 10000
LOG_TIMESTAMP = "%b %d, %Y %I:%M:%S %p"

GITHUB_LINK = "https://github.com/singofwalls/Lyrics-Tweeter"

CREDS_FILE = "creds.json"
PREV_SONGS = "previous_songs.json"
MAX_PREV_SONGS = 100
REPLAY_REDUCE_FACTOR = 1.5  # Divide CHANCE_TO_TWEET by this if song previously played in last MAX_PREV_SONGS

# Closer to 1 == strings must match more closely to be considered a match
REQUIRED_ARTIST_SCORE = 0.2
REQUIRED_SONG_SCORE = 0.3

EXCLUDED_GENIUS_TERMS = ["Songs That Reference Drugs"]
EXTRANEOUS_TEXT = "EmbedShare URLCopyEmbedCopy"



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
        song_search = clean(track)
        song = network.get_track(artist, song_search)
        if isinstance(song, type(None)):
            log(f"Song {song_search} by {artist} not found on Last.fm")
            return
    return song.get_url() + "/+lyrics"


def get_apple_link(terms, cleaned=False):
    """Get a link to the song from Apple based on artist, name, and album."""

    query = " ".join(terms)
    query = urllib.parse.quote_plus(query)

    response = requests.get(f"https://itunes.apple.com/search?term={query}&limit=1")
    if not response.ok or not response.content:
        return ""

    content = json.loads(response.content)
    results = content["results"]
    if not results:
        if not cleaned:
            return get_apple_link((terms[0],) + tuple(map(clean, query[1:])), True)
        return ""

    url = results[0]["trackViewUrl"]
    return url


def get_genius_song(song_name, artist_name, genius):
    """Get the corresponding song from Genius."""
    song_search = song_name
    for i in range(0, 2):
        song = genius.search_song(song_search, artist_name)
        if isinstance(song, type(None)) or not match(
	            (song_search, artist_name), (song.title, song.artist)
        ):
            if i:
                log(f"Song '{song_search}' by '{artist_name}' not found on Genius")
                return
            else:
                log(f"Song '{song_search}' by '{artist_name}' not found on Genius trying cleaning")
                song_search = clean(song_search)
        else:
            if i:
                log(f"Found match for '{song_search}' by '{artist_name}'")
            break

    return song


def get_spotify(s_creds, usernum):
    """Get the spotify object from which to make requests."""
    # Authorize Spotify

    token = spotipy.util.prompt_for_user_token(
        s_creds["usernames"][usernum],
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


def remove_extra(name):
    """Remove the parentheses and hyphens from a song name."""
    return re.sub("-[\S\s]*", "", re.sub("\([\w\W]*\)", "", name))


def clean(name):
    """Remove potential discrepencies from the string."""
    name = remove_extra(name)
    name = unidecode.unidecode(name)  # Remove diacritics
    name = "".join(
        list(filter(lambda c: c in (string.ascii_letters + string.digits + " "), name))
    )
    name = name.lower().strip()
    return name


def distance(str1, str2):
    """Return the Needleman-Wunsch similarity between two strings."""
    return levenshtein.normalized_distance(str1, str2)


def match(song, other):
    """Determine whether a song matches the result"""
    artist_name = clean(song[1])
    other_artist = clean(other[1])
    artist_dist = distance(artist_name, other_artist)
    if artist_dist > REQUIRED_ARTIST_SCORE:
        log(f"{artist_name} != {other_artist}: {artist_dist} < {REQUIRED_ARTIST_SCORE}")
        return False

    song_name = clean(song[0])
    other_name = clean(other[0])
    song_dist = distance(song_name, other_name)
    if (
        song_dist <= REQUIRED_SONG_SCORE
        or song_name in other_name
        or other_name in song_name
    ):
        return True

    log(f"{song_name} does not match {other_name}: {song_dist} < {REQUIRED_SONG_SCORE}")
    return False


def run(usernum, creds):

    spotify = get_spotify(creds["spotify"], usernum)
    current_song = spotify.current_user_playing_track()
    current_user = creds["spotify"]["usernames"][usernum]

    if (
        isinstance(current_song, type(None))
        or not current_song["is_playing"]
        or not current_song["item"]  # Happens with podcasts
    ):
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
    if same_play and NO_RETRY and not FORCE:
        log("Already tried roll")
        # Only try once for each song
        return

    genius = lyricsgenius.Genius(
        creds["genius"]["client access token"], excluded_terms=EXCLUDED_GENIUS_TERMS
    )
    song = get_genius_song(song_name, artist_name, genius)

    if isinstance(song, type(None)):
        log("Song not found on Genius")
        return

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
    if random.randrange(0, odds) and not FORCE:
        # One in CHANCE_TO_TWEET chance to tweet lyrics
        log("Failed roll")
        return

    chosen_lines = [set()] * len(paragraphs)
    chosen_paragraphs = set()
    selected_lines = []
    while len(paragraphs) != len(chosen_paragraphs):
        remaining_choices = list(set(range(0, len(paragraphs))) - chosen_paragraphs)
        if not remaining_choices:
            break
        paragraph_num = random.choice(remaining_choices)
        paragraph = paragraphs[paragraph_num]

        lines = [line for line in paragraph.split("\n") if line and line[0] != "["]
        start = random.choice(
            list(set(range(0, len(lines))) - chosen_lines[paragraph_num])
        )
        chosen_lines[paragraph_num].add(start)
        if len(lines) == len(chosen_lines[paragraph_num]):
            chosen_paragraphs.add(paragraph_num)

        selected = lines[start]
        shortened = False
        long_sentence = False
        while len(selected) > TWEET_LIMIT:
            if "." in selected:
                shortened = True
                selected = ".".join(selected.split(".")[:-1])
            else:
                long_sentence = True
                break

        if long_sentence:
            continue

        selected_lines = [selected]
        while random.randrange(0, CHANCE_TO_ADD_LINE) and not shortened:
            next_line_num = start + len(selected_lines)
            if next_line_num >= len(lines):
                break

            next_line = lines[next_line_num]
            current_len = len("\n".join(selected_lines))
            if current_len + len(next_line) > TWEET_LIMIT:
                break
            selected_lines.append(next_line)
        break

    if selected_lines[-1].endswith(EXTRANEOUS_TEXT):
        selected_lines[-1] = selected_lines[-1][:selected_lines[-1].index(EXTRANEOUS_TEXT)]

    if not selected_lines:
        log("No lines fit within tweet.")
        return

    if not (DONT_CONFIRM or input("Send Tweet? [Yy]").lower() == "y"):
        return
    status = "\n".join(selected_lines)

    if FILTER_SLURS:
       profanity.load_censor_words_from_file(BLACKLIST_PATH)
       if profanity.contains_profanity(status):
           log("Skipping tweet due to profanity:\n" + status)
           return

    log("****TWEETING****:\n" + status)

    twit = get_twitter(creds["twitter"][usernum])
    tweet = twit.PostUpdate(status)

    apple_link = get_apple_link((artist_name, song_name, album_name))
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
        if "force" in sys.argv:
            FORCE = True
            log("FORCING")
        main()
    except Exception as e:
        tb = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
        log("ERROR\n" + "".join(tb))
        raise e
