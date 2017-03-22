# -*- coding:UTF-8  -*-
"""
微博批量关注账号
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import net, robot, tool
import os
import time
COOKIE_INFO = {"SUB": ""}


# 检测登录状态
def check_login():
    if not COOKIE_INFO["SUB"]:
        return False
    cookies_list = {"SUB": COOKIE_INFO["SUB"]}
    weibo_index_page_url = "http://weibo.com/"
    weibo_index_page_response = net.http_request(weibo_index_page_url, cookies_list=cookies_list)
    if weibo_index_page_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        return weibo_index_page_response.data.find("$CONFIG['islogin']='1';") >= 0
    return False


# 使用浏览器保存的cookie模拟登录请求，获取一个session级别的访问cookie
def generate_login_cookie():
    global COOKIE_INFO
    login_url = "http://login.sina.com.cn/sso/login.php?url=http%3A%2F%2Fweibo.com"
    login_response = net.http_request(login_url, cookies_list=COOKIE_INFO)
    if login_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        set_cookies = net.get_cookies_from_response_header(login_response.headers)
        if set_cookies:
            COOKIE_INFO.update(set_cookies)
            return True
    return False


# 关注指定账号
def follow_account(account_id):
    follow_api_url = "http://weibo.com/aj/f/followed?ajwvr=6"
    post_data = {
        "uid": account_id,
        "refer_flag": "1005050001_",
    }
    header_list = {
        "Referer": "http://weibo.com/%s/follow" % account_id,
    }
    cookies_list = {"SUB": COOKIE_INFO["SUB"]}
    follow_api_response = net.http_request(follow_api_url, method="POST", post_data=post_data, header_list=header_list, cookies_list=cookies_list, json_decode=True)
    if follow_api_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        if robot.check_sub_key(("code",), follow_api_response.json_data) and robot.is_integer(follow_api_response.json_data["code"]):
            if int(follow_api_response.json_data["code"]) == 100000:
                tool.print_msg("关注%s成功" % account_id)
                return True
            elif int(follow_api_response.json_data["code"]) == 100027:
                tool.print_msg("关注%s失败，连续关注太多用户需要输入验证码，等待一会儿继续尝试" % account_id)
                # sleep 一段时间后再试
                time.sleep(60)
            elif int(follow_api_response.json_data["code"]) == 100001:
                tool.print_msg("达到今日关注上限，退出程序" % account_id)
                tool.process_exit()
            else:
                tool.print_msg("关注%s失败，返回内容：%s，退出程序！" % (account_id, follow_api_response.json_data))
                tool.process_exit()
            return False
    else:
        tool.print_msg("关注%s失败，请求返回结果：%s，退出程序！" % (account_id, robot.get_http_request_failed_reason(follow_api_response.status)))
        tool.process_exit()
    return False


if __name__ == "__main__":
    config = robot.read_config(os.path.join(os.getcwd(), "..\\common\\config.ini"))
    # 操作系统&浏览器
    browser_type = robot.get_config(config, "BROWSER_TYPE", 2, 1)
    # cookie
    is_auto_get_cookie = robot.get_config(config, "IS_AUTO_GET_COOKIE", True, 4)
    if is_auto_get_cookie:
        cookie_path = robot.tool.get_default_browser_cookie_path(browser_type)
    else:
        cookie_path = robot.get_config(config, "COOKIE_PATH", "", 0)
    all_cookie_from_browser = tool.get_all_cookie_from_browser(browser_type, cookie_path)
    if ".sina.com.cn" in all_cookie_from_browser:
        for cookie_key in all_cookie_from_browser[".sina.com.cn"]:
            COOKIE_INFO[cookie_key] = all_cookie_from_browser[".sina.com.cn"][cookie_key]
    else:
        tool.print_msg("没有获取到登录信息，退出！")
        tool.process_exit()
    if ".login.sina.com.cn" in all_cookie_from_browser:
        for cookie_key in all_cookie_from_browser[".login.sina.com.cn"]:
            COOKIE_INFO[cookie_key] = all_cookie_from_browser[".login.sina.com.cn"][cookie_key]
    else:
        tool.print_msg("没有获取到登录信息，退出！")
        tool.process_exit()

    # 检测登录状态
    if not check_login():
        # 如果没有获得登录相关的cookie，则模拟登录并更新cookie
        if generate_login_cookie() and not check_login():
            tool.print_msg("没有检测到您的登录信息，无法关注账号，退出！")
            tool.process_exit()

    # 存档位置
    save_data_path = robot.get_config(config, "SAVE_DATA_PATH", "info/save.data", 3)
    # 读取存档文件
    account_list = robot.read_save_data(save_data_path, 0, ["", "0", "0", "0", ""])
    for account_id in sorted(account_list.keys()):
        while not follow_account(account_id):
            pass

    tool.print_msg("关注完成")