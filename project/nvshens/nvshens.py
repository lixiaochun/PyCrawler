# -*- coding:UTF-8  -*-
"""
nvshens图片爬虫
https://www.nvshens.com/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import *
import os
import re
import traceback


# 获取图集首页
def get_index_page():
    index_url = "https://www.nvshens.com/gallery/"
    index_response = net.http_request(index_url, method="GET")
    result = {
        "max_album_id": None,  # 最新图集id
    }
    if index_response.status != net.HTTP_RETURN_CODE_SUCCEED:
        raise robot.RobotException(robot.get_http_request_failed_reason(index_response.status))
    album_id_find = re.findall("<a class='galleryli_link' href='/g/(\d*)/'", index_response.data)
    if len(album_id_find) == 0:
        raise robot.RobotException("页面匹配图集id失败\n%s" % index_response.data)
    result["max_album_id"] = max(map(int, album_id_find))
    return result


# 获取图集全部图片
def get_album_photo(album_id):
    page_count = max_page_count = 1
    image_count = 0
    result = {
        "album_title": "",  # 图集标题
        "image_url_list": [],  # 全部图片地址
        "is_delete": False,  # 是不是已经被删除
    }
    while page_count <= max_page_count:
        album_pagination_url = "https://www.nvshens.com/g/%s/%s.html" % (album_id, page_count)
        album_pagination_response = net.http_request(album_pagination_url, method="GET")
        if album_pagination_response.status != net.HTTP_RETURN_CODE_SUCCEED:
            raise robot.RobotException("第%s页 " % page_count + robot.get_http_request_failed_reason(album_pagination_response.status))
        # 判断图集是否已经被删除
        if page_count == 1:
            result["is_delete"] = album_pagination_response.data.find("<title>该页面未找到-宅男女神</title>") >= 0
            if result["is_delete"]:
                return result
            # 获取图集图片总数
            image_count = tool.find_sub_string(album_pagination_response.data, "<span style='color: #DB0909'>", "张照片</span>")
            if not robot.is_integer(image_count):
                raise robot.RobotException("页面截取图片总数失败\n%s" % album_pagination_response.data)
            image_count = int(image_count)
            if image_count == 0:
                result["is_delete"] = True
                return result
            # 获取图集标题
            result["album_title"] = str(tool.find_sub_string(album_pagination_response.data, '<h1 id="htilte">', "</h1>")).strip()
            if not result["album_title"]:
                raise robot.RobotException("页面截取标题失败\n%s" % album_pagination_response.data)
        # 获取图集图片地址，两种不同的页面样式
        if album_pagination_response.data.find('<ul id="hgallery">') >= 0:
            image_list_html = tool.find_sub_string(album_pagination_response.data, '<ul id="hgallery">', "</ul>")
            if not image_list_html:
                raise robot.RobotException("第%s页 页面截取图片列表失败\n%s" % album_pagination_response.data)
            image_url_list = re.findall("<img src='([^']*)'", image_list_html)
        elif album_pagination_response.data.find('<div class="caroufredsel_wrapper">') >= 0:
            image_list_html = tool.find_sub_string(album_pagination_response.data, '<div class="caroufredsel_wrapper">', "</ul>")
            if not image_list_html:
                raise robot.RobotException("第%s页 页面截取图片列表失败\n%s" % album_pagination_response.data)
            image_url_list = re.findall("src='([^']*)'", image_list_html)
        else:
            raise robot.RobotException("第%s页 未知的图集样式\n%s" % album_pagination_response.data)
        if len(image_url_list) == 0:
            raise robot.RobotException("第%s页 页面匹配图片地址失败\n%s" % (page_count, album_pagination_response.data))
        result["image_url_list"] += map(str, image_url_list)
        # 获取总页数
        max_page_count = 1
        pagination_html = tool.find_sub_string(album_pagination_response.data, '<div id="pages">', "</div>")
        if pagination_html:
            page_count_find = re.findall('/g/' + str(album_id) + '/([\d]*).html', pagination_html)
            if len(page_count_find) != 0:
                max_page_count = max(map(int, page_count_find))
            else:
                log.error("图集%s 第%s页分页异常" % (album_id, page_count))
        page_count += 1
    # 判断页面上的总数和实际地址数量是否一致
    if image_count != len(result["image_url_list"]):
        raise robot.RobotException("页面截取的图片数量 %s 和显示的总数 %s 不一致" % (image_count, len(result["image_url_list"])))
    return result


class Nvshens(robot.Robot):
    def __init__(self):
        sys_config = {
            robot.SYS_DOWNLOAD_IMAGE: True,
            robot.SYS_NOT_CHECK_SAVE_DATA: True,
        }
        robot.Robot.__init__(self, sys_config)

    def main(self):
        # 解析存档文件，获取上一次的album id
        album_id = 10000
        if os.path.exists(self.save_data_path):
            file_save_info = tool.read_file(self.save_data_path)
            if not robot.is_integer(file_save_info):
                log.error("存档内数据格式不正确")
                tool.process_exit()
            album_id = int(file_save_info)
        temp_path = ""

        try:
            # 获取图集首页
            try:
                index_response = get_index_page()
            except robot.RobotException, e:
                log.error("图集首页解析失败，原因：%s" % e.message)
                raise

            log.step("最新图集id：%s" % index_response["max_album_id"])

            while album_id <= index_response["max_album_id"]:
                if not self.is_running():
                    tool.process_exit(0)
                log.step("开始解析图集%s" % album_id)

                # 获取图集
                try:
                    album_pagination_response = get_album_photo(album_id)
                except robot.RobotException, e:
                    log.error("图集%s解析失败，原因：%s" % (album_id, e.message))
                    raise

                if album_pagination_response["is_delete"]:
                    log.step("图集%s不存在，跳过" % album_id)
                    album_id += 1
                    continue

                log.trace("图集%s解析的全部图片：%s" % (album_id, album_pagination_response["image_url_list"]))

                image_index = 1
                # 过滤标题中不支持的字符
                album_title = path.filter_text(album_pagination_response["album_title"])
                if album_title:
                    album_path = os.path.join(self.image_download_path, "%s %s" % (album_id, album_title))
                else:
                    album_path = os.path.join(self.image_download_path, str(album_id))
                temp_path = album_path
                for image_url in album_pagination_response["image_url_list"]:
                    if not self.is_running():
                        tool.process_exit(0)
                    log.step("图集%s 《%s》 开始下载第%s张图片 %s" % (album_id, album_title, image_index, image_url))

                    file_type = image_url.split(".")[-1]
                    file_path = os.path.join(album_path, "%03d.%s" % (image_index, file_type))
                    header_list = {"Referer": "https://www.nvshens.com/g/%s/" % album_id}
                    save_file_return = net.save_net_file(image_url, file_path, header_list=header_list)
                    if save_file_return["status"] == 0 and save_file_return["code"] == 404:
                        new_image_url = None
                        if image_url.find("/0.jpg") >= 0:
                            new_image_url = image_url.replace("/0.jpg", "/000.jpg")
                        elif image_url.find("/s/") >= 0:
                            new_image_url = image_url.replace("/s/", "/")
                        if new_image_url is not None:
                            save_file_return = net.save_net_file(new_image_url, file_path, header_list=header_list)
                    if save_file_return["status"] == 1:
                        log.step("图集%s 《%s》 第%s张图片下载成功" % (album_id, album_title, image_index))
                    else:
                        log.error("图集%s 《%s》 第%s张图片 %s 下载失败，原因：%s" % (album_id, album_title, image_index, image_url, robot.get_save_net_file_failed_reason(save_file_return["code"])))
                    image_index += 1
                # 图集内图片全部下载完毕
                temp_path = ""  # 临时目录设置清除
                self.total_image_count += image_index - 1  # 计数累加
                album_id += 1  # 设置存档记录
        except SystemExit, se:
            if se.code == 0:
                log.step("提前退出")
            else:
                log.error("异常退出")
            # 如果临时目录变量不为空，表示某个图集正在下载中，需要把下载了部分的内容给清理掉
            if temp_path:
                path.delete_dir_or_file(temp_path)
        except Exception, e:
            log.error("未知异常")
            log.error(str(e) + "\n" + str(traceback.format_exc()))

        # 重新保存存档文件
        tool.write_file(str(album_id), self.save_data_path, tool.WRITE_FILE_TYPE_REPLACE)
        log.step("全部下载完毕，耗时%s秒，共计图片%s张" % (self.get_run_time(), self.total_image_count))


if __name__ == "__main__":
    Nvshens().main()
