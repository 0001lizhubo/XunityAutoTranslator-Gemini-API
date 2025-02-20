import os
import re
import json
import time
from flask import Flask, request
from gevent.pywsgi import WSGIServer
from urllib.parse import unquote
from threading import Thread
from queue import Queue
import concurrent.futures
from google import genai  # 导入 Google GenAI 库

# 启用虚拟终端序列，支持 ANSI 转义代码，允许在终端显示彩色文本
os.system('')

# dict_path='用户替换字典.json' # 替换字典路径。如果不需要使用替换字典，请将此变量留空（设为 None 或空字符串 ""）
dict_path=None # 替换字典路径。如果不需要使用替换字典，请将此变量留空（设为 None 或空字符串 ""）
# API 配置参数
Model_Type =  "gemini-2.0-flash-001"    # 使用的模型类型，选择 GenAI 支持的模型，例如 "gemini-2.0-flash"

# 创建 Google GenAI 客户端实例
# 使用 genai.Client 进行客户端初始化，并配置 API 密钥
# 注意：请将 "YOUR_API_KEY" 替换为您自己的 Google GenAI API 密钥
client = genai.Client(api_key="YOUR_API_KEY") # 使用 genai.Client 初始化客户端，并配置 API 密钥  **请替换为您的 API 密钥**

# 译文重复内容检测参数
repeat_count=5 # 重复内容阈值。如果译文中有任意单字或单词连续重复出现次数大于等于 repeat_count，则认为译文质量不佳，会触发重试翻译逻辑

# 提示词 (Prompt) 配置
prompt= '''
你是资深本地化专家，负责将游戏日文文本译为简体中文。
**你的任务是精确翻译日文文本，仅输出译文，请勿添加任何与原文无关的解释、说明、补充信息或其他任何文字。** 接收文本后，请严格按照以下要求翻译：
翻译范围：翻译普通日文文本，保留原文叙述风格。
保留格式：保留转义字符、格式标签等非日文文本内容。
翻译原则：忠实准确，确保语义无误；对露骨性描写，可直白粗俗表述，不删减篡改；对双关语等特殊表达，找目标语言等效表达，保原作意图风格。
文本类型：游戏文本含角色对话、旁白、武器及物品名称、技能描述、格式标签、特殊符号等。
以下是待翻译的游戏文本：''' # 基础提示词，用于指导模型进行翻译，定义了翻译的角色、范围、格式、原则和文本类型
prompt_list=[prompt] # 提示词列表。可以配置多个提示词，程序会依次尝试使用列表中的提示词进行翻译，直到获得满意的结果
# l=len(prompt_list) # 获取提示词列表的长度 (此变量目前未被直接使用，移除)

# 提示字典相关的提示词配置
dprompt0='\n在翻译中使用以下字典,字典的格式为{\'原文\':\'译文\'}\n' # 提示模型在翻译时使用提供的字典。字典格式为 JSON 格式的字符串，键为原文，值为译文
dprompt1='\nDuring the translation, use a dictionary in {\'Japanese text \':\'translated text \'} format\n' # 英文版的字典提示词，可能用于多语言支持或模型偏好
# dprompt_list 字典提示词列表，与 prompt_list 提示词列表一一对应。当使用 prompt_list 中的第 i 个提示词时，会同时使用 dprompt_list 中的第 i 个字典提示词
dprompt_list=[dprompt0,dprompt1,dprompt1]
MAX_WORKERS = 2 # 线程池最大工作线程数 (直接在代码中定义)

app = Flask(__name__) # 创建 Flask 应用实例

