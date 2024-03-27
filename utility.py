import re
import unidecode
import string
import time
from difflib import SequenceMatcher
import requests.exceptions


# Closer to 1 == strings must match more closely to be considered a match
REQUIRED_ARTIST_SCORE = 0.2
REQUIRED_SONG_SCORE = 0.3

EXCLUDED_GENIUS_TERMS = ["Songs That Reference Drugs"]
EXTRANEOUS_TEXT = ["Translations.+\n", r"\[[a-zA-Z]+\]\n",
# TODO[reece]: Do not match to end of line for the translations substitution
# Either use a list of langauges to match with
# Or find or make a pull request to remove translation info from the HTML
                    "[0-9]+Embed", "EmbedShare URLCopyEmbedCopy", "Embed$",
                    "You might also like", r"See $BAND$ Live",
                    r"Get tickets as low as \$[0-9]+", r"$SONG$ Lyrics",
                    "[0-9]+ Contributors?"]


def clean_paragraphs(paragraphs, artist_name, song_name):
    """Remove extraneous lines of text from paragraphs"""
    clean_paragraphs = []

    for paragraph in paragraphs:
        for extraneous_pattern in EXTRANEOUS_TEXT:
            extraneous_pattern = extraneous_pattern.replace("$BAND$", re.escape(artist_name))
            extraneous_pattern = extraneous_pattern.replace("$SONG$", re.escape(song_name))

            paragraph = re.sub(extraneous_pattern, "", paragraph, flags=re.IGNORECASE)

        clean_paragraphs.append(paragraph)

    return clean_paragraphs


def distance(a: str, b: str):
    """Get the distance ratio between two strings."""
    return 1 - SequenceMatcher(None, a, b).ratio()


def remove_extra(name):
    """Remove the parentheses and hyphens from a song name."""
    return re.sub(r"-[\S\s]*", "", re.sub(r"\([\w\W]*\)", "", name))


def clean(name):
    """Remove potential discrepencies from the string."""
    name = remove_extra(name)
    name = unidecode.unidecode(name)  # Remove diacritics
    name = "".join(
        list(filter(lambda c: c in (string.ascii_letters + string.digits + " "), name))
    )
    name = name.lower().strip()
    return name


def match(song: tuple[str, str], other: tuple[str, str], log=None):
    """
    Determine whether a song matches the result.

    song: (song_name, artist_name)
    other: (song_name, artist_name)
    """
    if not isinstance(song, list) and not isinstance(song, tuple):
        raise ValueError("Song must be a tuple")
    if not isinstance(other, list) and not isinstance(other, tuple):
        raise ValueError("Other must be a tuple")

    artist_name = clean(song[1])
    other_artist = clean(other[1])
    artist_dist = distance(artist_name, other_artist)
    if artist_dist > REQUIRED_ARTIST_SCORE:
        if log:
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

    if log:
        log(f"{song_name} does not match {other_name}: {song_dist} < {REQUIRED_SONG_SCORE}")
    return False


def get_genius_song(song_name, artist_name, genius, log=None):
    """Get the corresponding song from Genius."""
    song_search = song_name
    for i in range(0, 2):
        # Try once as is and once cleaned
        song = None
        for i in range(1, 8):
            # Try several more times if there's timeouts but backoff
            try:
                song = genius.search_song(song_search, artist_name)
            except requests.exceptions.Timeout:
                print("Timeout from genius, sleeping")
                time.sleep(i**2 / 10)
            except Exception:
                break
            else:
                break
        else:
            print("Too many timeouts, skipping song")

        if isinstance(song, type(None)) or not match(
	            (song_search, artist_name), (song.title, song.artist)
        ):
            if i:
                if log:
                    log(f"Song '{song_search}' by '{artist_name}' not found on Genius")
                return
            else:
                if log:
                    log(f"Song '{song_search}' by '{artist_name}' not found on Genius trying cleaning")
                song_search = clean(song_search)
        else:
            if i:
                if log:
                    log(f"Found match for '{song_search}' by '{artist_name}'")
            break

    return song