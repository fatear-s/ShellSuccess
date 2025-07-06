
import subprocess
from typing import Union, List, Optional


def run_command(
        command: Union[str, List[str]],
        *,
        interactive: Optional[bool] = None,
        shell: bool = False,
        check: bool = False,
        **kwargs
) -> subprocess.CompletedProcess:
    """
    通用的命令执行函数

    参数:
        command: 命令字符串或参数列表
        interactive: 是否强制交互模式 (None=自动检测)
        shell: 是否使用shell执行
        check: 是否检查返回码
        **kwargs: 传递给subprocess的其他参数

    返回:
        subprocess.CompletedProcess 对象
    """
    # 自动检测是否需要交互模式
    if interactive is None:
        interactive = _is_interactive_command(command)

    if interactive:
        # 交互式命令 - 直接连接到当前终端
        return run_interactive_command(command)
    else:
        # 非交互式命令 - 捕获输出
        try:
            return run_command_interactive(command)
        except subprocess.TimeoutExpired:
            print("命令执行超时")
        except KeyboardInterrupt:
            print("命令被用户终止")
            return -1,"",None
        except subprocess.CalledProcessError as e:
            print(f"命令执行失败: {e}")

def _is_interactive_command(command: Union[str, List[str]]) -> bool:
    """检测命令是否需要交互式终端"""
    if isinstance(command, str):
        cmd = command.lower()
    else:
        cmd = command[0].lower()

    # 常见的交互式命令
    interactive_commands = {
        'vim', 'vi', 'nano', 'emacs',  # 文本编辑器
        'top', 'htop', 'btm',  # 系统监控
        'less', 'more', 'man',  # 分页查看器
        'ipython', 'python', 'python3',  # REPL
        'bash', 'zsh', 'fish', 'sh',  # Shell
        'ssh', 'telnet', 'ftp',  # 网络工具
        'mysql', 'psql', 'sqlite3',  # 数据库客户端
    }

    return cmd in interactive_commands


import pty
import select

from collections import deque


def run_interactive_command(command):
    """运行交互式命令并返回 exit_code, stdout, stderr"""
    master, slave = pty.openpty()

    # 用于存储 stdout 和 stderr
    stdout_queue = deque()
    stderr_queue = deque()

    process = subprocess.Popen(
        command,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
    )

    os.close(slave)  # 子进程持有 slave，主进程不再需要

    try:
        while True:
            rlist, _, _ = select.select([master, sys.stdin], [], [])

            if master in rlist:
                # 从伪终端读取数据（可能是 stdout 或 stderr）
                data = os.read(master, 1024).decode("utf-8", errors="replace")
                if not data:  # EOF（进程结束）
                    break

                # 由于 pty 合并了 stdout/stderr，我们无法直接区分它们
                # 这里统一当作 stdout 处理（Linux pty 默认合并输出）
                stdout_queue.append(data)
                print(data, end="", flush=True)  # 实时打印到终端

            if sys.stdin in rlist:
                # 用户输入 → 发送给子进程
                user_input = os.read(sys.stdin.fileno(), 1024)
                if b"\x1b" in user_input:
                    print("\n[Detected ESC key, exiting Insert mode]")

                os.write(master, user_input)
                if b":wq" in user_input:
                    break

    finally:
        os.close(master)
        returncode = process.wait()  # 获取 exit code

    # 合并所有输出（pty 无法区分 stdout/stderr）
    stdout = "".join(stdout_queue)
    stderr = None  # pty 模式下 stderr 通常为空（合并到 stdout）


    return returncode, stdout, stderr

from typing import Union, List, Tuple




from typing import Union, List, Optional, Tuple

import subprocess
import signal
import sys
import os
import time
from typing import Union, List, Tuple


# def run_command_interactive(
#         command: Union[str, List[str]],
#         shell: bool = False,
#         timeout: Optional[float] = None,
#         check: bool = False,
# ) -> Tuple[int, str, str]:
#     """
#     执行命令并支持 Ctrl+Z 真正终止（macOS/Linux/Windows）
#
#     参数:
#         command: 命令（字符串或列表）
#         shell: 是否使用shell执行
#         timeout: 超时时间（秒）
#         check: 返回码非零时是否抛出异常
#
#     返回:
#         (returncode, stdout, stderr)
#
#     示例:
#         returncode, stdout, stderr = run_command_interactive("ping 127.0.0.1")
#     """
#     # 存储输出
#     stdout_lines = []
#     stderr_lines = []
#     process = None
#
#     def signal_handler(signum, frame):
#         """处理终止信号"""
#         nonlocal process
#         if process is not None:
#             print(f"\n[接收到信号 {signum}，终止进程...]", file=sys.stderr)
#             process.terminate()  # 发送SIGTERM
#             time.sleep(0.5)
#             if process.poll() is None:  # 如果进程还在运行
#                 process.kill()  # 强制结束
#         raise KeyboardInterrupt("Command terminated by user")
#
#     # 设置信号处理（跨平台）
#     original_handlers = {}
#     signals = [signal.SIGINT, signal.SIGTERM]
#     if sys.platform != 'win32':
#         signals.append(signal.SIGTSTP)  # 添加Ctrl+Z处理（Unix）
#
#     for sig in signals:
#         original_handlers[sig] = signal.signal(sig, signal_handler)
#
#     try:
#         process = subprocess.Popen(
#             command,
#             shell=shell,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#             bufsize=1,
#             universal_newlines=True,
#         )
#
#         start_time = time.time()
#
#         # 实时处理输出
#         while True:
#             # 检查超时
#             if timeout is not None and (time.time() - start_time) > timeout:
#                 process.kill()
#                 raise subprocess.TimeoutExpired(command, timeout)
#
#             # 非阻塞读取
#             ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
#
#             for stream in ready:
#                 line = stream.readline()
#                 if not line and process.poll() is not None:
#                     break
#
#                 if stream == process.stdout:
#                     print(line, end='', flush=True)
#                     stdout_lines.append(line)
#                 else:
#                     print(line, end='', file=sys.stderr, flush=True)
#                     stderr_lines.append(line)
#
#             if process.poll() is not None:
#                 break
#
#         # 获取剩余输出
#         remaining_stdout, remaining_stderr = process.communicate()
#         if remaining_stdout:
#             print(remaining_stdout, end='', flush=True)
#             stdout_lines.append(remaining_stdout)
#         if remaining_stderr:
#             print(remaining_stderr, end='', file=sys.stderr, flush=True)
#             stderr_lines.append(remaining_stderr)
#
#         returncode = process.returncode
#
#         if check and returncode != 0:
#             raise subprocess.CalledProcessError(
#                 returncode, command, ''.join(stdout_lines), ''.join(stderr_lines)
#             )
#
#         return returncode, ''.join(stdout_lines), ''.join(stderr_lines)
#
#     finally:
#         # 恢复原始信号处理
#         for sig, handler in original_handlers.items():
#             if handler is not None:
#                 signal.signal(sig, handler)
#         # 确保进程终止
#         if process and process.poll() is None:
#             process.kill()


