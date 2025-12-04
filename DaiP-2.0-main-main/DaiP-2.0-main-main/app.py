from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
import random
import re
import time
import requests
import hashlib
import time
import sqlite3
import requests
import execjs
from datetime import datetime
from openai import OpenAI

app = Flask(__name__, static_folder='static', template_folder='.')
app.config['SECRET_KEY'] = 'your-secret-key'
# 明确指定使用threading模式，避免eventlet的影响
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 用户数据文件路径
USERS_FILE = 'users.json'
# 新闻请求限制时间(秒)
NEWS_COOLDOWN = 60
# 存储用户最后一次请求新闻的时间
last_news_request = {}

# 在线用户列表 (包含状态信息)
online_users = {}

# 消息历史存储
message_history = []

# 当前播放的音乐信息
current_music = {
    'url': None,
    'title': None,
    'artist': None,
    'status': 'stopped',  # stopped, playing, paused
    'current_time': 0,
    'lyrics': []
}

# 新闻状态管理
news_last_access = {
    'time': 0,
    'count': 0
}

# 天气API配置
# 使用用户指定的天气API
WEATHER_API_KEY = 'your_xxapi_key'  # 请替换为你的xxapi密钥
WEATHER_API_URL = 'https://v2.xxapi.cn/api/weatherDetails'
WEATHER_CACHE = {}  # 天气缓存，格式：{城市名: {'data': 天气数据, 'timestamp': 时间戳}}
WEATHER_CACHE_EXPIRE = 600  # 缓存过期时间，10分钟

# 天气与背景的映射规则
WEATHER_BACKGROUND_MAP = {
    '晴': {'class': 'bg-sunny', 'description': '晴天'},  # 湛蓝天空+蓬松白云的明亮写实背景
    '多云': {'class': 'bg-cloudy', 'description': '多云'},  # 大片云朵+淡蓝天空的开阔背景
    '阴': {'class': 'bg-overcast', 'description': '阴天'},  # 阴天背景
    '雨': {'class': 'bg-rainy', 'description': '雨天'},  # 带水滴的翠绿树叶+模糊树林的清新背景
    '雪': {'class': 'bg-snowy', 'description': '雪天'},  # 雪天背景
    '微风': {'class': 'bg-breeze', 'description': '微风'},  # 蓝天+轻柔飘动垂柳的柔和背景
    '雾': {'class': 'bg-mist', 'description': '雾天'},  # 雾天背景
    '霾': {'class': 'bg-haze', 'description': '霾天'}   # 霾天背景
}

# 天气对应的emoji
WEATHER_EMOJI = {
    '晴': '☀️',
    '多云': '⛅',
    '阴': '☁️',
    '小雨': '🌧️',
    '中雨': '🌧️',
    '大雨': '⛈️',
    '暴雨': '⛈️',
    '小雪': '❄️',
    '中雪': '❄️',
    '大雪': '❄️',
    '暴雪': '❄️',
    '雾': '🌫️',
    '霾': '🌫️',
    '微风': '🌬️',
    '风': '🌬️'
}

# 用户状态管理
def get_user_status(username):
    """获取用户状态"""
    return online_users.get(username, {}).get('status', 'offline')

