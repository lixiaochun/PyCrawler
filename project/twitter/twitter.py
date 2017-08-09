# -*- coding:UTF-8  -*-
"""
Twitter图片爬虫
https://twitter.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import *
import os
import re
import sys
import threading
import time
import traceback
import urllib

ACCOUNTS = []
INIT_MAX_ID = "999999999999999999"
TOTAL_IMAGE_COUNT = 0
TOTAL_VIDEO_COUNT = 0
IMAGE_TEMP_PATH = ""
IMAGE_DOWNLOAD_PATH = ""
VIDEO_TEMP_PATH = ""
VIDEO_DOWNLOAD_PATH = ""
NEW_SAVE_DATA_PATH = ""
IS_DOWNLOAD_IMAGE = True
IS_DOWNLOAD_VIDEO = True


# 根据账号名字获得账号id（字母账号->数字账号)
def get_account_index_page(account_name):
    account_index_url = "https://twitter.com/%s" % account_name
    account_index_response = net.http_request(account_index_url)
    result = {
        "account_id": None,  # account id
    }
    if account_index_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        account_id = tool.find_sub_string(account_index_response.data, '<div class="ProfileNav" role="navigation" data-user-id="', '">')
        if not robot.is_integer(account_id):
            raise robot.RobotException("页面截取用户id失败\n%s" % account_index_response.data)
        result["account_id"] = account_id
    elif account_index_response.status == 404:
        raise robot.RobotException("账号不存在")
    else:
        raise robot.RobotException(robot.get_http_request_failed_reason(account_index_response.status))
    return result


# 获取一页的媒体信息
def get_one_page_media(account_name, position_blog_id):
    media_pagination_url = "https://twitter.com/i/profiles/show/%s/media_timeline" % account_name
    media_pagination_url += "?include_available_features=1&include_entities=1&max_position=%s" % position_blog_id
    media_pagination_response = net.http_request(media_pagination_url, json_decode=True)
    result = {
        "is_error": False,  # 是不是格式不符合
        "is_over": False,  # 是不是已经最后一页媒体（没有获取到任何内容）
        "media_info_list": [],  # 所有媒体信息
        "next_page_position": None  # 下一页指针
    }
    if media_pagination_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        if not robot.check_sub_key(("has_more_items",), media_pagination_response.json_data):
            raise robot.RobotException("返回信息'has_more_items'字段不存在\n%s" % media_pagination_response.json_data)
        if not robot.check_sub_key(("items_html",), media_pagination_response.json_data):
            raise robot.RobotException("返回信息'items_html'字段不存在\n%s" % media_pagination_response.json_data)
        if not robot.check_sub_key(("new_latent_count",), media_pagination_response.json_data):
            raise robot.RobotException("返回信息'new_latent_count'字段不存在\n%s" % media_pagination_response.json_data)
        if not robot.is_integer(media_pagination_response.json_data["new_latent_count"]):
            raise robot.RobotException("返回信息'new_latent_count'字段类型不正确\n%s" % media_pagination_response.json_data)
        if not robot.check_sub_key(("min_position",), media_pagination_response.json_data):
            raise robot.RobotException("返回信息'min_position'字段不存在\n%s" % media_pagination_response.json_data)
        if not robot.is_integer(media_pagination_response.json_data["min_position"]) and media_pagination_response.json_data["min_position"] is not None:
            raise robot.RobotException("返回信息'min_position'字段类型不正确\n%s" % media_pagination_response.json_data)
        # 没有任何内容
        if int(media_pagination_response.json_data["new_latent_count"]) == 0 and not str(media_pagination_response.json_data["items_html"]).strip():
            result["is_skip"] = True
        else:
            # tweet信息分组
            temp_tweet_data_list = media_pagination_response.json_data["items_html"].replace("\n", "").replace('<li class="js-stream-item stream-item stream-item"', '\n<li class="js-stream-item stream-item stream-item"').split("\n")
            tweet_data_list = []
            for tweet_data in temp_tweet_data_list:
                if len(tweet_data) < 50:
                    continue
                tweet_data = tweet_data.encode("UTF-8")
                # 被圈出来的用户，追加到前面的页面中
                if tweet_data.find('<div class="account  js-actionable-user js-profile-popup-actionable') >= 0:
                    tweet_data_list[-1] += tweet_data
                else:
                    tweet_data_list.append(tweet_data)
            if len(tweet_data_list) == 0:
                raise robot.RobotException("tweet分组失败\n%s" % media_pagination_response.json_data["items_html"])
            if int(media_pagination_response.json_data["new_latent_count"]) != len(tweet_data_list):
                raise robot.RobotException("tweet分组数量和返回数据中不一致\n%s\n%s" % (media_pagination_response.json_data["items_html"], media_pagination_response.json_data["new_latent_count"]))
            for tweet_data in tweet_data_list:
                extra_media_info = {
                    "blog_id": None,  # 日志id
                    "has_video": False,  # 是不是包含视频
                    "image_url_list": [],  # 所有图片地址
                }
                # 获取日志id
                blog_id = tool.find_sub_string(tweet_data, 'data-tweet-id="', '"')
                if not robot.is_integer(blog_id):
                    raise robot.RobotException("tweet内容中截取tweet id失败\n%s" % tweet_data)
                extra_media_info["blog_id"] = str(blog_id)

                # 获取图片地址
                image_url_list = re.findall('data-image-url="([^"]*)"', tweet_data)
                extra_media_info["image_url_list"] = map(str, image_url_list)

                # 判断是不是有视频
                extra_media_info["has_video"] = tweet_data.find("PlayableMedia--video") >= 0

                result["media_info_list"].append(extra_media_info)

            # 判断是不是还有下一页
            if media_pagination_response.json_data["has_more_items"]:
                result["next_page_position"] = str(media_pagination_response.json_data["min_position"])
    else:
        raise robot.RobotException(robot.get_http_request_failed_reason(media_pagination_response.status))
    return result


# 根据视频所在推特的ID，获取视频的下载地址
def get_video_play_page(tweet_id):
    video_play_url = "https://twitter.com/i/videos/tweet/%s" % tweet_id
    video_play_response = net.http_request(video_play_url)
    result = {
        "video_url": None,  # 视频地址
    }
    if video_play_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        # 包含m3u8文件地址的处理
        # https://video.twimg.com/ext_tw_video/749759483224600577/pu/pl/DzYugRHcg3WVgeWY.m3u8
        m3u8_file_url = tool.find_sub_string(video_play_response.data, "&quot;video_url&quot;:&quot;", ".m3u8&quot;")
        if m3u8_file_url:
            m3u8_file_url = m3u8_file_url.replace("\\/", "/") + ".m3u8"
            file_url_protocol, file_url_path = urllib.splittype(m3u8_file_url)
            file_url_host = urllib.splithost(file_url_path)[0]
            m3u8_file_response = net.http_request(m3u8_file_url)
            if m3u8_file_response.status != net.HTTP_RETURN_CODE_SUCCEED:
                raise robot.RobotException("m3u8文件 %s 解析失败，%s" % (m3u8_file_url, robot.get_http_request_failed_reason(m3u8_file_response.status)))
            # 是否包含的是m3u8文件（不同分辨率）
            include_m3u8_file_list = re.findall("(/[\S]*.m3u8)", m3u8_file_response.data)
            if len(include_m3u8_file_list) > 0:
                # 生成最高分辨率视频所在的m3u8文件地址
                m3u8_file_url = "%s://%s%s" % (file_url_protocol, file_url_host, include_m3u8_file_list[-1])
                m3u8_file_response = net.http_request(m3u8_file_url)
                if m3u8_file_response.status != net.HTTP_RETURN_CODE_SUCCEED:
                    raise robot.RobotException("最高分辨率m3u8文件 %s 解析失败，%s" % (m3u8_file_url, robot.get_http_request_failed_reason(m3u8_file_response.status)))

            # 包含分P视频文件名的m3u8文件
            ts_url_find = re.findall("(/[\S]*.ts)", m3u8_file_response.data)
            if len(ts_url_find) == 0:
                raise robot.RobotException("m3u8文件截取视频地址失败\n%s\n%s" % (m3u8_file_url, m3u8_file_response.data))
            result["video_url"] = []
            for ts_file_path in ts_url_find:
                result["video_url"].append("%s://%s%s" % (file_url_protocol, file_url_host, str(ts_file_path)))
        else:
            # 直接包含视频播放地址的处理
            video_url = tool.find_sub_string(video_play_response.data, "&quot;video_url&quot;:&quot;", "&quot;")
            if video_url:
                result["video_url"] = video_url.replace("\\/", "/")
            else:
                # 直接包含视频播放地址的处理
                vmap_file_url = tool.find_sub_string(video_play_response.data, "&quot;vmap_url&quot;:&quot;", "&quot;")
                if not vmap_file_url:
                    raise robot.RobotException("页面截取视频播放地址失败\n%s" % video_play_response.data)
                vmap_file_url = vmap_file_url.replace("\\/", "/")
                vmap_file_response = net.http_request(vmap_file_url)
                if vmap_file_response.status != net.HTTP_RETURN_CODE_SUCCEED:
                    raise robot.RobotException("视频播放页 %s 解析失败\n%s" % (vmap_file_url, robot.get_http_request_failed_reason(vmap_file_response.status)))
                video_url = tool.find_sub_string(vmap_file_response.data, "<![CDATA[", "]]>")
                if not video_url:
                    raise robot.RobotException("视频播放页 %s 截取视频地址失败\n%s" % (vmap_file_url, video_play_response.data))
                result["video_url"] = str(video_url.replace("\\/", "/"))
    else:
        raise robot.RobotException(robot.get_http_request_failed_reason(video_play_response.status))
    return result


class Twitter(robot.Robot):
    def __init__(self, extra_config=None):
        global IMAGE_TEMP_PATH
        global IMAGE_DOWNLOAD_PATH
        global VIDEO_TEMP_PATH
        global VIDEO_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH
        global IS_DOWNLOAD_IMAGE
        global IS_DOWNLOAD_VIDEO

        sys_config = {
            robot.SYS_DOWNLOAD_IMAGE: True,
            robot.SYS_DOWNLOAD_VIDEO: True,
            robot.SYS_SET_PROXY: True,
        }
        robot.Robot.__init__(self, sys_config, extra_config)

        # 设置全局变量，供子线程调用
        IMAGE_TEMP_PATH = self.image_temp_path
        IMAGE_DOWNLOAD_PATH = self.image_download_path
        VIDEO_TEMP_PATH = self.video_temp_path
        VIDEO_DOWNLOAD_PATH = self.video_download_path
        IS_DOWNLOAD_IMAGE = self.is_download_image
        IS_DOWNLOAD_VIDEO = self.is_download_video
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)

    def main(self):
        global ACCOUNTS

        # 解析存档文件
        # account_name  image_count  last_image_time
        account_list = robot.read_save_data(self.save_data_path, 0, ["", "", "0", "0", "0"])
        ACCOUNTS = account_list.keys()

        # 循环下载每个id
        main_thread_count = threading.activeCount()
        for account_name in sorted(account_list.keys()):
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
            thread = Download(account_list[account_name], self.thread_lock)
            thread.start()

            time.sleep(1)

        # 检查除主线程外的其他所有线程是不是全部结束了
        while threading.activeCount() > main_thread_count:
            time.sleep(10)

        # 未完成的数据保存
        if len(ACCOUNTS) > 0:
            new_save_data_file = open(NEW_SAVE_DATA_PATH, "a")
            for account_name in ACCOUNTS:
                # account_name  image_count  last_image_time
                new_save_data_file.write("\t".join(account_list[account_name]) + "\n")
            new_save_data_file.close()

        # 删除临时文件夹
        self.finish_task()

        # 重新排序保存存档文件
        robot.rewrite_save_file(NEW_SAVE_DATA_PATH, self.save_data_path)

        log.step("全部下载完毕，耗时%s秒，共计图片%s张，视频%s个" % (self.get_run_time(), TOTAL_IMAGE_COUNT, TOTAL_VIDEO_COUNT))


class Download(threading.Thread):
    def __init__(self, account_info, thread_lock):
        threading.Thread.__init__(self)
        self.account_info = account_info
        self.thread_lock = thread_lock

    def run(self):
        global TOTAL_IMAGE_COUNT
        global TOTAL_VIDEO_COUNT

        account_name = self.account_info[0]

        try:
            log.step(account_name + " 开始")

            try:
                account_index_response = get_account_index_page(account_name)
            except robot.RobotException, e:
                log.error(account_name + " 首页解析失败，原因：%s" % e.message)
                raise

            if self.account_info[1] == "":
                self.account_info[1] = account_index_response["account_id"]
            else:
                if self.account_info[1] != account_index_response["account_id"]:
                    log.error(account_name + " account id 不符合，原账号已改名")
                    tool.process_exit()

            image_count = 1
            video_count = 1
            position_blog_id = INIT_MAX_ID
            is_over = False
            first_tweet_id = None
            image_path = os.path.join(IMAGE_TEMP_PATH, account_name)
            video_path = os.path.join(VIDEO_TEMP_PATH, account_name)
            while not is_over:
                log.step(account_name + " 开始解析position %s后的一页媒体列表" % position_blog_id)

                # 获取指定时间点后的一页图片信息
                try:
                    media_pagination_response = get_one_page_media(account_name, position_blog_id)
                except robot.RobotException, e:
                    log.error(account_name + " position %s后的一页媒体信息解析失败，原因：%s" % (position_blog_id, e.message))
                    raise

                if media_pagination_response["is_over"]:
                    break

                log.trace(account_name + " position %s解析的所有媒体信息：%s" % (position_blog_id, media_pagination_response["media_info_list"]))

                for media_info in media_pagination_response["media_info_list"]:
                    log.step(account_name + " 开始解析日志 %s" % media_info["blog_id"])

                    # 检查是否达到存档记录
                    if int(media_info["blog_id"]) <= int(self.account_info[4]):
                        is_over = True
                        break

                    # 新的存档记录
                    if first_tweet_id is None:
                        first_tweet_id = media_info["blog_id"]

                    # 视频
                    if IS_DOWNLOAD_VIDEO and media_info["has_video"]:
                        # 获取视频播放地址
                        try:
                            video_play_response = get_video_play_page(media_info["blog_id"])
                        except robot.RobotException, e:
                            log.error(account_name + " 日志%s的视频解析失败，原因：%s" % (media_info["blog_id"], e.message))
                            raise

                        video_url = video_play_response["video_url"]
                        log.step(account_name + " 开始下载第%s个视频 %s" % (video_count, video_url))

                        # 分割后的ts格式视频
                        if isinstance(video_url, list):
                            video_file_path = os.path.join(video_path, "%04d.ts" % video_count)
                            save_file_return = net.save_net_file_list(video_url, video_file_path)
                        # 其他格式的视频
                        else:
                            video_file_type = video_url.split(".")[-1]
                            video_file_path = os.path.join(video_path, "%04d.%s" % (video_count, video_file_type))
                            save_file_return = net.save_net_file(video_url, video_file_path)

                        if save_file_return["status"] == 1:
                            log.step(account_name + " 第%s个视频下载成功" % video_count)
                            video_count += 1
                        else:
                            log.error(account_name + " 第%s个视频 %s 下载失败" % (video_count, video_url))

                    # 图片
                    if IS_DOWNLOAD_IMAGE:
                        for image_url in media_info["image_url_list"]:
                            log.step(account_name + " 开始下载第%s张图片 %s" % (image_count, image_url))

                            file_type = image_url.split(".")[-1].split(":")[0]
                            image_file_path = os.path.join(image_path, "%04d.%s" % (image_count, file_type))
                            for retry_count in range(0, 5):
                                save_file_return = net.save_net_file(image_url, image_file_path)
                                if save_file_return["status"] == 1:
                                    log.step(account_name + " 第%s张图片下载成功" % image_count)
                                    image_count += 1
                                elif save_file_return["status"] == 0 and save_file_return["code"] == 404:
                                    log.error(account_name + " 第%s张图片 %s 已被删除，跳过" % (image_count, image_url))
                                elif save_file_return["status"] == 0 and save_file_return["code"] == 500:
                                    log.step(account_name + " 第%s张图片 %s 下载异常，重试" % (image_count, image_url))
                                    continue
                                else:
                                    log.error(account_name + " 第%s张图片 %s 下载失败，原因：%s" % (image_count, image_url, robot.get_save_net_file_failed_reason(save_file_return["code"])))
                                break

                if not is_over:
                    # 下一页的指针
                    if media_pagination_response["next_page_position"] is None:
                        is_over = True
                    else:
                        position_blog_id = media_pagination_response["next_page_position"]

            log.step(account_name + " 下载完毕，总共获得%s张图片和%s个视频" % (image_count - 1, video_count - 1))

            # 排序
            if image_count > 1:
                log.step(account_name + " 图片开始从下载目录移动到保存目录")
                destination_path = os.path.join(IMAGE_DOWNLOAD_PATH, account_name)
                if robot.sort_file(image_path, destination_path, int(self.account_info[2]), 4):
                    log.step(account_name + " 图片从下载目录移动到保存目录成功")
                else:
                    log.error(account_name + " 创建图片子目录 %s 失败" % destination_path)
                    tool.process_exit()
            if video_count > 1:
                log.step(account_name + " 视频开始从下载目录移动到保存目录")
                destination_path = os.path.join(VIDEO_DOWNLOAD_PATH, account_name)
                if robot.sort_file(video_path, destination_path, int(self.account_info[3]), 4):
                    log.step(account_name + " 视频从下载目录移动到保存目录成功")
                else:
                    log.error(account_name + " 创建视频保存目录 %s 失败" % destination_path)
                    tool.process_exit()

            # 新的存档记录
            if first_tweet_id is not None:
                self.account_info[2] = str(int(self.account_info[2]) + image_count - 1)
                self.account_info[3] = str(int(self.account_info[3]) + video_count - 1)
                self.account_info[4] = first_tweet_id

            # 保存最后的信息
            tool.write_file("\t".join(self.account_info), NEW_SAVE_DATA_PATH)
            self.thread_lock.acquire()
            TOTAL_IMAGE_COUNT += image_count - 1
            TOTAL_VIDEO_COUNT += video_count - 1
            ACCOUNTS.remove(account_name)
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
    Twitter().main()