import subprocess
import signal
import sys
import os
import time
import select
from typing import Union, List, Tuple, Optional

import subprocess
import signal
import sys
import os
import time
import select
from typing import Union, List, Tuple, Optional


def run_command_interactive(
        command: Union[str, List[str]],
        shell: bool = False,
        timeout: Optional[float] = None,
        check: bool = False,
) -> Tuple[int, str, str]:
    """
    终极解决方案 - 同时解决ping卡住和ls输出不完整问题

    参数:
        command: 命令（字符串或列表）
        shell: 是否使用shell执行
        timeout: 超时时间（秒）
        check: 返回码非零时是否抛出异常

    返回:
        (returncode, stdout, stderr)
    """

    # 预处理ping命令（关键改进）
    if isinstance(command, (list, str)) and "ping" in (command[0] if isinstance(command, list) else command):
        command = _adapt_ping_command(command)

    # 存储输出
    stdout_data = []
    stderr_data = []
    process = None

    def signal_handler(signum, frame):
        """增强的信号处理"""
        nonlocal process
        if process and process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM) if sys.platform != 'win32' else process.terminate()
            time.sleep(0.2)
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL) if sys.platform != 'win32' else process.kill()
        raise KeyboardInterrupt

    # 信号处理设置
    original_handlers = {}
    for sig in [signal.SIGINT, signal.SIGTERM] + ([signal.SIGTSTP] if sys.platform != 'win32' else []):
        original_handlers[sig] = signal.signal(sig, signal_handler)

    try:
        # 启动进程（关键参数设置）
        process = subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,  # 无缓冲
            universal_newlines=True,
            preexec_fn=os.setsid if sys.platform != 'win32' else None,
        )

        start_time = time.time()

        def read_available(stream, buffer, is_stdout=True):
            """可靠的非阻塞读取"""
            while True:
                chunk = stream.read(4096 if is_stdout else 1024)
                if not chunk:
                    break
                print(chunk, end='', flush=True, file=sys.stdout if is_stdout else sys.stderr)
                buffer.append(chunk)
            return bool(buffer and buffer[-1])

        # 主循环（双重超时检查）
        while True:
            # 优先检查进程状态
            if process.poll() is not None:
                break

            # 严格超时控制
            if timeout and (time.time() - start_time) > timeout:
                raise subprocess.TimeoutExpired(command, timeout)

            # 非阻塞IO处理
            readable = []
            if process.stdout:
                readable.append(process.stdout)
            if process.stderr:
                readable.append(process.stderr)

            if readable:
                ready, _, _ = select.select(readable, [], [], 0.1)
                activity = False

                for stream in ready:
                    if stream == process.stdout:
                        activity = read_available(stream, stdout_data) or activity
                    else:
                        activity = read_available(stream, stderr_data, False) or activity

                # 无活动且进程已结束则退出
                if not activity and process.poll() is not None:
                    break
            else:
                time.sleep(0.1)

        # 最终清理（关键保障）
        remaining_stdout, remaining_stderr = process.communicate(timeout=0.5)
        if remaining_stdout:
            print(remaining_stdout, end='', flush=True)
            stdout_data.append(remaining_stdout)
        if remaining_stderr:
            print(remaining_stderr, end='', file=sys.stderr, flush=True)
            stderr_data.append(remaining_stderr)

        returncode = process.returncode

        if check and returncode != 0:
            raise subprocess.CalledProcessError(
                returncode, command, ''.join(stdout_data), ''.join(stderr_data)
            )

        return returncode, ''.join(stdout_data), ''.join(stderr_data)

    except subprocess.TimeoutExpired:
        if 'process' in locals() and process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL) if sys.platform != 'win32' else process.kill()
        raise
    finally:
        # 恢复信号处理
        for sig, handler in original_handlers.items():
            signal.signal(sig, handler)


def _adapt_ping_command(command: Union[str, List[str]]) -> Union[str, List[str]]:
    """智能适配ping命令参数"""
    is_list = isinstance(command, list)
    cmd_list = command if is_list else command.split()

    # 确保有计数参数
    count_flag = '-n' if sys.platform == 'win32' else '-c'
    if count_flag not in cmd_list:
        cmd_list.insert(1, count_flag)
        cmd_list.insert(2, '4')  # 默认4次

    return cmd_list if is_list else ' '.join(cmd_list)

