#!/usr/bin/python
# -*- coding: UTF-8 -*-
import json
import time
import requests
import paho.mqtt.client as mqtt
import threading
import pyaudio
import opuslib
import socket
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import logging
from pynput import keyboard as pynput_keyboard
import numpy as np

OTA_VERSION_URL = 'https://api.tenclass.net/xiaozhi/ota/'
MAC_ADDR = '7c:10:c9:23:55:6d'
ENERGY_THRESHOLD = 1000
SILENCE_TIMEOUT = 2.0

mqtt_info = {}
aes_opus_info = {"session_id": None}
local_sequence = 0
listen_state = None
tts_state = None
key_state = None
audio = None
udp_socket = None
conn_state = False
mqttc = None
should_stop = False
is_voice_active = False
voice_start_time = None

recv_audio_thread = None
send_audio_thread = None
voice_energy_thread = None


def calculate_energy(audio_data):
    try:
        if not audio_data or len(audio_data) == 0:
            return 0.0

        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        if audio_array.size == 0:
            return 0.0

        audio_float = audio_array.astype(np.float64)
        mean_squared = np.mean(audio_float ** 2)

        if not np.isfinite(mean_squared) or mean_squared < 0:
            return 0.0

        energy = np.sqrt(mean_squared)
        return float(energy) if np.isfinite(energy) else 0.0

    except Exception as e:
        print(f"能量计算错误: {e}")
        return 0.0


def start_listening():
    global conn_state, aes_opus_info, tts_state

    if not conn_state or not aes_opus_info.get('session_id'):
        conn_state = True
        hello_msg = {
            "type": "hello",
            "version": 3,
            "transport": "udp",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60
            }
        }
        push_mqtt_msg(hello_msg)
        print(f"发送hello消息: {hello_msg}")
        return

    if tts_state in ["start", "sentence_start"]:
        push_mqtt_msg({"type": "abort"})
        print("发送中断消息")

    if aes_opus_info.get('session_id'):
        msg = {
            "session_id": aes_opus_info['session_id'],
            "type": "listen",
            "state": "start",
            "mode": "manual"
        }
        print(f"发送开始监听消息: {msg}")
        push_mqtt_msg(msg)


def stop_listening():
    global aes_opus_info

    if aes_opus_info.get('session_id'):
        msg = {
            "session_id": aes_opus_info['session_id'],
            "type": "listen",
            "state": "stop"
        }
        print(f"发送停止监听消息: {msg}")
        push_mqtt_msg(msg)


def voice_energy_detection():
    global audio, is_voice_active, voice_start_time, should_stop

    energy_mic = None
    try:
        energy_mic = audio.open(format=pyaudio.paInt16, channels=1, rate=16000,
                                input=True, frames_per_buffer=960)
        print("语音能量检测已启动")

        while not should_stop:
            try:
                data = energy_mic.read(960, exception_on_overflow=False)
                energy = calculate_energy(data)

                if energy > ENERGY_THRESHOLD:
                    if not is_voice_active:
                        is_voice_active = True
                        voice_start_time = time.time()
                        print(f"检测到语音活动，能量: {energy:.2f} - 直接开始监听")
                        start_listening()
                    else:
                        voice_start_time = time.time()
                else:
                    if is_voice_active and voice_start_time:
                        if time.time() - voice_start_time > SILENCE_TIMEOUT:
                            is_voice_active = False
                            voice_start_time = None
                            print(f"检测到语音结束，能量: {energy:.2f} - 直接停止监听")
                            stop_listening()

                time.sleep(0.01)

            except Exception as read_error:
                print(f"音频读取错误: {read_error}")
                time.sleep(0.1)

    except Exception as e:
        print(f"语音能量检测初始化错误: {e}")
    finally:
        if energy_mic:
            try:
                energy_mic.stop_stream()
                energy_mic.close()
            except:
                pass


def get_ota_version():
    global mqtt_info
    header = {
        'Device-Id': MAC_ADDR,
        'Content-Type': 'application/json'
    }
    post_data = {
        "flash_size": 16777216,
        "minimum_free_heap_size": 8318916,
        "mac_address": MAC_ADDR,
        "chip_model_name": "esp32s3",
        "chip_info": {"model": 9, "cores": 2, "revision": 2, "features": 18},
        "application": {
            "name": "xiaozhi",
            "version": "0.9.9",
            "compile_time": "Jan 22 2025T20:40:23Z",
            "idf_version": "v5.3.2-dirty",
            "elf_sha256": "22986216df095587c42f8aeb06b239781c68ad8df80321e260556da7fcf5f522"
        },
        "board": {
            "type": "bread-compact-wifi",
            "ssid": "mzy",
            "rssi": -58,
            "channel": 6,
            "ip": "192.168.124.38",
            "mac": "cc:ba:97:20:b4:bc"
        }
    }

    try:
        response = requests.post(OTA_VERSION_URL, headers=header, data=json.dumps(post_data))
        print('=========================')
        print(response.text)
        mqtt_info = response.json()['mqtt']
        return True
    except Exception as e:
        print(f"获取OTA版本失败: {e}")
        return False


