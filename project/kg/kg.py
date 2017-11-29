# -*- coding:UTF-8  -*-
"""
全民k歌歌曲爬虫
http://kg.qq.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import *
import os
import threading
import time
import traceback

ACCOUNT_LIST = {}
AUDIO_COUNT_PER_PAGE = 8
TOTAL_VIDEO_COUNT = 0
VIDEO_DOWNLOAD_PATH = ""
NEW_SAVE_DATA_PATH = ""


# 获取指定页数的一页歌曲信息
def get_one_page_audio(account_id, page_count):
    audio_pagination_url = "http://kg.qq.com/cgi/kg_ugc_get_homepage"
    query_data = {
        "type": "get_ugc",
        "format": "json",
        "share_uid": account_id,
        "start": page_count,
        "num": AUDIO_COUNT_PER_PAGE,
    }
    audio_pagination_response = net.http_request(audio_pagination_url, method="GET", fields=query_data, json_decode=True)
    result = {
        "audio_info_list": [],  # 全部歌曲信息
        "is_over": False,  # 是不是最后一页歌曲
    }
    if audio_pagination_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise robot.RobotException(robot.get_http_request_failed_reason(audio_pagination_response.status))
    if robot.check_sub_key(("code",), audio_pagination_response.json_data) and robot.is_integer(audio_pagination_response.json_data["code"]):
        if int(audio_pagination_response.json_data["code"]) == 1101:
            raise robot.RobotException("账号不存在")
    if not robot.check_sub_key(("data",), audio_pagination_response.json_data):
        raise robot.RobotException("返回数据'data'字段不存在\n%s" % audio_pagination_response.json_data)
    if not robot.check_sub_key(("has_more", "ugclist"), audio_pagination_response.json_data["data"]):
        raise robot.RobotException("返回数据'has_more'或者'ugclist'字段不存在\n%s" % audio_pagination_response.json_data)
    for audio_info in audio_pagination_response.json_data["data"]["ugclist"]:
        result_audio_info = {
            "audio_id": None,  # 歌曲id
            "audio_key": None,  # 歌曲访问token
            "audio_time": None,  # 歌曲上传时间
            "audio_title": "",  # 歌曲标题
        }
        # 获取歌曲id
        if not robot.check_sub_key(("ksong_mid",), audio_info):
            raise robot.RobotException("返回数据'ksong_mid'字段不存在\n%s" % audio_info)
        result_audio_info["audio_id"] = str(audio_info["ksong_mid"])
        # 获取歌曲访问token
        if not robot.check_sub_key(("shareid",), audio_info):
            raise robot.RobotException("返回数据'shareid'字段不存在\n%s" % audio_info)
        result_audio_info["audio_key"] = str(audio_info["shareid"])
        # 获取歌曲标题
        if not robot.check_sub_key(("title",), audio_info):
            raise robot.RobotException("返回数据'title'字段不存在\n%s" % audio_info)
        result_audio_info["audio_title"] = str(audio_info["title"].encode("UTF-8"))
        # 获取歌曲上传时间
        if not robot.check_sub_key(("time",), audio_info):
            raise robot.RobotException("返回数据'time'字段不存在\n%s" % audio_info)
        if not robot.is_integer(audio_info["time"]):
            raise robot.RobotException("返回数据'time'字段类型不正确\n%s" % audio_info)
        result_audio_info["audio_time"] = str(audio_info["time"])
        result["audio_info_list"].append(result_audio_info)
    # 判断是不是最后一页
    result["is_over"] = not bool(int(audio_pagination_response.json_data["data"]["has_more"]))
    return result


# 获取歌曲播放地址
def get_audio_play_page(audio_key):
    audio_play_url = "http://kg.qq.com/node/play"
    query_data = {"s": audio_key}
    audio_play_response = net.http_request(audio_play_url, method="GET", fields=query_data)
    result = {
        "audio_url": None,  # 歌曲地址
    }
    if audio_play_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise robot.RobotException(robot.get_http_request_failed_reason(audio_play_response.status))
    # 获取歌曲地址
    audio_url = tool.find_sub_string(audio_play_response.data, '"playurl":"', '"')
    if not audio_url:
        audio_url = tool.find_sub_string(audio_play_response.data, '"playurl_video":"', '"')
    if not audio_url:
        raise robot.RobotException("页面截取歌曲地址失败\n%s" % audio_play_response.data)
    result["audio_url"] = audio_url
    return result


class KG(robot.Robot):
    def __init__(self):
        global VIDEO_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH

        sys_config = {
            robot.SYS_DOWNLOAD_VIDEO: True,
        }
        robot.Robot.__init__(self, sys_config)

        # 设置全局变量，供子线程调用
        VIDEO_DOWNLOAD_PATH = self.video_download_path
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)

    def main(self):
        global ACCOUNT_LIST

        # 解析存档文件
        # account_id
        ACCOUNT_LIST = robot.read_save_data(self.save_data_path, 0, ["", "0"])

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

        log.step("全部下载完毕，耗时%s秒，共计歌曲%s首" % (self.get_run_time(), TOTAL_VIDEO_COUNT))


class Download(robot.DownloadThread):
    def __init__(self, account_info, main_thread):
        robot.DownloadThread.__init__(self, account_info, main_thread)

    def run(self):
        global TOTAL_VIDEO_COUNT

        account_id = self.account_info[0]
        if len(self.account_info) >= 3 and self.account_info[2]:
            account_name = self.account_info[2]
        else:
            account_name = self.account_info[0]
        total_video_count = 0

        try:
            log.step(account_name + " 开始")

            page_count = 1
            unique_list = []
            audio_info_list = []
            is_over = False
            # 获取全部还未下载过需要解析的歌曲
            while not is_over:
                log.step(account_name + " 开始解析第%s页歌曲" % page_count)

                # 获取一页歌曲
                try:
                    audio_pagination_response = get_one_page_audio(account_id, page_count)
                except robot.RobotException, e:
                    log.error(account_name + " 第%s页歌曲解析失败，原因：%s" % (page_count, e.message))
                    raise

                log.trace(account_name + " 第%s页解析的全部歌曲：%s" % (page_count, audio_pagination_response["audio_info_list"]))

                # 寻找这一页符合条件的歌曲
                for audio_info in audio_pagination_response["audio_info_list"]:
                    # 新增歌曲导致的重复判断
                    if audio_info["audio_id"] in unique_list:
                        continue
                    else:
                        unique_list.append(audio_info["audio_id"])

                    # 检查是否达到存档记录
                    if int(audio_info["audio_time"]) > int(self.account_info[1]):
                        audio_info_list.append(audio_info)
                    else:
                        is_over = True
                        break

                if audio_pagination_response["is_over"]:
                    is_over = True
                else:
                    page_count += 1

            log.step("需要下载的全部歌曲解析完毕，共%s首" % len(audio_info_list))

            while len(audio_info_list) > 0:
                audio_info = audio_info_list.pop()
                log.step("开始解析歌曲%s《%s》" % (audio_info["audio_key"], audio_info["audio_title"]))

                # 获取歌曲播放页
                try:
                    audio_play_response = get_audio_play_page(audio_info["audio_key"])
                except robot.RobotException, e:
                    log.error(account_name + " 歌曲%s《%s》解析失败，原因：%s" % (audio_info["audio_key"], audio_info["audio_title"], e.message))
                    raise

                log.step(account_name + " 开始下载歌曲%s《%s》 %s" % (audio_info["audio_key"], audio_info["audio_title"], audio_play_response["audio_url"]))

                file_type = audio_play_response["audio_url"].split(".")[-1].split("?")[0].split("&")[0]
                file_path = os.path.join(VIDEO_DOWNLOAD_PATH, account_name, "%s - %s.%s" % (audio_info["audio_id"], path.filter_text(audio_info["audio_title"]), file_type))
                save_file_return = net.save_net_file(audio_play_response["audio_url"], file_path)
                if save_file_return["status"] == 1:
                    log.step(account_name + " 歌曲%s《%s》下载成功" % (audio_info["audio_key"], audio_info["audio_title"]))
                else:
                    log.error(account_name + " 歌曲%s《%s》 %s 下载失败，原因：%s" % (audio_info["audio_key"], audio_info["audio_title"], audio_play_response["audio_url"], robot.get_save_net_file_failed_reason(save_file_return["code"])))
                # 歌曲下载完毕
                total_video_count += 1  # 计数累加
                self.account_info[1] = str(audio_info["audio_time"])  # 设置存档记录
        except SystemExit, se:
            if se.code == 0:
                log.step(account_name + " 提前退出")
            else:
                log.error(account_name + " 异常退出")
        except Exception, e:
            log.error(account_name + " 未知异常")
            log.error(str(e) + "\n" + str(traceback.format_exc()))

        # 保存最后的信息
        with self.thread_lock:
            tool.write_file("\t".join(self.account_info), NEW_SAVE_DATA_PATH)
            TOTAL_VIDEO_COUNT += total_video_count
            ACCOUNT_LIST.pop(account_id)
        log.step(account_name + " 下载完毕，总共获得%s首歌曲" % total_video_count)
        self.notify_main_thread()


if __name__ == "__main__":
    KG().main()
