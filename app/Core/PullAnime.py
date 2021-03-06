#!/ani-script/venv/bin/python3


import os
import sys
import ssl
import json
import glob
import base64
import urllib
import requests
import datetime
import feedparser
import progressbar
import transmissionrpc
import xml.etree.ElementTree as ET

from fuzzywuzzy import fuzz
from collections import OrderedDict

bar = progressbar.ProgressBar(maxval=1, widgets=[progressbar.Bar('=', '[', ']'), ' ', progressbar.Percentage()])
# feedparser.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
feedparser.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36'

FUZZ_RATIO = 75
TRANSMISSION_PORT = 9091
PATH_TO_TORRENT_FILES = '..//Data//torrents//'

#anime object to store relevant deets
class userClass():
	def __init__(self):
		self.userName = None
		self.Custom_Titles = []
		self.dataBaseFileName = None

	def setUserName(self, userName):
		self.userName = userName
	def getUserName(self):
		return self.userName
	def setCustom_Titles(self, customTitles):
		self.Custom_Titles = customTitles
	def getCustom_Titles(self):
		return self.Custom_Titles
	def setDataBaseFileName(self, dataBaseFileName):
		self.dataBaseFileName = dataBaseFileName
	def getDataBaseFileName(self):
		return self.dataBaseFileName

class anime():
	def __init__(self):
		self.show_id = None
		self.title = None
		self.alt_titles = []
		self.status = None
		self.last_watched = None

	def __eq__(self, other):
		return self.show_id == other.show_id
	def __hash__(self):
		return hash(self.show_id)
	def setShow_id(self, show_id):
		self.show_id = show_id
	def getShow_id(self):
		return self.show_id
	def setTitle(self, title):
		self.title = title
	def getTitle(self):
		return self.title
	def setAlt_titles(self, altTitles):
		self.alt_titles = altTitles
	def getAlt_titles(self):
		return self.alt_titles
	def setStatus(self, status):
		self.status = status
	def getStatus(self):
		return self.status
	def setLast_watched(self, last_watched):
		self.last_watched = last_watched
	def getLast_watched(self):
		return self.last_watched

def readJson():
	json_data=open("../vars.json").read()
	data = json.loads(json_data, object_pairs_hook=OrderedDict)
	return data #an OrderedDict

def getSeriesTitle(fileName):
	tempName = fileName.replace("_", " ")
	tempName = tempName.replace(u" – ", " - ")
	firstHyphen = tempName.rfind(' - ')
	prefixCBrac = tempName.index(']', 7)
	seriesName = tempName[prefixCBrac+2:firstHyphen]
	return seriesName

def getCRC(releaseTitle):
	lastRightBrac = releaseTitle.rfind(']')
	lastLeftBrac = releaseTitle.rfind('[')
	return releaseTitle[lastLeftBrac+1:lastRightBrac]

def pullAniListUserData(userList):
	for user in userList:
		os.chdir('../')
		command = "python3 Tools/retAniList.py " + '\"' + user + '\"'
		os.system(command)
		os.chdir('Core/')

def checkDupes(animeTitle, showList):
	allTitle = []
	for show in showList:
		allTitle.append(show.title)
		for altTitle in show.alt_titles:
			allTitle.append(allTitle)

	if(animeTitle not in allTitle):
		return True
	else:
		return False

def generateUserObjects(users):
	userList = []

	for user in users:
		dataBaseFileName = "../Data/" + user + ".json"
		newUser = userClass()
		newUser.setUserName(user)
		newUser.setCustom_Titles(users[user]['custom_titles'])
		newUser.setDataBaseFileName(dataBaseFileName)
		userList.append(newUser)

	return userList

def getAllUniqueAniListShows(users):
	allShows = [] #holds all watching and plan to watch shows
	currDate = datetime.datetime.today()
	lastWeek = currDate - datetime.timedelta(days=7)
	nextWeek = currDate + datetime.timedelta(days=7)
	tempShowId = 0

	# find all the user's PTW and Currently watching shows
	# if show hits criteria
	# make temp anime and add it to list

	for user in users:
		json_data=open(user.getDataBaseFileName()).read()
		data = json.loads(json_data)

		for bigList in data:
			if(bigList['status'] == "CURRENT" or bigList['status'] == "PLANNING"):
				for entry in bigList['entries']:
					tempAnime = anime()
					tempAnime.setShow_id(entry['mediaId'])
					tempAnime.setTitle(entry['media']['title']['romaji'])
					tempAnime.setLast_watched(entry['progress'])
					tempAnime.setStatus(entry['media']['status'])

					if(entry['media']["endDate"]['day'] != None):
						seriesEndStr = str(entry['media']["endDate"]['year']) + '-' + str(entry['media']["endDate"]['month']) + '-' + str(entry['media']["endDate"]['day'])
						seriesEnd = datetime.datetime.strptime(seriesEndStr, '%Y-%m-%d') #conversion from string to datetime

					if(entry['media']['title']['english'] != None):
						entry['media']['synonyms'].append(entry['media']['title']['english'])

					tempAnime.setAlt_titles(entry['media']['synonyms'])

					if(entry['media']['status'] == "RELEASING" or entry['media']['status'] == "NOT_YET_RELEASED"):
						allShows.append(tempAnime)
					elif(entry['media']['status'] == "FINISHED"):
						if (lastWeek <= seriesEnd <= nextWeek):
							allShows.append(tempAnime)

		# #Changed to add the custom titles after pruning all dupes
		# #add custom titles here
		# # set was working with ids
		for altTitle in user.getCustom_Titles():
			tempAnime = anime()
			tempAnime.setTitle(altTitle.strip())
			tempAnime.setShow_id(tempShowId)
			tempShowId += 1

			if(checkDupes(tempAnime.getTitle(), allShows)):
				allShows.append(tempAnime)

	# for animeShows in allShows:
		# print (animeShows.getTitle())

	print ("Length of all shows(dupes included): " + str(len(allShows)))
	allShows = list(set(allShows)) #Removes dupes from list
	print ("Length of all shows(incl custom title, no dupes): " + str(len(allShows)))

	return allShows