# 读取提示字典
prompt_dict= {} # 初始化提示字典为空字典
if dict_path: # 检查是否配置了字典路径
    try:
        with open(dict_path, 'r', encoding='utf8') as f: # 尝试打开字典文件
            tempdict = json.load(f) # 加载 JSON 字典数据
            # 按照字典 key 的长度从长到短排序，确保优先匹配长 key，避免短 key 干扰长 key 的匹配
            sortedkey = sorted(tempdict.keys(), key=lambda x: len(x), reverse=True)
            for i in sortedkey:
                prompt_dict[i] = tempdict[i] # 将排序后的字典数据存入 prompt_dict
        print(f"\033[32m字典文件 {dict_path} 加载成功，共加载 {len(prompt_dict)} 个词条。\033[0m") # 打印字典加载成功的消息
    except FileNotFoundError:
        print(f"\033[33m警告：字典文件 {dict_path} 未找到。\033[0m") # 警告用户字典文件未找到
    except json.JSONDecodeError:
        print(f"\033[31m错误：字典文件 {dict_path} JSON 格式错误，请检查字典文件。\033[0m") # 错误提示 JSON 格式错误
    except Exception as e:
        print(f"\033[31m读取字典文件时发生未知错误: {e}\033[0m") # 捕获其他可能的文件读取或 JSON 解析错误

def contains_japanese(text):
    """
    检测文本中是否包含日文字符。
    """
    pattern = re.compile(r'[\u3040-\u3096\u309D-\u309F\u30A1-\u30FA\u30FC-\u30FE]') # 日文字符的 Unicode 范围正则表达式
    return pattern.search(text) is not None # 使用正则表达式搜索文本中是否包含日文字符


