# -*- coding:utf-8  -*-
'''
Created on 2013-6-15

@author: hikaru
QQ: 286484545
email: hikaru870806@hotmail.com
如有问题或建议请联系
'''

from common import common
import copy
import os
import time

class downloadVideo(common.Tool):

    def trace(self, msg):
        super(downloadVideo, self).trace(msg, self.isShowError, self.traceLogPath, self.isShowError, self.isLog)
    
    def printErrorMsg(self, msg):
        super(downloadVideo, self).printErrorMsg(msg, self.isShowError, self.errorLogPath, self.isShowError, self.isLog)
        
    def printStepMsg(self, msg):
        super(downloadVideo, self).printStepMsg(msg, self.isShowError, self.stepLogPath, self.isShowError, self.isLog)
        
    def __init__(self):
        processPath = os.getcwd()
        configFile = open(processPath + "\\..\\common\\config.ini", 'r')
        lines = configFile.readlines()
        configFile.close()
        config = {}
        for line in lines:
            line = line.lstrip().rstrip().replace(" ", "")
            if len(line) > 1 and line[0] != "#":
                try:
                    line = line.split("=")
                    config[line[0]] = line[1]
                except Exception, e:
                    self.printMsg(str(e))
                    pass
        # 程序配置
        self.isLog = self.getConfig(config, "IS_LOG", 1, 2)
        self.isShowError = self.getConfig(config, "IS_SHOW_ERROR", 1, 2)
        self.isDebug = self.getConfig(config, "IS_DEBUG", 1, 2)
        self.isShowStep = self.getConfig(config, "IS_SHOW_STEP", 1, 2)
        # 代理
        self.isProxy = self.getConfig(config, "IS_PROXY", 2, 2)
        self.proxyIp = self.getConfig(config, "PROXY_IP", "127.0.0.1", 0)
        self.proxyPort = self.getConfig(config, "PROXY_PORT", "8087", 0)
        # 文件路径
        self.errorLogPath = self.getConfig(config, "ERROR_LOG_FILE_NAME", "\\log\\errorLog.txt", 3)
        if self.isLog == 0:
            self.traceLogPath = ''
            self.stepLogPath = ''
        else:
            self.traceLogPath = self.getConfig(config, "TRACE_LOG_FILE_NAME", "\\log\\traceLog.txt", 3)
            self.stepLogPath = self.getConfig(config, "STEP_LOG_FILE_NAME", "\\log\\stepLog.txt", 3)
        self.memberUIdListFilePath = self.getConfig(config, "MEMBER_UID_LIST_FILE_NAME", "\\info\\idlist.txt", 3)
        self.resultFilePath = self.getConfig(config, "GET_VIDEO_DOWNLOAD_URL_FILE_NAME", "\\info\\get_result.html", 3)
        self.printMsg(u"配置文件读取完成")
        
    def main(self):
        startTime = time.time()
        # 判断各种目录是否存在
        # 日志文件保存目录
        if self.isLog == 1:
            stepLogDir = os.path.dirname(self.stepLogPath)
            if not self.createDir(stepLogDir):
                self.printErrorMsg(u"创建步骤日志目录：" + stepLogDir + u" 失败，程序结束！")
                self.processExit()
            self.printStepMsg(u"步骤日志目录不存在，创建文件夹: " + stepLogDir)
            traceLogDir = os.path.dirname(self.traceLogPath)
            if not self.createDir(traceLogDir):
                self.printErrorMsg(u"创建调试日志目录：" + traceLogDir + u" 失败，程序结束！")
                self.processExit()
            self.printStepMsg(u"调试日志目录不存在，创建文件夹: " + traceLogDir)
        errorLogDir = os.path.dirname(self.errorLogPath)
        if not self.createDir(errorLogDir):
            self.printErrorMsg(u"创建错误日志目录：" + errorLogDir + u" 失败，程序结束！")
            self.processExit()
        self.printStepMsg(u"错误日志目录不存在，创建文件夹：" + errorLogDir)
        # 视频URL保存文件
        videoUrlFileDir = os.path.dirname(self.resultFilePath)
        if not self.createDir(videoUrlFileDir):
            self.printStepMsg(u"视频下载地址页面目录，创建文件夹：" + traceLogDir)
            self.processExit()
        self.printStepMsg(u"视频下载地址页面目录不存在，创建文件夹：" + videoUrlFileDir)
        # 视频url保存的html文件
        if os.path.exists(self.resultFilePath):
            isDelete = False
            while not isDelete:
                # 手动输入是否删除旧存档文件
                input = raw_input(u"视频下载地址页面：" + self.resultFilePath + u" 已经存在，是否需要删除该文件并继续程序? (Y)es or (N)o：")
                try:
                    input = input.lower()
                    if input in ["y", "yes"]:
                        isDelete = True
                    elif input in ["n", "no"]:
                        self.processExit()
                except Exception, e:
                    self.printErrorMsg(str(e))
                    pass
                resultFile = open(self.resultFilePath, 'w')
                resultFile.close()
        # 设置代理
        if self.isProxy == 1 or self.isProxy == 2:
            self.proxy(self.proxyIp, self.proxyPort, 'https')
        # 寻找idlist，如果没有结束进程
        userIdList = {}
        if os.path.exists(self.memberUIdListFilePath):
            userListFile = open(self.memberUIdListFilePath, 'r')
            allUserList = userListFile.readlines()
            userListFile.close()
            for userInfo in allUserList:
                if len(userInfo) < 10:
                    continue
                userInfo = userInfo.replace(" ", "")
                userInfo = userInfo.replace("\n", "")
                userInfoList = userInfo.split("\t")
                userIdList[userInfoList[0]] = userInfoList
        else:
            self.printErrorMsg(u"用户ID存档文件: " + self.memberUIdListFilePath + u"不存在，程序结束！")
            self.processExit()
        newMemberUidListFilePath = os.getcwd() + "\\info\\" + time.strftime('%Y-%m-%d_%H_%M_%S_', time.localtime(time.time())) + os.path.split(self.memberUIdListFilePath)[-1]
        newMemberUidListFile = open(newMemberUidListFilePath, 'w')
        newMemberUidListFile.close()
        # 复制处理存档文件
        newMemberUidList = copy.deepcopy(userIdList)
        for newUserId in newMemberUidList:
            # 如果没有名字，则名字用uid代替
            if len(newMemberUidList[newUserId]) < 2:
                newMemberUidList[newUserId].append(newMemberUidList[newUserId][0])
            # image count
            if len(newMemberUidList[newUserId]) < 3:
                newMemberUidList[newUserId].append("0")
            # image URL
            if len(newMemberUidList[newUserId]) < 4:
                newMemberUidList[newUserId].append("")
            # video count
            if len(newMemberUidList[newUserId]) < 5:
                newMemberUidList[newUserId].append("0")
            # video token
            if len(newMemberUidList[newUserId]) < 6:
                newMemberUidList[newUserId].append("")
            else:
                newMemberUidList[newUserId][5] = ""
            # 处理member 队伍信息
            if len(newMemberUidList[newUserId]) < 7:
                newMemberUidList[newUserId].append("")
                
        allVideoCount = 0
        # 循环获取每个id
        for userId in userIdList:
            userName = newMemberUidList[userId][1]
            self.printStepMsg(u"UID: " + str(userId) + u", 名字: " + userName.decode("GBK"))
            # 初始化数据
            videoCount = 0
            videoUrlList = []
            videoAlbumUrl = 'https://plus.google.com/' + userId + '/videos'
            self.trace(u"视频专辑地址：" + videoAlbumUrl)
            videoAlbumPage = self.doGet(videoAlbumUrl)
            if videoAlbumPage:
                videoUrlIndex = videoAlbumPage.find('&quot;https://video.googleusercontent.com/?token')
                while videoUrlIndex != -1:
                    videoUrlStart = videoAlbumPage.find("http", videoUrlIndex)
                    videoUrlStop = videoAlbumPage.find('&quot;', videoUrlStart)
                    videoUrl = videoAlbumPage[videoUrlStart:videoUrlStop].replace("\u003d", "=")
                    # video token 取前20位
                    tokenStart = videoUrl.find("?token=") + 7
                    videoToken = videoUrl[tokenStart:tokenStart + 20]
                    # 将第一个视频的token保存到新id list中
                    if newMemberUidList[userId][5] == "":
                        newMemberUidList[userId][5] = videoToken
                    if len(userIdList[userId]) >= 6:
                        if videoToken == userIdList[userId][5]:
                            break
                    # 判断是否重复
                    if videoUrl in videoUrlList:
                        videoUrlIndex = videoAlbumPage.find('&quot;https://video.googleusercontent.com/?token', videoUrlIndex + 1)
                        continue
                    videoUrlList.append(videoUrl)
                    videoCount += 1
                    videoUrlIndex = videoAlbumPage.find('&quot;https://video.googleusercontent.com/?token', videoUrlIndex + 1)
            else:
                self.printErrorMsg(u"无法获取视频首页: " + videoAlbumUrl)
            # 生成下载视频url的文件
            if videoCount > 0:
                allVideoCount += videoCount
                index = 0
                try:
                    index = int(userIdList[userId][4])
                except:
                    pass
                newMemberUidList[userId][4] = str(int(newMemberUidList[userId][4]) + videoCount)
                resultFile = open(self.resultFilePath, 'a')
                while videoUrlList != []:
                    videoUrl = videoUrlList.pop()
                    index += 1
                    resultFile.writelines("<a href=" + videoUrl + ">" + str(userName + "_" + "%03d" % index) + "</a><br>\n")
                resultFile.close()
            # 保存最后的信息
            newMemberUidListFile = open(newMemberUidListFilePath, 'a')
            newMemberUidListFile.write("\t".join(newMemberUidList[userId]) + "\n")
            newMemberUidListFile.close()

        # 排序并保存新的idList.txt
        tmpList = []
        tmpUserIdList = sorted(newMemberUidList.keys())
        for index in tmpUserIdList:
            tmpList.append("\t".join(newMemberUidList[index]))
        newMemberUidListString = "\n".join(tmpList)
        newMemberUidListFilePath = os.getcwd() + "\\info\\" + time.strftime('%Y-%m-%d_%H_%M_%S_', time.localtime(time.time())) + os.path.split(self.memberUIdListFilePath)[-1]
        self.printStepMsg(u"保存新存档文件：" + newMemberUidListFilePath)
        newMemberUidListFile = open(newMemberUidListFilePath, 'w')
        newMemberUidListFile.write(newMemberUidListString)
        newMemberUidListFile.close()
        
        stopTime = time.time()
        self.printStepMsg(u"存档文件中所有用户视频地址已成功获取，耗时" + str(int(stopTime - startTime)) + u"秒，共计视频地址" + str(allVideoCount) + "个")
        
if __name__ == '__main__':
    downloadVideo().main()
