# XunityAutoTranslator-Gemini-API
本项目是一个使用 Flask 框架和 Google Gemini GenAI 模型构建的 Web API 服务，用于将日文游戏文本翻译成简体中文。

## 日文游戏文本AI翻译API (基于Google Gemini)

本项目是一个使用 Flask 框架和 Google Gemini GenAI 模型构建的 Web API 服务，用于将日文游戏文本翻译成简体中文。

## 功能特点

*   **AI 驱动翻译:**  使用 Google Gemini GenAI 模型 `gemini-2.0-flash-001` 进行高质量的日文到简体中文翻译。
*   **游戏文本优化:**  针对游戏文本特点进行了优化，例如保留格式标签、处理特殊符号、保留原文风格等。
*   **质量检测与重试:**  自动检测译文质量，当检测到译文包含日文或重复内容时，会自动重试翻译。
*   **高并发处理:**  使用 Flask 框架和 gevent WSGI 服务器，支持高并发请求处理。
*   **异步请求处理:**  使用队列和线程池异步处理翻译请求，避免阻塞主线程，提高服务器响应速度。
*   **简单易用:**  提供简洁的 HTTP GET API 接口 `/translate`，方便集成到各种游戏或工具中。

## 快速开始

### 1. 前置条件

*   **Python 3.9+**
*   **已安装必要的 Python 库** (见 [依赖](#2-依赖库))
*   **Google Gemini API 密钥**

### 2. 依赖库

请确保已安装以下 Python 库：
```
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

```

## 配置说明

### API 配置
```python
Model_Type = "gemini-2.0-flash-001" # 使用的模型类型, 请根据Google的文档自行修改
client = genai.Client(api_key="YOUR_API_KEY") # 替换为你的 API 密钥
```

### 3. 配置 API 密钥
请修改代码，打开 脚本文件名.py 文件，找到以下代码行： 
> client = genai.Client(api_key="YOUR_API_KEY") # 使用 genai.Client 初始化客户端，并配置 API 密钥  **请替换为您的 API 密钥**
>

将 "YOUR_API_KEY" 替换为您自己的 Google Gemini API 密钥。 注意：请务必替换为您自己的 API 密钥，否则API将无法正常工作。


### 4. 运行 API 服务 在代码所在目录下，打开终端并执行以下命令： 
```Bash
   python 脚本文件名.py
```


### 代码配置 
以下参数在代码中直接定义，您可以根据需要修改代码进行调整： 
- Model_Type: 使用的 Google Gemini GenAI 模型类型，默认为 "gemini-2.0-flash-001"。您可以根据 Google GenAI API 的支持情况选择其他模型。 
- repeat_count: 重复内容检测阈值，默认为 5。用于检测译文中是否存在重复内容，数值越大，对重复内容检测的容忍度越高。 
- prompt: 基础提示词 (Prompt)，用于指导 AI 模型进行翻译。您可以根据需要修改提示词，以优化翻译效果。 
- prompt_list: 提示词列表，默认为包含单个基础提示词的列表。您可以配置多个提示词，程序会在翻译失败时自动尝试使用列表中的下一个提示词进行重试翻译。 
- MAX_WORKERS: 线程池最大工作线程数，默认为 2。您可以根据服务器性能和并发需求调整线程池大小。

### 配置XUnity.AutoTranslator
参考上一个项目：[项目地址](https://github.com/0001lizhubo/XUnity.AutoTranslator-deepseek/tree/main)
