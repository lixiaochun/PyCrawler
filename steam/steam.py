# -*- coding:UTF-8  -*-
"""
steam相关数据解析爬虫
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import net, tool
import json
import os
import re


# 读取cookies后获取指定账号的全部游戏列表
def get_owned_app_list(user_id):
    game_index_page_url = "http://steamcommunity.com/profiles/%s/games/?tab=all" % user_id
    game_index_page_return_code, game_index_page = net.http_request(game_index_page_url)[:2]
    if game_index_page_return_code == 1:
        owned_all_game_data = tool.find_sub_string(game_index_page, "var rgGames = ", ";")
        try:
            owned_all_game_data = json.loads(owned_all_game_data)
        except ValueError:
            pass
        else:
            app_id_list = []
            for game_data in owned_all_game_data:
                if "appid" in game_data:
                    app_id_list.append(str(game_data["appid"]))
            return app_id_list


# 获取所有打折游戏列表
def get_discount_list():
    page_count = 1
    total_page_count = -1
    discount_list = []
    app_id_list = []
    while total_page_count == -1 or page_count <= total_page_count:
        search_game_page_url = "http://store.steampowered.com/search/results?sort_by=Price_ASC&category1=998&os=win&specials=1&page=%s" % page_count
        search_game_page_response = net.http_request(search_game_page_url)
        if search_game_page_response != net.HTTP_RETURN_CODE_SUCCEED:
            break
        items_page = tool.find_sub_string(search_game_page_response.data, "<!-- List Items -->", "<!-- End List Items -->")
        items_page = tool.find_sub_string(items_page, "<a href=", None)
        items_page = items_page.replace("\n", "").replace("\r", "").replace("<a href=", "\n<a href=")
        items = items_page.split("\n")
        for item in items:
            app_id = tool.find_sub_string(item, 'data-ds-appid="', '"')
            discount_data = tool.find_sub_string(item, '<div class="col search_discount responsive_secondrow">', "</div>")
            discount = tool.find_sub_string(discount_data, "<span>", "</span>").replace("-", "").replace("%", "")
            if not discount:
                discount = 0
            price_data = tool.find_sub_string(item, '<div class="col search_price discounted responsive_secondrow">', "</div>", 2)
            old_price = tool.find_sub_string(price_data, "<strike>", "</strike>").replace("¥", "").strip()
            if not old_price:
                old_price = 0
            new_price = tool.find_sub_string(price_data, "<br>", "</div>").replace("¥", "").strip()
            if not new_price or not new_price.isdigit():
                new_price = 0
            if app_id not in app_id_list:
                discount_list.append("%s\t%s\t%s\t%s" % (app_id, discount, old_price, new_price))
                app_id_list.append(app_id)
        if total_page_count == -1:
            pagination_page = tool.find_sub_string(search_game_page_response.data, '<div class="search_pagination">', None)
            page_find = re.findall('return false;">([\d]*)</a>', pagination_page)
            if len(page_find) > 0:
                total_page_count = max(map(str, page_find))
        page_count += 1
    return discount_list


# 打折游戏列表保存到文件
def save_discount_list(discount_list):
    tool.write_file(tool.list_to_string(discount_list, "\n", ""), "discount.txt", 2)


# 获取文件中的打折列表
def load_discount_list():
    file_path = os.path.join("discount.txt")
    if not os.path.exists(file_path):
        return []
    file_handle = open("discount.txt", "r")
    lines = file_handle.readlines()
    file_handle.close()
    discount_list = []
    for line in lines:
        discount_list.append(line.replace("\n", ""))
    return discount_list
