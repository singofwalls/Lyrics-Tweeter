import re
import unidecode
import string
from difflib import SequenceMatcher


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
    return SequenceMatcher(None, a, b).ratio()


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


def match(song, other, log=None):
    """Determine whether a song matches the result"""
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
