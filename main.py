import lyricsgenius
import spotipy
import spotipy.util
import twitter
import json
import random

from functools import reduce


CHANCE_TO_TWEET = 1
CHANCE_TO_ADD_LINE = 2
TWEET_LIMIT = 280


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
        print("Not playing a song currently")
        return

    song_name = current_song["item"]["name"]
    artist_name = current_song["item"]["artists"][0]["name"]

    genius = lyricsgenius.Genius(creds["genius"]["client access token"])
    song = genius.search_song(song_name, artist_name)

    if isinstance(song, type(None)):
        print("Song not found on Genius")
        return

    paragraphs = song.lyrics.split("\n\n")

    if not paragraphs:
        print("No paragraphs")
        return

    if random.randrange(0, CHANCE_TO_TWEET):
        # One in ten chance to tweet lyrics
        print("Failed roll")
        return

    chosen_lines = [set()] * len(paragraphs)
    chosen_paragraphs = set()
    selected_lines = []
    while len(paragraphs) != len(chosen_paragraphs):
        paragraph_num = random.choice(list(set(range(0, len(paragraphs))) - chosen_paragraphs))
        paragraph = paragraphs[paragraph_num]

        lines = [line for line in paragraph.split("\n") if line and line[0] != "["]
        start = random.choice(list(set(range(0, len(lines))) - chosen_lines[paragraph_num]))
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
            current_len = sum(map(len, selected_lines))
            if current_len + len(next_line) > TWEET_LIMIT:
                break
            selected_lines.append(next_line)
        break

    print(selected_lines)

    # twit = get_twitter(creds["twitter"])
    # twit.PostUpdate()


if __name__ == "__main__":
    main()
