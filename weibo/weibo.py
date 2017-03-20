# -*- coding:UTF-8  -*-
"""
微博图片&视频爬虫
http://www.weibo.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import log, net, robot, tool
from common import net_tool
import hashlib
import json
import os
import random
import re
import threading
import time
import traceback
import urllib2

ACCOUNTS = []
INIT_SINCE_ID = "9999999999999999"
IMAGE_COUNT_PER_PAGE = 20  # 每次请求获取的图片数量
TOTAL_IMAGE_COUNT = 0
TOTAL_VIDEO_COUNT = 0
GET_IMAGE_COUNT = 0
GET_VIDEO_COUNT = 0
IMAGE_TEMP_PATH = ""
IMAGE_DOWNLOAD_PATH = ""
VIDEO_TEMP_PATH = ""
VIDEO_DOWNLOAD_PATH = ""
NEW_SAVE_DATA_PATH = ""
IS_SORT = True
IS_DOWNLOAD_IMAGE = True
IS_DOWNLOAD_VIDEO = True
COOKIE_INFO = {"SUB": ""}


# 图片二进制字节保存为本地文件
def save_image(image_byte, image_path):
    image_path = tool.change_path_encoding(image_path)
    image_file = open(image_path, "wb")
    image_file.write(image_byte)
    image_file.close()


# 将二进制数据生成MD5的hash值
def md5(file_byte):
    md5_obj = hashlib.md5()
    md5_obj.update(file_byte)
    return md5_obj.hexdigest()


# 访问微博域名网页，自动判断是否需要跳转
def auto_redirect_visit(url):
    page_return_code, page_response = net_tool.http_request(url)[:2]
    if page_return_code == 1:
        # 有重定向
        redirect_url_find = re.findall('location.replace\(["|\']([^"|^\']*)["|\']\)', page_response)
        if len(redirect_url_find) == 1:
            return auto_redirect_visit(redirect_url_find[0])
        # 没有cookies无法访问的处理
        if page_response.find("用户名或密码错误") != -1:
            log.error("登陆状态异常，请在浏览器中重新登陆微博账号")
            tool.process_exit()
        # 返回页面
        if page_response:
            return str(page_response)
    return False


# 获取一页的图片信息
def get_one_page_photo(account_id, page_count):
    index_page_url = "http://photo.weibo.com/photos/get_all?uid=%s&count=%s&page=%s&type=3" % (account_id, IMAGE_COUNT_PER_PAGE, page_count)
    header_list = {"cookie": "SUB=" + COOKIE_INFO["SUB"]}
    extra_info = {
        "is_error": True,  # 是不是格式不符合
        "image_info_list": [],  # 页面解析出的图片信息列表
        "is_over": False,  # 是不是最后一页图片
    }
    index_page_response = net.http_request(index_page_url, header_list=header_list, json_decode=True)
    if index_page_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        if (
            robot.check_sub_key(("data",), index_page_response.json_data) and
            robot.check_sub_key(("total", "photo_list"), index_page_response.json_data["data"]) and
            robot.is_integer(index_page_response.json_data["data"]["total"])
        ):
            extra_info["is_error"] = False
            for image_info in index_page_response.json_data["data"]["photo_list"]:
                extra_image_info = {
                    "image_time": None,  # 页面解析出的图片上传时间
                    "image_url": None,  # 页面解析出的图片地址
                    "json_data": image_info,  # 原始数据
                }
                if robot.check_sub_key(("timestamp",), image_info) and robot.is_integer(image_info["timestamp"]):
                    extra_image_info["image_time"] = int(image_info["timestamp"])
                else:
                    extra_info["is_error"] = True
                    break
                if robot.check_sub_key(("pic_host", "pic_name"), image_info):
                    extra_image_info["image_url"] = str(image_info["pic_host"]) + "/large/" + str(image_info["pic_name"])
                else:
                    extra_info["is_error"] = True
                    break
                extra_info["image_info_list"].append(extra_image_info)
            # 检测是不是还有下一页 总的图片数量 / 每页显示的图片数量 = 总的页数
            extra_info["is_over"] = page_count >= (index_page_response.json_data["data"]["total"] * 1.0 / IMAGE_COUNT_PER_PAGE)
    index_page_response.extra_info = extra_info
    return index_page_response


# 获取账号对应的page_id
def get_account_page_id(account_id):
    for i in range(0, 50):
        index_url = "http://weibo.com/u/%s?is_all=1" % account_id
        index_page = auto_redirect_visit(index_url)
        if index_page:
            account_page_id = tool.find_sub_string(index_page, "$CONFIG['page_id']='", "'")
            if account_page_id and account_page_id.isdigit():
                return account_page_id
        time.sleep(5)
    return None


# 获取一页的视频信息
# page_id -> 1005052535836307
def get_one_page_video_data(account_page_id, since_id):
    video_album_url = "http://weibo.com/p/aj/album/loading"
    video_album_url += "?type=video&since_id=%s&page_id=%s&page=1&ajax_call=1" % (since_id, account_page_id)
    for i in range(0, 50):
        video_page = auto_redirect_visit(video_album_url)
        if video_page:
            try:
                video_page = json.loads(video_page)
            except ValueError:
                pass
            else:
                if robot.check_sub_key(("code", "data"), video_page):
                    if int(video_page["code"]) == 100000:
                        return video_page[u"data"].encode("utf-8")
        time.sleep(5)
    return None


# 从视频信息中解析出全部的视频列表
def get_video_play_url_list(video_page):
    return re.findall('<a target="_blank" href="([^"]*)"><div ', video_page)


# 从视频播放页面中提取下载地址
def get_video_url(video_play_url):
    # http://miaopai.com/show/Gmd7rwiNrc84z5h6S9DhjQ__.htm
    if video_play_url.find("miaopai.com/show/") >= 0:  # 秒拍
        video_id = tool.find_sub_string(video_play_url, "miaopai.com/show/", ".")
        video_info_url = "http://gslb.miaopai.com/stream/%s.json?token=" % video_id
        video_info_page_return_code, video_info_page = net_tool.http_request(video_info_url)[:2]
        if video_info_page_return_code == 1:
            try:
                video_info_page = json.loads(video_info_page)
            except ValueError:
                pass
            else:
                if robot.check_sub_key(("status", "result"), video_info_page):
                    if int(video_info_page["status"]) == 200:
                        for result in video_info_page["result"]:
                            if robot.check_sub_key(("path", "host", "scheme"), result):
                                return 1, ["%s%s%s" % (result["scheme"], result["host"], result["path"])]
            return -1, None
        else:
            return -2, None
    # http://video.weibo.com/show?fid=1034:e608e50d5fa95410748da61a7dfa2bff
    elif video_play_url.find("video.weibo.com/show?fid=") >= 0:  # 微博视频
        # 多次尝试，在多线程访问的时候有较大几率无法返回正确的信息
        for i in range(0, 50):
            video_play_page = auto_redirect_visit(video_play_url)
            if video_play_page:
                m3u8_file_url = tool.find_sub_string(video_play_page, "video_src=", "&")
                if not m3u8_file_url:
                    m3u8_file_url = tool.find_sub_string(video_play_page, 'flashvars=\\"file=', '\\"\/>')
                if m3u8_file_url:
                    m3u8_file_url = urllib2.unquote(m3u8_file_url)
                    m3u8_file_data = auto_redirect_visit(m3u8_file_url)
                    if m3u8_file_data:
                        video_url_find = re.findall("[\n]([^#][\S]*)[\n]", m3u8_file_data)
                        if len(video_url_find) > 0:
                            video_url_list = []
                            for video_url in video_url_find:
                                video_url_list.append("http://us.sinaimg.cn/%s" % video_url)
                            return 1, video_url_list
                        else:
                            return -1, None
            time.sleep(5)
        return -2, None
    # http://www.meipai.com/media/98089758
    elif video_play_url.find("www.meipai.com/media") >= 0:  # 美拍
        video_play_page_return_code, video_play_page = net_tool.http_request(video_play_url)[:2]
        if video_play_page_return_code == 1:
            video_url_find = re.findall('<meta content="([^"]*)" property="og:video:url">', video_play_page)
            if len(video_url_find) == 1:
                return 1, [video_url_find[0]]
            return -1, None
        else:
            return -2, None
    # http://v.xiaokaxiu.com/v/0YyG7I4092d~GayCAhwdJQ__.html
    elif video_play_url.find("v.xiaokaxiu.com/v/") >= 0:  # 小咖秀
        video_id = video_play_url.split("/")[-1].split(".")[0]
        return 1, ["http://gslb.miaopai.com/stream/%s.mp4" % video_id]
    # http://www.weishi.com/t/2000546051794045
    elif video_play_url.find("www.weishi.com/t/") >= 0:  # 微视
        video_play_page_return_code, video_play_page = net_tool.http_request(video_play_url)[:2]
        if video_play_page_return_code == 1:
            video_id_find = re.findall('<div class="vBox js_player"[\s]*id="([^"]*)"', video_play_page)
            if len(video_id_find) == 1:
                video_id = video_play_url.split("/")[-1]
                video_info_url = "http://wsi.weishi.com/weishi/video/downloadVideo.php"
                video_info_url += "?vid=%s&device=1&id=%s" % (video_id_find[0], video_id)
                video_info_page_return_code, video_info_page = net_tool.http_request(video_info_url)[:2]
                if video_info_page_return_code == 1:
                    try:
                        video_info_page = json.loads(video_info_page)
                    except ValueError:
                        pass
                    else:
                        if robot.check_sub_key(("data",), video_info_page):
                            if robot.check_sub_key(("url",), video_info_page["data"]):
                                return 1, [random.choice(video_info_page["data"]["url"])]
            return -1, None
        return -2, None
    else:  # 其他视频，暂时不支持，收集看看有没有
        return -3, None


# 检测图片是不是被微博自动删除的文件
def check_image_invalid(file_path):
    file_md5 = tool.get_file_md5(file_path)
    if file_md5 in ["14f2559305a6c96608c474f4ca47e6b0", "37b9e6dec174b68a545c852c63d4645a"]:
        return True
    return False


class Weibo(robot.Robot):
    def __init__(self, extra_config=None):
        global GET_IMAGE_COUNT
        global GET_VIDEO_COUNT
        global IMAGE_TEMP_PATH
        global IMAGE_DOWNLOAD_PATH
        global VIDEO_TEMP_PATH
        global VIDEO_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH
        global IS_SORT
        global IS_DOWNLOAD_IMAGE
        global IS_DOWNLOAD_VIDEO
        global COOKIE_INFO

        sys_config = {
            robot.SYS_DOWNLOAD_IMAGE: True,
            # robot.SYS_DOWNLOAD_VIDEO: True,
            robot.SYS_SET_COOKIE: ("weibo.com", ".sina.com.cn"),
            robot.SYS_GET_COOKIE: {".sina.com.cn": ("SUB",)},
        }
        robot.Robot.__init__(self, sys_config, extra_config)

        # 设置全局变量，供子线程调用
        GET_IMAGE_COUNT = self.get_image_count
        GET_VIDEO_COUNT = self.get_video_count
        IMAGE_TEMP_PATH = self.image_temp_path
        IMAGE_DOWNLOAD_PATH = self.image_download_path
        VIDEO_TEMP_PATH = self.video_temp_path
        VIDEO_DOWNLOAD_PATH = self.video_download_path
        IS_SORT = self.is_sort
        IS_DOWNLOAD_IMAGE = self.is_download_image
        IS_DOWNLOAD_VIDEO = self.is_download_video
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)
        COOKIE_INFO["SUB"] = self.cookie_value["SUB"]

    def main(self):
        global ACCOUNTS

        # 解析存档文件
        # account_id  image_count  last_image_time  video_count  last_video_url  (account_name)
        account_list = robot.read_save_data(self.save_data_path, 0, ["", "0", "0", "0", ""])
        ACCOUNTS = account_list.keys()

        # 先访问下页面，产生cookies
        # auto_redirect_visit("http://www.weibo.com/")
        # time.sleep(2)

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

        log.step("全部下载完毕，耗时%s秒，共计图片%s张，视频%s个" % (self.get_run_time(), TOTAL_IMAGE_COUNT, TOTAL_VIDEO_COUNT))


class Download(threading.Thread):
    def __init__(self, account_info, thread_lock):
        threading.Thread.__init__(self)
        self.account_info = account_info
        self.thread_lock = thread_lock

    def run(self):
        global TOTAL_IMAGE_COUNT
        global TOTAL_VIDEO_COUNT

        account_id = self.account_info[0]
        if len(self.account_info) >= 6 and self.account_info[5]:
            account_name = self.account_info[5]
        else:
            account_name = self.account_info[0]

        try:
            log.step(account_name + " 开始")

            # 如果需要重新排序则使用临时文件夹，否则直接下载到目标目录
            if IS_SORT:
                image_path = os.path.join(IMAGE_TEMP_PATH, account_name)
                video_path = os.path.join(VIDEO_TEMP_PATH, account_name)
            else:
                image_path = os.path.join(IMAGE_DOWNLOAD_PATH, account_name)
                video_path = os.path.join(VIDEO_DOWNLOAD_PATH, account_name)

            # 视频
            video_count = 1
            account_page_id = None
            first_video_url = ""
            is_over = False
            need_make_video_dir = True
            since_id = INIT_SINCE_ID
            while IS_DOWNLOAD_VIDEO and (not is_over):
                # 获取page_id
                if account_page_id is None:
                    account_page_id = get_account_page_id(account_id)
                    if account_page_id is None:
                        log.error(account_name + " 微博主页没有解析到page_id")
                        break

                log.step(account_name + " 开始解析%s后一页视频" % since_id)

                # 获取指定时间点后的一页视频信息
                video_page_data = get_one_page_video_data(account_page_id, since_id)
                if video_page_data is None:
                    log.error(account_name + " 视频列表解析失败")
                    first_video_url = ""  # 存档恢复
                    break

                # 匹配获取全部的视频页面
                video_play_url_list = get_video_play_url_list(video_page_data)
                log.trace(account_name + "since_id：%s中的全部视频：%s" % (since_id, video_play_url_list))

                for video_play_url in video_play_url_list:
                    # 检查是否是上一次的最后视频
                    if self.account_info[4] == video_play_url:
                        is_over = True
                        break

                    # 将第一个视频的地址做为新的存档记录
                    if first_video_url == "":
                        first_video_url = video_play_url

                    # 获取这个视频的下载地址
                    return_code, video_url_list = get_video_url(video_play_url)
                    if return_code != 1:
                        if return_code == -1:
                            log.error(account_name + " 第%s个视频 %s 没有解析到源地址" % (video_count, video_play_url))
                        elif return_code == -2:
                            log.error(account_name + " 第%s个视频 %s 无法访问" % (video_count, video_play_url))
                        elif return_code == -3:
                            log.error(account_name + " 第%s个视频 %s 暂不支持的视频源" % (video_count, video_play_url))
                        continue
                    log.step(account_name + " 开始下载第%s个视频 %s" % (video_count, video_play_url))

                    # 第一个视频，创建目录
                    if need_make_video_dir:
                        if not tool.make_dir(video_path, 0):
                            log.error(account_name + " 创建图片下载目录 %s 失败" % video_path)
                            tool.process_exit()
                        need_make_video_dir = False

                    video_file_path = os.path.join(video_path, "%04d.mp4" % video_count)
                    for video_url in video_url_list:
                        if net_tool.save_net_file(video_url, video_file_path):
                            log.step(account_name + " 第%s个视频下载成功" % video_count)
                            video_count += 1
                        else:
                            log.error(account_name + " 第%s个视频 %s 下载失败" % (video_count, video_url))

                    # 达到配置文件中的下载数量，结束
                    if 0 < GET_VIDEO_COUNT < video_count:
                        is_over = True
                        break

                if not is_over:
                    # 获取下一页的since_id
                    since_id = tool.find_sub_string(video_page_data, "type=video&owner_uid=&since_id=", '">')
                    if not since_id:
                        break

            # 有历史记录，并且此次没有获得正常结束的标记，说明历史最后的视频已经被删除了
            if self.account_info[4] != "" and video_count > 1 and not is_over:
                log.error(account_name + " 没有找到上次下载的最后一个视频地址")

            # 图片
            image_count = 1
            page_count = 1
            first_image_time = "0"
            unique_list = []
            is_over = False
            need_make_image_dir = True
            while IS_DOWNLOAD_IMAGE and (not is_over):
                log.step(account_name + " 开始解析第%s页图片" % page_count)

                # 获取指定一页图片的信息
                index_page_response = get_one_page_photo(account_id, page_count)
                if index_page_response.status != net.HTTP_RETURN_CODE_SUCCEED:
                    log.error(account_name + " 第%s页图片访问失败，原因：%s" % (page_count, robot.get_http_request_failed_reason(index_page_response.status)))
                    tool.process_exit()

                if index_page_response.extra_info["is_error"]:
                    log.error(account_name + " 第%s页图片%s解析失败" % (page_count, index_page_response.json_data))
                    tool.process_exit()

                log.trace(account_name + "第%s页解析的全部图片信息：%s" % (page_count, index_page_response.extra_info["image_info_list"]))

                for image_info in index_page_response.extra_info["image_info_list"]:
                    if image_info["image_time"] is None:
                        log.error(account_name + " 第%s页图片%s解析失败" % (page_count, index_page_response.json_data))
                        tool.process_exit()

                    # 检查是否图片时间小于上次的记录
                    if image_info["image_time"] <= int(self.account_info[2]):
                        is_over = True
                        break

                    # 将第一张图片的上传时间做为新的存档记录
                    if first_image_time == "0":
                        first_image_time = str(image_info["image_time"])

                    # 新增图片导致的重复判断
                    if image_info["image_url"] in unique_list:
                        continue
                    else:
                        unique_list.append(image_info["image_url"])

                    log.step(account_name + " 开始下载第%s张图片 %s" % (image_count, image_info["image_url"]))

                    # 第一张图片，创建目录
                    if need_make_image_dir:
                        if not tool.make_dir(image_path, 0):
                            log.error(account_name + " 创建图片下载目录 %s 失败" % image_path)
                            tool.process_exit()
                        need_make_image_dir = False

                    file_type = image_info["image_url"].split(".")[-1]
                    if file_type.find("/") != -1:
                        file_type = "jpg"
                    image_file_path = os.path.join(image_path, "%04d.%s" % (image_count, file_type))
                    save_return = net.save_net_file(image_info["image_url"], image_file_path)
                    if save_return["status"] == 1:
                        if check_image_invalid(image_file_path):
                            log.error(account_name + " 第%s张图片 %s 资源已被删除，跳过" % (image_count, image_info["image_url"]))
                        else:
                            log.step(account_name + " 第%s张图片下载成功" % image_count)
                            image_count += 1
                    else:
                        log.error(account_name + " 第%s张图片 %s 下载失败，原因：%s" % (image_count, image_info["image_url"], robot.get_save_net_file_failed_reason(save_return["code"])))

                    # 达到配置文件中的下载数量，结束
                    if 0 < GET_IMAGE_COUNT < image_count:
                        is_over = True
                        break

                if not is_over:
                    if index_page_response.extra_info["is_over"]:
                        is_over = True
                    else:
                        page_count += 1

            log.step(account_name + " 下载完毕，总共获得%s张图片和%s个视频" % (image_count - 1, video_count - 1))

            # 排序
            if IS_SORT:
                if image_count > 1:
                    log.step(account_name + " 图片开始从下载目录移动到保存目录")
                    destination_path = os.path.join(IMAGE_DOWNLOAD_PATH, account_name)
                    if robot.sort_file(image_path, destination_path, int(self.account_info[1]), 4):
                        log.step(account_name + " 图片从下载目录移动到保存目录成功")
                    else:
                        log.error(account_name + " 创建图片保存目录 %s 失败" % destination_path)
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
            if first_image_time != "0":
                self.account_info[1] = str(int(self.account_info[1]) + image_count - 1)
                self.account_info[2] = first_image_time
            if first_video_url != "":
                self.account_info[3] = str(int(self.account_info[3]) + video_count - 1)
                self.account_info[4] = first_video_url

            # 保存最后的信息
            tool.write_file("\t".join(self.account_info), NEW_SAVE_DATA_PATH)
            self.thread_lock.acquire()
            TOTAL_IMAGE_COUNT += image_count - 1
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
    Weibo().main()