def aes_ctr_encrypt(key, nonce, plaintext):
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(plaintext) + encryptor.finalize()


def aes_ctr_decrypt(key, nonce, ciphertext):
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def send_audio():
    global aes_opus_info, udp_socket, local_sequence, listen_state, audio, should_stop

    if not aes_opus_info.get('udp'):
        return

    key = aes_opus_info['udp']['key']
    nonce = aes_opus_info['udp']['nonce']
    server_ip = aes_opus_info['udp']['server']
    server_port = aes_opus_info['udp']['port']

    encoder = opuslib.Encoder(16000, 1, opuslib.APPLICATION_AUDIO)
    mic = None

    try:
        mic = audio.open(format=pyaudio.paInt16, channels=1, rate=16000,
                         input=True, frames_per_buffer=960)

        while not should_stop and udp_socket:
            if listen_state == "stop":
                time.sleep(0.1)
                continue

            try:
                data = mic.read(960)
                encoded_data = encoder.encode(data, 960)
                local_sequence += 1
                new_nonce = (nonce[0:4] + format(len(encoded_data), '04x') +
                             nonce[8:24] + format(local_sequence, '08x'))
                encrypt_encoded_data = aes_ctr_encrypt(
                    bytes.fromhex(key), bytes.fromhex(new_nonce), bytes(encoded_data))
                data = bytes.fromhex(new_nonce) + encrypt_encoded_data
                udp_socket.sendto(data, (server_ip, server_port))
            except Exception as send_error:
                print(f"发送音频数据错误: {send_error}")
                break

    except Exception as e:
        print(f"发送音频错误: {e}")
    finally:
        if mic:
            try:
                mic.stop_stream()
                mic.close()
            except:
                pass


def recv_audio():
    global aes_opus_info, udp_socket, audio, should_stop

    if not aes_opus_info.get('udp') or not aes_opus_info.get('audio_params'):
        return

    key = aes_opus_info['udp']['key']
    sample_rate = aes_opus_info['audio_params']['sample_rate']
    frame_duration = aes_opus_info['audio_params']['frame_duration']
    frame_num = int(frame_duration / (1000 / sample_rate))

    decoder = opuslib.Decoder(sample_rate, 1)
    spk = None

    try:
        spk = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_rate,
                         output=True, frames_per_buffer=frame_num)

        while not should_stop and udp_socket:
            try:
                data, server = udp_socket.recvfrom(4096)
                if len(data) < 16:
                    continue

                nonce = data[:16]
                encrypted_data = data[16:]
                decrypt_data = aes_ctr_decrypt(bytes.fromhex(key), nonce, encrypted_data)
                spk.write(decoder.decode(decrypt_data, frame_num))
            except Exception as recv_error:
                print(f"接收音频数据错误: {recv_error}")
                break

    except Exception as e:
        print(f"接收音频错误: {e}")
    finally:
        if spk:
            try:
                spk.stop_stream()
                spk.close()
            except:
                pass


def reconnect_to_server():
    global conn_state, aes_opus_info, udp_socket, recv_audio_thread, send_audio_thread

    print("正在重新连接服务器...")

    cleanup_connections()

    conn_state = False
    aes_opus_info = {"session_id": None}

    if get_ota_version():
        hello_msg = {
            "type": "hello",
            "version": 3,
            "transport": "udp",
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60
            }
        }
        push_mqtt_msg(hello_msg)
        print("已发送重新连接请求")
    else:
        print("重新连接失败")


def cleanup_connections():
    global udp_socket, recv_audio_thread, send_audio_thread, local_sequence

    if udp_socket:
        try:
            udp_socket.close()
        except:
            pass
        udp_socket = None

    local_sequence = 0

    if recv_audio_thread and recv_audio_thread.is_alive():
        recv_audio_thread.join(timeout=1)
    if send_audio_thread and send_audio_thread.is_alive():
        send_audio_thread.join(timeout=1)


