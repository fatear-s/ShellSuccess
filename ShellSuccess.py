import os
import platform
import shlex
import subprocess
import sys

import requests
from typing import Tuple, Optional, Union, List
import json

from CommendMapper import CommandMapper
from command import run_command


class DeepSeekCLIExecutor:
    def __init__(self, api_key: str):
        """
        初始化命令行执行器

        :param api_key: DeepSeek API密钥
        """
        self.current_platform = platform.system().lower()  # windows/linux/darwin
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
        self.command_map = CommandMapper()

        # 常见命令的快速映射表
        self.command_mappings = self.command_map._load_config()

        '''
        {
            'ls': {'windows': 'dir', 'linux': 'ls', 'darwin': 'ls'},
            'dir': {'linux': 'ls', 'darwin': 'ls'},
            'clear': {'windows': 'cls'},
            'cls': {'linux': 'clear', 'darwin': 'clear'},
            'pwd': {'windows': 'cd'},
            'cd': {'windows': 'cd','linux': 'cd', 'darwin': 'cd'},  # Windows需要/D参数跨驱动器
        }
        '''

    def _call_deepseek(self, prompt: str) -> Optional[str]:
        """调用DeepSeek API获取响应"""
        try:
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 1000
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"DeepSeek API调用失败: {e}")
            return None

    def is_command_for_current_platform(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        判断命令是否适用于当前平台

        :param command: 输入命令
        :return: (是否适用, 转换后的命令或None)
        """
        # 提取基础命令(第一个单词)
        base_cmd = command.strip().split()[0].lower()

        # 检查快速映射表
        if base_cmd in self.command_mappings:
            if self.current_platform in self.command_mappings[base_cmd]:
                # 需要转换
                translated = self.command_mappings[base_cmd][self.current_platform]
                if len(command.split()) > 1:
                    translated += ' ' + ' '.join(command.split()[1:])
                return False, translated
            else:
                # 命令在当前平台有原生支持
                return True, None

        # 使用DeepSeek进行复杂判断
        prompt = (
            f"请严格判断以下命令是否适用于{self.current_platform}系统，只需回答yes或no:\n"
            f"命令: {command}\n"
            "注意: 如果命令是跨平台的(如python, git等)回答yes\n"
            "如果命令包含路径操作，考虑路径分隔符差异\n"
            "回答: "
        )

        response = self._call_deepseek(prompt)
        if response and response.lower().startswith('yes'):
            return True, None

        # 需要转换 - 获取转换后的命令
        prompt = (
            f"请将以下命令转换为适合{self.current_platform}系统的等效命令:\n"
            f"原始命令: {command}\n"
            "要求: 只返回转换后的命令，不要包含任何解释或额外文本\n"
            "转换结果: "
        )

        translated = self._call_deepseek(prompt)
        return False, translated if translated else command

    def translate_output(self, output: str) -> str:
        """将命令输出翻译为中文"""
        if not output.strip():
            return ""

        prompt = (
            "请将以下命令行输出翻译成简体中文，保持技术术语准确:\n"
            f"{output}\n"
            "翻译结果: "
        )

        translated = self._call_deepseek(prompt)
        return translated if translated else output

    def execute_command(self, command: str) -> Tuple[int, str, str]:
        """
        执行命令并返回结果

        :param command: 输入命令
        :return: (返回码, 标准输出, 标准错误)
        """
        # 判断并转换命令
        is_native, translated_cmd = self.is_command_for_current_platform(command)
        final_cmd = command if is_native else (translated_cmd or command)

        print(f"执行命令: {final_cmd}")

        # 增加配置
        cmd_in = shlex.split(final_cmd)
        mapcode = self.command_map.add_mapping(cmd_in[0], self.current_platform, cmd_in[0])
        self.command_mappings = self.command_map._load_config()
        # print("mapadd")
        # print(mapcode)

        # 执行命令
        try:
            # returncode = os.system(final_cmd)
            # stderr = 0
            # stdout = 1
            returncode,stdout,stderr = run_command(cmd_in) or (1,"","")
            #print(returncode,stdout,stderr)
            # 翻译输出
            if stderr:
                tmp = stderr
                stderr = self.translate_output(stderr)
                suggestion = self.get_ai_suggestion(tmp,final_cmd)
                print(suggestion)
            else:
                if stdout:  # 非ASCII输出才翻译
                    #stdout = self.translate_output(stdout)
                    stdout = stdout
            return returncode, stdout, stderr
        except Exception as e:
            print(str(e))
            error_msg = self.translate_output(str(e))
            print(error_msg)
            return 1, "", f"A命令执行失败: {error_msg}"

    def interactive_shell(self):
        """启动交互式命令行界面"""
        print(f"智能命令行执行器 (当前系统: {self.current_platform.capitalize()})")
        print("输入 'exit' 或 'quit' 退出\n")

        while True:
            try:
                user_input = input(f"{os.getcwd()}> ").strip()
                if user_input.lower() in ('exit', 'quit'):
                    break

                if not user_input:
                    continue

                returncode, stdout, stderr = self.execute_command(user_input)

                if stdout:
                    #print(stdout)
                    pass
                if stderr:
                    print(f"\033[91m{stderr}\033[0m")  # 红色显示错误

            except KeyboardInterrupt:
                print("\n使用 'exit' 或 'quit' 退出程序")
            except Exception as e:
                print(f"\033[91m发生意外错误: {str(e)}\033[0m")

    def get_ai_suggestion(self,error_message: str, cmd: str, model: str = "deepseek-chat") -> str:
        """
        使用DeepSeek大模型获取错误修复建议

        参数:
            error_message: 错误信息
            model: 使用的模型名称

        返回:
            AI生成的修复建议
        """
        prompt = (
            "你是一个专业的命令行助手，请根据错误信息给出具体的修复建议。\n"
            f"执行平台:{self.current_platform}\n"
            f"执行命令:{cmd}\n"
            f"错误信息:{error_message}\n"
            f"要求：只返回错误原因，和建议命令，不要包含任何解释或额外文本\n"
            f"错误原因:\n"
            f"建议命令:"
        )
        print(prompt)
        result = self._call_deepseek(prompt)
        return result







# 使用示例
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="跨平台命令行执行器")
    parser.add_argument("--api_key",default="", help="DeepSeek API密钥")
    args = parser.parse_args()

    executor = DeepSeekCLIExecutor(api_key=args.api_key)
    executor.interactive_shell()