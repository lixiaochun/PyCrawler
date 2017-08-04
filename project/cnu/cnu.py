# -*- coding:UTF-8  -*-
"""
CNU图片爬虫
http://www.cnu.cc/
@author: hikaru
email: hikaru870806@hotmail.com
如有问题或建议请联系
"""
from common import log, net, robot, tool
import json
import os


# 获取作品页面
def get_album_page(album_id):
    album_url = "http://www.cnu.cc/works/%s" % album_id
    album_response = net.http_request(album_url)
    extra_info = {
        "album_title": "",  # 页面解析出的作品标题
        "image_url_list": [],  # 页面解析出的所有图片地址列表
    }
    if album_response.status == net.HTTP_RETURN_CODE_SUCCEED:
        # 获取作品标题
        album_title = tool.find_sub_string(album_response.data, '<h2 class="work-title">', "</h2>")
        if not album_title:
            raise robot.RobotException("页面获取作品标题失败\n%s" % album_response.data)
        extra_info["album_title"] = album_title

        # 获取图片地址
        image_info_html = tool.find_sub_string(album_response.data, '<div id="imgs_json" style="display:none">', "</div>")
        if not image_info_html:
            raise robot.RobotException("页面截取图片列表失败\n%s" % album_response.data)
        try:
            image_info_data = json.loads(image_info_html)
        except ValueError:
            raise robot.RobotException("图片列表decode失败\n%s" % image_info_html)
        image_url_list = []
        for image_info in image_info_data:
            if not robot.check_sub_key(("img",), image_info):
                raise robot.RobotException("图片信息'img'字段不存在\n%s" % image_info)
            image_url_list.append("http://img.cnu.cc/uploads/images/920/" + str(image_info["img"]))
        extra_info["image_url_list"] = image_url_list
    elif album_response.status != 404:
        raise robot.RobotException(robot.get_http_request_failed_reason(album_response.status))
    album_response.extra_info = extra_info
    return album_response


class CNU(robot.Robot):
    def __init__(self):
        sys_config = {
            robot.SYS_DOWNLOAD_IMAGE: True,
            robot.SYS_NOT_CHECK_SAVE_DATA: True,
        }
        robot.Robot.__init__(self, sys_config)

    def main(self):
        # 解析存档文件，获取上一次的album id
        if os.path.exists(self.save_data_path):
            album_id = int(tool.read_file(self.save_data_path))
        else:
            album_id = 1

        # http://www.cnu.cc/about/ 所有作品
        total_image_count = 0
        is_over = False
        while not is_over:
            log.step("开始解析第%s页作品" % album_id)

            # 获取相册
            try:
                album_response = get_album_page(album_id)
            except robot.RobotException, e:
                log.error("第%s页作品解析失败，原因：%s" % (album_id, e.message))
                break
            except SystemExit:
                log.step("提前退出")
                break

            if album_response.status == 404:
                log.step("第%s页作品已被删除，跳过" % album_id)
                album_id += 1
                continue

            log.trace("第%s页作品解析的所有图片：%s" % (album_id, album_response.extra_info["image_url_list"]))

            # 过滤标题中不支持的字符
            album_title = robot.filter_text(album_response.extra_info["album_title"])
            if album_title:
                album_path = os.path.join(self.image_download_path, "%s %s" % (album_id, album_title))
            else:
                album_path = os.path.join(self.image_download_path, str(album_id))
            if not tool.make_dir(album_path, 0):
                # 目录出错，把title去掉后再试一次，如果还不行退出
                log.error("创建作品目录 %s 失败，尝试不使用title" % album_path)
                album_path = os.path.join(self.image_download_path, album_id)
                if not tool.make_dir(album_path, 0):
                    log.error("创建作品目录 %s 失败" % album_path)
                    tool.process_exit()

            image_count = 1
            for image_url in album_response.extra_info["image_url_list"]:
                log.step("作品%s 《%s》 开始下载第%s张图片 %s" % (album_id, album_title, image_count, image_url))

                file_type = image_url.split(".")[-1]
                file_path = os.path.join(album_path, "%03d.%s" % (image_count, file_type))
                try:
                    save_file_return = net.save_net_file(image_url, file_path)
                    if save_file_return["status"] == 1:
                        log.step("作品%s 《%s》 第%s张图片下载成功" % (album_id, album_title, image_count))
                        image_count += 1
                    else:
                         log.error("作品%s 《%s》 第%s张图片 %s 下载失败，原因：%s" % (album_id, album_title, image_count, image_url, robot.get_save_net_file_failed_reason(save_file_return["code"])))
                except SystemExit:
                    log.step("提前退出")
                    tool.remove_dir_or_file(album_path)
                    is_over = True
                    break

            if not is_over:
                total_image_count += image_count - 1
                album_id += 1

        # 重新保存存档文件
        tool.write_file(str(album_id), self.save_data_path, 2)

        log.step("全部下载完毕，耗时%s秒，共计图片%s张" % (self.get_run_time(), total_image_count))


if __name__ == "__main__":
    CNU().main()