def on_message(client, userdata, message):
    global aes_opus_info, udp_socket, tts_state, recv_audio_thread, send_audio_thread, listen_state

    try:
        msg = json.loads(message.payload)
        print(f"收到消息: {msg}")

        if msg['type'] == 'hello':
            aes_opus_info = msg

            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.connect((msg['udp']['server'], msg['udp']['port']))

            if not recv_audio_thread or not recv_audio_thread.is_alive():
                recv_audio_thread = threading.Thread(target=recv_audio)
                recv_audio_thread.daemon = True
                recv_audio_thread.start()

            if not send_audio_thread or not send_audio_thread.is_alive():
                send_audio_thread = threading.Thread(target=send_audio)
                send_audio_thread.daemon = True
                send_audio_thread.start()

            if is_voice_active:
                print("连接建立后立即开始监听（语音活动中）")
                start_listening()

        elif msg['type'] == 'listen':
            listen_state = msg['state']
            print(f"监听状态更新: {listen_state}")

        elif msg['type'] == 'tts':
            tts_state = msg['state']

        # 移除了处理goodbye消息的代码
    except Exception as e:
        print(f"处理MQTT消息错误: {e}")


def on_connect(client, userdata, flags, rc, properties=None):
    print("已连接到MQTT服务器")
    try:
        if 'subscribe_topic' in mqtt_info and mqtt_info['subscribe_topic'] != 'null':
            client.subscribe(mqtt_info['subscribe_topic'])
            print(f"已订阅主题: {mqtt_info['subscribe_topic']}")
    except Exception as e:
        print(f"订阅主题失败: {e}")


def on_disconnect(client, userdata, rc, properties=None):
    print("MQTT连接已断开")


def push_mqtt_msg(message):
    global mqtt_info, mqttc
    try:
        if mqttc and mqttc.is_connected():
            mqttc.publish(mqtt_info['publish_topic'], json.dumps(message))
        else:
            print("MQTT未连接，无法发送消息")
    except Exception as e:
        print(f"发布MQTT消息失败: {e}")


def on_space_key_press(event):
    global key_state
    if key_state == "press":
        return
    key_state = "press"
    print("手动触发开始监听")
    start_listening()


def on_space_key_release(event):
    global key_state
    key_state = "release"
    print("手动触发停止监听")
    stop_listening()


def on_press(key):
    if key == pynput_keyboard.Key.space:
        on_space_key_press(None)


def on_release(key):
    if key == pynput_keyboard.Key.space:
        on_space_key_release(None)
    if key == pynput_keyboard.Key.esc:
        return False


def connect_mqtt():
    global mqttc, mqtt_info

    mqttc = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                        client_id=mqtt_info['client_id'])
    mqttc.username_pw_set(username=mqtt_info['username'], password=mqtt_info['password'])
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_disconnect = on_disconnect

    try:
        mqttc.tls_set(ca_certs=None, certfile=None, keyfile=None,
                      cert_reqs=mqtt.ssl.CERT_NONE, tls_version=mqtt.ssl.PROTOCOL_TLS)
        mqttc.connect(host=mqtt_info['endpoint'], port=8883)
        print("SSL连接成功")
        return True
    except Exception as e:
        print(f"SSL连接失败: {e}")

    try:
        mqttc_plain = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=mqtt_info['client_id'])
        mqttc_plain.username_pw_set(username=mqtt_info['username'], password=mqtt_info['password'])
        mqttc_plain.on_connect = on_connect
        mqttc_plain.on_message = on_message
        mqttc_plain.on_disconnect = on_disconnect
        mqttc = mqttc_plain
        mqttc.connect(host=mqtt_info['endpoint'], port=1883)
        print("普通连接成功")
        return True
    except Exception as e:
        print(f"普通连接失败: {e}")
        return False


def run():
    global voice_energy_thread, should_stop

    if not get_ota_version():
        print("无法获取服务器配置，程序退出")
        return

    listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    if not voice_energy_thread or not voice_energy_thread.is_alive():
        voice_energy_thread = threading.Thread(target=voice_energy_detection)
        voice_energy_thread.daemon = True
        voice_energy_thread.start()
        print("语音能量检测已启动（优化版本）")

    while not should_stop:
        if connect_mqtt():
            try:
                mqttc.loop_forever()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"MQTT连接异常: {e}")

        print("尝试重新连接...")
        time.sleep(5)


if __name__ == "__main__":
    try:
        audio = pyaudio.PyAudio()
        print("程序启动 - 支持空格键手动触发和语音能量自动唤醒（优化版本）")
        print(f"语音能量阈值: {ENERGY_THRESHOLD}")
        print(f"静音超时时间: {SILENCE_TIMEOUT}秒")
        print("按ESC键退出程序")
        run()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行错误: {e}")
    finally:
        should_stop = True
        cleanup_connections()
        if audio:
            try:
                audio.terminate()
            except:
                pass
        print("程序已退出")
