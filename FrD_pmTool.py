'''
Put .py --> pyinstaller.shortcut
Put ffmpeg.win32.exe --> dist
Compile installer: edit productversion
'''

import sys
import os
import datetime
# import qdarkstyle
from PyQt4 import QtGui, QtCore, uic
from PyQt4.QtCore import QProcess, QThread, Qt
import getpass
import logging
import imageio
import csv
import glob
import re
# import pprint
# for Google SpreadSheet
# import pygsheets
import time
global startTime

print ('Loading Shotgun Support')
global sg
SERVER_PATH = "https://xyz.shotgunstudio.com" # fake path, due to company's private asset
SCRIPT_NAME = 'FrD_PMTool'
API = 'abcdefghijklmnopqrstuvwxyz'; # code with fake API, cuz this is the company's private asset,not gonna disclose in github

custom_ui = uic.loadUiType('FrD_pmTool.ui')[0]

PROGRAM_VERSION = " 2017.0824"
size = 0
conversion = ""
fileNum = 0  # number of mov
fileQueue = []
currRow = 0
totalFrame = 0
currFrame = 0
bStop = False
# os.path.basename(your_path) #Filename

# path
# SERVER_INSTALLER = r'\\zserver01\FreeDUI\FreeDUI\ShotgunTools\FrD_PMTool_INSTALL.exe'
NUKE_EXE = r'C:\Program Files\Nuke10.0v4\Nuke10.0.exe'
CONVERSION_H264 = r'\\in\D\FreeDUI\wBurnIn\conversion_h264.py'
CONVERSION_ANIM = r'\\in\D\FreeDUI\wBurnIn\conversion_anim.py'
OUTPUT_DIR = ""
OUTPUT_DIR2 = ""
CSV_DIR = ""
Folder_DIR = ""
# for shotgun --> GoogleSpreadSheet
SGCSV_DIR = ""
global CB_STYLE
global isStopCheck

# connect to shotgun


def shotgunConnect():
    from shotgun_api3 import Shotgun
    sg = Shotgun(SERVER_PATH, SCRIPT_NAME, API)
    return sg