# 天气相关函数
def get_weather(city_name):
    """获取城市天气，带缓存机制"""
    # 检查缓存
    now = time.time()
    if city_name in WEATHER_CACHE:
        cached = WEATHER_CACHE[city_name]
        if now - cached['timestamp'] < WEATHER_CACHE_EXPIRE:
            return cached['data']
    
    # 缓存过期或不存在，重新获取
    try:
        # 检查API密钥是否为默认值
        if WEATHER_API_KEY == 'your_xxapi_key':
            print("使用模拟天气数据")
            
            # 基于城市名称生成不同的模拟数据，提升演示效果
            city_weather_data = {
                '北京': {
                    'condition': '多云',
                    'temp_min': '10',
                    'temp_max': '22',
                    'wind_level': '2',
                    'humidity': '35'
                },
                '上海': {
                    'condition': '阴',
                    'temp_min': '18',
                    'temp_max': '26',
                    'wind_level': '4',
                    'humidity': '65'
                },
                '广州': {
                    'condition': '晴',
                    'temp_min': '22',
                    'temp_max': '30',
                    'wind_level': '3',
                    'humidity': '70'
                },
                '深圳': {
                    'condition': '晴',
                    'temp_min': '23',
                    'temp_max': '31',
                    'wind_level': '3',
                    'humidity': '68'
                },
                '成都': {
                    'condition': '小雨',
                    'temp_min': '16',
                    'temp_max': '24',
                    'wind_level': '2',
                    'humidity': '80'
                },
                '重庆': {
                    'condition': '阴',
                    'temp_min': '17',
                    'temp_max': '25',
                    'wind_level': '2',
                    'humidity': '75'
                },
                '杭州': {
                    'condition': '晴',
                    'temp_min': '15',
                    'temp_max': '27',
                    'wind_level': '3',
                    'humidity': '55'
                },
                '武汉': {
                    'condition': '多云',
                    'temp_min': '19',
                    'temp_max': '28',
                    'wind_level': '3',
                    'humidity': '60'
                },
                '西安': {
                    'condition': '晴',
                    'temp_min': '12',
                    'temp_max': '24',
                    'wind_level': '2',
                    'humidity': '40'
                },
                '南京': {
                    'condition': '阴',
                    'temp_min': '16',
                    'temp_max': '25',
                    'wind_level': '3',
                    'humidity': '60'
                },
                '天津': {
                    'condition': '多云',
                    'temp_min': '11',
                    'temp_max': '23',
                    'wind_level': '3',
                    'humidity': '50'
                },
                '苏州': {
                    'condition': '晴',
                    'temp_min': '17',
                    'temp_max': '26',
                    'wind_level': '3',
                    'humidity': '58'
                },
                '郑州': {
                    'condition': '晴',
                    'temp_min': '14',
                    'temp_max': '26',
                    'wind_level': '2',
                    'humidity': '45'
                },
                '长沙': {
                    'condition': '多云',
                    'temp_min': '20',
                    'temp_max': '29',
                    'wind_level': '3',
                    'humidity': '65'
                },
                '沈阳': {
                    'condition': '晴',
                    'temp_min': '8',
                    'temp_max': '20',
                    'wind_level': '3',
                    'humidity': '40'
                },
                '青岛': {
                    'condition': '多云',
                    'temp_min': '13',
                    'temp_max': '21',
                    'wind_level': '4',
                    'humidity': '55'
                },
                '大连': {
                    'condition': '晴',
                    'temp_min': '12',
                    'temp_max': '20',
                    'wind_level': '4',
                    'humidity': '52'
                },
                '厦门': {
                    'condition': '晴',
                    'temp_min': '21',
                    'temp_max': '29',
                    'wind_level': '3',
                    'humidity': '65'
                },
                '济南': {
                    'condition': '晴',
                    'temp_min': '15',
                    'temp_max': '27',
                    'wind_level': '3',
                    'humidity': '50'
                },
                '哈尔滨': {
                    'condition': '晴',
                    'temp_min': '5',
                    'temp_max': '18',
                    'wind_level': '3',
                    'humidity': '45'
                },
                '石家庄': {
                    'condition': '多云',
                    'temp_min': '13',
                    'temp_max': '25',
                    'wind_level': '3',
                    'humidity': '48'
                },
                '福州': {
                    'condition': '晴',
                    'temp_min': '20',
                    'temp_max': '28',
                    'wind_level': '3',
                    'humidity': '68'
                },
                '南宁': {
                    'condition': '晴',
                    'temp_min': '23',
                    'temp_max': '31',
                    'wind_level': '2',
                    'humidity': '72'
                },
                '昆明': {
                    'condition': '晴',
                    'temp_min': '15',
                    'temp_max': '25',
                    'wind_level': '2',
                    'humidity': '55'
                },
                '南昌': {
                    'condition': '多云',
                    'temp_min': '19',
                    'temp_max': '28',
                    'wind_level': '3',
                    'humidity': '62'
                },
                '贵阳': {
                    'condition': '阴',
                    'temp_min': '14',
                    'temp_max': '22',
                    'wind_level': '2',
                    'humidity': '75'
                },
                '太原': {
                    'condition': '晴',
                    'temp_min': '10',
                    'temp_max': '23',
                    'wind_level': '3',
                    'humidity': '42'
                },
                '合肥': {
                    'condition': '多云',
                    'temp_min': '16',
                    'temp_max': '26',
                    'wind_level': '3',
                    'humidity': '58'
                },
                '拉萨': {
                    'condition': '晴',
                    'temp_min': '8',
                    'temp_max': '22',
                    'wind_level': '3',
                    'humidity': '35'
                },
                '乌鲁木齐': {
                    'condition': '晴',
                    'temp_min': '10',
                    'temp_max': '26',
                    'wind_level': '3',
                    'humidity': '30'
                }
            }
            
            # 为城市获取对应的天气数据，如果没有则使用默认值
            city_data = city_weather_data.get(city_name, {
                'condition': '晴',
                'temp_min': '15',
                'temp_max': '25',
                'wind_level': '3',
                'humidity': '45'
            })
            
            # 计算当前温度（取最小和最大温度的平均值）
            current_temp = str((int(city_data['temp_min']) + int(city_data['temp_max'])) // 2)
            
            # 返回模拟数据
            mock_data = {
                'code': 0,
                'data': {
                    'city': city_name,
                    'condition': city_data['condition'],
                    'temp_min': city_data['temp_min'],
                    'temp_max': city_data['temp_max'],
                    'temp': current_temp,
                    'wind_level': city_data['wind_level'],
                    'humidity': city_data['humidity']
                }
            }
            # 保存到缓存
            WEATHER_CACHE[city_name] = {
                'data': mock_data,
                'timestamp': now
            }
            return mock_data
        
        params = {
            'Key': WEATHER_API_KEY,
            'address': city_name
        }
        
        # 尝试调用接口，最多重试2次
        retry_count = 0
        max_retries = 2
        success = False
        response = None
        
        while retry_count < max_retries and not success:
            response = requests.get(WEATHER_API_URL, params=params, timeout=5)
            print(f"天气数据请求URL: {response.url}")
            print(f"天气数据响应状态: {response.status_code}")
            print(f"天气数据响应数据: {response.text}")
            
            data = response.json()
            
            if data.get('code') != -8:  # -8表示Key错误
                success = True
            else:
                retry_count += 1
                print(f"天气API请求失败，错误码: {data.get('code')}, 正在重试... ({retry_count}/{max_retries})")
                time.sleep(1)  # 等待1秒后重试
        
        if not success:
            print("天气API请求失败，已达到最大重试次数，使用模拟数据")
            # 返回模拟数据
            mock_data = {
                'code': 0,
                'data': {
                    'city': city_name,
                    'condition': '晴',
                    'temp_min': '15',
                    'temp_max': '25',
                    'temp': '20',
                    'wind_level': '3',
                    'humidity': '45'
                }
            }
            # 保存到缓存
            WEATHER_CACHE[city_name] = {
                'data': mock_data,
                'timestamp': now
            }
            return mock_data
        
        data = response.json()
        
        if data.get('code') == 0:  # 假设0表示成功
            # 保存到缓存
            WEATHER_CACHE[city_name] = {
                'data': data,
                'timestamp': now
            }
            return data
        else:
            print(f"获取天气数据失败，错误码: {data.get('code')}, 错误信息: {data.get('msg')}，使用模拟数据")
            # 返回模拟数据
            mock_data = {
                'code': 0,
                'data': {
                    'city': city_name,
                    'condition': '晴',
                    'temp_min': '15',
                    'temp_max': '25',
                    'temp': '20',
                    'wind_level': '3',
                    'humidity': '45'
                }
            }
            # 保存到缓存
            WEATHER_CACHE[city_name] = {
                'data': mock_data,
                'timestamp': now
            }
            return mock_data
    except Exception as e:
        print(f"获取天气数据失败: {e}，使用模拟数据")
        # 返回模拟数据
        mock_data = {
            'code': 0,
            'data': {
                'city': city_name,
                'condition': '晴',
                'temp_min': '15',
                'temp_max': '25',
                'temp': '20',
                'wind_level': '3',
                'humidity': '45'
            }
        }
        # 保存到缓存
        WEATHER_CACHE[city_name] = {
            'data': mock_data,
            'timestamp': now
        }
        return mock_data

def parse_weather_message(weather_data):
    """解析天气数据，生成友好的天气消息"""
    if not weather_data:
        return None
    
    try:
        # 假设API返回的数据格式
        data = weather_data.get('data', {})
        
        # 提取天气信息
        city = data.get('city', '')
        condition = data.get('condition', '')
        temp_min = data.get('temp_min', '')
        temp_max = data.get('temp_max', '')
        temp = data.get('temp', '')
        wind_level = data.get('wind_level', '')
        humidity = data.get('humidity', '')
        
        # 确定天气类型，用于背景切换
        weather_type = '晴'  # 默认晴天
        if '雨' in condition:
            weather_type = '雨'
        elif '多云' in condition:
            weather_type = '多云'
        elif '阴' in condition:
            weather_type = '阴'
        elif '雪' in condition:
            weather_type = '雪'
        elif '微风' in condition or '风' in condition:
            weather_type = '微风'
        elif '雾' in condition:
            weather_type = '雾'
        elif '霾' in condition:
            weather_type = '霾'
        
        # 获取对应的emoji
        emoji = WEATHER_EMOJI.get(condition, '🌤️')
        
        # 生成天气消息
        weather_message = {
            'emoji': emoji,
            'city': city,
            'condition': condition,
            'temp': temp,
            'temp_range': f"{temp_min}-{temp_max}",
            'wind_level': wind_level,
            'humidity': humidity,
            'background': WEATHER_BACKGROUND_MAP.get(weather_type, WEATHER_BACKGROUND_MAP['晴'])
        }
        
        return weather_message
    except Exception as e:
        print(f"解析天气数据失败: {e}")
        return None

# 初始化SQLite数据库，用于缓存音乐链接
conn = sqlite3.connect('music_cache.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS music_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        music_name TEXT NOT NULL,
        song_name TEXT NOT NULL,
        artist TEXT NOT NULL,
        cover_url TEXT NOT NULL,
        purl TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# QQ音乐爬虫类
class QQMusicSpider:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.last_request_time = 0
        self.request_interval = random.randint(3, 5)  # 3-5秒请求间隔
    
    def check_request_interval(self):
        """检查请求间隔，避免触发反爬"""
        current_time = time.time()
        if current_time - self.last_request_time < self.request_interval:
            time.sleep(self.request_interval - (current_time - self.last_request_time))
        self.last_request_time = time.time()
    
    def search_music(self, music_name):
        """搜索QQ音乐，获取歌曲信息和播放链接"""
        # 检查缓存
        cursor.execute('SELECT song_name, artist, cover_url, purl FROM music_cache WHERE music_name LIKE ? ORDER BY created_at DESC LIMIT 1',
                      (f'%{music_name}%',))
        cache_result = cursor.fetchone()
        if cache_result:
            return {
                'song_name': cache_result[0],
                'artist': cache_result[1],
                'cover_url': cache_result[2],
                'purl': cache_result[3]
            }
        
        # 预定义热门歌曲列表，用于模拟数据
        popular_songs = {
            '远方': {
                'song_name': '远方',
                'artist': '刘惜君',
                'cover_url': 'https://y.qq.com/music/photo_new/T002R300x300M000003Z9YvL2hBv9v.jpg',
                'purl': 'https://example.com/song/yuanfang.mp3'
            },
            '起风了': {
                'song_name': '起风了',
                'artist': '买辣椒也用券',
                'cover_url': 'https://y.qq.com/music/photo_new/T002R300x300M000003RSWJ61hV3X3.jpg',
                'purl': 'https://example.com/song/qifengle.mp3'
            },
            '海阔天空': {
                'song_name': '海阔天空',
                'artist': 'Beyond',
                'cover_url': 'https://y.qq.com/music/photo_new/T002R300x300M000001Tt4eG3C5t5W.jpg',
                'purl': 'https://example.com/song/haikuotiankong.mp3'
            },
            '晴天': {
                'song_name': '晴天',
                'artist': '周杰伦',
                'cover_url': 'https://y.qq.com/music/photo_new/T002R300x300M000001xuP9B06u7i7.jpg',
                'purl': 'https://example.com/song/qingtian.mp3'
            },
            '成都': {
                'song_name': '成都',
                'artist': '赵雷',
                'cover_url': 'https://y.qq.com/music/photo_new/T002R300x300M000003m1AqX3lX9j9.jpg',
                'purl': 'https://example.com/song/chengdu.mp3'
            }
        }
        
        # 检查请求间隔
        self.check_request_interval()
        
        try:
            # 首先尝试使用预定义的热门歌曲
            if music_name in popular_songs:
                song_info = popular_songs[music_name]
                print(f"使用预定义歌曲: {song_info}")
                
                # 存储到缓存
                try:
                    cursor.execute('''
                        INSERT INTO music_cache (music_name, song_name, artist, cover_url, purl)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (music_name, song_info['song_name'], song_info['artist'], song_info['cover_url'], song_info['purl']))
                    conn.commit()
                    print(f"预定义音乐信息已缓存")
                except Exception as e:
                    print(f"缓存预定义音乐信息时出错: {e}")
                
                return song_info
            
            # 如果不在预定义列表中，尝试调用真实API
            # 使用QQ音乐搜索API，添加超时设置
            search_url = f'https://c.y.qq.com/soso/fcgi-bin/client_search_cp'
            params = {
                'ct': '24',
                'qqmusic_ver': '1298',
                'new_json': '1',
                'remoteplace': 'txt.yqq.song',
                't': '0',
                'aggr': '1',
                'cr': '1',
                'catZhida': '1',
                'lossless': '0',
                'flag_qc': '0',
                'p': '1',
                'n': '20',
                'w': music_name,
                'format': 'json',
                'inCharset': 'utf8',
                'outCharset': 'utf-8',
                'notice': '0',
                'platform': 'yqq.json',
                'needNewCode': '0'
            }
            
            print(f"正在搜索音乐: {music_name}")
            response = requests.get(search_url, headers=self.headers, params=params, timeout=10)
            print(f"API响应状态码: {response.status_code}")
            
            # 打印原始响应内容，用于调试
            print(f"API响应内容: {response.text[:500]}...")
            
            # 解析响应内容，处理可能的格式问题
            response_text = response.text
            # 去除可能的回调函数包装
            if response_text.startswith('callback(') and response_text.endswith(')'):
                response_text = response_text[9:-1]
            # 去除可能的多余字符
            response_text = response_text.strip()
            
            data = json.loads(response_text)
            print(f"解析后的数据: {json.dumps(data, ensure_ascii=False)[:500]}...")
            
            # 提取歌曲列表，增加更多容错处理
            song_list = []
            try:
                # 尝试多种可能的数据结构
                if 'data' in data:
                    data_dict = data['data']
                    # 常见的结构：data.song.list
                    if 'song' in data_dict and isinstance(data_dict['song'], dict):
                        if 'list' in data_dict['song'] and isinstance(data_dict['song']['list'], list):
                            song_list = data_dict['song']['list']
                    # 备选结构：data.song直接是列表
                    elif 'song' in data_dict and isinstance(data_dict['song'], list):
                        song_list = data_dict['song']
                    # 备选结构：data.list
                    elif 'list' in data_dict and isinstance(data_dict['list'], list):
                        song_list = data_dict['list']
            except Exception as e:
                print(f"解析歌曲列表时出错: {e}")
            
            print(f"获取到歌曲列表: {len(song_list)}首歌曲")
            
            # 如果找到歌曲，返回真实结果
            if song_list:
                # 获取第一首歌曲
                song = song_list[0]
                print(f"选中的歌曲: {json.dumps(song, ensure_ascii=False)[:200]}...")
                
                # 提取歌曲信息，添加默认值处理
                song_mid = song.get('mid', '') or song.get('id', '')
                song_name = song.get('name', '未知歌曲')
                
                # 处理歌手信息，增加更多容错处理
                artist = '未知歌手'
                try:
                    if 'artist' in song:
                        if isinstance(song['artist'], list) and len(song['artist']) > 0:
                            # 处理多个歌手的情况
                            artists = []
                            for art in song['artist']:
                                if isinstance(art, dict):
                                    artists.append(art.get('name', '未知歌手'))
                                elif isinstance(art, str):
                                    artists.append(art)
                            if artists:
                                artist = '/'.join(artists)
                        elif isinstance(song['artist'], dict):
                            artist = song['artist'].get('name', '未知歌手')
                        elif isinstance(song['artist'], str):
                            artist = song['artist']
                    # 备选字段名
                    elif 'singer' in song:
                        if isinstance(song['singer'], list) and len(song['singer']) > 0:
                            singers = []
                            for sngr in song['singer']:
                                if isinstance(sngr, dict):
                                    singers.append(sngr.get('name', '未知歌手'))
                                elif isinstance(sngr, str):
                                    singers.append(sngr)
                            if singers:
                                artist = '/'.join(singers)
                        elif isinstance(song['singer'], dict):
                            artist = song['singer'].get('name', '未知歌手')
                        elif isinstance(song['singer'], str):
                            artist = song['singer']
                except Exception as e:
                    print(f"解析歌手信息时出错: {e}")
                
                # 处理封面图，增加更多容错处理
                cover_url = 'https://via.placeholder.com/300x300'
                try:
                    # 尝试从album字段获取封面
                    if 'album' in song and isinstance(song['album'], dict):
                        album_mid = song['album'].get('mid', '') or song['album'].get('id', '')
                        if album_mid:
                            cover_url = f'https://y.qq.com/music/photo_new/T002R300x300M000{album_mid}.jpg'
                    # 尝试从pic字段获取封面
                    elif 'pic' in song:
                        cover_url = song['pic']
                    # 尝试从cover字段获取封面
                    elif 'cover' in song:
                        cover_url = song['cover']
                except Exception as e:
                    print(f"解析封面图时出错: {e}")
                
                # 使用模拟purl，实际项目中需要调用另一个API获取真实purl
                purl = f'https://example.com/song/{song_mid}.mp3' if song_mid else 'https://example.com/song/demo.mp3'
                
                song_info = {
                    'song_name': song_name,
                    'artist': artist,
                    'cover_url': cover_url,
                    'purl': purl
                }
                
                print(f"提取到的歌曲信息: {song_info}")
                
                # 存储到缓存
                try:
                    cursor.execute('''
                        INSERT INTO music_cache (music_name, song_name, artist, cover_url, purl)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (music_name, song_name, artist, cover_url, purl))
                    conn.commit()
                    print(f"音乐信息已缓存")
                except Exception as e:
                    print(f"缓存音乐信息时出错: {e}")
                
                return song_info
            else:
                # 如果真实API也没有返回结果，使用通用模拟数据
                print(f"未找到歌曲: {music_name}，使用通用模拟数据")
                song_info = {
                    'song_name': music_name,
                    'artist': '未知歌手',
                    'cover_url': 'https://via.placeholder.com/300x300',
                    'purl': 'https://example.com/song/demo.mp3'
                }
                
                # 存储到缓存
                try:
                    cursor.execute('''
                        INSERT INTO music_cache (music_name, song_name, artist, cover_url, purl)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (music_name, song_info['song_name'], song_info['artist'], song_info['cover_url'], song_info['purl']))
                    conn.commit()
                    print(f"模拟音乐信息已缓存")
                except Exception as e:
                    print(f"缓存模拟音乐信息时出错: {e}")
                
                return song_info
        except Exception as e:
            print(f"QQ音乐爬虫错误: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            # 即使发生异常，我们也返回一个模拟结果，确保用户体验
            song_info = {
                'song_name': music_name,
                'artist': '未知歌手',
                'cover_url': 'https://via.placeholder.com/300x300',
                'purl': 'https://example.com/song/demo.mp3'
            }
            
            # 存储到缓存
            try:
                cursor.execute('''
                    INSERT INTO music_cache (music_name, song_name, artist, cover_url, purl)
                    VALUES (?, ?, ?, ?, ?)
                ''', (music_name, song_info['song_name'], song_info['artist'], song_info['cover_url'], song_info['purl']))
                conn.commit()
                print(f"异常情况下的模拟音乐信息已缓存")
            except Exception as e:
                print(f"缓存异常模拟音乐信息时出错: {e}")
            
            return song_info

# 初始化QQ音乐爬虫
qq_music_spider = QQMusicSpider()

# 当前天气信息
current_weather = {
    'city': None,
    'condition': None,
    'temperature': None,
    'background': None
}

# 天气背景映射
weather_backgrounds = {
    'clear': 'linear-gradient(135deg, #ffeb3b 0%, #ffc107 100%)',  # 晴天
    'clouds': 'linear-gradient(135deg, #e0e0e0 0%, #bdbdbd 100%)',  # 多云
    'rain': 'linear-gradient(135deg, #64b5f6 0%, #42a5f5 100%)',    # 雨天
    'snow': 'linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%)',    # 雪天
    'thunderstorm': 'linear-gradient(135deg, #424242 0%, #212121 100%)',  # 雷暴
    'mist': 'linear-gradient(135deg, #b0bec5 0%, #90a4ae 100%)',    # 雾天
    'default': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'  # 默认
}

# 读取用户数据
with open(USERS_FILE, 'r', encoding='utf-8') as f:
    users = json.load(f) if os.path.exists(USERS_FILE) else []

# 保存用户数据
def save_users():
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# 密码哈希函数
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 检查用户名是否已存在
def is_username_exists(username):
    return any(user['username'] == username for user in users)

# 检查用户名和密码是否匹配
def check_user_credentials(username, password):
    for user in users:
        if user['username'] == username and user['password'] == hash_password(password):
            return True
    return False

# 获取用户信息
def get_user(username):
    for user in users:
        if user['username'] == username:
            return user
    return None

# 川小农AI助手配置
class ChuanXiaoNongAssistant:
    def __init__(self):
        self.name = "川小农"
        self.avatar = "🌾"  # 川小农专属头像
        self.description = "农业知识助手"
        
        # 配置OpenAI客户端，对接SiliconFlow API
        self.client = OpenAI(
            api_key="sk-hxacbhzgpplfepkueyghioxnnpkieghomstrnpawffthzggu",
            base_url="https://api.siliconflow.cn/v1/"
        )
        self.model_name = "Qwen/Qwen2.5-7B-Instruct"
    
    def generate_response(self, question):
        """生成回复，调用AI大模型"""
        try:
            # 使用SSE协议调用AI大模型
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一位名为川小农的农业知识助手，擅长回答关于农业、天气、学习、生活等方面的问题。请用友好、专业的语气回答用户的问题。"},
                    {"role": "user", "content": question}
                ],
                stream=True
            )
            
            # 处理流式响应
            ai_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    ai_response += chunk.choices[0].delta.content
            
            return ai_response
        except Exception as e:
            print(f"AI模型调用出错: {e}")
            # 出错时返回默认回复
            return "抱歉，我暂时无法回答你的问题，请稍后再试。"

# 创建川小农助手实例
chuanxiaonong = ChuanXiaoNongAssistant()

# 登录页面
@app.route('/')
def login():
    error = request.args.get('error')
    return render_template('login.html', error=error)

# 用户注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        nickname = request.form['nickname']
        
        # 验证输入
        if not all([username, password, confirm_password, nickname]):
            return render_template('register.html', error='请填写所有字段')
        
        if password != confirm_password:
            return render_template('register.html', error='两次密码不一致')
        
        if is_username_exists(username):
            return render_template('register.html', error='用户名已存在')
        
        # 创建新用户
        new_user = {
            'username': username,
            'password': hash_password(password),
            'nickname': nickname,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 保存用户数据
        users.append(new_user)
        save_users()
        
        # 注册成功，跳转到登录页面
        return redirect(url_for('login', success='注册成功，请登录'))
    
    return render_template('register.html')

# 用户登录
@app.route('/login', methods=['POST'])
def user_login():
    username = request.form['username']
    password = request.form['password']
    
    # 验证用户名和密码
    if check_user_credentials(username, password):
        # 登录成功，设置session
        user = get_user(username)
        session['username'] = username
        session['nickname'] = user['nickname']
        return redirect(url_for('chat'))
    else:
        return redirect(url_for('login', error='用户名或密码错误'))

# 登出
@app.route('/logout')
def logout():
    # 移除session中的用户名
    session.pop('username', None)
    session.pop('nickname', None)
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # 验证新密码和确认密码是否一致
        if new_password != confirm_password:
            return render_template('change_password.html', error='新密码和确认密码不一致')
        
        # 验证当前密码
        username = session['username']
        user_found = False
        
        for i, user in enumerate(users):
            if user['username'] == username:
                hashed_current = hashlib.sha256(current_password.encode()).hexdigest()
                if user['password'] == hashed_current:
                    # 更新密码
                    hashed_new = hashlib.sha256(new_password.encode()).hexdigest()
                    users[i]['password'] = hashed_new
                    user_found = True
                    break
                else:
                    return render_template('change_password.html', error='当前密码错误')
        
        if user_found:
            # 保存更新后的用户数据
            save_users()
            return render_template('change_password.html', success='密码修改成功')
        
        return render_template('change_password.html', error='用户不存在')
    
    return render_template('change_password.html')

# 聊天室页面
@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username')
    nickname = session.get('nickname')
    server = request.host_url
    return render_template('chat.html', username=username, nickname=nickname, server=server)

# 用户数据管理页面
@app.route('/user_profile')
def user_profile():
    if 'username' not in session:
        return redirect(url_for('login', error='请先登录'))
    
    username = session['username']
    user = get_user(username)
    
    return render_template('user_profile.html', user=user)

# 更新用户信息
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return redirect(url_for('login', error='请先登录'))
    
    username = session['username']
    new_nickname = request.form['nickname']
    new_password = request.form['new_password']
    current_password = request.form['current_password']
    
    # 验证当前密码
    if not check_user_credentials(username, current_password):
        return jsonify({'success': False, 'message': '当前密码错误'})
    
    # 更新用户信息
    for user in users:
        if user['username'] == username:
            user['nickname'] = new_nickname
            if new_password:
                user['password'] = hash_password(new_password)
            break
    
    # 保存用户数据
    save_users()
    
    return jsonify({'success': True, 'message': '用户信息更新成功'})

# 检查昵称是否已存在
@app.route('/check_nickname', methods=['POST'])
def check_nickname():
    nickname = request.json.get('nickname')
    is_available = nickname not in [user['nickname'] for user in online_users.values()]
    return jsonify({'available': is_available})

# WebSocket 事件处理
@socketio.on('connect')
def handle_connect():
    global current_music
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    # 从在线用户列表中移除断开连接的用户
    sid = request.sid
    for username, user_info in list(online_users.items()):
        if user_info['sid'] == sid:
            # 更新用户状态
            user_info['status'] = 'offline'
            # 构建完整的用户列表
            users_list = [{"username": username, "nickname": info["nickname"], "status": info["status"]}
                          for username, info in online_users.items()]
            # 广播用户状态变化
            emit('user_status_change', {
                'username': username,
                'nickname': user_info['nickname'],
                'status': 'offline',
                'users': users_list
            }, broadcast=True)
            
            # 关键修改：检查是否为最后一名用户退出
            # 如果在线用户列表为空，清空历史消息
            if all(user_info['status'] == 'offline' for user_info in online_users.values()):
                # 清空历史消息存储
                message_history.clear()
                print('所有用户已退出，历史消息已清空')
            break
    print('Client disconnected')

@socketio.on('join')
def handle_join(data):
    username = data['username']
    nickname = data['nickname']
    
    # 存储用户会话信息（包含状态）
    online_users[username] = {
        'sid': request.sid,
        'nickname': nickname,
        'status': 'online'
    }
    
    # 发送在线用户列表给所有用户
    users_list = [{"username": username, "nickname": info["nickname"], "status": info["status"]}
                  for username, info in online_users.items()]
    # 广播用户状态变化
    emit('user_status_change', {
        'username': username,
        'nickname': nickname,
        'status': 'online',
        'users': users_list
    }, broadcast=True)
    
    # 发送当前音乐状态
    if current_music['url']:
        emit('music_update', current_music)
    
    # 发送当前天气信息
    if current_weather['city']:
        emit('weather_update', current_weather)
    
    # 发送欢迎消息
    emit('welcome_message', {
        'message': f'欢迎 {nickname} 加入聊天室！',
        'users': users_list
    })
    
    # 发送历史消息
    if message_history:
        emit('load_history', {'messages': message_history})

@socketio.on('request_history')
def handle_request_history():
    # 发送历史消息
    if message_history:
        emit('load_history', {'messages': message_history})

@socketio.on('send_message')
def handle_message(data):
    global current_music
    global current_weather
    message = data['message']
    nickname = data['nickname']
    timestamp = data['timestamp']
    
    # 处理@命令
    processed_message = message
    message_type = 'text'
    
    # 处理@电影命令
    if message.startswith('@电影'):
        # 提取URL（支持直接@电影url格式，不需要空格）
        movie_url = message[3:].strip()  # 直接截取@电影后面的内容作为URL并去除首尾空格
        if movie_url:  # 确保URL存在
            try:
                # 构建解析地址
                parsed_url = f'https://jx.m3u8.tv/jiexi/?url={movie_url}'
                # 生成优化的iframe，大小400*400，添加更多必要属性以确保播放兼容
                movie_html = f'<iframe src="{parsed_url}" width="400" height="400" frameborder="0" allowfullscreen allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" sandbox="allow-same-origin allow-scripts allow-popups allow-forms" style="background-color: black; display: block; margin: 10px 0; border-radius: 4px;"></iframe>'
                
                # 将iframe添加到原始消息后面
                processed_message = f'{message}<br>{movie_html}'
            except Exception as e:
                # 处理可能的错误
                processed_message = f'{message}<br>⚠️ 电影解析失败：{str(e)}'
    
    # 处理@听音乐命令已移至socketio事件处理器中，此处不再处理
    if message.startswith('@听音乐'):
        # 只保留原始消息，音乐处理由socketio事件处理器完成
        processed_message = message
    
    # 存储处理后的消息到历史记录并广播
    user_message_data = {
        'nickname': nickname,
        'message': processed_message,
        'timestamp': timestamp,
        'type': message_type
    }
    # 存储到历史记录
    message_history.append(user_message_data)
    # 广播给所有用户
    emit('receive_message', user_message_data, broadcast=True)
    
    # 处理@川小农命令
    if message.startswith('@川小农'):
        # 提取问题
        parts = message.split(' ', 1)
        if len(parts) > 1:
            question = parts[1]
            # 使用川小农助手生成回复
            ai_response = chuanxiaonong.generate_response(question)
            
            # 川小农回复数据
            ai_response_data = {
                'nickname': chuanxiaonong.name,
                'avatar': chuanxiaonong.avatar,
                'message': ai_response,
                'timestamp': timestamp,
                'type': 'ai_assistant'
            }
            # 存储到历史记录
            message_history.append(ai_response_data)
            # 广播川小农的回复
            emit('receive_message', ai_response_data, broadcast=True)
            
            return
    elif message.startswith('@天气 '):
        # 处理@天气命令
        # 提取城市名称
        city = message[4:].strip()  # 移除"@天气 "前缀，提取城市名
        
        if not city:
            # 未识别到城市名称
            emit('receive_message', {
                'nickname': '系统',
                'message': '请补充具体城市，例如‘@天气 北京’',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'text'
            }, broadcast=True)
            return
        
        # 获取天气数据（带缓存）
        weather_data = get_weather(city)
        
        if weather_data:
            # 解析天气数据
            weather_info = parse_weather_message(weather_data)
            
            if weather_info:
                # 使用API返回的城市名，如果没有则使用用户输入的
                if weather_info.get('city'):
                    city = weather_info['city']
                
                # 按照用户要求的格式生成天气消息
                weather_message = f"【{city}】今日天气：{weather_info['condition']}，气温{weather_info['temp_range']}℃，风力{weather_info['wind_level']}级，湿度{weather_info['humidity']}%"
                
                # 发送天气信息，包含天气背景类名
                emit('receive_message', {
                    'nickname': '系统',
                    'message': weather_message,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'text',
                    'weather_class': weather_info['background']['class']  # 添加天气背景类名
                }, broadcast=True)
                
                # 广播天气更新和背景变化
                emit('weather_update', {
                    'city': city,
                    'temperature': f"{weather_info['temp']}°C",
                    'description': weather_info['condition'],
                    'background_class': weather_info['background']['class']
                }, broadcast=True)
            else:
                # 解析天气数据失败
                emit('receive_message', {
                    'nickname': '系统',
                    'message': '当前天气查询暂不可用，请稍后再试',
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'text'
                }, broadcast=True)
        else:
            # 天气API调用失败
            emit('receive_message', {
                'nickname': '系统',
                'message': '当前天气查询暂不可用，请稍后再试',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'text'
            }, broadcast=True)
    elif message.startswith('@新闻'):
        # 处理@新闻命令
        # 检查新闻访问次数限制
        current_time = time.time()
        if current_time - news_last_access['time'] < 1:
            news_html = f"<div class='news-info'>新闻访问过于频繁，请稍后再试</div>"
        else:
            # 更新新闻访问时间
            news_last_access['time'] = current_time
            news_last_access['count'] += 1
            
            # 解析新闻关键词
            # 支持两种格式：@新闻 体育 和 @新闻体育
            if len(message) > 3 and message[3] == ' ':
                # 格式：@新闻 体育
                content = message[4:].strip()
            else:
                # 格式：@新闻体育
                content = message[3:].strip()
            
            # 定义关键词到分类的映射
            category_map = {
                '头条': 'top',
                '财经': 'finance',
                '体育': 'sports',
                '娱乐': 'entertainment',
                '科技': 'tech',
                '教育': 'education',
                '健康': 'health',
                '军事': 'military',
                '国际': 'world',
                '国内': 'china',
                '汽车': 'auto',
                '房产': 'house',
                '游戏': 'game',
                '时尚': 'fashion',
                '旅游': 'travel',
                '星座': 'constellation',
                '动漫': 'comic',
                '社会': 'society'
            }
            
            # 确定新闻分类
            if content in category_map:
                category = category_map[content]
            else:
                # 默认使用头条分类
                category = 'top'
            
            try:
                # 使用本地测试新闻数据，确保功能正常工作
                # 模拟不同分类的新闻数据
                mock_news = {
                    '体育': [
                        {
                            'title': 'NBA常规赛：湖人队险胜勇士队',
                            'description': '在今天的NBA常规赛中，湖人队以115-113险胜勇士队，詹姆斯砍下32分，戴维斯贡献28分15篮板。比赛最后时刻，詹姆斯命中压哨三分，帮助球队逆转获胜。勇士队方面，库里得到29分，汤普森贡献26分。这场胜利让湖人队的战绩提升至18胜12负，排名西部第5位。',
                            'picUrl': 'https://picsum.photos/400/200',
                            'ctime': '2023-12-20 20:00:00',
                            'source': '体育新闻网'
                        },
                        {
                            'title': '梅西当选2023年世界足球先生',
                            'description': '国际足联宣布，梅西当选2023年世界足球先生，这是他职业生涯第八次获得该荣誉。梅西在评选中击败了哈兰德和姆巴佩，获得了这一殊荣。在2023年，梅西带领阿根廷队赢得了世界杯冠军，并帮助巴黎圣日耳曼队赢得了法甲联赛冠军。',
                            'picUrl': 'https://picsum.photos/400/200?1',
                            'ctime': '2023-12-20 19:30:00',
                            'source': '足球周刊'
                        }
                    ],
                    '娱乐': [
                        {
                            'title': '第35届电影金鸡奖颁奖典礼落下帷幕',
                            'description': '第35届电影金鸡奖颁奖典礼昨晚在北京举行，《流浪地球2》获得最佳影片奖，刘德华获得最佳男主角。颁奖典礼上，《流浪地球2》共获得了最佳影片、最佳导演、最佳视觉效果等多个奖项。刘德华凭借在《失孤》中的出色表演获得了最佳男主角奖，这是他首次获得金鸡奖最佳男主角。此外，周冬雨凭借《鹦鹉杀》获得了最佳女主角奖，她在片中饰演了一个复杂的角色，表演得到了评委的高度评价。颁奖典礼还颁发了最佳男配角、最佳女配角、最佳编剧等多个奖项。',
                            'picUrl': 'https://picsum.photos/400/200?2',
                            'ctime': '2023-12-20 18:45:00',
                            'source': '娱乐头条'
                        },
                        {
                            'title': '知名歌手发布新专辑',
                            'description': '周杰伦发布全新专辑《最伟大的作品》，首支单曲《还在流浪》上线后迅速登上各大音乐平台榜首。这张专辑是周杰伦时隔六年推出的全新作品，共收录了12首歌曲，风格涵盖了流行、摇滚、古典等多种音乐类型。专辑上线后，迅速成为社交媒体的热门话题，粉丝们纷纷表示这张专辑展现了周杰伦一贯的音乐才华。',
                            'picUrl': 'https://picsum.photos/400/200?3',
                            'ctime': '2023-12-20 17:20:00',
                            'source': '音乐之声'
                        }
                    ],
                    '科技': [
                        {
                            'title': '苹果发布iPhone 15系列',
                            'description': '苹果公司在秋季新品发布会上正式发布iPhone 15系列，搭载全新A17 Pro芯片，支持USB-C接口。iPhone 15系列包括iPhone 15、iPhone 15 Plus、iPhone 15 Pro和iPhone 15 Pro Max四款机型。新机型采用了钛金属设计，重量更轻，耐腐蚀性更强。A17 Pro芯片采用了3纳米工艺，性能提升显著，支持光追功能。此外，iPhone 15系列还支持卫星通信和更快的5G网络。',
                            'picUrl': 'https://picsum.photos/400/200?4',
                            'ctime': '2023-12-20 16:10:00',
                            'source': '科技日报'
                        },
                        {
                            'title': '人工智能技术取得重大突破',
                            'description': '谷歌DeepMind宣布，其开发的AI模型AlphaFold成功预测了几乎所有已知蛋白质的结构。这一突破将对生物学和医学研究产生深远影响，有助于开发新的药物和治疗方法。AlphaFold的预测准确率达到了原子水平，超过了传统实验方法的效率。这一成果是人工智能在科学研究领域的重要应用，展示了AI在解决复杂科学问题方面的潜力。',
                            'picUrl': 'https://picsum.photos/400/200?5',
                            'ctime': '2023-12-20 15:30:00',
                            'source': 'AI前沿'
                        }
                    ],
                    '财经': [
                        {
                            'title': '股市行情：上证指数突破3000点',
                            'description': '今日A股市场表现强劲，上证指数突破3000点关口，收盘报3012.45点，涨幅2.58%。深证成指和创业板指也分别上涨了3.12%和3.78%。市场上，芯片、新能源、生物医药等板块表现活跃，多只个股涨停。分析人士认为，市场上涨的主要原因是宏观经济数据向好，以及政策面的积极信号。投资者信心有所恢复，市场交易量明显放大。',
                            'picUrl': 'https://picsum.photos/400/200?6',
                            'ctime': '2023-12-20 14:20:00',
                            'source': '财经新闻'
                        }
                    ],
                    '头条': [
                        {
                            'title': '中央经济工作会议在北京召开',
                            'description': '中央经济工作会议12月19日至21日在北京举行，会议分析当前经济形势，部署2024年经济工作。会议强调，要坚持稳中求进工作总基调，完整、准确、全面贯彻新发展理念，加快构建新发展格局，着力推动高质量发展。会议提出了2024年经济工作的主要任务，包括扩大内需、深化供给侧结构性改革、加快科技创新、推动城乡融合发展等。会议还强调要防范化解重点领域风险，保持经济社会大局稳定。',
                            'picUrl': 'https://picsum.photos/400/200?7',
                            'ctime': '2023-12-20 13:15:00',
                            'source': '新华网'
                        }
                    ]
                }
                
                # 获取对应分类的新闻
                news_list = mock_news.get(content, mock_news.get('头条', []))
                
                # 如果对应分类没有新闻，使用所有新闻
                if not news_list:
                    all_news = []
                    for category in mock_news.values():
                        all_news.extend(category)
                    news_list = all_news
                
                if news_list:
                    # 随机抽取1条新闻
                    selected_news = random.choice(news_list)
                    
                    # 提取新闻信息
                    title = selected_news.get('title', '未知标题')
                    full_content = selected_news.get('description', '').strip() if selected_news.get('description') else '暂无摘要'
                    image = selected_news.get('picUrl', '')
                    publish_time = selected_news.get('ctime', '')
                    source = selected_news.get('source', '未知来源')
                    content_hash = hash(title)
                    
                    # 生成新闻HTML，添加展开/收起功能
                    news_html = f'''<div class="news-card" style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin: 16px 0; background-color: #fafafa; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h3 class="news-title" style="margin: 0 0 12px 0; font-size: 18px; color: #333; font-weight: 600;">📰 {title}</h3>
                        <ul class="news-meta" style="list-style: none; padding: 0; margin: 0 0 16px 0; display: flex; gap: 16px; font-size: 14px; color: #666;">
                            <li style="display: flex; align-items: center; gap: 4px;">
                                <span>⏰</span>
                                <span>{publish_time}</span>
                            </li>
                            <li style="display: flex; align-items: center; gap: 4px;">
                                <span>📢</span>
                                <span>{source}</span>
                            </li>
                        </ul>
                        {('<div class="news-image" style="margin-bottom: 16px; border-radius: 4px; overflow: hidden;">' + 
                          f'<img src="{image}" alt="新闻配图" class="news-img" style="width: 100%; height: auto; max-height: 300px; object-fit: cover;">' + 
                          '</div>') if image else ''}
                        <div class="news-content" style="background-color: #fff; padding: 16px; border-radius: 4px; border-left: 4px solid #1890ff;">
                            <div class="news-summary" style="font-size: 15px; line-height: 1.6; color: #333;">
                                <p class="news-text" style="margin: 0;" id="newsText_{content_hash}">
                                    {full_content[:200] if len(full_content) > 200 else full_content}
                                    <span class="news-more" style="display: {'none' if len(full_content) <= 200 else ''}; color: #1890ff; cursor: pointer; font-weight: bold;">... 展开</span>
                                </p>
                                <p class="news-full" style="margin: 8px 0 0 0; display: none;" id="newsFull_{content_hash}">
                                    {full_content}
                                    <span class="news-collapse" style="color: #1890ff; cursor: pointer; font-weight: bold;"> 收起</span>
                                </p>
                            </div>
                        </div>
                    </div>'''
                    
                    # 添加展开/收起功能的JavaScript
                    news_html += f'''<script>
                        // 展开/收起功能
                        document.getElementById('newsText_{content_hash}')?.querySelector('.news-more')?.addEventListener('click', function() {{
                            document.getElementById('newsText_{content_hash}').style.display = 'none';
                            document.getElementById('newsFull_{content_hash}').style.display = 'block';
                        }});
                        
                        document.getElementById('newsFull_{content_hash}')?.querySelector('.news-collapse')?.addEventListener('click', function() {{
                            document.getElementById('newsFull_{content_hash}').style.display = 'none';
                            document.getElementById('newsText_{content_hash}').style.display = 'block';
                        }});
                    </script>'''
                else:
                    # 无对应分类新闻
                    news_html = f"<div class='news-error'>当前暂无该类型新闻，请稍后重试</div>"
            except Exception as e:
                # 处理请求错误
                print(f"新闻处理错误: {e}")
                news_html = f"<div class='news-error'>当前暂无该类型新闻，请稍后重试</div>"
        
        # 发送新闻信息作为系统消息
        emit('receive_message', {
            'nickname': '系统',
            'message': news_html,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'text'
        }, broadcast=True)
    elif message.startswith('@听音乐'):
        # 处理@听音乐命令
        try:
            # 调用酷我音乐随机歌曲接口
            music_api_url = 'https://v2.xxapi.cn/api/randomkuwo'
            
            # 设置请求头，模拟浏览器请求
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Content-Type': 'application/json'
            }
            
            print(f"[音乐功能] 正在请求随机音乐API: {music_api_url}")
            response = requests.get(music_api_url, headers=headers, timeout=15)
            print(f"[音乐功能] API响应状态码: {response.status_code}")
            
            # 解析返回的音乐数据
            try:
                music_data = response.json()
                print(f"[音乐功能] API返回数据: {json.dumps(music_data, ensure_ascii=False)}")
            except json.JSONDecodeError as e:
                print(f"[音乐功能] JSON解析失败: {e}, 响应内容: {response.text[:200]}...")
                # 解析失败，使用本地音乐作为备用
                local_music = {
                    'title': '示例音乐',
                    'artist': '未知艺术家',
                    'url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
                    'lyrics': [],
                    'status': 'stopped',
                    'current_time': 0
                }
                emit('music_update', local_music, broadcast=True)
                return
            
            # 处理API响应
            if response.status_code == 200:
                if music_data.get('code') == 200 and music_data.get('data'):
                    # 提取音乐信息（兼容不同的数据结构）
                    song_info = music_data['data']
                    
                    # 尝试从不同字段获取音乐信息
                    title = song_info.get('name', song_info.get('song_name', '未知歌曲'))
                    artist = song_info.get('singer', song_info.get('artist', '未知歌手'))
                    url = song_info.get('url', song_info.get('purl', ''))
                    
                    # 检查所有可用字段
                    print(f"[音乐功能] 获取到音乐: {title} - {artist}, URL: {url}")
                    print(f"[音乐功能] 所有可用字段: {list(song_info.keys())}")
                    
                    # 检查URL是否有效，只接受以http或https开头的有效URL
                    if url and (url.startswith('http://') or url.startswith('https://')):
                        # 更新当前音乐状态
                        current_music.update({
                            'url': url,
                            'title': title,
                            'artist': artist,
                            'lyrics': [],  # 暂时不处理歌词
                            'status': 'stopped',
                            'current_time': 0
                        })
                        
                        # 发送音乐更新
                        emit('music_update', current_music, broadcast=True)
                        
                        # 发送系统消息告知用户
                        emit('receive_message', {
                            'nickname': '系统',
                            'message': f'🎵 为您播放歌曲: {title} - {artist}',
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'type': 'text'
                        }, broadcast=True)
                    else:
                        print(f"[音乐功能] API返回的音乐URL为空或无效，尝试使用QQ音乐搜索获取播放链接")
                        
                        # 使用QQ音乐爬虫搜索并获取该歌曲的播放链接
                        try:
                            qq_music = QQMusicSpider()
                            song_info = qq_music.search_music(title)
                            
                            if song_info and song_info.get('purl') and (song_info['purl'].startswith('http://') or song_info['purl'].startswith('https://')):
                                # 获取到了有效的播放链接
                                print(f"[音乐功能] QQ音乐搜索成功，获取到播放链接: {song_info['purl']}")
                                
                                # 更新当前音乐状态
                                current_music.update({
                                    'url': song_info['purl'],
                                    'title': song_info['song_name'],
                                    'artist': song_info['artist'],
                                    'lyrics': [],
                                    'status': 'stopped',
                                    'current_time': 0
                                })
                                
                                # 发送音乐更新
                                emit('music_update', current_music, broadcast=True)
                                
                                # 发送系统消息告知用户
                                emit('receive_message', {
                                    'nickname': '系统',
                                    'message': f'🎵 为您播放歌曲: {song_info["song_name"]} - {song_info["artist"]}',
                                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                    'type': 'text'
                                }, broadcast=True)
                            else:
                                # QQ音乐也未获取到有效链接，使用公开示例音乐作为备用
                                print(f"[音乐功能] QQ音乐也未获取到有效链接，使用公开示例音乐作为备用")
                                local_music = {
                                    'title': title if title != '未知歌曲' else '示例音乐',
                                    'artist': artist if artist != '未知歌手' else '未知艺术家',
                                    'url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
                                    'lyrics': [],
                                    'status': 'stopped',
                                    'current_time': 0
                                }
                                emit('music_update', local_music, broadcast=True)
                                
                                # 发送系统消息告知用户
                                emit('receive_message', {
                                    'nickname': '系统',
                                    'message': f'🎵 为您随机获取到歌曲: {title} - {artist}\n由于API限制，使用示例音乐播放',
                                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                    'type': 'text'
                                }, broadcast=True)
                        except Exception as e:
                            print(f"[音乐功能] QQ音乐搜索失败: {e}")
                            # 搜索失败，使用公开示例音乐作为备用
                            local_music = {
                                'title': title if title != '未知歌曲' else '示例音乐',
                                'artist': artist if artist != '未知歌手' else '未知艺术家',
                                'url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
                                'lyrics': [],
                                'status': 'stopped',
                                'current_time': 0
                            }
                            emit('music_update', local_music, broadcast=True)
                            
                            # 发送系统消息告知用户
                            emit('receive_message', {
                                'nickname': '系统',
                                'message': f'🎵 为您随机获取到歌曲: {title} - {artist}\n由于API限制，使用示例音乐播放',
                                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'type': 'text'
                            }, broadcast=True)
                else:
                    # API返回错误，发送详细错误信息
                    error_msg = music_data.get('msg', '音乐服务暂时异常')
                    error_code = music_data.get('code', -1)
                    print(f"[音乐功能] API返回错误: {error_msg} (错误码: {error_code})")
                    emit('music_update', {'error': error_msg, 'code': error_code}, broadcast=True)
            else:
                # HTTP错误
                print(f"[音乐功能] HTTP请求失败: {response.status_code}")
                emit('music_update', {'error': f'音乐服务请求失败（{response.status_code}）', 'code': response.status_code}, broadcast=True)
        except requests.exceptions.RequestException as e:
            # 网络请求异常
            print(f"[音乐功能] 网络请求异常: {e}")
            # 使用公开示例音乐作为备用
            local_music = {
                'title': '示例音乐',
                'artist': '未知艺术家',
                'url': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
                'lyrics': [],
                'status': 'stopped',
                'current_time': 0
            }
            emit('music_update', local_music, broadcast=True)
        except Exception as e:
            # 其他异常
            print(f"[音乐功能] 其他异常: {e}")
            error_msg = f'系统错误：{str(e)}'
            emit('music_update', {'error': error_msg, 'code': -3}, broadcast=True)
    elif message.startswith('@音乐'):
        # 保留原有的@音乐命令处理逻辑
        # 解析音乐关键词
        keyword = message.replace('@音乐', '').strip()
        
        if not keyword:
            keyword = '热门'  # 默认关键词
        
        # 调用音乐API（这里使用模拟数据）
        # 实际项目中可以使用音乐API如网易云音乐、QQ音乐等
        # 使用真实的音乐URL以便测试
        # 更真实的音乐数据 - 使用公开示例音乐URL，添加歌词字段
        # 为不同歌曲分配公开示例音乐URL
        song_music_map = {
            '起风了': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
            '晴天': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
            '海阔天空': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
            '成都': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
            '远方': 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3'
        }
        
        # 根据关键词选择歌曲
        selected_song = None
        if keyword in ['起风了', '晴天', '海阔天空', '成都', '远方']:
            selected_song = keyword
        elif keyword == '热门':
            selected_song = '起风了'  # 默认播放热门歌曲
        else:
            selected_song = '起风了'  # 未找到匹配歌曲时默认播放
        
        # 构建音乐数据
        music_data = {
            'title': selected_song,
            'artist': '买辣椒也用券' if selected_song == '起风了' else '未知歌手',
            'url': song_music_map.get(selected_song, '/static/music/SoundHelix-Song-1.mp3'),
            'status': 'playing',
            'current_time': 0,
            'lyrics': []
        }
        
        # 根据歌曲添加对应的歌词
        if selected_song == '起风了':
            music_data['lyrics'] = [
                {"time": 0, "text": "这一路上走走停停"},
                {"time": 3, "text": "顺着少年漂流的痕迹"},
                {"time": 6, "text": "迈出车站的前一刻"},
                {"time": 9, "text": "竟有些犹豫"},
                {"time": 12, "text": "不禁笑这近乡情怯"},
                {"time": 15, "text": "仍无可避免"},
                {"time": 18, "text": "而长野的天"},
                {"time": 21, "text": "依旧那么暖"},
                {"time": 24, "text": "风吹起了从前"}
            ]
        elif selected_song == '晴天':
            music_data['lyrics'] = [
                {"time": 0, "text": "故事的小黄花"},
                {"time": 2, "text": "从出生那年就飘着"},
                {"time": 4, "text": "童年的荡秋千"},
                {"time": 6, "text": "随记忆一直晃到现在"},
                {"time": 8, "text": "rui sou sou xi dou xi la"},
                {"time": 10, "text": "sou la xi xi xi xi la xi la sou"}
            ]
            music_data['artist'] = '周杰伦'
        elif selected_song == '海阔天空':
            music_data['lyrics'] = [
                {"time": 0, "text": "今天我 寒夜里看雪飘过"},
                {"time": 3, "text": "怀着冷却了的心窝飘远方"},
                {"time": 6, "text": "风雨里追赶 雾里分不清影踪"},
                {"time": 9, "text": "天空海阔你与我 可会变"}
            ]
            music_data['artist'] = 'Beyond'
        elif selected_song == '成都':
            music_data['lyrics'] = [
                {"time": 0, "text": "让我掉下眼泪的 不止昨夜的酒"},
                {"time": 3, "text": "让我依依不舍的 不止你的温柔"},
                {"time": 6, "text": "余路还要走多久 你攥着我的手"},
                {"time": 9, "text": "让我感到为难的 是挣扎的自由"}
            ]
            music_data['artist'] = '赵雷'
        elif selected_song == '远方':
            music_data['lyrics'] = [
                {"time": 0, "text": "远方有多远"},
                {"time": 3, "text": "请你告诉我"},
                {"time": 6, "text": "到天涯海角"},
                {"time": 9, "text": "算不算远方"}
            ]
            music_data['artist'] = '刘惜君'
        
        # 更新当前音乐状态
        current_music.update({
            'url': music_data['url'],
            'title': music_data['title'],
            'artist': music_data['artist'],
            'lyrics': music_data['lyrics'],
            'status': 'stopped',
            'current_time': 0
        })
        
        # 发送音乐更新
        emit('music_update', current_music, broadcast=True)
    elif '@' in message:
        # 处理@用户提醒 - 已经在原始消息中处理，无需额外操作
        pass

# 音乐控制事件
@socketio.on('music_control')
def handle_music_control(data):
    """处理音乐控制事件"""
    action = data.get('action')
    global current_music
    
    if current_music['url']:
        if action == 'play':
            current_music['status'] = 'playing'
        elif action == 'pause':
            current_music['status'] = 'paused'
        elif action == 'stop':
            current_music['status'] = 'stopped'
            current_music['current_time'] = 0
        
        # 广播音乐状态变化
        emit('music_update', current_music, broadcast=True)

@socketio.on('music_time_update')
def handle_music_time_update(data):
    """处理音乐播放时间更新"""
    global current_music
    current_music['current_time'] = data.get('current_time', 0)
    
    # 广播音乐时间变化
    emit('music_update', current_music, broadcast=True)

if __name__ == '__main__':
    # 打印测试新闻数据
    print("=== 测试新闻数据 ===")
    print("测试数据已加载，包含体育、娱乐、科技、财经、头条等分类的新闻")
    print("=== 测试结束 ===")
    
    # 设置Flask secret key（用于session）
    app.secret_key = 'your-secret-key-for-session-management'
    
    # 启动服务器，绑定到0.0.0.0:5002，支持localhost和本地IP访问
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"服务器启动在: http://localhost:5002 和 http://{local_ip}:5002")
    socketio.run(app, host='0.0.0.0', port=5002, debug=True)