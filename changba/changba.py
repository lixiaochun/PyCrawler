# -*- coding:UTF-8  -*-
"""
唱吧歌曲爬虫
http://changba.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import log, net, robot, tool
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


# 获取账号首页页面
def get_user_index_page(account_id):
    index_url = "http://changba.com/u/%s" % account_id
    index_page_response = net.http_request(index_url)
    extra_info = {
        "user_id": None,  # 页面解析出的user id
    }
    if index_page_response.status == 200:
        # 获取user id
        user_id = tool.find_sub_string(index_page_response.data, "var userid = '", "'")
        if user_id and user_id.isdigit():
            extra_info["user_id"] = user_id
    index_page_response.extra_info = extra_info
    return index_page_response


# 获取指定页数的所有歌曲信息
# user_id -> 4306405
def get_one_page_audio(user_id, page_count):
    # http://changba.com/member/personcenter/loadmore.php?userid=4306405&pageNum=1
    index_page_url = "http://changba.com/member/personcenter/loadmore.php?userid=%s&pageNum=%s" % (user_id, page_count)
    return net.http_request(index_page_url, json_decode=True)


# 获取指定id的歌曲播放页
# audio_en_word_id => w-ptydrV23KVyIPbWPoKsA
def get_audio_play_page(audio_en_word_id):
    audio_play_page_url = "http://changba.com/s/%s" % audio_en_word_id
    extra_info = {
        "audio_url": None,  # 页面解析出的user id
    }
    audio_play_page_response = net.http_request(audio_play_page_url)
    if audio_play_page_response.status == 200:
        # 获取歌曲下载地址
        audio_source_url = tool.find_sub_string(audio_play_page_response.data, 'var a="', '"')
        if audio_source_url:
            # 从JS处解析的规则
            special_find = re.findall("userwork/([abc])(\d+)/(\w+)/(\w+)\.mp3", audio_source_url)
            if len(special_find) == 0:
                extra_info["audio_url"] = audio_source_url
            elif len(special_find) == 1:
                e = int(special_find[0][1], 8)
                f = int(special_find[0][2], 16) / e / e
                g = int(special_find[0][3], 16) / e / e
                if "a" == special_find[0][0] and g % 1000 == f:
                    extra_info["audio_url"] = "http://a%smp3.changba.com/userdata/userwork/%s/%g.mp3" % (e, f, g)
                else:
                    extra_info["audio_url"] = "http://aliuwmp3.changba.com/userdata/userwork/%s.mp3" % g
    audio_play_page_response.extra_info = extra_info
    return audio_play_page_response


class ChangBa(robot.Robot):
    def __init__(self):
        global GET_VIDEO_COUNT
        global VIDEO_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH

        sys_config = {
            robot.SYS_DOWNLOAD_VIDEO: True,
        }
        robot.Robot.__init__(self, sys_config)

        # 设置全局变量，供子线程调用
        GET_VIDEO_COUNT = self.get_video_count
        VIDEO_DOWNLOAD_PATH = self.video_download_path
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)

    def main(self):
        global ACCOUNTS

        # 解析存档文件
        # account_id  last_audio_id
        account_list = robot.read_save_data(self.save_data_path, 0, ["", "0"])
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

        log.step("全部下载完毕，耗时%s秒，共计歌曲%s首" % (self.get_run_time(), TOTAL_VIDEO_COUNT))


class Download(threading.Thread):
    def __init__(self, account_info, thread_lock):
        threading.Thread.__init__(self)
        self.account_info = account_info
        self.thread_lock = thread_lock

    def run(self):
        global TOTAL_VIDEO_COUNT

        account_id = self.account_info[0]
        if len(self.account_info) >= 3 and self.account_info[2]:
            account_name = self.account_info[2]
        else:
            account_name = self.account_info[0]

        try:
            log.step(account_name + " 开始")

            video_path = os.path.join(VIDEO_DOWNLOAD_PATH, account_name)

            # 查找账号user id
            account_index_page_response = get_user_index_page(account_id)
            if account_index_page_response.status != 200:
                log.error(account_name + " 主页访问失败，原因：%s" % robot.get_http_request_failed_reason(account_index_page_response.status))
                tool.process_exit()

            if not account_index_page_response.extra_info["user_id"]:
                log.error(account_name + " user id获取失败")
                tool.process_exit()

            page_count = 0
            video_count = 1
            first_audio_id = "0"
            unique_list = []
            is_over = False
            need_make_download_dir = True
            while not is_over:
                log.step(account_name + " 开始解析第%s页歌曲" % page_count)

                # 获取一页歌曲
                index_page_response = get_one_page_audio(account_index_page_response.extra_info["user_id"], page_count)
                if index_page_response.status != 200:
                    log.error(account_name + " 第%s页歌曲访问失败，原因：%s" % (page_count, robot.get_http_request_failed_reason(index_page_response.status)))
                    tool.process_exit()

                # 如果为空，表示已经取完了
                if index_page_response.json_data is []:
                    break

                log.trace(account_name + " 第%s页获取的所有歌曲：%s" % (page_count, index_page_response.json_data))

                for audio_info in index_page_response.json_data:
                    if not robot.check_sub_key(("songname", "workid", "enworkid"), audio_info):
                        log.error(account_name + " 第%s首歌曲信息%s异常" % (video_count, audio_info))
                        continue
                    audio_id = str(audio_info["workid"])

                    # 检查是否已下载到前一次的歌曲
                    if int(audio_id) <= int(self.account_info[1]):
                        is_over = True
                        break

                    # 将第一首歌曲的id做为新的存档记录
                    if first_audio_id == "0":
                        first_audio_id = str(audio_id)

                    # 新增歌曲导致的重复判断
                    if audio_id in unique_list:
                        continue
                    else:
                        unique_list.append(audio_id)

                    audio_name = audio_info["songname"].encode("utf-8")
                    # 获取歌曲播放页
                    audio_play_page_response = get_audio_play_page(str(audio_info["enworkid"]))
                    if audio_play_page_response.status != 200:
                        log.error(account_name + " 歌曲《%s》播放页面访问失败，原因：%s" % (audio_name, robot.get_http_request_failed_reason(audio_play_page_response.status)))
                        continue

                    audio_url = audio_play_page_response.extra_info["audio_url"]
                    log.step(account_name + " 开始下载第%s首歌曲《%s》 %s" % (video_count, audio_name, audio_url))

                    # 第一首歌曲，创建目录
                    if need_make_download_dir:
                        if not tool.make_dir(video_path, 0):
                            log.error(account_name + " 创建歌曲下载目录 %s 失败" % video_path)
                            tool.process_exit()
                        need_make_download_dir = False

                    file_path = os.path.join(video_path, "%s - %s.mp3" % (audio_id, audio_name))
                    save_file_return = net.save_net_file(audio_url, file_path)
                    if save_file_return["status"] == 1:
                        log.step(account_name + " 第%s首歌曲下载成功" % video_count)
                        video_count += 1
                    else:
                        log.error(account_name + " 第%s首歌曲《%s》 %s 下载失败，原因：%s" % (video_count, audio_name, audio_url, robot.get_save_net_file_failed_reason(save_file_return["code"])))

                    # 达到配置文件中的下载数量，结束
                    if 0 < GET_VIDEO_COUNT < video_count:
                        is_over = True
                        break

                if not is_over:
                    # 获取的歌曲数量少于1页的上限，表示已经到结束了
                    # 如果歌曲数量正好是页数上限的倍数，则由下一页获取是否为空判断
                    if len(index_page_response.json_data) < 20:
                        is_over = True
                    else:
                        page_count += 1

            log.step(account_name + " 下载完毕，总共获得%s首歌曲" % (video_count - 1))

            # 新的存档记录
            if first_audio_id != "0":
                self.account_info[1] = first_audio_id

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
    ChangBa().main()
