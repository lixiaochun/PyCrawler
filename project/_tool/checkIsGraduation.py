# -*- coding:UTF-8  -*-
# 获取指定存档文件中所有毕业成员的名字
import os


# 存档路径
SAVE_FILE_PATH = os.path.join("save.data")
# 存档中记录成员名字的字段下标
NAME_COLUMN = 4


# 从现役成员名单中获取所有成员名字（由get48GroupMember.py生成）
def get_member_list():
    file_handle = open("member.txt", "r")
    lines = file_handle.readlines()
    file_handle.close()
    member = []
    for line in lines:
        temp_list = line.replace("\n", "").split("\t")
        member.append(temp_list[0])
    return member


# 从存档文件中获取所有名字（NAME_COLUMN对应的名字必须和从官网获取的成员本名一致）
def get_save_file_name_list():
    file_handle = open(SAVE_FILE_PATH, "r")
    lines = file_handle.readlines()
    file_handle.close()
    member = []
    for line in lines:
        temp_list = line.replace("\n", "").split("\t")
        member.append(temp_list[NAME_COLUMN])
    return member


def check_is_graduation():
    member_list = get_member_list()
    save_file_account_name_list = get_save_file_name_list()
    for account_name in save_file_account_name_list:
        if account_name not in member_list:
            print account_name


if __name__ == "__main__":
    check_is_graduation()