raspberrypi llm chat for Hildy 项目安装与运行指南
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
## 克隆代码仓库：
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

## 如果你希望raspchat.py作为子程序同时运行，请确保主程序和raspchat.py处在同一目录中，同一虚拟环境（或者全局环境）中
