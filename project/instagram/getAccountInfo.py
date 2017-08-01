# -*- coding:UTF-8  -*-
"""
Instagram批量获取账号介绍
https://www.instagram.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import *
import os
import sys


# 获取账号首页
def get_account_index_page(account_name):
    account_index_url = "https://www.instagram.com/%s/" % account_name
    account_index_response = net.http_request(account_index_url)
    extra_info = {
        "account_info": "",  # 页面解析出的自我介绍
        "external_url": "",  # 页面解析出的外部地址
    }
    if account_index_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        account_info = tool.find_sub_string(account_index_response.data, '"biography": "', '"')
        if account_info:
            account_info = account_info.replace(r"\n", "").replace("'", chr(1))
            account_info = eval("u'%s'" % account_info).replace(chr(1), "'").encode("UTF-8")
            extra_info["account_info"] = account_info
        extra_info["external_url"] = tool.find_sub_string(account_index_response.data, '"external_url": "', '"')
    account_index_response.extra_info = extra_info
    return account_index_response


def main():
    config = config = robot.read_config(tool.PROJECT_CONFIG_PATH)
    # 存档位置
    save_data_path = robot.get_config(config, "SAVE_DATA_PATH", "info/save.data", 3)
    # 读取存档文件
    account_list = robot.read_save_data(save_data_path, 0, [""])
    # 设置代理
    is_proxy = robot.get_config(config, "IS_PROXY", 2, 1)
    if is_proxy == 1 or is_proxy == 2:
        proxy_ip = robot.get_config(config, "PROXY_IP", "127.0.0.1", 0)
        proxy_port = robot.get_config(config, "PROXY_PORT", "8087", 0)
        # 使用代理的线程池
        net.set_proxy(proxy_ip, proxy_port)

    result_file_path = "info/account_info.data"
    for account in sorted(account_list.keys()):
        account_index_response = get_account_index_page(account)
        if account_index_response.status == net.HTTP_RETURN_CODE_SUCCEED:
            tool.write_file("%s\t%s\t%s" % (account, account_index_response.extra_info["account_info"], account_index_response.extra_info["external_url"]), result_file_path)

if __name__ == "__main__":
    main()
