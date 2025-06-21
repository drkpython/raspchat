###### 更新日志
2025 年 06 月 21 日
## 1.修复 SSL 证书验证过期问题
优化证书校验机制，解决因证书到期导致的服务连接异常，确保数据传输安全与服务稳定性。
## 2.强化 numpy 语音对话计算能力
基于 numpy 库升级音频信号处理算法，提升语音识别、特征提取及对话语义计算的效率，支持更复杂的语音交互场景（如多语种识别、噪声环境优化）。
## 3.优化心跳包防断联机制
改进网络连接保活策略，动态调整心跳包发送频率，减少弱网环境下的连接断开问题，提升客户端与服务器的长连接稳定性。

# raspberrypi llm chat for Hildy 项目安装与运行指南
## 经典更新(默认使用vscode终端运行)
首先更新系统软件包：
```bash
sudo apt update
sudo apt upgrade -y
```
安装工具和环境：
```bash
sudo apt install git python3 python3-venv python3-pip
```
## 克隆代码仓库(默认会在/home目录下)：
```bash
git clone https://github.com/drkpython/raspchat.git
```
## 创建虚拟环境（如果你的其他主程序都是在全局环境中跑的，请忽略这一步）
进入仓库文件夹：
```bash
cd raspchat
```
创建 Python 虚拟环境：
```bash
python3 -m venv venv
```
激活虚拟环境
```bash
source venv/bin/activate
```
## 装依赖
```bash
pip install -r requirements.txt
```
## 运行
在虚拟环境激活（或者全局环境）且位于项目目录的状态下，运行主程序：
```bash
python raspchat.py
```
## 按住空格跟它说话(调用默认扬声器和麦克风，如果你有多个设备，请在右上角右键修改为你想用的设备)

## 结束工作
退出虚拟环境：
```bash
deactivate
```
## 在win上跑
在win上也能跑，拉完仓库开虚拟环境装依赖之后，要把opus.dll放到\raspchat\.venv\Scripts中，这个opus包在win上会缺少这个dll文件

## 如果你希望raspchat.py作为子程序同时运行，请确保主程序和raspchat.py处在同一目录中，同一虚拟环境（或者全局环境）中，或者指定运行路径
