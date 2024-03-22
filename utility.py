import re


EXCLUDED_GENIUS_TERMS = ["Songs That Reference Drugs"]
EXTRANEOUS_TEXT = ["Translations.+\n", r"\[[a-zA-Z]+\]\n",
# TODO[reece]: Do not match to end of line for the translations substitution
# Either use a list of langauges to match with
# Or find or make a pull request to remove translation info from the HTML
                    "[0-9]+Embed", "EmbedShare URLCopyEmbedCopy", "Embed$",
                    "You might also like", r"See $BAND$ Live",
                    r"Get tickets as low as \$[0-9]+", r"$SONG$ Lyrics",
                    "[0-9]+ Contributors"]



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
