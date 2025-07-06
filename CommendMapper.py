import json
import os
import sys
from pathlib import Path
from typing import Dict, Any


class CommandMapper:
    def __init__(self, config_path: str = "./conf/command_mappings.json"):
        self.config_path = Path(config_path)
        self.command_mappings = self._load_config()
        self.system = self._detect_system()

    def _detect_system(self) -> str:
        """检测操作系统类型"""
        if sys.platform.startswith('win'):
            return 'windows'
        elif sys.platform.startswith('linux'):
            return 'linux'
        elif sys.platform.startswith('darwin'):
            return 'darwin'
        return 'linux'  # 默认回退到linux

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # 默认配置
            return {
                "ls": {
                    "windows": "dir",
                    "linux": "ls",
                    "darwin": "ls"
                },
                # ...其他默认配置
            }

    def _save_config(self):
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.command_mappings, f, indent=2, ensure_ascii=False)

    def get_command(self, original_cmd: str) -> str:
        """
        获取适用于当前系统的命令
        如果发现新映射会自动更新配置
        """
        # 检查命令是否已存在映射
        if original_cmd in self.command_mappings:
            sys_cmd = self.command_mappings[original_cmd].get(self.system)
            return sys_cmd if sys_cmd else original_cmd

        # 新命令处理逻辑
        new_mapping =  {
                "windows": "ipconfig",
                "linux": "ifconfig",
                "darwin": "ifconfig"
            }
        if new_mapping:
            self.command_mappings[original_cmd] = new_mapping
            self._save_config()
            return new_mapping.get(self.system, original_cmd)

        return original_cmd

    def add_mapping(self, original_cmd: str, platform: str, mapped_cmd: str) -> int:
        """
        添加新命令映射到配置文件

        参数:
            original_cmd: 原始命令 (如 'ls')
            platform: 平台名 ('windows'/'linux'/'darwin')
            mapped_cmd: 该平台对应的命令 (如 'dir')

        返回:
            returncode:
                0 - 添加成功
                1 - 无效平台
                2 - 映射已存在且相同
                3 - 映射已存在但不同（已更新）
                4 - 文件写入失败
        """
        # 验证平台有效性
        valid_platforms = ['windows', 'linux', 'darwin']
        if platform not in valid_platforms:
            return 1

        # 检查是否已存在相同映射
        existing_mapping = self.command_mappings.get(original_cmd, {})
        if platform in existing_mapping:
            if existing_mapping[platform] == mapped_cmd:
                return 2  # 已存在相同映射
            else:
                # 更新现有映射
                self.command_mappings[original_cmd][platform] = mapped_cmd
                return_code = 3
        else:
            # 添加新映射
            if original_cmd not in self.command_mappings:
                self.command_mappings[original_cmd] = {}
            self.command_mappings[original_cmd][platform] = mapped_cmd
            return_code = 0

        # 尝试保存到文件
        try:
            self._save_config()
        except (IOError, PermissionError):
            return 4

        return return_code


if __name__ == "__main__":
    # 初始化
    mapper = CommandMapper()

    # 获取转换后的命令
    print(mapper.get_command('ls'))  # windows返回'dir'，linux/mac返回'ls'

    # 添加新映射
    mapper.add_mapping('vim','linux','vim')

    # 自动检测新命令（假设实现检测逻辑后）
    print(mapper.get_command('nslookup'))  # 可能返回平台特定命令