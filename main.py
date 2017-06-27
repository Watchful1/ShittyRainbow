#!/usr/bin/python3

import praw
import os
import logging.handlers
import time
import sys
import configparser
import signal
import traceback
import re
from datetime import datetime
from datetime import timedelta

### Config ###
LOG_FOLDER_NAME = "logs"
SUBREDDIT = "shittyrainbow6"
THRESHOLD = 80
USER_AGENT = "shittyrainbow (by /u/Watchful1)"
LOOP_TIME = 15*60
SAVE_FILE_NAME = "ids.txt"

### Logging setup ###
LOG_LEVEL = logging.DEBUG
if not os.path.exists(LOG_FOLDER_NAME):
	os.makedirs(LOG_FOLDER_NAME)
LOG_FILENAME = LOG_FOLDER_NAME+"/"+"bot.log"
LOG_FILE_BACKUPCOUNT = 5
LOG_FILE_MAXSIZE = 1024 * 256

log = logging.getLogger("bot")
log.setLevel(LOG_LEVEL)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
log_stderrHandler = logging.StreamHandler()
log_stderrHandler.setFormatter(log_formatter)
log.addHandler(log_stderrHandler)
if LOG_FILENAME is not None:
	log_fileHandler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=LOG_FILE_MAXSIZE, backupCount=LOG_FILE_BACKUPCOUNT)
	log_formatter_file = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	log_fileHandler.setFormatter(log_formatter_file)
	log.addHandler(log_fileHandler)


def signal_handler(signal, frame):
	log.info("Handling interupt")
	sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

log.debug("Connecting to reddit")

once = False
debug = False
user = None
if len(sys.argv) >= 2:
	user = sys.argv[1]
	for arg in sys.argv:
		if arg == 'once':
			once = True
		elif arg == 'debug':
			debug = True
else:
	log.error("No user specified, aborting")
	sys.exit(0)


try:
	r = praw.Reddit(
		user
		,user_agent=USER_AGENT)
except configparser.NoSectionError:
	log.error("User "+user+" not in praw.ini, aborting")
	sys.exit(0)

def getSidebar(sub):
	description = sub.description
	begin = description[0:description.find("#Leaderboards")]
	leaderboardStr = description[description.find("#Leaderboards"):]
	userPoints = re.findall('(?:/u/)(.+)', leaderboardStr)
	leaderboard = []
	for userPointStr in userPoints:
		userPoint = userPointStr.split(" | ")
		if len(userPoint) == 2 and userPoint[1].isdigit():
			leaderboard.append({'user': userPoint[0], 'points': int(userPoint[1])})

	return begin, leaderboard


checkedIDs = {}
for postStr in open('ids.txt', 'r').read().split('\n'):
	postStrs = postStr.split("|")
	if len(postStrs) == 2:
		checkedIDs[postStrs[0]] = datetime.strptime(postStrs[1], "%Y-%m-%d %H:%M:%S")

log.info("Loaded posts: "+str(len(checkedIDs)))

sub = r.subreddit(SUBREDDIT)
begin, leaderboard = getSidebar(sub)
leaderboardMin = leaderboard[len(leaderboard) - 1]['points']

while True:
	startTime = time.perf_counter()
	log.debug("Starting run")

	try:
		for post in sub.new(limit=100):
			if post.score >= 80 and post.id not in checkedIDs:
				if str(post.author_flair_text) == "None":
					points = 1
				else:
					flair = post.author_flair_text
					pointsStr = re.findall('(?:Points: )(\d+)', flair)
					if len(pointsStr) and pointsStr[0].isdigit():
						points = int(pointsStr[0]) + 1
					else:
						points = 1
				log.info("Setting flair for /u/"+str(post.author)+" to "+str(points))
				#sub.flair.set(post.author, "Points: "+str(points))
				checkedIDs[post.id] = datetime.utcfromtimestamp(post.created_utc)

				if points > leaderboardMin:
					begin, leaderboard = getSidebar(sub)
					newLeaderboard = []
					oldLeader = None
					updated = False
					for leader in leaderboard:
						if points == leader['points'] and str(post.author) == leader['user']:
							newLeaderboard = leaderboard
							break
						elif points > leader['points']:
							if str(post.author) == leader['user']:
								leader['points'] = points
								newLeaderboard.append(leader)
								updated = True
							elif updated:
								newLeaderboard.append(leader)
							elif oldLeader is None:
								newLeaderboard.append({'user': str(post.author), 'points': points})
								oldLeader = leader
							else:
								newLeaderboard.append(oldLeader)
								oldLeader = leader
						else:
							newLeaderboard.append(leader)

					leaderboard = newLeaderboard
					leaderboardMin = leaderboard[len(leaderboard) - 1]['points']

					output = [begin]
					output.append("#Leaderboards [[?]](https://www.reddit.com/r/shittyrainbow6/comments/6i4ylr/css_update_meme_points_bot/)\n\n")
					output.append("User | Score\n---|---\n")
					for leader in leaderboard:
						output.append("/u/")
						output.append(leader['user'])
						output.append(" | ")
						output.append(str(leader['points']))

					sub.mod.update(description=''.join(output))


		fh = open(SAVE_FILE_NAME, 'w')
		remove = set()
		for postID, date in checkedIDs.items():
			if date < (datetime.now() - timedelta(days=60)):
				log.info("Removing old post: "+postID+" with timestamp: "+date.strftime("%Y-%m-%d %H:%M:%S"))
				remove.add(postID)
			else:
				fh.write(postID+"|"+date.strftime("%Y-%m-%d %H:%M:%S")+"\n")
		fh.close()
		for postID in remove:
			checkedIDs.pop(postID)

	except Exception as e:
		log.error("Error in main loop")
		log.warning(traceback.format_exc())

	log.debug("Run complete after: %d", int(time.perf_counter() - startTime))
	if once:
		break
	time.sleep(LOOP_TIME)
