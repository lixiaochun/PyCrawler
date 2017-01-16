# -*- coding:UTF-8  -*-
"""
半次元图片爬虫
http://bcy.net
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import log, robot, tool
import base64
import cookielib
import json
import os
import re
import threading
import time
import traceback
import urllib2

ACCOUNTS = []
TOTAL_IMAGE_COUNT = 0
GET_PAGE_COUNT = 0
IMAGE_DOWNLOAD_PATH = ""
NEW_SAVE_DATA_PATH = ""
IS_AUTO_FOLLOW = True
NOT_LOGIN_CAN_RUN = False
SAVE_ACCOUNT_INFO = True
COOKIE_INFO = {"acw_tc": "", "PHPSESSID": ""}


# 检测登录状态
def check_login():
    if not COOKIE_INFO["acw_tc"] or not COOKIE_INFO["PHPSESSID"]:
        return False
    home_page_url = "http://bcy.net/home/user/index"
    header_list = {"Cookie": "acw_tc=%s; PHPSESSID=%s; mobile_set=no" % (COOKIE_INFO["acw_tc"], COOKIE_INFO["PHPSESSID"])}
    home_page_response = tool.http_request2(home_page_url, header_list=header_list)
    if home_page_response.status == 200:
        if home_page_response.data.find('<a href="/login">登录</a>') == -1:
            return True
        else:
            return False
    return False


# 从文件中获取账号信息
def read_cookie_info_from_file():
    if not os.path.exists("account.data"):
        return False
    file_handle = open("account.data", "r")
    cookie_info = file_handle.read()
    file_handle.close()
    try:
        cookie_info = json.loads(base64.b64decode(cookie_info[1:]))
    except TypeError:
        pass
    except ValueError:
        pass
    else:
        if robot.check_sub_key(("acw_tc", "PHPSESSID"), cookie_info):
            global COOKIE_INFO
            COOKIE_INFO["acw_tc"] = cookie_info["acw_tc"]
            COOKIE_INFO["PHPSESSID"] = cookie_info["PHPSESSID"]
            return True
    return False


# 保存账号信息到到文件中
def save_cookie_info_to_file(cookie_info):
    account_info = tool.generate_random_string(1) + base64.b64encode(json.dumps(cookie_info))
    file_handle = open("account.data", "w")
    file_handle.write(account_info)
    file_handle.close()


# 从控制台输入获取账号信息
def get_account_info_from_console():
    while True:
        email = raw_input(tool.get_time() + " 请输入邮箱: ")
        password = raw_input(tool.get_time() + " 请输入密码: ")
        while True:
            input_str = raw_input(tool.get_time() + " 是否使用这些信息(Y)es或重新输入(N)o: ")
            input_str = input_str.lower()
            if input_str in ["y", "yes"]:
                return email, password
            elif input_str in ["n", "no"]:
                break
            else:
                pass


# 模拟登录
def login():
    global COOKIE_INFO
    # 访问首页，获取一个随机session id
    home_page_url = "http://bcy.net/home/user/index"
    home_page_response = tool.http_request2(home_page_url)
    if home_page_response.status == 200 and "Set-Cookie" in home_page_response.headers:
        COOKIE_INFO["acw_tc"] = tool.find_sub_string(home_page_response.headers["Set-Cookie"], "acw_tc=", ";")
        COOKIE_INFO["PHPSESSID"] = tool.find_sub_string(home_page_response.headers["Set-Cookie"], "PHPSESSID=", ";")
    else:
        return False
    # 从命令行中输入账号密码
    email, password = get_account_info_from_console()
    login_url = "http://bcy.net/public/dologin"
    login_post = {"email": email, "password": password}
    header_list = {"Cookie": "acw_tc=%s; PHPSESSID=%s; mobile_set=no" % (COOKIE_INFO["acw_tc"], COOKIE_INFO["PHPSESSID"])}
    login_response = tool.http_request2(login_url, login_post, header_list=header_list)
    if login_response.status == 200:
        if login_response.data.find('<a href="/login">登录</a>') == -1:
            if SAVE_ACCOUNT_INFO:
                save_cookie_info_to_file(COOKIE_INFO)
            return True
    return False


# 关注指定账号
def follow(account_id):
    follow_url = "http://bcy.net/weibo/Operate/follow?"
    follow_post_data = {"uid": account_id, "type": "dofollow"}
    follow_response = tool.http_request2(follow_url, follow_post_data)
    if follow_response.status == 200:
        # 0 未登录，11 关注成功，12 已关注
        if int(follow_response.data) == 12:
            return True
    return False


# 取消关注指定账号
def unfollow(account_id):
    unfollow_url = "http://bcy.net/weibo/Operate/follow?"
    unfollow_post_data = {"uid": account_id, "type": "unfollow"}
    unfollow_response = tool.http_request2(unfollow_url, unfollow_post_data)
    if unfollow_response.status == 200:
        if int(unfollow_response.data) == 1:
            return True
    return False


# 获取一页的作品信息
def get_one_page_post(coser_id, page_count):
    # http://bcy.net/u/50220/post/cos?&p=1
    post_url = "http://bcy.net/u/%s/post/cos?&p=%s" % (coser_id, page_count)
    post_page_response = tool.http_request2(post_url)
    if post_page_response.status == 200:
        return post_page_response.data
    return None


# 解析作品信息，获取所有的正片信息
def get_rp_list(post_page):
    cp_and_rp_id_list = re.findall('/coser/detail/(\d+)/(\d+)"', post_page)
    title_list = re.findall('<img src="\S*" alt="([\S ]*)" />', post_page)
    if "${post.title}" in title_list:
        title_list.remove("${post.title}")
    cp_id = None
    rp_list = {}
    if len(cp_and_rp_id_list) == len(title_list):
        for cp_id, rp_id in cp_and_rp_id_list:
            rp_list[rp_id] = title_list.pop(0)
    return cp_id, rp_list


# 获取正片页面内的所有图片地址列表
# cp_id -> 9299
# rp_id -> 36484
def get_image_url_list(cp_id, rp_id):
    # http://bcy.net/coser/detail/9299/36484
    rp_url = "http://bcy.net/coser/detail/%s/%s" % (cp_id, rp_id)
    rp_page_response = tool.http_request2(rp_url)
    if rp_page_response.status == 200:
        if rp_page_response.data.find("该作品属于下属违规情况，已被管理员锁定：") >= 0:
            return -1, []
        else:
            return 1, re.findall("src='([^']*)'", rp_page_response.data)
    return 0, []


# 根据当前作品页面，获取作品页数上限
def get_max_page_count(coser_id, post_page):
    max_page_count = tool.find_sub_string(post_page, '<a href="/u/%s/post/cos?&p=' % coser_id, '">')
    if max_page_count:
        max_page_count = int(max_page_count)
    else:
        max_page_count = 1
    return max_page_count


class Bcy(robot.Robot):
    def __init__(self):
        global GET_PAGE_COUNT
        global IMAGE_DOWNLOAD_PATH
        global NEW_SAVE_DATA_PATH
        global COOKIE_INFO

        sys_config = {
            robot.SYS_DOWNLOAD_IMAGE: True,
            robot.SYS_GET_COOKIE: {"bcy.net": ("acw_tc", "PHPSESSID")},
        }
        robot.Robot.__init__(self, sys_config)

        # 设置全局变量，供子线程调用
        GET_PAGE_COUNT = self.get_page_count
        IMAGE_DOWNLOAD_PATH = self.image_download_path
        NEW_SAVE_DATA_PATH = robot.get_new_save_file_path(self.save_data_path)
        COOKIE_INFO["acw_tc"] = self.cookie_value["acw_tc"]
        # COOKIE_INFO["PHPSESSID"] = self.cookie_value["PHPSESSID"]

    def main(self):
        global ACCOUNTS

        # 检测登录状态
        # 未登录时提示可能无法获取粉丝指定的作品
        if not check_login():
            # 尝试从文件中获取账号信息
            if read_cookie_info_from_file() and check_login():
                pass
            else:
                while True:
                    input_str = raw_input(tool.get_time() + " 没有检测到您的账号信息，可能无法获取那些只对粉丝开放的隐藏作品，是否手动输入账号密码登录(Y)es？ 或者跳过登录继续程序(C)ontinue？或者退出程序(E)xit？:")
                    input_str = input_str.lower()
                    if input_str in ["y", "yes"]:
                        if login():
                            break
                        else:
                            log.step("登录失败！")
                    elif input_str in ["e", "exit"]:
                        tool.process_exit()
                    elif input_str in ["c", "continue"]:
                        break

        # 解析存档文件
        # account_id  last_rp_id
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

        # 重新排序保存存档文件
        robot.rewrite_save_file(NEW_SAVE_DATA_PATH, self.save_data_path)

        log.step("全部下载完毕，耗时%s秒，共计图片%s张" % (self.get_run_time(), TOTAL_IMAGE_COUNT))


class Download(threading.Thread):
    def __init__(self, account_info, thread_lock):
        threading.Thread.__init__(self)
        self.account_info = account_info
        self.thread_lock = thread_lock

    def run(self):
        global TOTAL_IMAGE_COUNT

        coser_id = self.account_info[0]
        if len(self.account_info) >= 3:
            cn = self.account_info[2]
        else:
            cn = self.account_info[0]

        try:
            log.step(cn + " 开始")

            image_path = os.path.join(IMAGE_DOWNLOAD_PATH, cn)

            # 图片下载
            this_cn_total_image_count = 0
            page_count = 1
            total_rp_count = 1
            first_rp_id = ""
            unique_list = []
            is_over = False
            need_make_download_dir = True  # 是否需要创建cn目录
            while not is_over:
                log.step(cn + " 开始解析第%s页作品" % page_count)

                # 获取一页的作品信息
                post_page = get_one_page_post(coser_id, page_count)
                if post_page is None:
                    log.error(cn + " 无法访问第%s页作品" % page_count)
                    tool.process_exit()

                # 解析作品信息，获取所有的正片信息
                cp_id, rp_list = get_rp_list(post_page)
                if cp_id is None:
                    log.error(cn + " 第%s页作品解析异常" % page_count)
                    tool.process_exit()
                log.trace(cn + " cp_id：%s" % cp_id)
                log.trace(cn + " 第%s页获取的所有作品：%s" % (page_count, rp_list))

                for rp_id, title in rp_list.iteritems():
                    # 检查是否已下载到前一次的图片
                    if int(rp_id) <= int(self.account_info[1]):
                        is_over = True
                        break

                    # 将第一个作品的id做为新的存档记录
                    if first_rp_id == "":
                        first_rp_id = rp_id

                    # 新增正片导致的重复判断
                    if rp_id in unique_list:
                        continue
                    else:
                        unique_list.append(rp_id)

                    log.step(cn + " 开始解析作品%s" % rp_id)

                    if need_make_download_dir:
                        if not tool.make_dir(image_path, 0):
                            log.error(cn + " 创建CN目录 %s 失败" % image_path)
                            tool.process_exit()
                        need_make_download_dir = False

                    # 过滤标题中不支持的字符
                    title = robot.filter_text(title)
                    if title:
                        rp_path = os.path.join(image_path, "%s %s" % (rp_id, title))
                    else:
                        rp_path = os.path.join(image_path, rp_id)
                    if not tool.make_dir(rp_path, 0):
                        # 目录出错，把title去掉后再试一次，如果还不行退出
                        log.error(cn + " 创建作品目录 %s 失败，尝试不使用title" % rp_path)
                        rp_path = os.path.join(image_path, rp_id)
                        if not tool.make_dir(rp_path, 0):
                            log.error(cn + " 创建作品目录 %s 失败" % rp_path)
                            tool.process_exit()

                    # 获取正片页面内的所有图片地址列表
                    image_url_status, image_url_list = get_image_url_list(cp_id, rp_id)
                    if image_url_status == 0:
                        log.error(cn + " 无法访问正片：%s，cp_id：%s" % (rp_id, cp_id))
                        continue
                    elif image_url_status == -1:
                        log.error(cn + " 正片：%s，已被管理员锁定，cp_id：%s" % (rp_id, cp_id))
                        continue

                    if len(image_url_list) == 0 and IS_AUTO_FOLLOW:
                        log.step(cn + " 检测到可能有私密作品且账号不是ta的粉丝，自动关注")
                        if follow(coser_id):
                            # 重新获取下正片页面内的所有图片地址列表
                            image_url_status, image_url_list = get_image_url_list(cp_id, rp_id)
                            if image_url_status == 0:
                                log.error(cn + " 无法访问正片：%s，cp_id：%s" % (rp_id, cp_id))
                                continue

                    if len(image_url_list) == 0:
                        log.error(cn + " 正片：%s没有任何图片，可能是你使用的账号没有关注ta，所以无法访问只对粉丝开放的私密作品，cp_id：%s" % (rp_id, cp_id))
                        continue

                    image_count = 1
                    for image_url in list(image_url_list):
                        # 禁用指定分辨率
                        image_url = "/".join(image_url.split("/")[0:-1])
                        log.step(cn + " %s 开始下载第%s张图片 %s" % (rp_id, image_count, image_url))

                        if image_url.rfind("/") < image_url.rfind("."):
                            file_type = image_url.split(".")[-1]
                        else:
                            file_type = "jpg"
                        file_path = os.path.join(rp_path, "%03d.%s" % (image_count, file_type))
                        if tool.save_net_file(image_url, file_path):
                            image_count += 1
                            log.step(cn + " %s 第%s张图片下载成功" % (rp_id, image_count))
                        else:
                            log.error(cn + " %s 第%s张图片 %s 下载失败" % (rp_id, image_count, image_url))

                    this_cn_total_image_count += image_count - 1

                    if 0 < GET_PAGE_COUNT < total_rp_count:
                        is_over = True
                        break
                    else:
                        total_rp_count += 1

                if not is_over:
                    if page_count >= get_max_page_count(coser_id, post_page):
                        is_over = True
                    else:
                        page_count += 1

            log.step(cn + " 下载完毕，总共获得%s张图片" % this_cn_total_image_count)

            # 新的存档记录
            if first_rp_id != "":
                self.account_info[1] = first_rp_id

            # 保存最后的信息
            tool.write_file("\t".join(self.account_info), NEW_SAVE_DATA_PATH)
            self.thread_lock.acquire()
            TOTAL_IMAGE_COUNT += this_cn_total_image_count
            ACCOUNTS.remove(coser_id)
            self.thread_lock.release()

            log.step(cn + " 完成")
        except SystemExit:
            log.error(cn + " 异常退出")
        except Exception, e:
            log.error(cn + " 未知异常")
            log.error(str(e) + "\n" + str(traceback.format_exc()))


if __name__ == "__main__":
    Bcy().main()