def has_repeated_sequence(string, count):
    """
    检测字符串中是否存在连续重复的字符或子串。
    """
    # 检查单个字符的重复
    for char in set(string):
        if string.count(char) >= count:
            return True

    # 检查字符串片段（子串）的重复
    for size in range(2, len(string) // count + 1):
        for start in range(0, len(string) - size + 1):
            substring = string[start:start + size]
            matches = re.findall(re.escape(substring), string)
            if len(matches) >= count:
                return True

    return False


# 获得文本中包含的字典词汇 (优化后)
def get_dict(text, dictionary):
    """
    从文本中提取出在提示字典 (dictionary) 中存在的词汇及其翻译 (优化版本，不修改原文).

    Args:
        text (str): 待处理的文本.
        dictionary (dict): 提示字典.

    Returns:
        dict:  一个字典，key 为在文本中找到的字典原文，value 为对应的译文.
               如果文本中没有找到任何字典词汇，则返回空字典.
    """
    res = {}
    for key in dictionary:
        if key in text:
            res[key] = dictionary[key]
    return res


request_queue = Queue()  # 创建请求队列
def handle_translation(text, translation_queue):
    """
    处理翻译请求的核心函数.
    """
    text = unquote(text) # URL 解码

    max_retries = 3  # 最大 API 请求重试次数
    retries = 0  # 重试计数器

    special_chars = ['，', '。', '？','...'] # 句末特殊字符
    text_end_special_char = None
    if text and text[-1] in special_chars: # 避免空字符串索引错误
        text_end_special_char = text[-1]

    special_char_start = "「"
    special_char_end = "」"
    has_special_start = text.startswith(special_char_start)
    has_special_end = text.endswith(special_char_end)

    if has_special_start and has_special_end:
        text = text[len(special_char_start):-len(special_char_end)]

    try: # 捕获 API 异常
        dict_inuse = get_dict(text, prompt_dict) # 获取字典词汇 (优化: 仅调用一次)
        for i in range(len(prompt_list)): # 遍历提示词列表
            prompt = prompt_list[i]
            if dict_inuse: # 如果有字典词汇，则添加字典提示
                prompt += dprompt_list[i] + str(dict_inuse)

            content_to_translate = prompt + text # 构建完整的翻译内容

            response_test = client.models.generate_content( # API 调用
                model=Model_Type, contents=content_to_translate
            )
            translations = response_test.text
            print(f"【API 原始输出 (未经处理):】\n{repr(translations)}")  # 打印原始值
            if translations.endswith("\n"): # 移除尾部换行符
                translations = translations[:-1]

            print(f"【API 翻译结果 (经处理):】\n{repr(translations)}") # 打印处理后的值，用于调试或日志记录
            # print(f'{prompt}\n{translations}')  # 打印提示词和翻译结果, 调试用


            if has_special_start and has_special_end: # 特殊字符处理
                if not translations.startswith(special_char_start):
                    translations = special_char_start + translations
                if not translations.endswith(special_char_end):
                    translations = translations + special_char_end

            translation_end_special_char = None
            if translations and translations[-1] in special_chars: # 避免空字符串索引错误
                translation_end_special_char = translations[-1]

            if text_end_special_char and translation_end_special_char:
                if text_end_special_char != translation_end_special_char:
                    translations = translations[:-1] + text_end_special_char
            elif text_end_special_char and not translation_end_special_char:
                translations += text_end_special_char
            elif not text_end_special_char and translation_end_special_char:
                translations = translations[:-1]

            contains_japanese_characters = contains_japanese(translations) # 检测日文
            repeat_check = has_repeated_sequence(translations, repeat_count) # 重复检测

            if not contains_japanese_characters and not repeat_check: # 质量检测通过则跳出循环
                break
            elif contains_japanese_characters:
                print("\033[31m检测到译文中包含日文字符，尝试使用下一个提示词进行翻译。\033[0m")
                continue
            elif repeat_check:
                print("\033[31m检测到译文中存在重复短语。\033[0m")
                # 可以在此处添加更复杂的重试策略，例如更换提示词组合，调整模型参数等 (当前版本暂未实现)
                break

        if not contains_japanese_characters and not repeat_check: # 最终质量检测
            pass # 翻译成功
        print(f"\033[36m[译文]\033[0m:\033[31m {translations}\033[0m")
        print("-------------------------------------------------------------------------------------------------------")
        translation_queue.put(translations) # 放入结果队列

    except Exception as e: # API 异常处理
        retries += 1
        print(f"\033[31mAPI请求超时或发生错误 (第 {retries} 次重试): {e}\033[0m") # 打印错误信息
        if retries == max_retries:
            print(f"\033[31m达到最大重试次数，翻译失败。\033[0m")
            translation_queue.put(False) # 放入失败标志
            return # 达到最大重试次数，返回
        time.sleep(1) # 等待重试
        handle_translation(text, translation_queue) # 递归重试
        return # 重试后返回


@app.route('/translate', methods=['GET'])
def translate():
    """
    Flask 路由函数，处理 "/translate" GET 请求.
    """
    text = request.args.get('text')  # 获取待翻译文本
    print(f"\033[36m[原文]\033[0m \033[35m{text}\033[0m") # 打印原文

    translation_queue = Queue() # 创建结果队列

    request_queue.put_nowait(text) # 放入请求队列

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor: # 使用配置的线程池大小 (直接使用硬编码值)
        future = executor.submit(handle_translation, text, translation_queue) # 提交翻译任务

        try: # 超时处理
            translation_result = future.result(timeout=30) # 获取结果，设置超时时间
        except concurrent.futures.TimeoutError:
            print("\033[31m翻译请求超时。\033[0m") # 打印超时信息
            return "[请求超时] " + text, 500 # 返回超时错误

    translation = translation_queue.get() # 获取翻译结果
    request_queue.get_nowait() # 从请求队列移除已处理请求

    if isinstance(translation, str): # 翻译成功
        return translation # 返回翻译结果
    else: # 翻译失败
        return "[翻译失败] " , 500 # 返回失败状态码


def main():
    """
    主函数，启动 Flask 应用和 gevent 服务器.
    """
    print("\033[31m服务器在 http://127.0.0.1:4000 上启动\033[0m") # 启动信息
    http_server = WSGIServer(('127.0.0.1', 4000), app, log=None, error_log=None) # 创建 gevent WSGIServer 实例
    http_server.serve_forever() # 启动服务器

if __name__ == '__main__':
    main() # 运行主函数
