# Lyrics Tweeter
In use here: [@42Versificator](https://twitter.com/42Versificator)

A twitter bot hosted on a raspberry pi which, every few minutes, checks if a song is being played on the authed Spotify account and, if a random roll is passed, tweets random lyrics from the song.

## Lyrics Choice

Lyrics are pulled from Genius.

If a relatively low-chance random roll passes, the bot chooses a random block (e.g. a single verse, the chorus, etc.) of lines from the current song's lyrics, and then chooses a random line from the block. If a 50/50 roll is passed, it adds the following line. It continues adding subsequent lines in this way until a roll fails, it reaches the end of the block, or it runs out of space in the tweet.

Links are pulled from Genius, Spotify, Apple Music, and Lastfm and posted in reply to the lyrics.

## Extra
The bot should tweet around once per day if the average day sees 80 scrobbles (this is probably rather high for the average listener, but the bot was built for [grahammathews42](https://www.last.fm/user/grahammathews42), who happens to be a not-so-average listener).

In a sense, the bot is a bit of a roulette due to lyrics not being vetted and tweets having the potential to occur at any moment. But then, I suppose that's part of the appeal.

I acknowledge the untidiness of the code. I originally intended for this to be a quick-and-dirty private repo but ultimately decided to go public.

## Setup
To host your own, credentials must be obtained for [Spotify](https://developer.spotify.com/dashboard/applications), [Genius](https://genius.com/api-clients/new), [Twitter](https://developer.twitter.com/en/application/use-case), and [Last.fm](https://www.last.fm/api/account/create). These should be placed in a creds.json file as demonstrated in the [example_creds.json](example_creds.json), replacing everything between "<>." Python 3.6 (or perhaps greater) is necesary to run this code. [Get Python and Pip here](https://www.python.org/downloads/). The necessary libraries can be installed with pip using the [requirements.txt](requirements.txt) file. If you have not yet cloned this repo, do so using your VCS of choice ([git can be downloaded here](https://git-scm.com/downloads)).

Clone the repo.
```Shell
git clone https://github.com/singofwalls/Lyrics-Tweeter.git
```
Install the dependencies
```Shell
cd Lyrics-Tweeter
sudo pip install -r requirements.txt
```
Spotipy may not work if installed with pip. In this case, install it from the Github repo:
```Shell
sudo pip uninstall spotipy
sudo pip install git+https://git@github.com/plamere/spotipy.git@master#egg=spotipy-2.4.4
```
Once you have created the creds.json file based on the [example_creds.json](example_creds.json), the bot can be ran once with
```Shell
sudo python main.py
```
A taskscheduler can be used to run the script periodically. I use crontab on linux (raspbian in this case):
```Shell
sudo crontab -e
```
Append the task to the end of the crontab
```Shell
*/5 * * * * (cd /path/to/Lyrics-Tweeter && ./main.py) &
```
Edit the shebang in [main.py](main.py) to point to your install of python.
```Shell
nano main.py
```
The following line should point to your install.
```Python
#!/usr/bin/env python3.7
```
Make sure [main.py](main.py) is executable.
```Shell
chmod +x main.py
```

Boom. You've got yourself a Twitter bot.

If I missed any steps or messed something up, let me know. Contact information available at [my profile](https://github.com/singofwalls).