# -*- coding:UTF-8  -*-
"""
微博视频爬虫
http://www.weibo.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import *
from project.meipai import meipai
import weiboCommon
import base64
import os
import random
import re
import threading
import time
import traceback
import urllib2

INIT_SINCE_ID = "9999999999999999"
ACCOUNT_LIST = {}
TOTAL_VIDEO_COUNT = 0
VIDEO_DOWNLOAD_PATH = ""
NEW_SAVE_DATA_PATH = ""
COOKIE_INFO = {"SUB": ""}


# 获取一页的视频信息
# page_id -> 1005052535836307
def get_one_page_video(account_page_id, since_id):
    # http://weibo.com/p/aj/album/loading?type=video&since_id=9999999999999999&page_id=1005052535836307&page=1&ajax_call=1
    video_pagination_url = "http://weibo.com/p/aj/album/loading"
    query_data = {
        "type": "video",
        "since_id": since_id,
        "page_id": account_page_id,
        "ajax_call": "1",
        "__rnd": int(time.time() * 1000),
    }
    cookies_list = {"SUB": COOKIE_INFO["SUB"]}
    result = {
        "is_error": False,  # 是不是格式不符合
        "next_page_since_id": None,  # 下一页视频指针
        "video_play_url_list": [],  # 全部视频地址
    }
    video_pagination_response = net.http_request(video_pagination_url, method="GET", fields=query_data, cookies_list=cookies_list, json_decode=True)
    if video_pagination_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise robot.RobotException(robot.get_http_request_failed_reason(video_pagination_response.status))
    if not robot.check_sub_key(("code", "data"), video_pagination_response.json_data):
        raise robot.RobotException("返回信息'code'或'data'字段不存在\n%s" % video_pagination_response.json_data)
    if not robot.is_integer(video_pagination_response.json_data["code"]):
        raise robot.RobotException("返回信息'code'字段类型不正确\n%s" % video_pagination_response.json_data)
    if int(video_pagination_response.json_data["code"]) != 100000:
        raise robot.RobotException("返回信息'code'字段取值不正确\n%s" % video_pagination_response.json_data)
    page_html = video_pagination_response.json_data["data"].encode("UTF-8")
    # 获取视频播放地址
    video_play_url_list = re.findall('<a target="_blank" href="([^"]*)"><div ', page_html)
    if len(video_play_url_list) == 0:
        if since_id != INIT_SINCE_ID or page_html.find("还没有发布过视频") == -1:
            raise robot.RobotException("返回信息匹配视频地址失败\n%s" % video_pagination_response.json_data)
    else:
        result["video_play_url_list"] = map(str, video_play_url_list)
    # 获取下一页视频的指针
    next_page_since_id = tool.find_sub_string(page_html, "type=video&owner_uid=&viewer_uid=&since_id=", '">')
    if next_page_since_id:
        if not robot.is_integer(next_page_since_id):
            raise robot.RobotException("返回信息截取下一页指针失败\n%s" % video_pagination_response.json_data)
        result["next_page_since_id"] = next_page_since_id
    return result


# 从视频播放页面中提取下载地址
def get_video_url(video_play_url):
    video_url = None
    # http://miaopai.com/show/Gmd7rwiNrc84z5h6S9DhjQ__.htm
    if video_play_url.find("miaopai.com/show/") >= 0:  # 秒拍
        video_id = tool.find_sub_string(video_play_url, "miaopai.com/show/", ".")
        video_info_url = "http://gslb.miaopai.com/stream/%s.json" % video_id
        query_data = {"token": ""}
        video_info_response = net.http_request(video_info_url, method="GET", fields=query_data, json_decode=True)
        if video_info_response.status != net.HTTP_RETURN_CODE_SUCCEED:
            raise robot.RobotException(robot.get_http_request_failed_reason(video_info_response.status))
        if not robot.check_sub_key(("status", "result"), video_info_response.json_data):
            raise robot.RobotException("返回信息'status'或'result'字段不存在\n%s" % video_info_response.json_data)
        if not robot.is_integer(video_info_response.json_data["status"]):
            raise robot.RobotException("返回信息'status'字段类型不正确\n%s" % video_info_response.json_data)
        if int(video_info_response.json_data["status"]) != 200:
            raise robot.RobotException("返回信息'status'字段取值不正确\n%s" % video_info_response.json_data)
        if len(video_info_response.json_data["result"]) == 0:
            raise robot.RobotException("返回信息'result'字段长度不正确\n%s" % video_info_response.json_data)
        for video_info in video_info_response.json_data["result"]:
            if robot.check_sub_key(("path", "host", "scheme"), video_info):
                video_url = str(video_info["scheme"] + video_info["host"] + video_info["path"])
                break
        if video_url is None:
            raise robot.RobotException("返回信息匹配视频地址失败\n%s" % video_info_response.json_data)
    # http://video.weibo.com/show?fid=1034:e608e50d5fa95410748da61a7dfa2bff
    elif video_play_url.find("video.weibo.com/show?fid=") >= 0:  # 微博视频
        cookies_list = {"SUB": COOKIE_INFO["SUB"]}
        video_play_response = net.http_request(video_play_url, method="GET", cookies_list=cookies_list)
        if video_play_response.status == net.HTTP_RETURN_CODE_SUCCEED:
            video_url = tool.find_sub_string(video_play_response.data, "video_src=", "&")
            if not video_url:
                video_url = tool.find_sub_string(video_play_response.data, 'flashvars="list=', '"')
            if not video_url:
                raise robot.RobotException("页面截取视频地址失败\n%s" % video_play_response.data)
            video_url = str(urllib2.unquote(video_url))
            if video_url.find("//") == 0:
                video_url = "http:" + video_url
        elif video_play_response.status == 404:
            video_url = ""
        else:
            raise robot.RobotException(robot.get_http_request_failed_reason(video_play_response.status))
    # http://www.meipai.com/media/98089758
    elif video_play_url.find("www.meipai.com/media") >= 0:  # 美拍
        video_play_response = net.http_request(video_play_url, method="GET")
        if video_play_response.status != net.HTTP_RETURN_CODE_SUCCEED:
            raise robot.RobotException(robot.get_http_request_failed_reason(video_play_response.status))
        video_url_find = re.findall('<meta content="([^"]*)" property="og:video:url">', video_play_response.data)
        if len(video_url_find) != 1:
            raise robot.RobotException("页面匹配加密视频信息失败\n%s" % video_play_response.data)
        video_url = meipai.decrypt_video_url(video_url_find[0])
        if video_url is None:
            raise robot.RobotException("加密视频地址解密失败\n%s" % video_url_find[0])
    # http://v.xiaokaxiu.com/v/0YyG7I4092d~GayCAhwdJQ__.html
    elif video_play_url.find("v.xiaokaxiu.com/v/") >= 0:  # 小咖秀
        video_id = video_play_url.split("/")[-1].split(".")[0]
        video_url = "http://gslb.miaopai.com/stream/%s.mp4" % video_id
    else:  # 其他视频，暂时不支持，收集看看有没有
        raise robot.RobotException("未知的第三方视频\n%s" % video_play_url)
    return video_url


class Weibo(robot.Robot):
    def __init__(self, extra_config=None):
        global VIDEO_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH
        global COOKIE_INFO

        sys_config = {
            robot.SYS_DOWNLOAD_VIDEO: True,
            robot.SYS_GET_COOKIE: {
                ".sina.com.cn": (),
                ".login.sina.com.cn": (),
            },
        }
        robot.Robot.__init__(self, sys_config, extra_config)

        # 设置全局变量，供子线程调用
        VIDEO_DOWNLOAD_PATH = self.video_download_path
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)
        COOKIE_INFO.update(self.cookie_value)

    def main(self):
        global ACCOUNT_LIST
        global COOKIE_INFO

        # 检测登录状态
        if not weiboCommon.check_login(COOKIE_INFO):
            # 如果没有获得登录相关的cookie，则模拟登录并更新cookie
            new_cookies_list = weiboCommon.generate_login_cookie(COOKIE_INFO)
            if new_cookies_list:
                COOKIE_INFO.update(new_cookies_list)
            # 再次检测登录状态
            if not weiboCommon.check_login(COOKIE_INFO):
                log.error("没有检测到登录信息")
                tool.process_exit()

        # 解析存档文件
        # account_id  video_count  last_video_url  (account_name)
        ACCOUNT_LIST = robot.read_save_data(self.save_data_path, 0, ["", "0", ""])

        # 循环下载每个id
        main_thread_count = threading.activeCount()
        for account_id in sorted(ACCOUNT_LIST.keys()):
            # 检查正在运行的线程数
            if threading.activeCount() >= self.thread_count + main_thread_count:
                self.wait_sub_thread()

            # 提前结束
            if not self.is_running():
                break

            # 开始下载
            thread = Download(ACCOUNT_LIST[account_id], self)
            thread.start()

            time.sleep(1)

        # 检查除主线程外的其他所有线程是不是全部结束了
        while threading.activeCount() > main_thread_count:
            self.wait_sub_thread()

        # 未完成的数据保存
        if len(ACCOUNT_LIST) > 0:
            tool.write_file(tool.list_to_string(ACCOUNT_LIST.values()), NEW_SAVE_DATA_PATH)

        # 重新排序保存存档文件
        robot.rewrite_save_file(NEW_SAVE_DATA_PATH, self.save_data_path)

        log.step("全部下载完毕，耗时%s秒，共计视频%s个" % (self.get_run_time(), TOTAL_VIDEO_COUNT))


class Download(robot.DownloadThread):
    def __init__(self, account_info, main_thread):
        robot.DownloadThread.__init__(self, account_info, main_thread)
        self.account_id = self.account_info[0]
        if len(self.account_info) >= 4 and self.account_info[3]:
            self.account_name = self.account_info[3]
        else:
            self.account_name = self.account_info[0]
        log.step(self.account_name + " 开始")

    # 获取所有可下载图片
    def get_crawl_list(self):
        # 获取账号首页
        try:
            account_index_response = weiboCommon.get_account_index_page(self.account_id)
        except robot.RobotException, e:
            log.error(self.account_name + " 首页解析失败，原因：%s" % e.message)
            raise

        video_play_url_list = []
        since_id = INIT_SINCE_ID
        is_over = False
        # 获取全部还未下载过需要解析的视频
        while not is_over:
            self.main_thread_check()  # 检测主线程运行状态
            log.step(self.account_name + " 开始解析%s后一页视频" % since_id)

            # 获取指定时间点后的一页视频信息
            try:
                video_pagination_response = get_one_page_video(account_index_response["account_page_id"], since_id)
            except robot.RobotException, e:
                log.error(self.account_name + " %s后的一页视频解析失败，原因：%s" % (since_id, e.message))
                raise

            log.trace(self.account_name + "since_id：%s解析的全部视频：%s" % (since_id, video_pagination_response["video_play_url_list"]))

            # 寻找这一页符合条件的视频
            for video_play_url in video_pagination_response["video_play_url_list"]:
                # 检查是否达到存档记录
                if self.account_info[2] != video_play_url:
                    video_play_url_list.append(video_play_url)
                else:
                    is_over = True
                    break

            if not is_over:
                if video_pagination_response["next_page_since_id"] is None:
                    is_over = True
                    # todo 没有找到历史记录如何处理
                    # 有历史记录，但此次直接获取了全部视频
                    if self.account_info[2] != "":
                        log.error(self.account_name + " 没有找到上次下载的最后一个视频地址")
                else:
                    # 设置下一页指针
                    since_id = video_pagination_response["next_page_since_id"]

        return video_play_url_list

    # 解析单个视频
    def crawl_video(self, video_play_url):
        # 获取这个视频的下载地址
        try:
            video_url = get_video_url(video_play_url)
        except robot.RobotException, e:
            log.error(self.account_name + " 视频 %s 解析失败，原因：%s" % (video_play_url, e.message))
            raise

        if video_url is "":
            return

        self.main_thread_check()  # 检测主线程运行状态
        video_index = int(self.account_info[1]) + 1
        log.step(self.account_name + " 开始下载第%s个视频 %s" % (video_index, video_url))

        video_file_path = os.path.join(VIDEO_DOWNLOAD_PATH, self.account_name, "%04d.mp4" % video_index)
        save_file_return = net.save_net_file(video_url, video_file_path)
        if save_file_return["status"] == 1:
            log.step(self.account_name + " 第%s个视频下载成功" % video_index)
        else:
            log.error(self.account_name + " 第%s个视频 %s（%s) 下载失败，原因：%s" % (video_index, video_play_url, video_url, robot.get_save_net_file_failed_reason(save_file_return["code"])))
            return

        # 视频下载完毕
        self.total_video_count += 1  # 计数累加
        self.account_info[1] = str(video_index)  # 设置存档记录
        self.account_info[2] = video_play_url  # 设置存档记录

    def run(self):
        try:
            # 获取所有可下载视频
            video_play_url_list = self.get_crawl_list()
            log.step(self.account_name + " 需要下载的全部视频片解析完毕，共%s个" % len(video_play_url_list))

            # 从最早的图片开始下载
            while len(video_play_url_list) > 0:
                video_play_url = video_play_url_list.pop()
                log.step(self.account_name + " 开始解析第%s个视频 %s" % (int(self.account_info[1]) + 1, video_play_url))
                self.crawl_video(video_play_url)
                self.main_thread_check()  # 检测主线程运行状态
        except SystemExit, se:
            if se.code == 0:
                log.step(self.account_name + " 提前退出")
            else:
                log.error(self.account_name + " 异常退出")
        except Exception, e:
            log.error(self.account_name + " 未知异常")
            log.error(str(e) + "\n" + str(traceback.format_exc()))

        # 保存最后的信息
        with self.thread_lock:
            global TOTAL_VIDEO_COUNT
            tool.write_file("\t".join(self.account_info), NEW_SAVE_DATA_PATH)
            TOTAL_VIDEO_COUNT += self.total_video_count
            ACCOUNT_LIST.pop(self.account_id)
        log.step(self.account_name + " 下载完毕，总共获得%s个视频" % self.total_video_count)
        self.notify_main_thread()


if __name__ == "__main__":
    Weibo().main()