# Log file
extra = {'user_name': getpass.getuser()}
logger = logging.getLogger("sg_update_shotStatus")
handler = logging.FileHandler('//zserver01/FreeDUI/FreeDUI/ShotgunTools/FrD_pmTool/sg_update_shotStatus.log')
formatter = logging.Formatter('%(asctime)s : %(user_name)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger = logging.LoggerAdapter(logger, extra)

# MultiThreading 1: (SHOTGUN) Create / update playlist


class PlayListThread(QThread):

    def __init__(self, verNames, plID, senderBtn):
        QThread.__init__(self)
        self.progress = 0
        self.verNames = verNames
        self.plID = plID
        self.senderBtn = senderBtn

    def __del__(self):
        self.wait()

    def SGPL_linkVersion(self):

        for verName in self.verNames:
            verID = sg.find("Version", filters=[['cached_display_name', 'is', verName]], fields=['id'])
            try:
                verID = verID[0]['id']
            except:
                print 'link version to playlist failed / linked version already existed in entity.'
                self.progress += 1
                self.emit(QtCore.SIGNAL('linkVerFailed'), verName, self.verNames, self.progress, self.senderBtn)
                # pass
                continue
            # connect version to playlist
            data = {
                'version': {'type': 'Version', 'id': verID},
                'playlist': {'type': 'Playlist', 'id': self.plID}
            }
            try:
                plVerObj = sg.create('PlaylistVersionConnection', data)
            except:
                plVerObj = None
            if not plVerObj:
                print 'link version to playlist failed / linked version already existed in entity.'
                self.progress += 1
                self.emit(QtCore.SIGNAL('linkVerFailed'), verName, self.verNames, self.progress, self.senderBtn)
                # self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), "link version to playlist FAILED."))
            else:
                self.progress += 1
                self.emit(QtCore.SIGNAL('VerLinked'), verName, self.verNames, self.progress, self.senderBtn)
                # self.output_TE.append('%s %s %s %s' % (self.SGT_getTimeNow1(), "linked version: \"", verName, "\" to playlist."))


# class CutDurationCheckThread(QThread):

#     def __init__(self):
#         QThread.__init__(self)

#     def __del__(self):
#         self.wait()

#     def runCheck(self):
#         print "run check"

# Main Class: FrD_PMTool


class FrD_pmTool(QtGui.QMainWindow, custom_ui):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        global PROGRAM_VERSION
        self.setWindowTitle('FrD pmTool ' + PROGRAM_VERSION)

        # Enable Drag and Drop
        self.mov_LW.setAcceptDrops(True)
        self.list_of_tags = []
        # Progress Bar style
        PB_STYLE = """
        QProgressBar{
            border: 1px solid black;
            border-radius: 1px;
            text-align: center
        }

        QProgressBar::chunk {
            background-color: cadetblue;
            width: 2px;
            margin: 1px;
        }
        """
        # cadetblue;

        self.progress_PB.setStyleSheet(PB_STYLE)
        # Set up handlers for the LW
        self.mov_LW.dragEnterEvent = self.lwDragEnterEvent
        self.mov_LW.dragMoveEvent = self.lwDragMoveEvent
        self.mov_LW.dropEvent = self.lwDropEvent
        self.connect(self.mov_LW, QtCore.SIGNAL("dropped"), self.movFileDropped)

        self.seq_LW.dragEnterEvent = self.lwDragEnterEvent
        self.seq_LW.dragMoveEvent = self.lwDragMoveEvent
        self.seq_LW.dropEvent = self.folderDropEvent
        self.connect(self.seq_LW, QtCore.SIGNAL("dropped"), self.folderDropped)

        username = getpass.getuser()
        global sg
        sg = shotgunConnect()
        if sg:
            self.output_TE.append('%s %s%s' % ("Hi,", username, "."))
            self.output_TE.append('%s %s' % (
                self.SGT_getTimeNow1(), "Shotgun Connected"))
        else:
            self.output_TE.append('%s %s' % (
                self.SGT_getTimeNow1(), "Shotgun Connection Fail"))

        act_projects = sg.find("Project", filters=[
                               ['sg_status', 'is', 'Active']], fields=['name'])
        for project in act_projects:
            self.sgProject_CB.addItem(project['name'])

        self.sgProject_CB.setCurrentIndex(-1)
        self.updateShot_Btn.clicked.connect(self.updateStatus)
        self.updateShot_Btn.setEnabled(False)
        # ==================PLAYLIST(CSV)=========================
        self.browseCSV_Btn.clicked.connect(self.browseCSV)
        self.playlist_Btn.clicked.connect(self.createPlaylist)
        # ==================PLAYLIST(folder)=========================
        # self.browsefolder_Btn.clicked.connect(self.browseFolder)
        # self.playlist_Btn_2.clicked.connect(self.createPlaylist)
        # ================== SHOTGUN -> GOOGLE SPREADSHEET =================
        self.browseShotgunCSV_Btn.clicked.connect(self.browseSGCSV)
        self.updateGoogleSS_Btn.clicked.connect(self.updateGoogleSS)
        # =================  MOV ==========================
        self.clearitem_Btn.clicked.connect(self.movClearItem)
        self.clearall_Btn.clicked.connect(self.movClearAll)
        self.render_anim_Btn.clicked.connect(self.readyrenderAnimMOV)
        self.render_h264_Btn.clicked.connect(self.readyrenderH264MOV)
        self.stop_Btn.clicked.connect(self.stopRender)
        # =========================================================
        self.browse_Btn.clicked.connect(self.setExistingDirectory)
        # ======================MENU BAR===========================
        # self.checkUpdate.triggered.connect(self.versionUpdate)
        self.actionAbout.triggered.connect(self.showAbout)

        self.csv_RB.toggled.connect(lambda: self.createPlaylistMethod(self.csv_RB))
        self.scanMov_RB.toggled.connect(lambda: self.createPlaylistMethod(self.scanMov_RB))
        self.scanFolder_RB.toggled.connect(lambda: self.createPlaylistMethod(self.scanFolder_RB))

        self.movProcess = QProcess(self)

        # check Nuke 10.0
        if not os.path.isfile(NUKE_EXE):
            self.showDialogMsg('Info', 'Nuke10.0v4 not found.')

        self.clearAllCheck_BN.clicked.connect(self.clearAllCheck)
        self.clearSelCheck_BN.clicked.connect(self.clearSelCheck)
        self.checkCutDuration_BN.clicked.connect(self.checkCutDuration)
        # self.stopCheck_BN.clicked.connect(self.stopCheck)

        global CB_STYLE
        CB_STYLE = """
        QCheckBox::indicator{
            border: 1px solid #666;
        }
        """
        self.dragReplace_CB.setStyleSheet(CB_STYLE)
        self.dragReplace_CB.clicked.connect(self.changeStyleForBorder)

        self.updateOutputHistory_BN.clicked.connect(self.updateOutputHistory)

    # def keyPressEvent(self, event):
    #     if event.key() == QtCore.Qt.Key_Escape:
    #           self.close()
    #           print 'ESCAPE pressed'

    # def stopCheck(self):
    #     isStopCheck = True

    def updateOutputHistory(self):

        projectName = str(self.sgProject_CB.currentText())
        if projectName:

            QtGui.QApplication.setOverrideCursor(Qt.WaitCursor)

            startTime = time.clock()

            projObj = sgProject(sg, projectName)
            projID = projObj['id']

            self.output_TE.clear()

            filter = [
                ['project', 'is', {'type': 'Project', 'id': projID}],
                {
                    "filter_operator": "any",
                    "filters": [
                        ['code', 'contains', 'output'],
                        ['code', 'contains', 'mov']
                    ]
                }
            ]

            plObj = sg.find('Playlist', filter, ['code'])
            # pprint.pprint(plObj)

            plOutputDict = {}
            plMovDict = {}

            # -----------------------
            #  METHOD 1:
            #  LOOP FROM PLAYLIST
            # -----------------------

            # CLEAN ALL DATA IN FIELD outputhistory, movhistory ---------------------
            filter = [
                ['project', 'is', {'type': 'Project', 'id': projID}]
            ]
            shotObj = sg.find("Shot", filter)

            batch_data = []
            for shot in shotObj:

                shotID = shot['id']

                data = {
                    "sg_outputhistory": '',
                    "sg_movhistory": '',
                }
                batch_data.append({"request_type": "update", "entity_type": "Shot", "entity_id": shotID, "data": data})

            self.output_TE.append('Clearing all data for Shots\' field "Output History" and "Mov History"')
            QtGui.QApplication.processEvents()

            try:
                sg.batch(batch_data)
            except(RuntimeError, TypeError, NameError):
                self.output_TE.append('Error. Pls check if the fields "sg_outputhistory" and "sg_movhistory" exist in Shot')
                return ''

            total = len(plObj)
            i = 0

            # CREATE DICT -----------------------------------------------------------
            for pl in plObj:

                i += 1
                self.output_TE.append('Processing target playlists {} / {}'.format(i, total))
                QtGui.QApplication.processEvents()

                plID = pl['id']
                # plID = 1038

                filter = [
                    ['playlist', 'is', {'type': 'Playlist', 'id': plID}]
                ]

                fields = ['version.Version.code', 'version.Version.entity']
                vrsObj = sg.find('PlaylistVersionConnection', filter, fields)

                for vrs in vrsObj:

                    matchObj = re.match(r'\w+_(v\d+\w*)$', vrs['version.Version.code'], re.M | re.I)

                    if matchObj:

                        connectedShotID = vrs['version.Version.entity']
                        # pprint.pprint(connectedShotID)

                        shotID = str(connectedShotID['id'])

                        if 'output' in pl['code']:

                            if shotID not in plOutputDict.keys():
                                plOutputDict[shotID] = []
                            plOutputDict[shotID].append('{} : {}'.format(pl['code'], matchObj.group(1)))
                            # plOutputDict[shotID].append({pl['code']: matchObj.group(1)})

                        elif 'mov' in pl['code']:

                            if shotID not in plMovDict.keys():
                                plMovDict[shotID] = []
                            plMovDict[shotID].append('{} : {}'.format(pl['code'], matchObj.group(1)))
                            # plMovDict[shotID].append({pl['code']: matchObj.group(1)})

                    else:
                        print ("version doesn't match required format: " + vrs['version.Version.code'])

            batch_data = []

            # BATCH UPDATE -----------------------------------------------------------
            # for k in plOutputDict.keys():
            for k in plOutputDict.keys():

                data = {
                    'sg_outputhistory': '\n'.join(plOutputDict[k])
                }
                batch_data.append({"request_type": "update", "entity_type": "Shot", "entity_id": int(k), "data": data})

            # for k in plMovDict.keys():
            for k in plMovDict.keys():

                data = {
                    'sg_movhistory': '\n'.join(plMovDict[k])
                }
                batch_data.append({"request_type": "update", "entity_type": "Shot", "entity_id": int(k), "data": data})

            self.output_TE.append('Updating ...')
            QtGui.QApplication.processEvents()

            try:
                sg.batch(batch_data)
            except(RuntimeError, TypeError, NameError):
                self.output_TE.append('Error. Pls check if the fields "sg_outputhistory" and "sg_movhistory" exist in Shot')

            QtGui.QApplication.restoreOverrideCursor()

            # -----------------------
            #  METHOD 2:
            #  LOOP FROM SHOT
            # -----------------------

            # shotObj = sgShot(sg, projID)

            # i = 0
            # total = len(shotObj)
            # for shot in shotObj:

            #     i += 1
            #     self.progress_PB.setValue(100.0 * i / total)

            #     shotID = shot['id']
            #     filter = [
            #         ['project', 'is', {'type': 'Project', 'id': projID}],
            #         ['entity', 'is', {'type': 'Shot', 'id': shotID}]
            #     ]

            #     vrsObj = sg.find('Version', filter, ['code'])

            #     outputHistoryStr = ''
            #     for vrs in vrsObj:

            #         vrsID = vrs['id']

            #         filter = [
            #             ['version', 'is', {'type': 'Version', 'id': vrsID}],
            #             ['playlist.Playlist.code', 'contains', 'output']
            #         ]
            #         fields = ['playlist.Playlist.code']
            #         # , 'sg_sort_order', 'version.Version.code', 'version.Version.user', 'version.Version.entity']
            #         plObj = sg.find('PlaylistVersionConnection', filter, fields)

            #         for pl in plObj:
            #             if pl['playlist.Playlist.code']:

            #                 matchObj = re.match(r'\w+_(v\d+\w*)$', vrs['code'], re.M | re.I)
            #                 if matchObj:
            #                     outputHistoryStr += '{} : {}\n'.format(pl['playlist.Playlist.code'], matchObj.group(1))
            #                 else:
            #                     print ("version doesn't match required format: " + vrs['version.Version.code'])

            #     # print outputHistoryStr
            #     if outputHistoryStr:

            #         # self.output_TE.append('{} -> {} '.format(shot['code'], outputHistoryStr))
            #         sg.update("Shot", shotID, {'sg_outputhistory': outputHistoryStr})
            #         print '{} / {}'.format(i, total)

            #         QtGui.QApplication.processEvents()

            self.output_TE.append('')
            self.output_TE.append("Completed in %s sec" % round(time.clock() - startTime, 2))

    def changeStyleForBorder(self, state):

        global CB_STYLE
        if state:
            EMPTY_STYLE = """
            QCheckBox::indicator{
            }
            """
            self.dragReplace_CB.setStyleSheet(EMPTY_STYLE)
        else:
            self.dragReplace_CB.setStyleSheet(CB_STYLE)

    def createPlaylistMethod(self, rb):

        if rb.text() == "Reading from CSV":
            if rb.isChecked():
                self.tag_LB.setVisible(True)
                self.tag_LW.setVisible(True)

        elif rb.text() == "Scan MOVs Name":
            if rb.isChecked():
                self.tag_LB.setVisible(False)
                self.tag_LW.setVisible(False)

        elif rb.text() == "Scan Folders Name":
            if rb.isChecked():
                self.tag_LB.setVisible(False)
                self.tag_LW.setVisible(False)

    def deleteTemp(self):
        global OUTPUT_DIR2, OUTPUT_DIR
        OUTPUT_DIR2 = str(OUTPUT_DIR).replace('/', '\\')
        dir = os.listdir(OUTPUT_DIR2 + "/")
        for file in range(len(dir)):
            if not os.path.splitext(OUTPUT_DIR2 + "/" + dir[file])[1]:
                if os.path.isfile(OUTPUT_DIR2 + "/" + dir[file]):
                    os.system(r'taskkill /F /IM QuickTimeHelper-32.exe /T')
                    os.remove(OUTPUT_DIR2 + "\\" + dir[file])

    def closeEvent(self, event):
        self.stopRender()
        self.deleteTemp()
        event.accept()

# ==============================================Tool Bar================================== #
# ============Version Update=============#

    # def versionUpdate(self):
    #     import pefile
    #     global SERVER_INSTALLER
    #     if not os.path.exists(SERVER_INSTALLER):
    #         self.showDialogMsg('Info', 'Server installer not found.')
    #         return
    #     pe = pefile.PE(SERVER_INSTALLER)

    #     productVersion = '0'
    #     try:
    #         productVersion = pe.FileInfo[0].StringTable[0].entries['ProductVersion']
    #         if not productVersion:
    #             productVersion = '0'
    #     except:
    #         self.showDialogMsg('Info', 'Loading product version failed.')
    #         return

    #     global PROGRAM_VERSION

    #     if float(productVersion.strip()) > float(PROGRAM_VERSION):
    #         reply = self.askMsg(' ', 'New version available.\t\nUpdate ?')
    #         if reply == QtGui.QMessageBox.Yes:
    #             os.startfile(SERVER_INSTALLER)
    #             sys.exit(0)
    #     else:
    #         self.showDialogMsg('Info', 'This is the lastest version.')

    def showAbout(self):
        aboutMsg = '''

        FrD_pmTool

        Copyright (c)2017 Free-D Workshop Ltd.
        All rights reserved.

        Developed by chi (chi@nickyliu.com), lindy (lindy@freedworkshop.com)
        --------------------------------------------------------------------------------------------------------------------------------------------------------------------
        Version Log

            2017
                0824  Support name like proj_op_035_mot_v04
                0727  Ignore sg_sequence check just like SGT (Jules)
                0426  Recognize shot name with proj name prefix, for shot duration check (Jules)
                0329  Disable batch update status (Jules)
                0323  Add update "Output History" and "Mov History" under tab "Batch Tools" (Jules)
                0316  Add cut duration check, mainly for output (Jules)
                0309  Fast UI
                0223  Cleanup UI and codes by chi
                0202  create new / update existing playlist and linking shot version acc to dpx folder names &
                        .mov file names under a folder directory.
                0111  published 2nd version of 'create playlist' with customize playlist name and sleected by tags functions
                0109  beta version of create playlist with loaded csv spreadsheet

            2016
                0929  provide options for user to select different type of nuke license (render-only / Interactive)
                0920  Clear output UI, fixed minor bugs with fileQueue, render in Nuke10.0v4
                0907  Different Format sizes option (root, FullHD, 1280, 960, 720)
                0819  Added stop function and codec minor improvement
                0818  Updated UI and browse function, install-free
                0817  Added mov -> mov conversions (H.264 and Animation) function for PM(s)
                0811  First launch: Update Shotgun Shot Status function released
        '''
        self.showDialogMsg('About', aboutMsg)
# ==============================================Tool Bar End ================================== #

# ============Drag and Drop============= #

    def lwDragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def lwDragMoveEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def lwDropEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
            links = []
            for url in event.mimeData().urls():
                links.append(str(url.toLocalFile()))
            # self.emit(QtCore.SIGNAL("dropped"), links)
            self.movFileDropped(links)
        else:
            event.ignore()

    def folderDropEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
            links = []
            for url in event.mimeData().urls():
                links.append(str(url.toLocalFile()))
            # self.emit(QtCore.SIGNAL("dropped"), links)
            self.folderDropped(links)
        else:
            event.ignore()

    def SGT_getTimeNow1(self):
        return datetime.datetime.strftime(datetime.datetime.now(), '%m%d %H:%M:%S >')

    def SGT_getTimeNow2(self):
        return datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d')

    def SGT_getTimeNow3(self):
        return datetime.datetime.strftime(datetime.datetime.now(), '%H:%M:%S')
    # def createAnimtt(self):
    #     self.showDialogMsg('MOV codec - Animation', 'For Sendout purpose\n\nQuality: Best (100%)\n\n Update Gizmo info: \n 1. Current Date Time \n 2.Artist Name -> "FreeD03"')

    # def createH264tt(self):
    #     self.showDialogMsg('MOV codec - H264', 'For Presentation\n Quality: High (70%)\n')

    def showDialogMsg(self, title, text):
        qmsgbox = QtGui.QMessageBox()
        QtGui.QMessageBox.information(qmsgbox, title, text)

    def showFinishMsg(self, title, text):
        qmsgbox = QtGui.QMessageBox()
        return QtGui.QMessageBox.question(qmsgbox, title, text, QtGui.QMessageBox.Ok)

    def askMsg(self, title, text):
        qmsgbox = QtGui.QMessageBox()
        return QtGui.QMessageBox.question(qmsgbox, title, text, QtGui.QMessageBox.Yes | QtGui.QMessageBox.Cancel)

    def get_immediate_subdirectories(self, a_dir):
        return [name for name in os.listdir(a_dir)
                if os.path.isdir(os.path.join(a_dir, name))]

    def movFileDropped(self, arg):

        global fileQueue, fileNum
        i = 0
        for url in sorted(arg):
            if os.path.exists(url):
                if os.path.isfile(url) and url.endswith('.mov'):
                    if url in fileQueue:
                        pass
                    else:
                        self.hint_LB.setVisible(False)
                        self.mov_LW.addItem(os.path.basename(url))
                        fileQueue.append(url)
                        i += 1
        fileNum = len(fileQueue)
        self.render_LB.setText('0/ ' + str(fileNum) + ' Videos rendered.')

    def folderDropped(self, arg):

        if self.dragReplace_CB.isChecked():
            self.seq_LW.clear()

        allItems = [str(self.seq_LW.item(i).text()) for i in range(self.seq_LW.count())]

        i = 0
        for url in sorted(arg):
            if os.path.exists(url) and os.path.isdir(url):
                if url not in allItems:
                    self.hintCheck_LB.setVisible(False)
                    self.seq_LW.addItem(url)
                    i += 1

# ========================== Buttons Action ====================================== #

    def movClearItem(self):
        selItems = []
        selItems = self.mov_LW.selectedItems()
        if not selItems:
            return
        for item in selItems:
            global fileQueue, fileNum
            # print fileQueue
            for file in fileQueue:
                if str(item.text()) in file:
                    fileQueue.remove(file)
            self.mov_LW.takeItem(self.mov_LW.row(item))
        # print fileQueue
        fileNum = len(fileQueue)
        global currRow
        self.render_LB.setText(str(currRow) + " / " + str(fileNum) + ' Videos rendered.')

    def movClearAll(self):
        self.mov_LW.clear()
        global fileQueue, fileNum
        fileQueue = []
        fileNum = len(fileQueue)
        global currRow
        self.render_LB.setText(str(currRow) + " / " + str(fileNum) + ' Videos rendered.')
        self.hint_LB.setVisible(True)

    # ==========================================================================================================
    def clearAllCheck(self):

        self.seq_LW.clear()
        self.hintCheck_LB.setVisible(True)

    def clearSelCheck(self):

        selItems = self.seq_LW.selectedItems()
        allItems = [str(self.seq_LW.item(i).text()) for i in range(self.seq_LW.count())]

        for sel in selItems:
            if str(sel.text()) in allItems:
                self.seq_LW.takeItem(self.seq_LW.row(sel))

    # ==========================================================================================================
    # def callCutDurationCheckThread(self):

    #     self.CutDurationCheckThread = CutDurationCheckThread()
        # self.CutDurationCheckThread.runCheck()

    def checkCutDuration(self):

        allItems = [str(self.seq_LW.item(i).text()) for i in range(self.seq_LW.count())]

        matchedCount = 0
        failedCount = 0
        unknownCount = 0
        notFoundShotCount = 0

        # matchedItem  =  []
        failedItem = []
        unknownItem = []
        notFoundShotItem = []

        total = len(allItems)
        if total < 0:
            return

        self.output_TE.clear()
        self.output_TE.append('{} Start checking'.format(self.SGT_getTimeNow1()))

        QtGui.QApplication.setOverrideCursor(Qt.WaitCursor)

        global isStopCheck
        isStopCheck = False
        i = 0

        for d in allItems:

            self.progress_PB.setValue(100.0 * i / total)
            # print item
            folderName = os.path.basename(d)
            prjSeqShtPipVrs = self.SGT_parseForShot(folderName)

            if prjSeqShtPipVrs:

                # print prjSeqShtPipVrs
                prj = prjSeqShtPipVrs[0]
                seq = prjSeqShtPipVrs[1]
                sht = ''
                if seq:
                    sht = prj + '_' + seq + '_' + prjSeqShtPipVrs[2]
                else:
                    sht = prj + '_' + prjSeqShtPipVrs[2]

                projObj = sg.find('Project', [['name', 'contains', '~' + prj]])

                if projObj:
                    projID = projObj[0]['id']

                    if seq:
                        filter = [
                            ['project', 'is', {'type': 'Project', 'id': projID}],
                            ['code', 'is', sht] #,
                            # ['sg_sequence', 'name_is', seq]
                        ]
                    else:
                        filter = [
                            ['project', 'is', {'type': 'Project', 'id': projID}],
                            ['code', 'is', sht]
                        ]

                    shotObj = sg.find('Shot', filter, ['id', 'sg_cut_duration'])

                    if shotObj:

                        # searchStr = prj + '_' + sht
                        # filter = [
                        #     ['project', 'is', {'type': 'Project', 'id': projID}],
                        #     ['code', 'starts_with', searchStr]
                        # ]
                        # versionObj = sg.find('Version', filter, ['code'])
                        # if versionObj:
                        #     for i in range(len(shotObj)) > 1:
                        #         print versionObj[i]['code']

                        files = [item for item in os.listdir(d) if os.path.isfile(os.path.join(d, item))]
                        # print files
                        if 'Thumbs.db' in files:
                            files.remove('Thumbs.db')
                        if 'thumbs.db' in files:
                            files.remove('thumbs.db')

                        fileCount = len(files)
                        cutDuration = shotObj[0]['sg_cut_duration']
                        if cutDuration is None:
                            cutDuration = 0

                        if fileCount == cutDuration:
                            matchedCount += 1
                        else:
                            failedCount += 1
                            failedItem.append('{:35} : Cut {:<4}   File {:<4}'.format(folderName, cutDuration, fileCount))
                    else:
                        notFoundShotCount += 1
                        notFoundShotItem.append(folderName)
                else:
                    self.output_TE.append('{:35} : Proj not found'.format(folderName))
            else:
                unknownCount += 1
                unknownItem.append(folderName)

            i += 1

        QtGui.QApplication.restoreOverrideCursor()
        self.progress_PB.setValue(0)

        self.output_TE.append('')
        # self.output_TE.append('---------------------')
        # self.output_TE.append('       RESULT')
        self.output_TE.append('---------------------------------------------')
        self.output_TE.append('{} RESULT :'.format(self.SGT_getTimeNow1()))
        self.output_TE.append('---------------------------------------------')
        # self.output_TE.append('----------------------------------------------------------------------------')
        self.output_TE.append('')
        self.output_TE.append('{:17} {}'.format('Folders checked', total))
        self.output_TE.append('')
        self.output_TE.append('{:17} {}'.format('Matched', matchedCount))
        self.output_TE.append('{:17} {}'.format('Mis-matched', failedCount))

        j = 0
        for x in failedItem:
            j += 1
            if j % 2 == 1:
                self.output_TE.setTextColor(QtGui.QColor(233, 180, 180, 255))
            else:
                self.output_TE.setTextColor(QtGui.QColor(233, 180, 180, 170))

            self.output_TE.append('{:17} {}'.format('', x))

        self.output_TE.setTextColor(QtGui.QColor(255, 255, 255, 255))
        self.output_TE.append('{:17} {}'.format('Unknown folder', unknownCount))
        self.output_TE.setTextColor(QtGui.QColor(150, 150, 150, 255))
        for x in unknownItem:
            self.output_TE.append('{:17} {}'.format('', x))

        self.output_TE.setTextColor(QtGui.QColor(255, 255, 255, 255))
        self.output_TE.append('{:17} {}'.format('Shot not found', notFoundShotCount))

        self.output_TE.setTextColor(QtGui.QColor(150, 150, 150, 255))
        for x in notFoundShotItem:
            self.output_TE.append('{:17} {}'.format('', x))

        self.output_TE.setTextColor(QtGui.QColor(255, 255, 255, 255))

    def SGT_parseForShot(self, name=''):

        # matchObj = re.match(r'([a-z][A-Z]+)_(\S+\d+\S*)_(sh\d+\S*)_(\S+)_v(\d+)', name, re.M | re.I)
        matchObj = re.match(r'([a-z][A-Z]+)_(\S+)_(\S+)_(\S+)_v(\d+)', name, re.M | re.I)
        # Job with Seq
        if matchObj and ('_L' not in matchObj.group(3)):
            return [matchObj.group(1), matchObj.group(2), matchObj.group(3), matchObj.group(4), matchObj.group(5)]
        else:
            # Job without Seq
            # matchObj = re.match(r'([a-z][A-Z]+)_(sh\d+\S*)_(\S+)_v(\d+)', name, re.M | re.I)
            matchObj = re.match(r'([a-z][A-Z]+)_(\S+)_(\S+)_v(\d+)', name, re.M | re.I)
            if matchObj and ('_L' not in matchObj.group(2)):
                return [matchObj.group(1), '', matchObj.group(2), matchObj.group(3), matchObj.group(4)]
            else:
                # Job with Scene (+Layer no.)
                # matchObj = re.match(r'([a-z][A-Z]+)_(\S+\d\S*)_(sh\d+\S*)_(L\d+)_(\S+)_v(\d+)', name, re.M | re.I)
                matchObj = re.match(r'([a-z][A-Z]+)_(\S+)_(\S+)_(L\d+)_(\S+)_v(\d+)', name, re.M | re.I)
                if matchObj:
                    return [matchObj.group(1), matchObj.group(2), matchObj.group(3), matchObj.group(5), matchObj.group(6)]
                # Job without Scene (+Layer no.)
                else:
                    # matchObj = re.match(r'([a-z][A-Z]+)_(sh\d+\S*)_(L\d+)_(\S+)_v(\d+)', name, re.M | re.I)
                    matchObj = re.match(r'([a-z][A-Z]+)_(\S+)_(L\d+)_(\S+)_v(\d+)', name, re.M | re.I)
                    if matchObj:
                        return [matchObj.group(1), '', matchObj.group(2), matchObj.group(4), matchObj.group(5)]
            return []

    # ==========================================================================================================
    def updateStatus(self):

        if (self.askMsg('Info', 'Are you sure ?') == QtGui.QMessageBox.Yes):

            self.output_TE.clear()
            self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), "Start Checking......"))
            QtGui.QApplication.processEvents()
            shot_I = []
            tasks = []
            # PROJECT
            projectName = str(self.sgProject_CB.currentText())
            if projectName:
                project = sgProject(sg, projectName)
                project_ID = project['id']

                # SHOT
                # get and print shots' status
                shots = sgShot(sg, project_ID)

                for shot in range(len(shots)):
                    # print shots[shot]['sg_status_list']
                    shot_ID.append(shots[shot]['id'])

                # TASK
                updateCount = 0
                for shot in range(len(shot_ID)):  # for each shot
                    task = sgTask(sg, project_ID, shot_ID[shot])  # for each task
                    for t in range(len(task)):
                        tasks.append(task[t]['sg_status_list'])
                    for status in range(len(tasks)):
                        if tasks[status] == 'fin':
                            final = True
                        else:
                            final = False
                            break
                    # update task status
                    if (final is True and shots[shot]['sg_status_list'] == 'act'):
                        updateData = {'sg_status_list': 'fin'}
                        sg.update('Shot', shots[shot]['id'], updateData)
                        tasks = []
                        logger.info(projectName + "/" + shots[shot]['code'] + " to FINAL")
                        self.output_TE.append('%s %s %s %s' % (self.SGT_getTimeNow1(
                        ), "Updated shot :", shots[shot]['code'], " status to FINAL"))
                        QtGui.QApplication.processEvents()
                        updateCount += 1
                    else:
                        tasks = []
                self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), updateCount, " shot(s) updated."))
                self.output_TE.append("FINISH.")
                QtGui.QApplication.processEvents()

    def addToList(self, str_to_add):
        if str_to_add not in self.list_of_tags:
            self.list_of_tags.append(str_to_add)

    def browseCSV(self):

        global CSV_DIR
        global Folder_DIR

        if self.csv_RB.isChecked():
            # options = QtGui.QFileDialog.DontResolveSymlinks | QtGui.QFileDialog.ShowDirsOnly
            CSV_DIR = QtGui.QFileDialog.getOpenFileName(self,
                                                        "Select spreadsheet(.csv)", '',
                                                        "SpreadSheet (*.csv);;All Files (*)")
            if (CSV_DIR == ""):
                print ("CANCEL.")
            else:
                CSV_DIR = str(CSV_DIR).replace('\\', '/')
                self.playlistPath_ET.setText(CSV_DIR)
                self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), 'CSV PATH: ', CSV_DIR))
                # Read Tags from CSV File
                csvfile = open(CSV_DIR, 'r')
                self.list_of_tags = []
                for row in csv.DictReader(csvfile):
                    # Get type of Tags from csv
                    if row['Tags'] != "":
                        self.addToList(str(row['Tags']))
                for tag in range(len(self.list_of_tags)):
                    self.tag_LW.addItem(self.list_of_tags[tag])
                csvfile.close()
        else:
            options = QtGui.QFileDialog.DontResolveSymlinks | QtGui.QFileDialog.ShowDirsOnly
            FOLDER_DIR = QtGui.QFileDialog.getExistingDirectory(self,
                                                                "Select Folder Directory ",
                                                                "D:/" + getpass.getuser(), options)
            # print "ORIGINAL dir: " + str(OUTPUT_DIR)
            if (Folder_DIR == ""):
                print ("CANCEL.")
            else:
                FOLDER_DIR = str(Folder_DIR).replace('\\', '/')
                self.playlistPath_ET.setText(Folder_DIR)
                # self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), 'Folder Directory: ', Folder_DIR))

    # def browseFolder(self):

    def createPlaylist(self):

        if self.csv_RB.isChecked():

            # PG Bar set value back to 0
            self.progress_PB.setValue(0)
            global CSV_DIR
            CSV_DIR = self.playlistPath_ET.toPlainText()
            CSV_DIR = str(CSV_DIR).replace('\\', '/')
            # print CSV_DIR
            verNames = []
            projID = ""
            TagContent = []
            self.output_TE.clear()

            if self.playlistName_TE.toPlainText() == "":
                self.showDialogMsg("Warning", "Please enter a playlist name before creating playlist. ")
                return
            elif len(self.tag_LW.selectedItems()) < 1:
                self.showDialogMsg("Warning", "Please select tag(s) before creating playlist. ")
                return
            else:
                for item in self.tag_LW.selectedItems():
                    TagContent.append(item.text())
                # Read CSV File
                csvfile = open(CSV_DIR, 'r')
                for row in csv.DictReader(csvfile):
                    for tag in TagContent:
                        # Get all the clip with selected tag(s)
                        if row['Tags'] == tag:
                            verNames.append(row['Clip'])
                csvfile.close()
                # Get active projects from shotgun
                # act_projects = sg.find("Project", filters=[
                #                        ['sg_status', 'is', 'Active']], fields=['name'])
                act_projects = sg.find("Project", filters=[], fields=['name'])

                for project in act_projects:
                    if verNames[0].split("_")[0] == project['name'].split("~")[-1]:
                        projID = project['id']
                        print projID

                # Find if today's output list exist or not
                # todayStr = self.SGT_getTimeNow2()
                filter = [
                    ['project', 'is', {'type': 'Project', 'id': projID}],
                    ['code', 'contains', str(self.playlistName_TE.toPlainText())]]

                playlist = sg.find('Playlist', filter, [])

                # if playlist already exist,
                if playlist:
                    print 'duplicate playlist found! '
                    if self.askMsg("Info", "Playlist already exists !\nLink the shots to this playlist?     ") == QtGui.QMessageBox.Yes:
                        self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), 'Playlist updated:', "\"" + str(self.playlistName_TE.toPlainText()) + "\""))
                        plID = playlist[0]['id']
                    else:
                        return True
                    # index = len(playlist) + 1
                    # data = {
                    #     'project': {'type': 'Project', 'id': projID},
                    #     'code': str(todayStr + "_output_" + str(index))
                    # }
                # if playlist not exist,
                else:
                    data = {
                        'project': {'type': 'Project', 'id': projID},
                        'code': str(self.playlistName_TE.toPlainText())
                    }
                    # Create Playlist
                    playlist = sg.create('Playlist', data)
                    if playlist:
                        print "Today's Output playlist created."
                        self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), 'Today\'s output playlist created: ', "\"" + str(data['code'] + "\"")))
                        plID = playlist['id']
                    else:
                        self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), "Create Playlist Failed! Please try again later."))
                        print 'Create Playlist Failed! Please try again later.'

            # Version ID
            self.PlayListThread = PlayListThread(verNames, plID, self.sender().objectName())
            self.connect(self.PlayListThread, QtCore.SIGNAL('linkVerFailed'), self.linkPB_fail)
            self.connect(self.PlayListThread, QtCore.SIGNAL('VerLinked'), self.linkPB_ok)
            self.connect(self.PlayListThread, QtCore.SIGNAL('finished'), self.linkVerFinished)
            self.PlayListThread.SGPL_linkVersion()
            self.linkVerFinished()

        if self.scanMov_RB.isChecked() or self.scanFolder_RB.isChecked():

            # PG Bar set value back to 0
            self.progress_PB.setValue(0)
            global FOLDER_DIR
            FOLDER_DIR = self.playlistPath_ET.toPlainText()
            FOLDER_DIR = str(FOLDER_DIR).replace('\\', '/')
            verNames = []
            projID = ""
            # .mov Files check box
            if self.scanMov_RB.isChecked():
                movArr = []
                for mov in glob.glob(FOLDER_DIR + "/*mov"):
                    mov = str(mov).replace('\\', '/')
                    movArr.append(str(mov))
                print movArr
                # each mov get its shot and version name
                for mov in movArr:
                    verNames.append(os.path.splitext(os.path.basename(mov))[0])
                    # verNames.append(os.path.splitext(os.path.basename(mov)))[0]
                print verNames

            # subfolder (dpx folder) check box
            if self.scanFolder_RB.isChecked():

                # folderArr = []
                name = [name for name in os.listdir(FOLDER_DIR + "/") if os.path.isdir(str(FOLDER_DIR + "/" + name))]
                verNames += name
                print verNames

            self.output_TE.clear()

            if self.playlistName_TE.toPlainText() == "":
                self.showDialogMsg("Info", "Please enter a playlist name.      ")
            else:
                if len(verNames) > 0:
                    # Get active projects from shotgun
                    # act_projects = sg.find("Project", filters=[
                    #                        ['sg_status', 'is', 'Active']], fields=['name'])
                    act_projects = sg.find("Project", filters=[], fields=['name'])
                    # Get the target active project ID from the short form of verNames
                    for project in act_projects:
                        if verNames[0].split("_")[0] == project['name'].split("~")[-1]:
                            projID = project['id']
                            print projID
                    # Find if today's output list exist or not
                    filter = [
                        ['project', 'is', {'type': 'Project', 'id': projID}],
                        ['code', 'contains', str(self.playlistName_TE.toPlainText())]]

                    playlist = sg.find('Playlist', filter, [])

                    # if playlist already exist,
                    if playlist:
                        print 'duplicate playlist found! '
                        if self.askMsg("Info", "Playlist already exists !\nLink the shots to this playlist ?     ") == QtGui.QMessageBox.Yes:
                            self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), 'Playlist updated:', "\"" + str(self.playlistName_TE.toPlainText()) + "\""))
                            plID = playlist[0]['id']
                        else:
                            return True

                    else:
                        data = {
                            'project': {'type': 'Project', 'id': projID},
                            'code': str(self.playlistName_TE.toPlainText())
                        }
                        # Create Playlist
                        playlist = sg.create('Playlist', data)
                        if playlist:
                            print "New playlist created."
                            self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), 'New playlist created:', "\"" + str(data['code'] + "\"")))
                            plID = playlist['id']
                        else:
                            self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), "Create Playlist Failed! Try again later."))
                            print 'Create Playlist Failed! Try again later.'

            if len(verNames) > 0:
                # Version ID
                self.PlayListThread = PlayListThread(verNames, plID, self.sender().objectName())
                self.connect(self.PlayListThread, QtCore.SIGNAL('linkVerFailed'), self.linkPB_fail)
                self.connect(self.PlayListThread, QtCore.SIGNAL('VerLinked'), self.linkPB_ok)
                self.connect(self.PlayListThread, QtCore.SIGNAL('finished'), self.linkVerFinished)
                self.PlayListThread.SGPL_linkVersion()
                self.linkVerFinished()
            else:
                self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), 'No valid version matched in shotgun.'))

    def linkPB_fail(self, verName, verNames, progress, senderBtn):

        self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), verName, "Version already connected/existed OR non-existing version."))
        self.output_TE.moveCursor(QtGui.QTextCursor.End)
        percent = int(100 * progress / len(verNames))
        self.progress_PB.setValue(percent)
        QtGui.QApplication.processEvents()

    def linkPB_ok(self, verName, verNames, progress, senderBtn):

        percent = int(100 * progress / len(verNames))
        self.progress_PB.setValue(percent)
        self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), "Linked to playlist:", verName, ))
        self.output_TE.moveCursor(QtGui.QTextCursor.End)
        QtGui.QApplication.processEvents()

    def linkVerFinished(self):

        self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), "Finished."))
        self.output_TE.moveCursor(QtGui.QTextCursor.End)
        self.showDialogMsg('Info', 'Versions linked to Playlist.      ')
        self.progress_PB.setValue(0)
        QtGui.QApplication.processEvents()

    # ===========================  SHOTGUN --> GOOGLE SPREADSHEET ================================== #
    def browseSGCSV(self):

        global SGCSV_DIR
        SGCSV_DIR = QtGui.QFileDialog.getOpenFileName(self,
                                                      "Select spreadsheet(.csv)", '',
                                                      "SpreadSheet (*.csv);;All Files (*)")
        if (SGCSV_DIR == ""):
            print ("CANCEL.")
        else:
            SGCSV_DIR = str(SGCSV_DIR).replace('\\', '/')
            self.shotgunCSV_text.setText(SGCSV_DIR)
            self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), 'SGCSV PATH: ', SGCSV_DIR))

    def updateGoogleSS(self):
        pass

        # # get authorize from google user (generate the .json for access if .json is not existed)
        # gc = pygsheets.authorize()
        # # Open spreadsheet with the given name
        # sh = gc.open(self.shotgunCSV_text_2.toPlainText())

        # # ====================== LOADING CURSOR ================= #
        # QtGui.QApplication.setOverrideCursor(Qt.WaitCursor)
        # # select the 1st worksheet from spreadsheet
        # wks = sh.worksheet('index', 0)
        # print wks
        # # get the COLUMN row from the spreadsheet
        # keyRow_num = 0
        # keyRow = None
        # keyColumn_Dict = {}  # get the column item (col position) e.g. Shot:0 dura:2 --> can specific the position e.g. wks[keyRow_num][keyColumn_Dict['Shot']]
        # for row in wks:
        #     if 'shot' in row[0].lower() or 'shot code' in row[0].lower():
        #         keyRow = row
        #         break
        #     keyRow_num += 1
        # if keyRow is not None:
        #     i = 0
        #     for item in keyRow:
        #         if item != '':
        #             if item != 'thumbnail':
        #                 keyColumn_Dict[item] = wks[keyRow_num][i]
        #         i += 1
        # # print keyColumn_Dict
        # # read CSV
        # keyColumn_CSV_Arr = []
        # sgcsvfile = open(SGCSV_DIR, 'r')
        # next(sgcsvfile)  # get it from the 2nd row
        # for row in csv.DictReader(sgcsvfile):
        #     for item in row:
        #         if item.lower() != "thumbnail":
        #             keyColumn_CSV_Arr.append(item)
        #     break
        #     # print (row['Shot Code'] + " " + row['Cut Duration'] + " " + row['Description'])
        # sgcsvfile.close()
        # # print keyColumn_CSV_Arr

        # # get the targeted of update columns
        # updateCols = []
        # for kg in keyColumn_Dict:
        #     for kc in keyColumn_CSV_Arr:
        #         if kg.rstrip() == kc.rstrip():
        #             updateCols.append(kg)
        # print updateCols

        # # update the targeted
        # # =================== RESTORE CURESOR ================== #
        # QtGui.QApplication.restoreOverrideCursor()
        # # print keyColumn_Dict
        # # print keyColumn_Dict['Shot']

    # ===========================  RENDER MOV - MOV FUNCTIONS ============================================= #
    def setExistingDirectory(self):
        global OUTPUT_DIR

        options = QtGui.QFileDialog.DontResolveSymlinks | QtGui.QFileDialog.ShowDirsOnly
        OUTPUT_DIR = QtGui.QFileDialog.getExistingDirectory(self,
                                                            "Select Output Directory ",
                                                            "D:/" + getpass.getuser(), options)
        # print "ORIGINAL dir: " + str(OUTPUT_DIR)
        if (OUTPUT_DIR == ""):
            print ("CANCEL.")
        else:
            OUTPUT_DIR = str(OUTPUT_DIR).replace('\\', '/')
            self.path_text.setText(OUTPUT_DIR)
            self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), 'OUTPUT PATH: ', OUTPUT_DIR))
            # self.output_TE.clear()
            # self.renderMOV()

    def readyrenderAnimMOV(self):
        self.output_TE.clear()
        global OUTPUT_DIR, currRow
        OUTPUT_DIR = self.path_text.toPlainText()
        OUTPUT_DIR = str(OUTPUT_DIR).replace('\\', '/')
        if OUTPUT_DIR == str(os.path.dirname(fileQueue[currRow])):
            self.showDialogMsg('Warning', str(OUTPUT_DIR) + '\nOutput path cannot be the same as the source. Try another output path.')
        else:
            global conversion
            conversion = "anim"
            self.renderMOV()

    def readyrenderH264MOV(self):
        self.output_TE.clear()
        global OUTPUT_DIR, currRow
        OUTPUT_DIR = self.path_text.toPlainText()
        OUTPUT_DIR = str(OUTPUT_DIR).replace('\\', '/')
        if OUTPUT_DIR == str(os.path.dirname(fileQueue[currRow])):
            self.showDialogMsg('Warning', str(OUTPUT_DIR) + '\nOutput path cannot be the same as the source. Try another output path.')
        else:
            global conversion
            conversion = "h264"
            self.renderMOV()

    def renderMOV(self):
        global fileQueue, fileNum
        global currRow, totalFrame, CONVERSION_ANIM, CONVERSION_H264
        # print str(OUTPUT_DIR)  #// -- server path
        # print str(os.path.dirname(fileQueue[currRow]))
        self.render_LB.setText(str(currRow) + " / " + str(fileNum) + ' Videos rendered.')
        if (os.path.isdir(OUTPUT_DIR)) and fileQueue and (bStop is False):
            self.render_anim_Btn.setEnabled(False)
            self.render_h264_Btn.setEnabled(False)
            if currRow < len(fileQueue):
                self.progress_PB.setValue(0)
                QtGui.QApplication.processEvents()
                self.output_TE.setTextColor(QtGui.QColor('white'))
                global conversion
                if conversion == "anim":
                    self.output_TE.append('%s %s %s %s' % (self.SGT_getTimeNow1(), "Start rendering ", os.path.basename(fileQueue[currRow]), "(Animation)......"))
                else:
                    self.output_TE.append('%s %s %s %s' % (self.SGT_getTimeNow1(), "Start rendering ", os.path.basename(fileQueue[currRow]), "(H.264)......"))
                vid = imageio.get_reader(fileQueue[currRow], 'ffmpeg')
                totalFrame = int(vid._meta['nframes'])
                # print "TOTAL FRAME: " + str(totalFrame)
                self.movProcess = QProcess(self)

                global size
                if self.format1_RB.isChecked():
                    size = 0
                elif self.format2_RB.isChecked():
                    size = 1
                elif self.format3_RB.isChecked():
                    size = 2
                elif self.format4_RB.isChecked():
                    size = 3
                elif self.format5_RB.isChecked():
                    size = 4
                # size = self.size_CBB.getCurrentIndex()

                if conversion == "anim":
                    args = self.createMovCmdArg(str(fileQueue[currRow]), str(OUTPUT_DIR), CONVERSION_ANIM, str(size))
                    # print self.format_CB.currentIndex()
                elif conversion == "h264":
                    args = self.createMovCmdArg(str(fileQueue[currRow]), str(OUTPUT_DIR), CONVERSION_H264, str(size))
                    # print self.format_CB.currentIndex()
                    # print args
                    # print "h264"
                self.movProcess.setProcessChannelMode(QProcess.MergedChannels)
                self.movProcess.start(NUKE_EXE, args)
                # self.movProcess.setReadChannel(QProcess.StandardOutput)
                self.movProcess.readyRead.connect(self.readRenderMOV)
                self.movProcess.finished.connect(self.renderMOVDone)
            else:  # Complete
                currRow = 0
                fileQueue = []
                self.render_anim_Btn.setEnabled(True)
                self.render_h264_Btn.setEnabled(True)
                self.progress_PB.setValue(0)
                QtGui.QApplication.processEvents()
                self.output_TE.setTextColor(QtGui.QColor('white'))
                self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), "Render MOV(s) completed."))
                QtGui.QApplication.processEvents()
                reply = self.showFinishMsg('Finish', 'Render MOV(s) completed.')
                if reply == QtGui.QMessageBox.Ok:
                    global OUTPUT_DIR2
                    OUTPUT_DIR2 = str(OUTPUT_DIR).replace('/', '\\')
                    os.startfile(OUTPUT_DIR2)

        elif not (os.path.isdir(OUTPUT_DIR)):
            self.showDialogMsg('Warning', '\nInvalid output path! Please check if the output path is correct.')
        elif not fileQueue:
            pass
        else:
            self.render_anim_Btn.setEnabled(True)
            self.render_h264_Btn.setEnabled(True)
            # ======================== SHOTGUN FIND ====================== #

    def stopRender(self):
        if self.movProcess is not None:
            global bStop
            bStop = True
            self.movProcess.closeWriteChannel()
            self.movProcess.kill()
            self.deleteTemp()

    def readRenderMOV(self):

        while (self.movProcess.canReadLine()):
            line = str(self.movProcess.readLine())
            # print line
            if 'Writing' in line:
                global currFrame, totalFrame
                currFrame += 1
                # print str(currFrame) + " / " + str(totalFrame)
                percent = int(100 * currFrame / totalFrame)
                # print str(percent)
                # print "currFrame: " + str(currFrame)
                self.progress_PB.setValue(percent)
                # print "%" + str(percent)
                QtGui.QApplication.processEvents()
                if 'Write access not permitted on' in line:
                    self.output_TE.setTextColor(QtGui.QColor(200, 88, 88, 255))
                    self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), 'Failed to render : MOV file is in use / opening by other program.'))
            elif 'A license for \'nuke\' was not found.' in line:
                self.output_TE.setTextColor(QtGui.QColor(200, 88, 88, 255))
                self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), 'Locate Nuke License Server Failed! Please try again later.'))
                # print "DISCONNECTED"
                self.stopRender()
            elif 'All licenses are currently in use' in line:
                self.output_TE.setTextColor(QtGui.QColor(200, 88, 88, 255))
                self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), 'All render license are currently in use! Please try again later.'))
                self.showDialogMsg('Info', 'All Nuke Licenses are in use !       ')
                self.stopRender()

    def renderMOVDone(self):
        global bStop, currFrame, currRow, fileQueue
        currFrame = 0
        # Running
        if bStop is False and os.path.exists(OUTPUT_DIR + "/" + os.path.basename(fileQueue[currRow])):
            self.mov_LW.takeItem(0)  # !!!!
            # change text output to light green
            self.output_TE.setTextColor(QtGui.QColor('lightgreen'))
            self.output_TE.append('%s %s %s' % (self.SGT_getTimeNow1(), os.path.basename(fileQueue[currRow]), " CREATED."))
            # self.output_TE.setStyleSheet('QTextEdit {color:lightgreen;}')
            currRow += 1  # !!!!
            self.render_LB.setText(str(currRow) + str(fileNum) + ' Videos rendered.')
            self.progress_PB.setValue(100)
            QtGui.QApplication.processEvents()
            self.renderMOV()
        # Stop
        else:
            bStop = False
            self.progress_PB.setValue(0)
            self.output_TE.setTextColor(QtGui.QColor(200, 88, 88, 255))
            self.output_TE.append('%s %s' % (self.SGT_getTimeNow1(), "PAUSE: Render process stopped. (Press run button to resume.)      "))
            self.render_anim_Btn.setEnabled(True)
            self.render_h264_Btn.setEnabled(True)
            QtGui.QApplication.processEvents()

    def createMovCmdArg(self, src, dist, conversion, reformat):
        global currRow
        # if self.Render_RB.isChecked():
        #     return [
        #         "-t",
        #         conversion,
        #         src,
        #         dist + "/" + os.path.basename(fileQueue[currRow]),
        #         "\'" + reformat + "\'"
        #     ]
        # else:
        return [
            "-ti",
            conversion,
            src,
            dist + "/" + os.path.basename(fileQueue[currRow]),
            "\'" + reformat + "\'"
        ]


def sgProject(sg, project):
    # check name == variable
    filter = [
        ['name', 'is', project]
    ]
    return sg.find_one("Project", filter)


def sgShot(sg, project_ID):
    filter = [
        ['project', 'is', {'type': 'Project', 'id': project_ID}]
    ]
    return sg.find("Shot", filter, ['sg_status_list', 'code'])


def sgTask(sg, project_ID, shot_ID):
    filter = [
        ['project', 'is', {'type': 'Project', 'id': project_ID}], [
            'entity', 'is', {'type': 'Shot', 'id': shot_ID}]
    ]
    return sg.find('Task', filter, ['sg_status_list'])


def isrunning(exe):
    try:
        p = os.popen(r'tasklist /FI "IMAGENAME eq "' + exe + ' /FO "LIST" 2>&1', 'r')
        PID = p.read().split('\n')[2].split(":")[1].lstrip(" ")
        p.close()
        return PID
    except:
        p.close()
        return "None"


def main():
    app = QtGui.QApplication(sys.argv)
    # app.setStyleSheet(qdarkstyle.load_stylesheet(pyside=False))
    app.setStyle("plastique")
    myWin = FrD_pmTool()
    myWin.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
