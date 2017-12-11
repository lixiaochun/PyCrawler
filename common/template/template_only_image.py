# -*- coding:UTF-8  -*-
"""
模板
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import *
import json
import os
import re
import threading
import time
import traceback

ACCOUNT_LIST = {}
TOTAL_IMAGE_COUNT = 0
IMAGE_DOWNLOAD_PATH = ""
NEW_SAVE_DATA_PATH = ""


# 获取一页日志
def get_one_page_blog(account_id, page_count):
    result = {
        "blog_id_list": [],  # 日志id
    }
    return result


# 获取指定日志
def get_blog_page(account_id, blog_id):
    result = {
        "image_url_list": [],  # 全部图片地址
    }
    return result


class Template(robot.Robot):
    def __init__(self):
        global IMAGE_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH

        # todo 配置
        sys_config = {
            robot.SYS_DOWNLOAD_IMAGE: True,
            robot.SYS_SET_PROXY: True,
            robot.SYS_NOT_CHECK_SAVE_DATA: True,
        }
        robot.Robot.__init__(self, sys_config)

        # 设置全局变量，供子线程调用
        IMAGE_DOWNLOAD_PATH = self.image_download_path
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)

    def main(self):
        global ACCOUNT_LIST

        # todo 存档文件格式
        # 解析存档文件
        # account_id
        ACCOUNT_LIST = robot.read_save_data(self.save_data_path, 0, ["", ])

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
        self.account_id = self.account_info[0]
        # todo 是否有需要显示不同名字
        self.account_name = self.account_id
        log.step(self.account_name + " 开始")

    # 获取所有可下载日志
    def get_crawl_list(self):
        page_count = 1
        blog_id_list = []
        is_over = False
        # 获取全部还未下载过需要解析的日志
        while not is_over:
            self.main_thread_check()  # 检测主线程运行状态
            log.step(self.account_name + " 开始解析第%s页日志" % page_count)

            # todo 一页日志解析规则
            # 获取指定时间后的一页日志
            try:
                blog_pagination_response = get_one_page_blog(self.account_id, page_count)
            except robot.RobotException, e:
                log.error(self.account_name + " 第%s页日志解析失败，原因：%s" % (page_count, e.message))
                raise

            log.trace(self.account_name + " 第%s页解析的全部日志：%s" % (page_count, blog_pagination_response["blog_id_list"]))

            # 寻找这一页符合条件的媒体
            for blog_id in blog_pagination_response["blog_id_list"]:
                # 检查是否达到存档记录
                if int(blog_id) > int(self.account_info[3]):
                    blog_id_list.append(blog_id)
                else:
                    is_over = True
                    break

        return blog_id_list

    # 解析单个日志
    def crawl_blog(self, blog_id):
        # todo 日志解析规则
        # 获取指定日志
        try:
            blog_response = get_blog_page(self.account_id, blog_id)
        except robot.RobotException, e:
            log.error(self.account_name + " 日志%s解析失败，原因：%s" % (blog_id, e.message))
            raise

        # todo 图片下载逻辑
        # 图片下载
        image_index = self.account_info[1] + 1
        for image_url in blog_response["image_url_list"]:
            self.main_thread_check()  # 检测主线程运行状态
            log.step(self.account_name + " 开始下载第%s张图片 %s" % (image_index, image_url))

            file_type = image_url.split(".")[-1]
            image_file_path = os.path.join(IMAGE_DOWNLOAD_PATH, self.account_name, "%04d.%s" % (image_index, file_type))
            save_file_return = net.save_net_file(image_url, image_file_path)
            if save_file_return["status"] == 1:
                # 设置临时目录
                self.temp_path_list.append(image_file_path)
                log.step(self.account_name + " 第%s张图片下载成功" % image_index)
                image_index += 1
            else:
                log.error(self.account_name + " 第%s张图片 %s 下载失败，原因：%s" % (image_index, image_url, robot.get_save_net_file_failed_reason(save_file_return["code"])))

        # 媒体内图片全部下载完毕
        self.temp_path_list = []  # 临时目录设置清除
        self.total_image_count += (image_index - 1) - int(self.account_info[1])  # 计数累加
        self.account_info[1] = str(image_index - 1)  # 设置存档记录
        self.account_info[2] = ""  # 设置存档记录

    def run(self):
        try:
            # 获取所有可下载日志
            blog_id_list = self.get_crawl_list()
            log.step(self.account_name + " 需要下载的全部日志解析完毕，共%s个" % len(blog_id_list))

            # 从最早的日志开始下载
            while len(blog_id_list) > 0:
                blog_id = blog_id_list.pop()
                log.step(self.account_name + " 开始解析日志%s" % blog_id)
                self.crawl_blog(blog_id)
                self.main_thread_check()  # 检测主线程运行状态
        except SystemExit, se:
            if se.code == 0:
                log.step(self.account_name + " 提前退出")
            else:
                log.error(self.account_name + " 异常退出")
            # 如果临时目录变量不为空，表示某个日志正在下载中，需要把下载了部分的内容给清理掉
            self.clean_temp_path()
        except Exception, e:
            log.error(self.account_name + " 未知异常")
            log.error(str(e) + "\n" + str(traceback.format_exc()))

        # 保存最后的信息
        with self.thread_lock:
            global TOTAL_IMAGE_COUNT
            tool.write_file("\t".join(self.account_info), NEW_SAVE_DATA_PATH)
            TOTAL_IMAGE_COUNT += self.total_image_count
            ACCOUNT_LIST.pop(self.account_id)
        log.step(self.account_name + " 下载完毕，总共获得%s张图片" % self.total_image_count)
        self.notify_main_thread()


if __name__ == "__main__":
    Template().main()