def getMatches(releases, allShows, matches):
	for release in releases:
		seriesTitle = getSeriesTitle(release.title)
		for show in allShows:
			if(fuzz.ratio(show.getTitle().lower(), seriesTitle.lower()) > FUZZ_RATIO):
				if (len(show.getTitle()) != 1): #DARN 'K' ANIME MESSING EVERYTHING UP, since the title splitter on line 130 picks up only 'k' as the title
					matches.append(release) #it matches any anime title with 'k' in it
			elif(len(show.getAlt_titles()) > 0):
				for altTitle in show.getAlt_titles():
					if(fuzz.ratio(altTitle, seriesTitle) > FUZZ_RATIO):
						matches.append(release)
						pass
	return matches

def makeMagnets(matches, transmissionClient):
	tidfile = open('../Data/tidfile', 'r+') #stores torrent tids so that they wont download again
	existingTIDs = tidfile.read().split("\n")
	tidfile.close()
	isTorrentFile = False

	currDate = datetime.datetime.strptime(datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S") #getting today with out stupid microseconds
	lastWeek = currDate - datetime.timedelta(days=7)
	nextWeek = currDate + datetime.timedelta(days=7)

	for matchedShow in matches:
		title = getSeriesTitle(matchedShow.title)
		title = title.replace("'", "\'")
		print(title)

		url = matchedShow.link

		pubDate = matchedShow.published[:-6]
		datetime_publish = datetime.datetime.strptime(pubDate, '%a, %d %b %Y %H:%M:%S')

		if(lastWeek <= datetime_publish <= nextWeek):
			if ("subsplease_size" in matchedShow.keys()):
				tid = getCRC(matchedShow.title)
				url = matchedShow.link
			elif("Submitter: subsplease" in matchedShow.summary): #subsplease TT RSS
				tid = matchedShow.link[21:28]
				startMagnetIndex = matchedShow.summary.index('magnet:')
				endMagnetIndex  = matchedShow.summary.rfind('>Magnet ')
				url = matchedShow.summary[startMagnetIndex:endMagnetIndex - 1]
			else:
				print("Something went wrong")

		if tid not in existingTIDs: #if tid doesn't already exist
			if(isTorrentFile):
				with open(PATH_TO_TORRENT_FILES + tid + '.torrent', "rb") as torrentFile:
					incomingTorrent = transmissionClient.add_torrent(base64.b64encode(torrentFile.read()).decode())
			else:
				incomingTorrent = transmissionClient.add_torrent(url)

			tidfile = open('../Data/tidfile', 'a+') #stores torrent tids so that they wont download again
			tidfile.write(tid+"\n")
			pollTorrent(transmissionClient, incomingTorrent.hashString)

	files = glob.glob(PATH_TO_TORRENT_FILES + '*')
	for f in files:
		os.remove(f)
	tidfile.close()

def pollTorrent(transmissionClient, torrentID):
	torrent = transmissionClient.get_torrent(torrentID)
	while(torrent.metadataPercentComplete < 1.0):
		torrent = transmissionClient.get_torrent(torrentID)
	bar.start()
	while(torrent.percentDone < 1.0):
		bar.update(torrent.percentDone)
		torrent = transmissionClient.get_torrent(torrentID)
	bar.finish()
	fullPath = torrent.downloadDir + '/' + torrent.name

	if("'" in torrent.name):
		command = "python3 ../Sync.py \'" +  fullPath.replace("'", "\'\\'\'") + '\' \'' + torrentID + '\' \'' + torrent.name.replace("'", "\'\\'\'") + '\''
	else:
		command = "python3 ../Sync.py \'" +  fullPath + '\' \'' + torrentID + '\' \'' + torrent.name + '\''
	# print(command)
	os.system(command)

def getFeeds(Rss_Feeds):
	feedList = []

	for feed in Rss_Feeds:
		feedList.append(Rss_Feeds[feed])

	return feedList

settings = readJson()

#pull updated user list from Anilist. not /really/ required, but w/e
tc = transmissionrpc.Client('localhost', port=TRANSMISSION_PORT)
pullAniListUserData(settings['Users'].keys())
userObjects = generateUserObjects(settings['Users'])
allShows = getAllUniqueAniListShows(userObjects)
feedUrls = getFeeds(settings['Rss Feeds'])

matches = []

for url in feedUrls:
	if hasattr(ssl, '_create_unverified_context'):
	    ssl._create_default_https_context = ssl._create_unverified_context
	if(url != ""):
		feed = feedparser.parse(url)
		print("Status of RSS Feed: " + str(feed.status))
		releases = feed.get('entries')
		matches = getMatches(releases, allShows, matches)

print ("Length of matches: " + str(len(matches)))
makeMagnets(matches, tc)
