#!/usr/bin/python

import sys
import os
import json
import subprocess
import glob
import xml.etree.ElementTree as ET
import multiprocessing
import transmissionrpc
from fuzzywuzzy import fuzz
from multiprocessing import Process
from collections import OrderedDict

FUZZ_RATIO = 85
TRANSMISSION_PORT = 9091
validFileExtensions = ['.avi', '.mkv', '.mp4']

class Series:
	seriesName = ""
	episode = -1
	filePath = ""
	fileNameRaw = ""
	fileNameClean = ""
	torrentHash = sys.argv[2]

	def setSeriesName(self, seriesName):
		self.seriesName = seriesName
	def setSeriesEpisode(self, episodeNumber):
		self.episode = int(episodeNumber)
	def setFileNameRaw(self, fileName):
		self.fileNameRaw = fileName
	def setFileNameClean(self, fileName):
		self.fileNameClean = fileName
	def setFilePath(self, filePath):
		self.filePath = filePath

	def getSeriesName(self):
		seriesName = self.encodeForFileSystem(self.seriesName)
		return seriesName
	def getSeriesEpisode(self):
		return int(self.episode)
	def getFileNameRaw(self):
		fileNameRaw = self.encodeForFileSystem(self.fileNameRaw)
		return fileNameRaw
	def getFileNameClean(self):
		fileNameClean = self.encodeForFileSystem(self.fileNameClean)
		return fileNameClean
	def getFilePath(self):
		filePath = self.encodeForFileSystem(self.filePath)
		return filePath

	def encodeForFileSystem(self, obj):
		if(type(obj) == str):
			try:
				if("'" in obj):
					obj = obj.replace("'", "\'\\'\'")
				return obj
			except:
				print ('oops')

	def setSeriesTitle(self, fileName):
		#TODO fix j'darc
		tempName = fileName.replace("_", " ")

		firstHyphen = tempName.rfind(' - ')
		firstCBrac = tempName.index(']', 0)
		seriesName = tempName[firstCBrac+2:firstHyphen]
		episode = tempName[firstHyphen+3:]
		episode = episode[:episode.index(' ',0)]
		filename = seriesName + ' - ' + episode + '.mkv'

		self.setSeriesEpisode(episode)
		self.setFileNameRaw(fileName)
		self.setFileNameClean(filename)
		self.setSeriesName(seriesName)

	def getTorrentHash(self):
		return self.torrentHash

class User:
	def __init__(self, user, userSettings):
		self.userName = user
		self.remote_port = userSettings['remote_port']
		self.remote_host = userSettings['remote_host']
		self.remote_download_dir = userSettings['remote_download_dir']
		self.discord_ID = userSettings['discord_ID']
		self.custom_titles = userSettings['custom_titles']
		self.AniListShows = {} #titles of AniList shows
		self.AniListDatabaseFileName = "Data/" + user + ".json" #Database File name

	def getUserName(self):
		return self.userName
	def getRemote_Port(self):
		return self.remote_port
	def getRemote_Host(self):
		return self.remote_host
	def getRemote_Download_Dir(self):
		return self.remote_download_dir
	def getDiscord_ID(self):
		return self.discord_ID
	def getCustom_Titles(self):
		return self.custom_titles
	def addAniListShow(self, AniListShow, episodesWatched):
		newShow = {AniListShow: {'episodesWatched': int(episodesWatched)}}
		self.AniListShows.update(newShow)
	def getAniListShows(self):
		return self.AniListShows
	def getAniListDatabaseFileName(self):
		return self.AniListDatabaseFileName

def singleFile(torrentTitle):
	if(os.path.isdir(torrentTitle)):
		return False
	else:
		return True

def readJson():
	json_data=open("../vars.json").read()
	data = json.loads(json_data, object_pairs_hook=OrderedDict)
	return data #an OrderedDict

def pullAniListUserData(userList):
	for user in userList:
		command = "python3 Tools/retAniList.py " + '\"' + user + '\"'
		os.system(command)

def getAniListShows(AniListUserFile, user):
	json_data=open(AniListUserFile).read()
	data = json.loads(json_data)

	for bigList in data:
		if(bigList['status'] == "CURRENT" or bigList['status'] == "PLANNING"):
			for entry in bigList['entries']:
				title = entry['media']['title']['romaji']
				alt_title = entry['media']['synonyms']
				my_watched_episodes = entry['progress']

				for element in alt_title:
					if(len(element) >= 1):
						user.addAniListShow(element, my_watched_episodes)

				if(entry['media']['title']['english'] != None):
					user.addAniListShow(entry['media']['title']['english'], my_watched_episodes)

				user.addAniListShow(title, my_watched_episodes)

	for show in user.getCustom_Titles():
		user.addAniListShow(show, 0)

def getMatches(AniListShows, listOfValidFiles):
	matches = []

	for validFile in listOfValidFiles:
		for show in AniListShows.keys():
			if (fuzz.ratio(show, validFile.getSeriesName()) > FUZZ_RATIO) and validFile not in matches:
				if validFile.getSeriesEpisode() > AniListShows[show]['episodesWatched']:
					matches.append(validFile)
				elif (validFile.getSeriesEpisode() == 0) and (AniListShows[show]['episodesWatched'] == 0):
					matches.append(validFile)
	return matches

