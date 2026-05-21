import argparse
import logging
import os
import shutil
from os import PathLike
from typing import Union

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 默认源目录和目标目录
DEFAULT_SRC_DIR = "/Users/yuyingui/CocosProjects/baloot/build/jsb-link/frameworks/modifiedfiles"
DEFAULT_DST_DIR = "/Applications/Cocos/Creator/2.4.13/CocosCreator.app/Contents/Resources/cocos2d-x"

# 需要忽略的文件列表
IGNORED_FILES = ['.DS_Store']


def copy_and_replace(src: Union[str, PathLike], dst: Union[str, PathLike], confirm=True):
    """
    递归遍历 src 目录，将文件拷贝到 dst 目录，强制覆盖或新增
    
    Args:
        src: 源目录路径
        dst: 目标目录路径
        confirm: 是否需要用户确认
    """
    if not os.path.exists(src):
        logging.error(f"源目录 {src} 不存在，无法执行复制操作。")
        return False

    # 用户确认
    if confirm:
        user_input = input(f"将从 {src} 复制文件到 {dst}，这可能会覆盖现有文件。确认继续? (y/n): ")
        if user_input.lower() != 'y':
            logging.info("操作已取消")
            return False

    try:
        file_count = 0
        ignored_count = 0
        for root, dirs, files in os.walk(src):
            # 计算目标路径
            relative_path = os.path.relpath(root, src)
            target_root = os.path.join(dst, relative_path)

            # 确保目标路径存在
            os.makedirs(target_root, exist_ok=True)

            # 强制拷贝所有文件
            for file in files:
                # 忽略指定的文件
                if file in IGNORED_FILES:
                    logging.debug(f"已忽略: {os.path.join(root, file)}")
                    ignored_count += 1
                    continue
                    
                src_file = os.path.join(root, file)
                dst_file = os.path.join(target_root, file)

                try:
                    # 使用正确的类型进行复制
                    shutil.copy2(src_file, dst_file)  # 强制覆盖
                    logging.info(f"已复制: {dst_file}")
                    file_count += 1
                except Exception as e:
                    logging.error(f"复制文件 {src_file} 到 {dst_file} 失败: {str(e)}")

        logging.info(f"复制完成，共复制 {file_count} 个文件，忽略 {ignored_count} 个文件")
        return True
    except Exception as e:
        logging.error(f"复制过程中发生错误: {str(e)}")
        return False


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='复制修改后的Cocos文件到目标目录')
    parser.add_argument('--src', default=DEFAULT_SRC_DIR, help='源目录路径')
    parser.add_argument('--dst', default=DEFAULT_DST_DIR, help='目标目录路径')
    parser.add_argument('--no-confirm', action='store_true', help='跳过确认提示')
    args = parser.parse_args()

    # 执行复制
    copy_and_replace(args.src, args.dst, confirm=False)
