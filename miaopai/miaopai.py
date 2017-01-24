# -*- coding:UTF-8  -*-
"""
秒拍视频爬虫
http://www.miaopai.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import log, net, robot, tool
import json
import os
import re
import threading
import time
import traceback

ACCOUNTS = []
TOTAL_VIDEO_COUNT = 0
GET_VIDEO_COUNT = 0
VIDEO_TEMP_PATH = ""
VIDEO_DOWNLOAD_PATH = ""
NEW_SAVE_DATA_PATH = ""
IS_SORT = True


# 获取指定账号的全部关注列表
# suid -> 0r9ewgQ0v7UoDptu
def get_follow_list(suid):
    page_count = 1
    follow_list = {}
    while True:
        one_page_follow_data = get_one_page_follow_data(suid, page_count)
        if one_page_follow_data is None:
            break
        print one_page_follow_data
        stat = int(one_page_follow_data["stat"])
        if stat == 1 or stat == 2:
            one_page_follow_list = re.findall('<a title="([^"]*)" href="http://www.miaopai.com/u/paike_([^"]*)">', one_page_follow_data["msg"])
            for account_name, account_id in one_page_follow_list:
                follow_list[account_id] = account_name
            if stat == 1:
                page_count += 1
            else:
                return follow_list
    return None


# 获取指定账号一页的关注列表
# suid -> 0r9ewgQ0v7UoDptu
def get_one_page_follow_data(suid, page_count):
    follow_list_url = "http://www.miaopai.com/gu/follow?page=%s&suid=%s" % (page_count, suid)
    follow_list_page_response = net.http_request(follow_list_url)
    if follow_list_page_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        try:
            follow_list_data = json.loads(follow_list_page_response.data)
        except ValueError:
            pass
        else:
            if robot.check_sub_key(("msg", "stat"), follow_list_data) and follow_list_data["stat"].isdigit():
                return follow_list_data
    return None


# 获取用户的suid，作为查找指定用户的视频页的凭证
# account_id -> mi9wmdhhof
def get_suid(account_id):
    index_page_url = "http://www.miaopai.com/u/paike_%s" % account_id
    index_page_response = net.http_request(index_page_url)
    if index_page_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        suid = tool.find_sub_string(index_page_response.data, '<button class="guanzhu gz" suid="', '" heade="1" token="">+关注</button>')
        if suid:
            return suid
    return None


# 获取一页的视频信息
# suid -> 0r9ewgQ0v7UoDptu
def get_one_page_video_data(suid, page_count):
    # http://www.miaopai.com/gu/u?page=1&suid=0r9ewgQ0v7UoDptu&fen_type=channel
    media_page_url = "http://www.miaopai.com/gu/u?page=%s&suid=%s&fen_type=channel" % (page_count, suid)
    media_page_response = net.http_request(media_page_url)
    if media_page_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        try:
            media_page = json.loads(media_page_response.data)
        except ValueError:
            pass
        else:
            if robot.check_sub_key(("isall", "msg"), media_page):
                return media_page
    return None


# 获取scid列表
def get_scid_list(msg_data):
    return re.findall('data-scid="([^"]*)"', msg_data)


# 根据video id获取下载地址
# video_id -> 9oUkvbHMnrliNyKX3VSDNw__
def get_video_url_by_video_id(video_id):
    video_info_url = "http://gslb.miaopai.com/stream/%s.json?token=" % video_id
    video_info_page_response = net.http_request(video_info_url)
    if video_info_page_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        try:
            video_info_page = json.loads(video_info_page_response.data)
        except ValueError:
            pass
        else:
            if robot.check_sub_key(("status", "result"), video_info_page):
                if int(video_info_page["status"]) == net.HTTP_RETURN_CODE_SUCCEED:
                    for result in video_info_page["result"]:
                        if robot.check_sub_key(("path", "host", "scheme"), result):
                            return str(result["scheme"]) + str(result["host"]) + str(result["path"])
    return None


class MiaoPai(robot.Robot):
    def __init__(self):
        global GET_VIDEO_COUNT
        global VIDEO_TEMP_PATH
        global VIDEO_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH
        global IS_SORT

        sys_config = {
            robot.SYS_DOWNLOAD_VIDEO: True,
        }
        robot.Robot.__init__(self, sys_config)

        # 设置全局变量，供子线程调用
        GET_VIDEO_COUNT = self.get_video_count
        VIDEO_TEMP_PATH = self.video_temp_path
        VIDEO_DOWNLOAD_PATH = self.video_download_path
        IS_SORT = self.is_sort
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)

    def main(self):
        global ACCOUNTS

        # 解析存档文件
        # account_id  video_count  last_video_url
        account_list = robot.read_save_data(self.save_data_path, 0, ["", "0", "0", ""])
        ACCOUNTS = account_list.keys()

        # 循环下载每个id
        main_thread_count = threading.activeCount()
        for account_id in sorted(account_list.keys()):
            # 检查正在运行的线程数
            while threading.activeCount() >= self.thread_count + main_thread_count:
                if robot.is_process_end() == 0:
                    time.sleep(10)
                else:
                    break

            # 提前结束
            if robot.is_process_end() > 0:
                break

            # 开始下载
            thread = Download(account_list[account_id], self.thread_lock)
            thread.start()

            time.sleep(1)

        # 检查除主线程外的其他所有线程是不是全部结束了
        while threading.activeCount() > main_thread_count:
            time.sleep(10)

        # 未完成的数据保存
        if len(ACCOUNTS) > 0:
            new_save_data_file = open(NEW_SAVE_DATA_PATH, "a")
            for account_id in ACCOUNTS:
                new_save_data_file.write("\t".join(account_list[account_id]) + "\n")
            new_save_data_file.close()

        # 删除临时文件夹
        self.finish_task()

        # 重新排序保存存档文件
        robot.rewrite_save_file(NEW_SAVE_DATA_PATH, self.save_data_path)

        log.step("全部下载完毕，耗时%s秒，共计视频%s个" % (self.get_run_time(), TOTAL_VIDEO_COUNT))


class Download(threading.Thread):
    def __init__(self, account_info, thread_lock):
        threading.Thread.__init__(self)
        self.account_info = account_info
        self.thread_lock = thread_lock

    def run(self):
        global TOTAL_VIDEO_COUNT

        account_id = self.account_info[0]
        if len(self.account_info) >= 4 and self.account_info[3]:
            account_name = self.account_info[3]
        else:
            account_name = self.account_info[0]

        try:
            log.step(account_name + " 开始")

            # 如果需要重新排序则使用临时文件夹，否则直接下载到目标目录
            if IS_SORT:
                video_path = os.path.join(VIDEO_TEMP_PATH, account_name)
            else:
                video_path = os.path.join(VIDEO_DOWNLOAD_PATH, account_name)

            suid = get_suid(account_id)
            if suid is None:
                log.error(account_name + " suid获取失败")

            page_count = 1
            video_count = 1
            first_video_scid = ""
            unique_list = []
            is_over = False
            need_make_download_dir = True
            while suid != "" and (not is_over):
                log.step(account_name + " 开始解析第%s页视频" % page_count)

                # 获取指定一页的视频信息
                media_page = get_one_page_video_data(suid, page_count)
                if media_page is None:
                    log.error(account_name + " 视频列表获取失败")
                    tool.process_exit()

                # 获取视频scid列表
                scid_list = get_scid_list(media_page["msg"])
                if len(scid_list) == 0:
                    log.error(account_name + " 在视频列表：%s 中没有找到视频scid" % str(media_page["msg"]))
                    tool.process_exit()

                log.trace(account_name + " 第%s页获取的全部视频：%s" % (page_count, scid_list))

                for scid in scid_list:
                    scid = str(scid)

                    # 检查是否已下载到前一次的图片
                    if first_video_scid == self.account_info[2]:
                        is_over = True
                        break

                    # 将第一个视频的id做为新的存档记录
                    if first_video_scid == "":
                        first_video_scid = scid

                    # 新增视频导致的重复判断
                    if scid in unique_list:
                        continue
                    else:
                        unique_list.append(scid)

                    # 获取视频下载地址
                    video_url = get_video_url_by_video_id(scid)
                    if video_url is None:
                        log.error(account_name + " 第%s个视频 %s 获取下载地址失败" % (video_count, scid))
                        continue
                    log.step(account_name + " 开始下载第%s个视频 %s" % (video_count, video_url))

                    # 第一个视频，创建目录
                    if need_make_download_dir:
                        if not tool.make_dir(video_path, 0):
                            log.error(account_name + " 创建视频下载目录 %s 失败" % video_path)
                            tool.process_exit()
                        need_make_download_dir = False

                    file_path = os.path.join(video_path, "%04d.mp4" % video_count)
                    save_file_return = net.save_net_file(video_url, file_path)
                    if save_file_return["status"] == 1:
                        log.step(account_name + " 第%s个视频下载成功" % video_count)
                        video_count += 1
                    else:
                        log.error(account_name + " 第%s个视频 %s 下载失败，原因：%s" % (video_count, video_url, robot.get_save_net_file_failed_reason(save_file_return["code"])))

                    # 达到配置文件中的下载数量，结束
                    if 0 < GET_VIDEO_COUNT < video_count:
                        is_over = True
                        break

                if not is_over:
                    if media_page["isall"]:
                        is_over = True
                    else:
                        page_count += 1

            log.step(account_name + " 下载完毕，总共获得%s个视频" % (video_count - 1))

            # 排序
            if IS_SORT and video_count > 1:
                log.step(account_name + " 视频开始从下载目录移动到保存目录")
                destination_path = os.path.join(VIDEO_DOWNLOAD_PATH, account_name)
                if robot.sort_file(video_path, destination_path, int(self.account_info[1]), 4):
                    log.step(account_name + " 视频从下载目录移动到保存目录成功")
                else:
                    log.error(account_name + " 创建视频保存目录 %s 失败" % destination_path)
                    tool.process_exit()

            # 新的存档记录
            if first_video_scid != "":
                self.account_info[1] = str(int(self.account_info[1]) + video_count - 1)
                self.account_info[2] = first_video_scid

            # 保存最后的信息
            tool.write_file("\t".join(self.account_info), NEW_SAVE_DATA_PATH)
            self.thread_lock.acquire()
            TOTAL_VIDEO_COUNT += video_count - 1
            ACCOUNTS.remove(account_id)
            self.thread_lock.release()

            log.step(account_name + " 完成")
        except SystemExit, se:
            if se.code == 0:
                log.step(account_name + " 提前退出")
            else:
                log.error(account_name + " 异常退出")
        except Exception, e:
            log.error(account_name + " 未知异常")
            log.error(str(e) + "\n" + str(traceback.format_exc()))


if __name__ == "__main__":
    MiaoPai().main()