def userLoop(settings, isSingleFileDownload, user, returnDict):
	pullAniListUserData(settings['Users'].keys())
	syncingUser = User(user, settings['Users'][user]) #name, name data
	getAniListShows(syncingUser.getAniListDatabaseFileName(), syncingUser)

	# return either list of one match, or multiple
	listOfValidFiles = []

	if(isSingleFileDownload == True):
		serialToSync = Series()
		serialToSync.setSeriesTitle(sys.argv[3])
		serialToSync.setFilePath(settings['System Settings']['host_download_dir'] + sys.argv[3])
		listOfValidFiles.append(serialToSync)
	else:
		#glob the files here as a list of files
		print ('Globbing')
		os.chdir(settings['System Settings']['host_download_dir'] + sys.argv[3])
		for fileExtension in validFileExtensions:
			fileExtension = "*" + fileExtension #regexify it
			for fileTitle in sorted(glob.glob(fileExtension)):
				serialToSync = Series()
				serialToSync.setSeriesTitle(fileTitle)
				serialToSync.setFilePath(settings['System Settings']['host_download_dir'] + sys.argv[3] + '/' + fileTitle)
				listOfValidFiles.append(serialToSync)

		os.chdir(settings['System Settings']['script_location'])

	matches = getMatches(syncingUser.getAniListShows(), listOfValidFiles)
	if(matches is not None):
		for match in matches:
			#TODO fix multiple matches
			print ("Matched: " + match.getSeriesName())

			status = sync(syncingUser, match)
			returnDict[user] = status
			
			os.chdir(settings['System Settings']['script_location'])
			
			command = "python3 Tools/DiscordAnnounce.py \'" + serialToSync.getFileNameClean() + '\' ' + syncingUser.getUserName()
			subprocess.call(command, shell=True)
			
			hashtoFile(serialToSync.getTorrentHash())

def sync(syncingUser, serialToSync):
	if(syncingUser.getRemote_Host() != ''):
		print ("Syncing: " + serialToSync.getSeriesName() + ' - ' + str(serialToSync.getSeriesEpisode()) + ' to ' + syncingUser.getUserName())
		#TODO wrap in try except

		if(settings['System Settings']['individual folders'] == "True"):
			mkdirCommand = "mkdir -p \'" + syncingUser.getRemote_Download_Dir() + serialToSync.getSeriesName() + '\''
			subprocess.check_call(mkdirCommand, shell=True)

			moveToCommand = "cp \'" + serialToSync.getFilePath() + "\' \'" + syncingUser.getRemote_Download_Dir() + serialToSync.getSeriesName() + '\''
			renameFileCommand = "mv '" + syncingUser.getRemote_Download_Dir() + serialToSync.getSeriesName() + '/' + serialToSync.getFileNameRaw() + "' '" + syncingUser.getRemote_Download_Dir() + serialToSync.getSeriesName() + '/' + serialToSync.getFileNameClean() + '\''
			changeOwnerCommand = "chown 1000:1000 \'" + syncingUser.getRemote_Download_Dir() + serialToSync.getSeriesName() + '/' + serialToSync.getFileNameClean() + '\''
			changeModCommand = "chmod 0770 \'" + syncingUser.getRemote_Download_Dir() + serialToSync.getSeriesName() + '/' + serialToSync.getFileNameClean() + '\''
		
		elif(settings['System Settings']['individual folders'] == "False"):
			moveToCommand = "cp \'" + serialToSync.getFilePath() + "\' \'" + syncingUser.getRemote_Download_Dir() + '\''
			renameFileCommand = "mv '" + syncingUser.getRemote_Download_Dir() + '/' + serialToSync.getFileNameRaw() + "' '" + syncingUser.getRemote_Download_Dir() + '/' + serialToSync.getFileNameClean() + '\''
			changeOwnerCommand = "chown 1000:1000 \'" + syncingUser.getRemote_Download_Dir() + '/' + serialToSync.getFileNameClean() + '\''
			changeModCommand = "chmod 0770 \'" + syncingUser.getRemote_Download_Dir() + '/' + serialToSync.getFileNameClean() + '\''

		subprocess.check_call(moveToCommand, shell=True)
		subprocess.check_call(renameFileCommand, shell=True)
		subprocess.check_call(changeOwnerCommand, shell=True)
		subprocess.check_call(changeModCommand, shell=True)

		return True

def hashtoFile(theHash):
	os.chdir(settings['System Settings']['script_location'])
	completed = open("Data/completed.txt", "a")
	completed.write(theHash)
	completed.write('\n')
	completed.close()

if __name__=='__main__':
	try:
		# print ('arg1: ' + sys.argv[1])
		# print ('arg2: ' + sys.argv[2])
		# print ('arg3: ' + sys.argv[3])
		settings = readJson()

		#check for list index out of range
		isSingleFileDownload = singleFile(sys.argv[1])

		#for automation tools because PATH is hard
		os.chdir(settings['System Settings']['script_location'])

		#check if the download exists in the correct directory
		if settings['System Settings']['host_download_dir'] not in sys.argv[1]:
			sys.exit(1)

		#create a job pool, and a manager (shared dict between processes)
		jobs = []
		manager = multiprocessing.Manager()
		returnDict = manager.dict()

		for user in settings['Users']:
			p = multiprocessing.Process(target=userLoop, args=(settings, isSingleFileDownload, user, returnDict))
			jobs.append(p)
			p.start()

		for process in jobs:
			process.join()

		#checks if the status of the sync was sucessful, otherwise prints failed syncs
		if(False in returnDict.values()):
			for user in returnDict.keys():
				if(returnDict[value] == False):
					print ('Failed to sync to ' + user)
		# else:
			# tc = transmissionrpc.Client('localhost', port=TRANSMISSION_PORT)
			# tc.remove_torrent(sys.argv[2], True)

	except Exception as e:
		print (e)
