# -*- coding:UTF-8  -*-
"""
Flickr图片爬虫
https://www.flickr.com/
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
IMAGE_COUNT_PER_PAGE = 50
TOTAL_IMAGE_COUNT = 0
IMAGE_DOWNLOAD_PATH = ""
NEW_SAVE_DATA_PATH = ""
COOKIE_INFO = {}


# 获取账号相册首页
def get_account_index_page(account_name):
    account_index_url = "https://www.flickr.com/photos/%s" % account_name
    account_index_response = net.http_request(account_index_url, method="GET", cookies_list=COOKIE_INFO)
    result = {
        "site_key": None,  # site key
        "user_id": None,  # user id
        "csrf": None,  # csrf
        "cookie_session": None,  # cookie_session
    }
    if account_index_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        # 获取user id
        user_id = tool.find_sub_string(account_index_response.data, 'params: {"nsid":"', '"')
        if not user_id:
            raise robot.RobotException("页面截取nsid失败\n%s" % account_index_response.data)
        result["user_id"] = user_id
        # 获取site key
        site_key = tool.find_sub_string(account_index_response.data, 'root.YUI_config.flickr.api.site_key = "', '"')
        if not site_key:
            raise robot.RobotException("页面截取site key失败\n%s" % account_index_response.data)
        result["site_key"] = site_key
        # 获取CSRF
        root_auth = tool.find_sub_string(account_index_response.data, "root.auth = ", "};")
        if not site_key:
            raise robot.RobotException("页面截取root.auth失败\n%s" % account_index_response.data)
        csrf = tool.find_sub_string(root_auth, '"csrf":"', '",')
        if not csrf:
            raise robot.RobotException("页面截取csrf失败\n%s" % account_index_response.data)
        result["csrf"] = csrf
        # 获取cookie_session
        set_cookies = net.get_cookies_from_response_header(account_index_response.headers)
        if not robot.check_sub_key(("cookie_session",), set_cookies):
            raise robot.RobotException("请求返回cookie匹配cookie_session失败\n%s" % account_index_response.data)
        result["cookie_session"] = set_cookies["cookie_session"]
    elif account_index_response.status == 404:
        raise robot.RobotException("账号不存在")
    else:
        raise robot.RobotException(robot.get_http_request_failed_reason(account_index_response.status))
    return result


# 获取指定页数的全部图片
# user_id -> 36587311@N08
def get_one_page_photo(user_id, page_count, api_key, csrf, request_id, cookie_session):
    api_url = "https://api.flickr.com/services/rest"
    # API文档：https://www.flickr.com/services/api/flickr.people.getPhotos.html
    # 全部可支持的参数
    # extras = [
    #     "can_addmeta", "can_comment", "can_download", "can_share", "contact", "count_comments", "count_faves",
    #     "count_views", "date_taken", "date_upload", "description", "icon_urls_deep", "isfavorite", "ispro", "license",
    #     "media", "needs_interstitial", "owner_name", "owner_datecreate", "path_alias", "realname", "rotation",
    #     "safety_level", "secret_k", "secret_h", "url_c", "url_f", "url_h", "url_k", "url_l", "url_m", "url_n",
    #     "url_o", "url_q", "url_s", "url_sq", "url_t", "url_z", "visibility", "visibility_source", "o_dims",
    #     "is_marketplace_printable", "is_marketplace_licensable", "publiceditability"
    # ]
    query_data = {
        "method": "flickr.people.getPhotos", "view_as": "use_pref", "sort": "use_pref", "format": "json", "nojsoncallback": 1, "get_user_info": 0, "privacy_filter": 1,
        "per_page": IMAGE_COUNT_PER_PAGE, "page": page_count, "user_id": user_id, "api_key": api_key, "hermes": 1, "reqId": request_id, "csrf": csrf,
        "extras": "date_upload,url_c,url_f,url_h,url_k,url_l,url_m,url_n,url_o,url_q,url_s,url_sq,url_t,url_z",
    }
    COOKIE_INFO.update({"cookie_session": cookie_session})
    photo_pagination_response = net.http_request(api_url, method="GET", fields=query_data, cookies_list=COOKIE_INFO, json_decode=True)
    result = {
        "image_info_list": [],  # 全部图片信息
        "is_over": False,  # 是不是最后一页图片
    }
    if photo_pagination_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise robot.RobotException(robot.get_http_request_failed_reason(photo_pagination_response.status))
    if not robot.check_sub_key(("photos",), photo_pagination_response.json_data):
        raise robot.RobotException("返回数据'photos'字段不存在\n%s" % photo_pagination_response.json_data)
    if not robot.check_sub_key(("photo", "pages"), photo_pagination_response.json_data["photos"]):
        raise robot.RobotException("返回数据'photo'或者'pages'字段不存在\n%s" % photo_pagination_response.json_data)
    if not isinstance(photo_pagination_response.json_data["photos"]["photo"], list) or len(photo_pagination_response.json_data["photos"]["photo"]) == 0:
        raise robot.RobotException("返回数据'photo'字段类型不正确\n%s" % photo_pagination_response.json_data)
    if not robot.is_integer(photo_pagination_response.json_data["photos"]["pages"]):
        raise robot.RobotException("返回数据'pages'字段类型不正确\n%s" % photo_pagination_response.json_data)
    # 获取图片信息
    for photo_info in photo_pagination_response.json_data["photos"]["photo"]:
        result_image_info = {
            "image_time": None,  # 图片上传时间
            "image_url": None,  # 图片地址
        }
        # 获取图片上传时间
        if not robot.check_sub_key(("dateupload",), photo_info):
            raise robot.RobotException("图片信息'dateupload'字段不存在\n%s" % photo_info)
        if not robot.is_integer(photo_info["dateupload"]):
            raise robot.RobotException("图片信息'dateupload'字段类型不正确\n%s" % photo_info)
        result_image_info["image_time"] = int(photo_info["dateupload"])
        # 获取图片地址
        max_resolution = 0
        max_resolution_photo_type = ""
        # 可获取图片尺寸中最大的那张
        for photo_type in ["c","f","h","k","l","m","n","o","q","s","sq","t","z"]:
            if robot.check_sub_key(("width_" + photo_type, "height_" + photo_type), photo_info):
                resolution = int(photo_info["width_" + photo_type]) * int(photo_info["height_" + photo_type])
                if resolution > max_resolution:
                    max_resolution = resolution
                    max_resolution_photo_type = photo_type
        if not max_resolution_photo_type:
            raise robot.RobotException("图片信息匹配最高分辨率的图片尺寸失败\n%s" % photo_info)
        if robot.check_sub_key(("url_" + max_resolution_photo_type + "_cdn",), photo_info):
            result_image_info["image_url"] = str(photo_info["url_" + max_resolution_photo_type + "_cdn"])
        elif robot.check_sub_key(("url_" + max_resolution_photo_type,), photo_info):
            result_image_info["image_url"] = str(photo_info["url_" + max_resolution_photo_type])
        else:
            raise robot.RobotException("图片信息'url_%s_cdn'或者'url_%s_cdn'字段不存在\n%s" % (max_resolution_photo_type, max_resolution_photo_type, photo_info))
        result["image_info_list"].append(result_image_info)
    # 判断是不是最后一页
    if page_count >= int(photo_pagination_response.json_data["photos"]["pages"]):
        result["is_over"] = True
    return result


class Flickr(robot.Robot):
    def __init__(self):
        global IMAGE_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH
        global COOKIE_INFO

        sys_config = {
            robot.SYS_DOWNLOAD_IMAGE: True,
            robot.SYS_SET_PROXY: True,
            robot.SYS_GET_COOKIE: {".flickr.com": ()}
        }
        robot.Robot.__init__(self, sys_config)

        # 设置全局变量，供子线程调用
        IMAGE_DOWNLOAD_PATH = self.image_download_path
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)
        COOKIE_INFO = self.cookie_value

    def main(self):
        global ACCOUNT_LIST

        # 解析存档文件
        # account_id  image_count  last_image_time
        ACCOUNT_LIST = robot.read_save_data(self.save_data_path, 0, ["", "0", "0"])

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

        # 检查除主线程外的其他全部线程是不是全部结束了
        while threading.activeCount() > main_thread_count:
            self.wait_sub_thread()

        # 未完成的数据保存
        if len(ACCOUNT_LIST) > 0:
            tool.write_file(tool.list_to_string(ACCOUNT_LIST.values()), NEW_SAVE_DATA_PATH)

        # 重新排序保存存档文件
        robot.rewrite_save_file(NEW_SAVE_DATA_PATH, self.save_data_path)

        log.step("全部下载完毕，耗时%s秒，共计图片%s张" % (self.get_run_time(), TOTAL_IMAGE_COUNT))


class Download(robot.DownloadThread):
    request_id = tool.generate_random_string(8)  # 生成一个随机的request id用作访问（模拟页面传入）

    def __init__(self, account_info, main_thread):
        robot.DownloadThread.__init__(self, account_info, main_thread)
        self.account_name = self.account_info[0]
        log.step(self.account_name + " 开始")

    # 获取所有可下载图片
    def get_crawl_list(self, user_id, site_key, csrf, cookie_session):
        page_count = 1
        image_info_list = []
        is_over = False
        # 获取全部还未下载过需要解析的图片
        while not is_over:
            self.main_thread_check()  # 检测主线程运行状态
            log.step(self.account_name + " 开始解析第%s页图片" % page_count)

            # 获取一页图片
            try:
                photo_pagination_response = get_one_page_photo(user_id, page_count, site_key, csrf, self.request_id, cookie_session)
            except robot.RobotException, e:
                log.error(self.account_name + " 第%s页图片解析失败，原因：%s" % (page_count, e.message))
                raise

            log.trace(self.account_name + " 第%s页解析的全部图片：%s" % (page_count, photo_pagination_response["image_info_list"]))

            # 寻找这一页符合条件的图片
            for image_info in photo_pagination_response["image_info_list"]:
                # 检查是否达到存档记录
                if image_info["image_time"] > int(self.account_info[2]):
                    image_info_list.append(image_info)
                else:
                    is_over = True
                    break

            if not is_over:
                if photo_pagination_response["is_over"]:
                    is_over = True
                else:
                    page_count += 1

        return image_info_list

    # 下载同一上传时间的所有图片
    def crawl_image(self, image_info_list):
        image_index = int(self.account_info[1]) + 1
        for image_info in image_info_list:
            self.main_thread_check()  # 检测主线程运行状态
            log.step(self.account_name + " 开始下载第%s张图片 %s" % (image_index, image_info["image_url"]))
            file_type = image_info["image_url"].split(".")[-1]
            file_path = os.path.join(IMAGE_DOWNLOAD_PATH, self.account_name, "%04d.%s" % (image_index, file_type))
            save_file_return = net.save_net_file(image_info["image_url"], file_path)
            if save_file_return["status"] == 1:
                # 设置临时目录
                self.temp_path_list.append(file_path)
                log.step(self.account_name + " 第%s张图片下载成功" % image_index)
                image_index += 1
            else:
                log.error(self.account_name + " 第%s张图片 %s 下载失败，原因：%s" % (image_index, image_info["image_url"], robot.get_save_net_file_failed_reason(save_file_return["code"])))

        # 图片下载完毕
        self.temp_path_list = []  # 临时目录设置清除
        self.total_image_count += (image_index - 1) - int(self.account_info[1])  # 计数累加
        self.account_info[1] = str(image_index - 1)  # 设置存档记录
        self.account_info[2] = str(image_info_list[0]["image_time"])  # 设置存档记

    def run(self):
        try:
            # 获取相册首页页面
            try:
                account_index_response = get_account_index_page(self.account_name)
            except robot.RobotException, e:
                log.error(self.account_name + " 相册首页解析失败，原因：%s" % e.message)
                raise

            # 获取所有可下载图片
            image_info_list = self.get_crawl_list(account_index_response["user_id"], account_index_response["site_key"], account_index_response["csrf"], account_index_response["cookie_session"])
            log.step(self.account_name + " 需要下载的全部图片解析完毕，共%s张" % len(image_info_list))

            # 从最早的图片开始下载
            deal_image_info_list = []
            while len(image_info_list) > 0:
                image_info = image_info_list.pop()
                # 下一张图片的上传时间一致，合并下载
                deal_image_info_list.append(image_info)
                if len(image_info_list) > 0 and image_info_list[-1]["image_time"] == image_info["image_time"]:
                    continue

                # 下载同一上传时间的所有图片
                self.crawl_image(deal_image_info_list)
                deal_image_info_list = []  # 累加图片地址清除
                self.main_thread_check()  # 检测主线程运行状态
        except SystemExit, se:
            if se.code == 0:
                log.step(self.account_name + " 提前退出")
            else:
                log.error(self.account_name + " 异常退出")
            # 如果临时目录变量不为空，表示同一时间的图片正在下载中，需要把下载了部分的内容给清理掉
            self.clean_temp_path()
        except Exception, e:
            log.error(self.account_name + " 未知异常")
            log.error(str(e) + "\n" + str(traceback.format_exc()))

        # 保存最后的信息
        with self.thread_lock:
            global TOTAL_IMAGE_COUNT
            tool.write_file("\t".join(self.account_info), NEW_SAVE_DATA_PATH)
            TOTAL_IMAGE_COUNT += self.total_image_count
            ACCOUNT_LIST.pop(self.account_name)
        log.step(self.account_name + " 下载完毕，总共获得%s张图片" % self.total_image_count)
        self.notify_main_thread()


if __name__ == "__main__":
    Flickr().main()
