# -*- coding:UTF-8  -*-
"""
看了又看APP图片爬虫
http://share.yasaxi.com/share.html
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
import os
import threading
import time
import traceback

from common import *
import yasaxiCommon

ACCOUNT_LIST = {}
IMAGE_COUNT_PER_PAGE = 20
TOTAL_IMAGE_COUNT = 0
IMAGE_DOWNLOAD_PATH = ""
NEW_SAVE_DATA_PATH = ""


# 获取指定页数的全部日志
def get_one_page_photo(account_id, cursor):
    photo_pagination_url = "https://api.yasaxi.com/statuses/user"
    query_data = {
        "userId": account_id,
        "cursor": cursor,
        "count": IMAGE_COUNT_PER_PAGE,
    }
    header_list = {
        "x-access-token": yasaxiCommon.ACCESS_TOKEN,
        "x-auth-token": yasaxiCommon.AUTH_TOKEN,
        "x-zhezhe-info": yasaxiCommon.ZHEZHE_INFO,
        "User-Agent": "User-Agent: Dalvik/1.6.0 (Linux; U; Android 4.4.2; Nexus 6 Build/KOT49H)",
    }
    result = {
        "is_error": False,  # 是不是格式不符合
        "is_over": False,  # 是不是已经没有新的图片
        "next_page_cursor": None,  # 下一页图片的指针
        "status_info_list": [],  # 全部状态信息
    }
    photo_pagination_response = net.http_request(photo_pagination_url, method="GET", fields=query_data, header_list=header_list, is_random_ip=False, json_decode=True)
    if photo_pagination_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise robot.RobotException(robot.get_http_request_failed_reason(photo_pagination_response.status))
    # 异常返回
    if robot.check_sub_key(("meta",), photo_pagination_response.json_data) and robot.check_sub_key(("code",), photo_pagination_response.json_data["meta"]):
        if photo_pagination_response.json_data["meta"]["code"] == "NoMoreDataError":
            result["is_over"] = True
        elif photo_pagination_response.json_data["meta"]["code"] == "TooManyRequests":
            time.sleep(30)
            return get_one_page_photo(account_id, cursor)
        else:
            raise robot.RobotException("返回信息'code'字段取值不正确\n%s" % photo_pagination_response.json_data)
    # 正常数据返回
    elif robot.check_sub_key(("data",), photo_pagination_response.json_data):
        if not isinstance(photo_pagination_response.json_data["data"], list):
            raise robot.RobotException("返回信息'data'字段类型不正确\n%s" % photo_pagination_response.json_data)
        if len(photo_pagination_response.json_data["data"]) == 0:
            raise robot.RobotException("返回信息'data'字段长度不正确\n%s" % photo_pagination_response.json_data)
        for status_info in photo_pagination_response.json_data["data"]:
            result_status_info = {
                "id": None,  # 状态id
                "image_url_list": [],  # 全部图片地址
            }
            # 获取状态id
            if not robot.check_sub_key(("statusId",), status_info):
                raise robot.RobotException("状态信息'statusId'字段不存在\n%s" % status_info)
            result_status_info["id"] = str(status_info["statusId"])
            # 获取图片、视频地址
            if not robot.check_sub_key(("medias",), status_info):
                raise robot.RobotException("状态信息'medias'字段不存在\n%s" % status_info)
            if not isinstance(status_info["medias"], list):
                raise robot.RobotException("状态信息'medias'字段类型不正确\n%s" % status_info)
            if len(status_info["medias"]) == 0:
                raise robot.RobotException("状态信息'medias'字段长度不正确\n%s" % status_info)
            for media_info in status_info["medias"]:
                # 带模糊效果的，XXXXX_b.webp
                # https://s3-us-west-2.amazonaws.com/ysx.status.2/1080/baf196caa043a88ecf35a4652fa6017648aa5a02_b.webp?AWSAccessKeyId=AKIAJGLBMFWYTNLTZTOA&Expires=1498737886&Signature=%2F5Gmp5HRNXkGnlwJ2aulGfEqhh8%3D
                # 原始图的，XXXXX.webp
                # https://s3-us-west-2.amazonaws.com/ysx.status.2/1080/7ec8bccbbf0d618d67170f77054e3931220e3c14.webp?AWSAccessKeyId=AKIAJGLBMFWYTNLTZTOA&Expires=1498737886&Signature=9hvWk62TmAAPq67Rn577WU8NyYI%3D
                if not robot.check_sub_key(("origin", "downloadUrl", "thumb"), media_info):
                    raise robot.RobotException("媒体信息'origin'、'downloadUrl'、'thumb'字段不存在\n%s" % media_info)
                if not robot.check_sub_key(("mediaType",), media_info):
                    raise robot.RobotException("媒体信息'mediaType'字段不存在\n%s" % media_info)
                if not robot.is_integer(media_info["mediaType"]):
                    raise robot.RobotException("媒体信息'mediaType'字段不存在\n%s" % media_info)
                if int(robot.is_integer(media_info["mediaType"])) not in [1, 2]:
                    raise robot.RobotException("媒体信息'mediaType'取值不正确\n%s" % media_info)
                # 优先使用downloadUrl
                if media_info["downloadUrl"]:
                    result_status_info["image_url_list"].append(str(media_info["downloadUrl"]))
                # 前次使用downloadUrl
                elif media_info["origin"]:
                    result_status_info["image_url_list"].append(str(media_info["origin"]))
                else:
                    # 视频，可能只有预览图
                    if int(media_info["mediaType"]) == 2:
                        if not media_info["thumb"]:
                            raise robot.RobotException("媒体信息'downloadUrl'、'origin'、'thumb'字段都没有值\n%s" % media_info)
                        result_status_info["image_url_list"].append(str(media_info["thumb"]))
                    # 图片，不存在origin和downloadUrl，抛出异常
                    elif int(media_info["mediaType"]) == 1:
                        raise robot.RobotException("媒体信息'origin'和'downloadUrl'字段都没有值\n%s" % media_info)
            result["status_info_list"].append(result_status_info)
        # 获取下一页指针
        if not robot.check_sub_key(("next",), photo_pagination_response.json_data):
            raise robot.RobotException("返回信息'next'字段不存在\n%s" % photo_pagination_response.json_data)
        if photo_pagination_response.json_data["next"] and robot.is_integer(photo_pagination_response.json_data["next"]):
            result["next_page_cursor"] = int(photo_pagination_response.json_data["next"])
    else:
        raise robot.RobotException("返回信息'code'或'data'字段不存在\n%s" % photo_pagination_response.json_data)
    return result


class Yasaxi(robot.Robot):
    def __init__(self):
        global IMAGE_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH

        sys_config = {
            robot.SYS_DOWNLOAD_IMAGE: True,
            robot.SYS_NOT_CHECK_SAVE_DATA: True,
        }
        robot.Robot.__init__(self, sys_config)

        # 服务器有请求数量限制，所以取消多线程
        self.thread_count = 1

        # 设置全局变量，供子线程调用
        IMAGE_DOWNLOAD_PATH = self.image_download_path
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)

    def main(self):
        global ACCOUNT_LIST

        # 从文件中宏读取账号信息（访问token）
        if not yasaxiCommon.get_token_from_file():
            log.error("保存的账号信息读取失败")
            tool.process_exit()

        # 解析存档文件
        # account_id  status_id
        ACCOUNT_LIST = robot.read_save_data(self.save_data_path, 0, ["", ""])

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

        log.step("全部下载完毕，耗时%s秒，共计图片%s张" % (self.get_run_time(), TOTAL_IMAGE_COUNT))


class Download(robot.DownloadThread):
    def __init__(self, account_info, main_thread):
        robot.DownloadThread.__init__(self, account_info, main_thread)

    def run(self):
        global TOTAL_IMAGE_COUNT

        account_id = self.account_info[0]
        account_name = self.account_info[2]
        image_count = 1

        try:
            log.step(account_name + " 开始")

            cursor = 0
            is_over = False
            first_status_id = None
            image_path = os.path.join(IMAGE_DOWNLOAD_PATH, account_name)
            while not is_over:
                log.step(account_name + " 开始解析cursor '%s'的图片" % cursor)

                # 获取一页图片
                try:
                    photo_pagination_response = get_one_page_photo(account_id, cursor)
                except robot.RobotException, e:
                    log.error(account_name + " cursor '%s'后的一页图片解析失败，原因：%s" % (cursor, e.message))
                    raise

                if photo_pagination_response["is_over"]:
                    break

                for status_info in photo_pagination_response["status_info_list"]:
                    # 检查是否达到存档记录
                    if status_info["id"] == self.account_info[1]:
                        is_over = True
                        break

                    # 新的存档记录
                    if first_status_id is None:
                        first_status_id = status_info["id"]

                    log.step(account_name + " 开始解析状态%s的图片" % status_info["id"])

                    for image_url in status_info["image_url_list"]:
                        file_name_and_type = image_url.split("?")[0].split("/")[-1]
                        resolution = image_url.split("?")[0].split("/")[-2]
                        file_name = file_name_and_type.split(".")[0]
                        file_type = file_name_and_type.split(".")[1]
                        if file_name[-2:] != "_b" and resolution == "1080":
                            image_file_path = os.path.join(image_path, "origin/%s.%s" % (file_name, file_type))
                        else:
                            image_file_path = os.path.join(image_path, "other/%s.%s" % (file_name, file_type))
                        log.step(account_name + " 开始下载第%s张图片 %s" % (image_count, image_url))
                        save_file_return = net.save_net_file(image_url, image_file_path)
                        if save_file_return["status"] == 1:
                            log.step(account_name + " 第%s张图片下载成功" % image_count)
                            image_count += 1
                        else:
                            log.error(account_name + " 第%s张图片 %s 下载失败，原因：%s" % (image_count, image_url, robot.get_save_net_file_failed_reason(save_file_return["code"])))

                if not is_over:
                    if photo_pagination_response["next_page_cursor"] is not None:
                        cursor = photo_pagination_response["next_page_cursor"]
                    else:
                        is_over = True
            # 新的存档记录
            if first_status_id is not None:
                self.account_info[1] = first_status_id
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
            TOTAL_IMAGE_COUNT += image_count - 1
            ACCOUNT_LIST.pop(account_id)
        log.step(account_name + " 下载完毕，总共获得%s张图片" % (image_count - 1))
        self.notify_main_thread()

if __name__ == "__main__":
    Yasaxi().main()
